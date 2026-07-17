# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run the CLI negotiation system
python -m src.main
# Or, after `pip install -e .`:
revolution

# Run the web app (two terminals)
python -m uvicorn server.main:app --reload          # backend, :8000
#   or: revolution-server
cd web && pnpm install && pnpm dev                  # frontend, :5173

# Install dependencies
pip install -r requirements.txt
# Web app dev tooling (needs Node 22+ and pnpm via corepack):
cd web && pnpm install

# Set up environment
cp .env.example .env
# Add ANTHROPIC_API_KEY to .env
# MODEL_NAME is a CLI fallback only — the web UI sets the model per-debate

# Tests, lint, type-check (dev extras: pip install -e ".[dev]")
pytest
ruff check .
mypy src server
cd web && pnpm typecheck && pnpm build

# Pre-commit hooks (runs ruff --fix on each commit)
pip install pre-commit && pre-commit install
```

## Architecture

Revolution is a multi-agent political negotiation system using LangGraph for orchestration and Claude for reasoning. 22 AI agents (11 per party) debate and vote on user-submitted proposals.

### LangGraph Structure

**Main Graph** (`src/graphs/main_graph.py`) — one deliberation node is generated per participating party (default democrat + republican):
```
START → receive_proposal → <party>_deliberation (×N, seating order) → initial_voting
      → cross_party_debate → [conditional: continue/vote] → final_voting
      → [conditional: resolve/markup] → resolution → END

