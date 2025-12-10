# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run the negotiation system
python -m src.main

# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Add ANTHROPIC_API_KEY to .env
```

## Architecture

Revolution is a multi-agent political negotiation system using LangGraph for orchestration and Claude for reasoning. 22 AI agents (11 per party) debate and vote on user-submitted proposals.

### LangGraph Structure

**Main Graph** (`src/graphs/main_graph.py`):
```
START → receive_proposal → republican_deliberation → democrat_deliberation
      → cross_party_debate → [conditional: continue/vote] → final_voting → resolution → END
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

Agents defined in `src/agents/republican.py` and `src/agents/democrat.py` as lists of `Agent` dataclasses. Each agent has:
- Role hierarchy: `party_head` → `advisor` → `assistant`
- Unique philosophy and communication style
- Specialty area (economics, defense, social policy, etc.)

System prompts generated via `Agent.get_system_prompt()` in `src/agents/base.py`, templates in `src/agents/prompts.py`.

### Node Implementation

All graph nodes in `src/graphs/nodes.py`:
- `party_head_intro`, `advisor_discussion`, `assistant_research`, `form_party_position` - Party deliberation
- `cross_party_debate` - Cross-party interaction
- `conduct_voting` - Final voting with vote parsing

Nodes accept optional `display_callback` for real-time CLI output.

### Display System

`src/cli/display.py` uses Rich library with party-colored panels (red=Republican, blue=Democrat). The `NegotiationDisplay.display_callback()` method is passed to graph nodes.

## Key Patterns

- Graphs built with `StateGraph(TypedDict)` and compiled via `builder.compile()`
- Async execution: `await graph.ainvoke(initial_state)`
- All LLM calls use `ChatAnthropic` from langchain-anthropic
- Model configured via `MODEL_NAME` env var (default: claude-sonnet-4-20250514)
