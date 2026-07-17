# 🗳️ Revolution

> *Where AI agents debate politics so you don't have to!* 🎭

A multi-agent political simulation where richly-drawn AI personas — Democrats and Republicans by default, plus a growing bench of Libertarians, Greens, Constitutionalists, Reformers, Forwards, Democratic Socialists, and Working Families — caucus internally, debate across the aisle, and vote on proposals you submit. Comes as a **CLI** and a **full web app** (FastAPI backend + React frontend) with a live legislative-chamber visualisation.

[![Made with Claude](https://img.shields.io/badge/Made%20with-Claude%20Code-blueviolet)](https://claude.com/claude-code)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![LangGraph](https://img.shields.io/badge/Powered%20by-LangGraph-orange)](https://github.com/langchain-ai/langgraph)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/Frontend-React%2018-61DAFB.svg)](https://react.dev/)
[![Vite](https://img.shields.io/badge/Bundler-Vite-646CFF.svg)](https://vitejs.dev/)

---

## 🎬 What is This?

Revolution is an **agentic experiment** that simulates political negotiations using LangGraph for orchestration and Claude for reasoning. Users submit proposals (e.g., *"Should we implement universal basic income?"*), and the system runs a full deliberation process: each caucus first deliberates privately, then meets the other caucuses on the chamber floor, then votes — and agents can change their minds along the way.

![The Floor — Revolution's dashboard with hero, chamber composition, KPIs, and legislative record](docs/images/1-dashboard.png)

> 🪧 The default chamber seats Democrats vs. Republicans, but any registered caucus can join a debate: toggle it on from the [Launch screen](docs/USER_GUIDE.md#4--launch-a-debate) and the deliberation flow runs it end-to-end alongside the others. Seven bench caucuses (Libertarian, Green, Constitution, Reform, Forward, DSA, Working Families) ship with real-politician personas, and you can register more from the [Party Manager](docs/USER_GUIDE.md#7-️-party-manager).

### 🌀 The deliberation pipeline

```mermaid
flowchart LR
    Proposal([💡 Your proposal]) --> Caucus
    subgraph Caucus[" 🏛️ Caucus deliberation · runs per party "]
        direction TB
        Head[🎖️ Party head intro] --> Advisors[🎓 Advisor analysis]
        Advisors --> Assistants[📊 Assistant research]
        Assistants --> Position[📝 Party position]
    end
    Caucus --> Debate[⚔️ Cross-party debate<br/>1–5 rounds · amendments]
    Debate --> Vote[🗳️ Final vote<br/>persuasion mechanic ✨]
    Vote --> Result{Passage rule<br/>majority · 3/5 · 2/3}
    Result -->|meets threshold| Passed([✅ Passed])
    Result -->|fails + markup on| Markup[📜 Markup round<br/>top amendment incorporated]
    Markup --> Vote
    Result -->|fails| Rejected([❌ Rejected])
    Result -->|passes after markup| Amended([📜 Passed as amended])
```

After the gavel falls, every debate gets a tabbed results page — overview hemicycle, per-agent vote breakdown, persuasion timeline, full transcript, and amendments — plus one-click PDF / Markdown / JSON export.

![A resolved debate — Overview tab with vote-colored hemicycle, final motion, and amendment list](docs/images/3-3-debate-done-overview.png)

👉 **Want the full tour?** → **[Read the User Guide](docs/USER_GUIDE.md)** — every screen, every panel, every screenshot.

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🎭 **Richly-drawn personas** | Every agent carries a documented philosophy, communication style, red lines, rhetorical signatures, and per-agent relationships |
| 🏛️ **Party hierarchy** | Party Head → Senior Advisors → Policy Assistants, with the head synthesising the caucus position |
| 🔄 **Multi-round debates** | 1–5 configurable cross-party negotiation rounds with amendment tabling |
| 🖼️ **Real portraits** | Official public-domain congressional portraits and license-verified Wikimedia photos for all personas ([attributions](web/public/portraits/ATTRIBUTIONS.md)) |
| ⚖️ **Passage rules** | Simple majority, 3⁄5 cloture, or 2⁄3 supermajority — integer-exact math, chosen per debate |
| 🪑 **Seat-weighted voting** | Optionally weight each caucus's ballots by its real chamber strength (2026 splits ship as defaults) |
| 📜 **Amendment markup round** | A failed vote can trigger a markup: the most-sponsored amendment is incorporated, heads debate the revised text, and the chamber re-votes — motions can pass *as amended* |
| 🗳️ **Structured ballots** | Votes are tool-forced structured output — malformed replies can't silently become abstentions, and every amendment records its sponsors |
| 🤝 **Persuasion mechanic** | Agents can change their vote during deliberation; the Persuasion Timeline tells the story |
| 🎨 **Beautiful CLI** | Party-colored panels rendered with Rich |
| 🌐 **Live web app** | FastAPI backend + React/Vite frontend with a live hemicycle, SSE streaming, and per-debate dashboards |
| 🎒 **Persona Manager** | Browse, search, edit, and create personas; group by caucus; tune posture, positions, and relationships inline |
| 🏳️ **Party Manager** | Curate caucus ideology, motto, history, key policies, color, and roster |
| 🕸️ **Relationship Graph** | Intra-party ally / rival visualization that explains *why* caucuses cohere or splinter |
| ⚙️ **Settings** | Editable engine credentials, eight system prompts, and reference vocabularies — all persisted to `data/settings.json` and shared with the CLI |
| 📄 **Export** | One-click PDF, Markdown, and JSON export of any debate (transcript + votes + amendments) |

## 🧾 Example Output

Want to see what a full negotiation looks like? Check out this example session:

👉 **[UBI Negotiation Example](examples/ubi_negotiation.md)** — A complete 2-round debate on Universal Basic Income (result: 11-11 REJECTED)

## 🎒 The Seeded Roster (Democrats + Republicans)

These 22 personas ship as the default chamber, fact-checked against the 119th Congress as of **July 2026**. Many more (Libertarians, Greens, Constitutionalists, Reformers, Forwards, Democratic Socialists, Working Families — each with their own real-politician personas) are available in the [Persona Manager](docs/USER_GUIDE.md#6--persona-manager).

> ♻️ **Upgrading an existing install?** The runtime copy under `data/personas/` is seeded once and never overwritten. To pick up the refreshed roster, delete `data/personas/democrat` and `data/personas/republican` and restart the server (portraits backfill automatically; custom personas in other folders are untouched).

### 🔴 Republican Party (11 agents)

| Role | 👤 Name | 🏷️ Title | 🎯 Specialty |
|------|---------|----------|--------------|
| 🎖️ Party Head | Mike Johnson | Speaker of the House | Legislative Strategy |
| 🎓 Advisor | John Thune | Senate Majority Leader | Tax/Fiscal Policy |
| 🎓 Advisor | Tom Cotton | Conference Chair, Intelligence Chairman | National Security |
| 🎓 Advisor | Josh Hawley | Senator from Missouri | Cultural Conservatism |
| 🎓 Advisor | Ted Cruz | Commerce Committee Chairman | Constitutional Law |
| 📊 Assistant | Steve Scalise | House Majority Leader | Federal Budget |
| 📊 Assistant | Adrian Smith | Ways & Means Trade Subcommittee Chairman | International Trade |
| 📊 Assistant | John Barrasso | Senate Majority Whip | Energy Policy |
| 📊 Assistant | Rand Paul | Homeland Security Committee Chairman | Healthcare Policy |
| 📊 Assistant | Katie Britt | Senator from Alabama | Immigration Policy |
| 📊 Assistant | Todd Young | Senator from Indiana | Policy Strategy |

### 🔵 Democrat Party (11 agents)

| Role | 👤 Name | 🏷️ Title | 🎯 Specialty |
|------|---------|----------|--------------|
| 🎖️ Party Head | Chuck Schumer | Senate Minority Leader | Caucus Strategy |
| 🎓 Advisor | Elizabeth Warren | Senator from Massachusetts | Financial Regulation |
| 🎓 Advisor | Alexandria Ocasio-Cortez | Representative from New York | Climate Action |
| 🎓 Advisor | Cory Booker | Senator from New Jersey | Criminal Justice/Civil Rights |
| 🎓 Advisor | Jamie Raskin | Representative from Maryland | Constitutional Law |
| 📊 Assistant | Hakeem Jeffries | House Minority Leader | Budget Strategy |
| 📊 Assistant | Bernie Sanders | Senator from Vermont | Labor/Inequality |
| 📊 Assistant | Patty Murray | Senator from Washington | Healthcare Policy |
| 📊 Assistant | Katherine Clark | House Minority Whip | Education Policy |
| 📊 Assistant | Ilhan Omar | Representative from Minnesota | Immigration/Refugees |
| 📊 Assistant | Amy Klobuchar | Senator from Minnesota | Antitrust/Tech Policy |

## 🚀 Quick Start

### Prerequisites

- 🐍 Python 3.11+
- 📦 Node 22+ and pnpm (via `corepack`) — only needed for the web app
- 🔑 Anthropic API key

### Installation

```bash
# 1️⃣ Clone the repository
git clone https://github.com/floriangrousset/Revolution.git
cd Revolution

# 2️⃣ Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3️⃣ Install dependencies
pip install -r requirements.txt

# 4️⃣ Configure your API key
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
# (You can also set the key from the web app's Settings page — see the User Guide.)
```

### Usage — CLI

```bash
python -m src.main
```

You'll be prompted to:

1. 📝 Enter your proposal (e.g., *"Should we legalize marijuana?"*)
2. 🔢 Set the maximum number of negotiation rounds (1–5)

Then sit back and watch the political fireworks! 🎆

### Usage — Web app 🌐

The web app wraps the same LangGraph engine in a FastAPI backend with a React/Vite frontend. It adds the Persona Manager, Party Manager, Relationship Graph, Launch screen, Settings, live legislative-chamber view with SSE streaming, and PDF/Markdown/JSON export.

```bash
# Terminal 1 — backend (FastAPI on :8000)
python -m uvicorn server.main:app --reload
# or, after `pip install -e .`:
revolution-server

# Terminal 2 — frontend (Vite on :5173)
cd web
pnpm install        # first run only
pnpm dev
```

Open **http://localhost:5173** and navigate around:

- **🏛️ The Floor** — Dashboard with chamber composition, KPIs, and recent deliberations
- **🚀 Launch a Debate** — Compose a motion, pick rounds (1–5) and temperature, choose participating caucuses, and watch the session forecast update live
- **🎙️ Live debate / Results** — A hemicycle that lights up as agents take the floor, plus tabs for `Overview`, `Vote Breakdown`, `Persuasion Timeline`, `Transcript`, and `Amendments`. Export to PDF / Markdown / JSON.
- **🎭 Persona Manager** — Browse, search, filter, view, edit, and create personas. Each profile holds philosophy, communication style, key positions, red lines, rhetorical signatures, and ally / rival relationships.
- **🏳️ Party Manager** — Curate caucus ideology, motto, history, key policies, color identity, and roster.
- **🕸️ Relationship Graph** — Intra-party ally / rival visualization with hover focus and a slide-up persona card.
- **⚙️ Settings** — API key, default model, default temperature, eight editable system prompts, and reference vocabularies. Everything writes to `data/settings.json` and is read by both the web app and the CLI.

The CLI (`python -m src.main`) keeps working unchanged — both run against the same persona JSON files (auto-seeded into `data/personas/` on first web boot).

📖 For a screen-by-screen walkthrough → **[docs/USER_GUIDE.md](docs/USER_GUIDE.md)**

## ⚙️ Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `ANTHROPIC_API_KEY` | Your Anthropic API key (CLI + initial web bootstrap; can also be set from the web Settings page) | **Required** |
| `MODEL_NAME` | Claude model — **CLI fallback only**; the web app uses the value set in Settings and lets you override per debate from Launch | `claude-sonnet-4-6` |
| `MAX_ROUNDS` | Default max negotiation rounds (CLI) | `5` |
| `DATA_DIR` | Where the web app stores its file DB | `./data` |
| `CORS_ORIGINS` | Allowed origins for the API | `http://localhost:5173` |

## 📁 Project Structure

```
Revolution/
├── src/                           # 🧠 Engine (CLI + library)
│   ├── main.py                    # 🚀 CLI entry point
│   ├── state/types.py             # 📋 NegotiationState + PartyState + reducers
│   ├── agents/                    # 🤖 Agent class + persona JSON
│   │   ├── base.py prompts.py
│   │   ├── republican.py democrat.py
│   │   └── data/{republican,democrat}/*.json
│   ├── graphs/                    # 🎯 LangGraph nodes + flow
│   │   ├── main_graph.py party_graph.py nodes.py
│   ├── voting/consensus.py        # 🗳️ Voting tally
│   └── cli/display.py             # 🎨 Rich console output
│
├── server/                        # 🌐 FastAPI backend
│   ├── main.py                    # App factory + uvicorn entry
│   ├── settings.py                # Env config (pydantic-settings)
│   ├── db.py                      # File-DB access (atomic writes, per-debate locks)
│   ├── engine.py                  # Wraps run_negotiation → SSE events
│   ├── events.py                  # SSE Event + EventBroadcaster
│   ├── exporters.py               # PDF / Markdown / JSON
│   └── routers/                   # personas, parties, relationships,
│                                  # debates, stream, settings
│
├── web/                           # ⚛️ React + Vite + TypeScript frontend
│   ├── index.html package.json vite.config.ts
│   └── src/
│       ├── App.tsx main.tsx theme.ts api.ts types.ts hooks.ts
│       ├── components/            # Icon, Avatar, Btn, Tags, Sidebar, …
│       └── screens/               # Dashboard, Launch, Results,
│                                  # Personas + PersonaDetail + AddPersonaModal,
│                                  # Parties, Graph, Settings, ExportModal,
│                                  # Placeholder
│
├── data/                          # 🗂️ Runtime file DB (gitignored)
│   ├── parties.json index.json settings.json
│   ├── personas/<party>/*.json    # Seeded from src/agents/data/ on first boot
│   └── debates/<id>/              # debate.json transcript.jsonl votes.json amendments.json
│
├── docs/                          # 📖 Documentation
│   ├── USER_GUIDE.md              # Full screen-by-screen tour
│   └── images/                    # Screenshots (1-dashboard, 2-launch-debate, …)
│
├── examples/
│   ├── sample_proposals.txt       # 💡 Example proposals
│   └── ubi_negotiation.md         # 📄 Example session output
├── requirements.txt pyproject.toml .env.example
└── tests/
```

## 🛠️ Tech Stack

| Technology | Purpose |
|------------|---------|
| [🔗 LangGraph](https://github.com/langchain-ai/langgraph) | Multi-agent orchestration |
| [🧠 Claude API](https://www.anthropic.com/) | LLM reasoning (Opus / Sonnet / Haiku) |
| [🎨 Rich](https://github.com/Textualize/rich) | Beautiful terminal output (CLI) |
| [⚡ FastAPI](https://fastapi.tiangolo.com/) | Async HTTP + SSE backend |
| [⚛️ React 18](https://react.dev/) + [Vite](https://vitejs.dev/) + TS | Frontend |
| [📄 ReportLab](https://www.reportlab.com/) | PDF export |
| [✅ Pydantic](https://docs.pydantic.dev/) + pydantic-settings | Data validation & config |

## 💡 Sample Proposals to Try

### ⚖️ Social Issues
- *"Should we legalize gay marriage nationwide?"*
- *"Should we implement stricter gun control measures?"*

### 💰 Economic Policy
- *"Should we raise the federal minimum wage to $15/hour?"*
- *"Should we implement a universal basic income?"*

### 🏥 Healthcare
- *"Should we implement Medicare for All?"*

### 🌍 Climate
- *"Should we implement a Green New Deal?"*

### ⚖️ Criminal Justice
- *"Should we abolish the death penalty?"*

## 🔄 How It Works

### Phase 1: 🏛️ Party Deliberation

Each party runs an internal subgraph:

1. **🎖️ Party Head Introduction** — Frames the proposal and sets the agenda
2. **🎓 Advisor Analysis** — Each of 4 advisors analyses from their expertise
3. **📊 Assistant Research** — 6 assistants provide supporting data
4. **📝 Position Synthesis** — Party head synthesises into the official caucus position

### Phase 2: ⚔️ Cross-Party Debate

- Party heads present their positions
- Advisors engage in point/counterpoint
- Amendments may be tabled
- **N rounds** are configurable per debate (1–5 from Launch)

### Phase 3: 🗳️ Final Voting

- Every seated agent votes: **SUPPORT** / **OPPOSE** / **ABSTAIN**
- Each provides reasoning grounded in their philosophy
- 🤝 **Persuasion mechanic**: a custom `add_votes` reducer keys votes by agent id, so an agent who's been swayed during cross-party debate can simply re-emit a different vote — the diff is what powers the **Persuasion Timeline** in the web UI
- Simple majority wins (50%+1 of non-abstaining votes)

## ⏱️ Performance Notes

| Metric | Value |
|--------|-------|
| ⏰ Session Time | 5–15 minutes (depending on rounds) |
| 📡 API Calls | ~50–100 per session |
| 💵 Recommended Model | Claude Sonnet (cost-efficient default) |
| 🏆 Premium Model | Claude Opus (higher quality) |

## 🤝 Contributing

Contributions are welcome! On the roadmap (see [docs/REALISM.md](docs/REALISM.md) for the full realism analysis behind these):

- 🏛️ **Committee stage.** Generalize the markup node into a pre-floor committee subgraph — a subset of agents marks the motion up *before* it ever reaches the floor.
- 🏦 **Bicameralism.** Two sequential chamber runs with different seat configs (House 218–212, Senate 53–47) plus a reconciliation step.
- ✍️ **Veto & override.** A president actor after passage, with an automatic 2⁄3 override re-vote — the passage-rule machinery already supports it.
- 🤫 **Whip counts.** Give party heads the initial-vote tally as a "whip count" signal they can act on during debate.
- 🔊 **Token-level streaming for the live arena.** Today the SSE stream emits one event per completed turn (see the `astream` hook in `src/graphs/nodes.py`); finer-grained streaming would make the "composing remarks…" indicator feel even more alive.
- 🎭 **More personas.** Add real-politician profiles to the bench caucuses, or invent new ones entirely.
- 📊 **Historical voting record tracking.** A leaderboard that shows which agents flip most, which caucuses pass the most motions, which postures (dealmaker vs. hardliner) actually win.

## 📄 License

MIT License — see LICENSE file for details.

---

<div align="center">

**Built with ❤️ and [Claude Code](https://claude.com/claude-code)**

*"Democracy is the art of thinking independently together." — Alexander Meiklejohn*

🗳️ **Happy Debating!** 🗳️

</div>