markup branch (bounded; only when the vote failed, amendments exist,
and markup_rounds remain):  final_voting → markup → markup_debate → final_voting
```

**Party Subgraph** (`src/graphs/party_graph.py`):
```
START → party_head_intro → advisor_discussion → assistant_research → form_position → END
```

### State Management

Two TypedDict states in `src/state/types.py`:
- **NegotiationState**: Main orchestration state (proposal, positions, votes, phase)
- **PartyState**: Party deliberation state (discussion, party_position, member_votes)

Custom reducers `add_messages` and `add_votes` handle state accumulation. The `add_votes` reducer allows agents to change their vote (keyed by agent_id).

### Agent System

Agent personas live as JSON files in `src/agents/data/{republican,democrat}/` (11 per party).
`src/agents/republican.py` and `src/agents/democrat.py` are thin loaders that call
`load_agents()` → `validate_relationships()` → `register_agents()` from `src/agents/base.py`.
To add or edit a persona, edit the JSON, not the Python.

Each agent has:
- Role hierarchy: `party_head` → `advisor` → `assistant`
- Philosophy, communication style, specialty
- Optional `Source` entries (citations) — validated strictly at load time;
  malformed sources raise rather than being silently dropped.

System prompts generated via `Agent.get_system_prompt()` in `src/agents/base.py`, templates in `src/agents/prompts.py`.

### Node Implementation

All graph node implementations in `src/graphs/nodes.py`. Function names sometimes differ
from the registered graph-node names used in the flow diagrams above:
- `party_head_intro`, `advisor_discussion`, `assistant_research`, `form_party_position` (registered as `form_position`) — party deliberation
- `cross_party_debate` — cross-party interaction
- `conduct_voting` (registered as `final_voting`) — final voting with vote parsing

Nodes accept optional `display_callback` for real-time CLI output.

### Display System

`src/cli/display.py` uses Rich library with party-colored panels (red=Republican, blue=Democrat). The `NegotiationDisplay.display_callback()` method is passed to graph nodes.

### Voting & Result

`src/voting/consensus.py` aggregates votes into a `VotingResult` (per-party tallies, `passed`, `bipartisan`, `margin`, `rule`, `required`, weighted totals).

- **Ballots are structured output**: `cast_ballot` in `src/graphs/nodes.py` forces a pydantic `VoteBallot` (`src/voting/ballot.py`) via `with_structured_output`, retries once, falls back to the legacy `parse_vote` text parser, and only then records an explicit `[unparsed]` abstain. Test stubs without `with_structured_output` go straight to the text path.
- **Passage rules**: `VotingRules(rule=majority|three_fifths|two_thirds, quorum=...)` — integer/Fraction-exact comparisons, never float thresholds. Per-debate via `run_negotiation(passage_rule=...)`; default from the settings store (`voting.passage_rule`).
- **Seat weighting**: `determine_final_result(..., seat_weights={party: seats})` weights each ballot by `seats / ballots_cast` (exact `Fraction`). The debate config snapshots registry seats at creation (`seat_config`), so later registry edits don't change old debates.
- **Markup loop**: when a final vote fails, amendments exist, and `markup_rounds` remain, the graph routes `final_voting → markup → markup_debate (heads only) → final_voting`. The clerk incorporates the most-sponsored amendment (`AMENDMENT_MARKUP_PROMPT`), bumps `Proposal.current_version`, and a subsequent pass can resolve as `"amended"`. Loop bound lives in state (`markup_rounds_done`).
- The resolution node stores its full `VotingResult` on the state (`voting_result`); `server/engine.py` and `src/main.py` read it from there instead of recomputing.

## Key Patterns

- Graphs built with `StateGraph(TypedDict)` and compiled via `builder.compile()`
- Async execution: `await graph.ainvoke(initial_state)`
- All LLM calls use `ChatAnthropic` from langchain-anthropic
- Model + temperature can be pinned **per debate** via contextvars in `src/graphs/nodes.py`. `run_negotiation(..., model=, temperature=)` calls `set_model_overrides()` before building the graph; `get_model()` resolves `_model_override → MODEL_NAME env → default ('claude-sonnet-4-6')`. The CLI never sets the contextvars, so it follows env/default; the web's `server/engine.run_debate` sets them from the debate config.
- Requires Python 3.11+

## Web Layer (server/ + web/ + data/)

Added on top of the engine without rewriting it. The CLI continues to work unchanged.

### `server/` — FastAPI shell

- `main.py` — app factory, CORS, `load_dotenv()` *before* any router import so the engine's `os.environ` reads of `ANTHROPIC_API_KEY` succeed
- `settings.py` — pydantic-settings: `ANTHROPIC_API_KEY`, `MODEL_NAME`, `DATA_DIR`, `CORS_ORIGINS`
- `db.py` — file-DB access (atomic writes, per-debate `asyncio.Lock`s). Seeds `data/personas/` from `src/agents/data/` on first boot, and backfills `data/parties.json` metadata in place
- `engine.py` — `run_debate(debate_id)` wraps `run_negotiation`. The `display_callback` is wired to **both** the persisted `transcript.jsonl` and the `events.broadcaster` for live SSE
- `events.py` — `Event` dataclass + `EventBroadcaster` (per-debate queue, multi-subscriber)
- `exporters.py` — PDF (reportlab), Markdown, JSON. Every export embeds the simulation disclaimer
- `routers/` — `personas`, `parties`, `debates`, `stream` (SSE replay + tail)

### `web/` — React + Vite + TypeScript

- Lifted the prototype's design tokens + component library 1:1 into `web/src/{theme.ts,components/*}`
- `theme.ts` has a process-wide party-color registry hydrated by `App.tsx` via `setPartyRegistry()`; custom parties (libertarian, green, …) carry their real color through every screen
- Screens: Dashboard, Personas (+ Detail + AddPersonaModal), Parties (+ Detail), Launch, Results (Overview / Breakdown / Timeline / Transcript / Amendments + ExportModal), Graph
- Live debate UX lives **inside** the Results page Overview tab — the chamber hemicycle, phase rail, and speaker spotlight. Polling refreshes every 5s while a debate runs; SSE `turn_start` drives the "Composing remarks…" live indicator
- No `/arena` route — legacy `#/arena/{id}` URLs redirect to `#/results/{id}` (Overview tab is the default)

### `data/` — runtime file DB (gitignored)

| Path | Contents |
|---|---|
| `parties.json` | Registry: id, label, color, ideology, founded_year, motto, description, created_at |
| `personas/<party>/*.json` | One Agent JSON per persona. Schema is identical to `src/agents/data/` |
| `index.json` | Denormalized debate list (dashboard read path) |
| `debates/<id>/debate.json` | Config + status + result + tally |
| `debates/<id>/transcript.jsonl` | Append-only turns, written live via the `display_callback` |
| `debates/<id>/votes.json` | Final vote roll-call (written at completion) |
| `debates/<id>/amendments.json` | Amendments tabled by agents |

### Multi-party notes

- `data/parties.json` is the source of truth. The LangGraph flow is N-party: `build_main_graph(parties=[...])` generates one deliberation node per party id, and the Launch screen lets users toggle any registered caucus into a debate. `democrat` + `republican` remain the non-deletable seeded chamber and the default when no parties are passed.
- Party rows carry `voting_seats` (configured chamber strength for seat-weighted voting — democrat 212 / republican 218 by default, July-2026 House split) distinct from the derived `seats` API field (persona-file count).
- `Agent.party` was loosened from a closed `Literal` to a non-empty `str` (see `src/agents/base.py`) so custom-party personas validate. The parties registry decides which ids are recognized at the UI layer.
