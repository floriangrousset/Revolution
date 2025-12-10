# Revolution

A multi-agent political negotiation system where 22 AI agents (11 Republican, 11 Democrat) debate and vote on user-submitted proposals.

## Overview

Revolution is an agentic experiment that simulates political negotiations using LangGraph for orchestration and Claude for reasoning. Users submit proposals (e.g., "Should we implement universal basic income?"), and the system runs a full deliberation process:

1. **Party Deliberation** - Each party internally debates the proposal
2. **Cross-Party Debate** - Party leaders and advisors engage across the aisle
3. **Final Voting** - All 22 agents cast their votes with reasoning

## Features

- **22 Distinct Political Personas** - Each agent has a unique background, philosophy, and communication style
- **Hierarchical Party Structure** - Party Head → Senior Advisors → Policy Assistants
- **Multi-Round Negotiation** - Configurable debate rounds with amendment proposals
- **Vote Change Mechanic** - Agents can be persuaded during debate
- **Beautiful CLI Output** - Party-colored panels using Rich library

## Architecture

```
User Proposal
      │
      ▼
┌─────────────────────────────────────────────────────────────────┐
│                    MAIN ORCHESTRATOR                             │
│                                                                  │
│  ┌──────────────────┐        ┌──────────────────┐              │
│  │ REPUBLICAN PARTY │        │  DEMOCRAT PARTY  │              │
│  │   (11 agents)    │        │   (11 agents)    │              │
│  │                  │        │                  │              │
│  │ Party Head       │        │ Party Head       │              │
│  │   ├─ Advisors(4) │        │   ├─ Advisors(4) │              │
│  │   └─ Assists(6)  │        │   └─ Assists(6)  │              │
│  └────────┬─────────┘        └────────┬─────────┘              │
│           │                           │                         │
│           ▼                           ▼                         │
│              CROSS-PARTY DEBATE                                 │
│                      │                                          │
│                      ▼                                          │
│               FINAL VOTING                                      │
│                      │                                          │
│                      ▼                                          │
│            PASSED / REJECTED                                    │
└─────────────────────────────────────────────────────────────────┘
```

## Agent Roster

### Republican Party (11 agents)

| Role | Name | Title | Specialty |
|------|------|-------|-----------|
| Party Head | Senator Mitchell Crawford | Senate Majority Leader | Overall Strategy |
| Advisor | Dr. Harrison Wells | Chief Economic Advisor | Tax/Fiscal Policy |
| Advisor | General (Ret.) Robert Steele | Defense Policy Advisor | National Security |
| Advisor | Pastor David Whitfield | Social Policy Advisor | Traditional Values |
| Advisor | Judge Victoria Harrington | Legal Counsel | Constitutional Law |
| Assistant | Margaret Chen | Budget Analyst | Fiscal Analysis |
| Assistant | Marcus Reilly | Trade Specialist | International Trade |
| Assistant | Jake Patterson | Energy Policy Analyst | Energy Independence |
| Assistant | Dr. Sarah Mitchell | Healthcare Analyst | Healthcare Policy |
| Assistant | Sheriff Ricardo Mendez | Immigration Specialist | Border Policy |
| Assistant | Dr. Thomas Blackwell | Research Director | Data & Statistics |

### Democrat Party (11 agents)

| Role | Name | Title | Specialty |
|------|------|-------|-----------|
| Party Head | Rep. Angela Washington | Speaker of the House | Coalition Building |
| Advisor | Dr. Janet Ramirez | Chief Economic Advisor | Labor/Progressive Tax |
| Advisor | Dr. Michael Green | Climate Policy Advisor | Environment |
| Advisor | Maya Jefferson | Social Justice Advisor | Civil Rights |
| Advisor | Prof. Eleanor Goldstein | Legal Counsel | Constitutional Law |
| Assistant | Derek Washington | Budget Analyst | Progressive Revenue |
| Assistant | Maria Santos | Labor Relations Specialist | Workers' Rights |
| Assistant | Dr. Patricia Chen | Healthcare Policy Analyst | Universal Healthcare |
| Assistant | Principal James Wright | Education Specialist | Public Education |
| Assistant | Sofia Herrera | Immigration Specialist | Immigration Reform |
| Assistant | Dr. Anthony Liu | Research Director | Policy Research |

## Installation

### Prerequisites

- Python 3.11+
- Anthropic API key

### Setup

1. Clone the repository:
```bash
git clone https://github.com/floriangrousset/Revolution.git
cd Revolution
```

2. Create and activate virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure your API key:
```bash
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

## Usage

Run the negotiation system:

```bash
python -m src.main
```

You'll be prompted to:
1. Enter your proposal (e.g., "Should we legalize marijuana?")
2. Set the maximum number of negotiation rounds (1-5)

### Example Session

```
╔══════════════════════════════════════════════════════════════╗
║  REVOLUTION                                                   ║
║  Multi-Agent Political Negotiation System                     ║
╚══════════════════════════════════════════════════════════════╝

Enter your proposal for negotiation:
Your proposal: Should we implement universal basic income?
Maximum negotiation rounds: 3

═══ Republican Party Deliberation ═══

╭─── [rep_head] Senator Mitchell Crawford ───╮
│ Colleagues, we need to address this        │
│ Universal Basic Income proposal with the   │
│ serious analysis it deserves...            │
╰────────────────────────────────────────────╯

... (deliberation continues) ...

═══ Final Voting ═══

Republican Party:
  Senator Mitchell Crawford    NO   Traditional values and fiscal...
  Dr. Harrison Wells          NO   Supply-side economics...
  ...

Democrat Party:
  Rep. Angela Washington      YES  Economic justice and...
  Dr. Janet Ramirez          YES  Progressive taxation can...
  ...

╭─── Final Result ───╮
│ REJECTED           │
│ Vote: 11-11        │
│ Bipartisan: No     │
╰────────────────────╯
```

## Configuration

Environment variables (`.env`):

| Variable | Description | Default |
|----------|-------------|---------|
| `ANTHROPIC_API_KEY` | Your Anthropic API key | Required |
| `MODEL_NAME` | Claude model to use | `claude-sonnet-4-20250514` |
| `MAX_ROUNDS` | Default max negotiation rounds | `5` |

## Project Structure

```
Revolution/
├── src/
│   ├── main.py              # Entry point
│   ├── state/
│   │   └── types.py         # State definitions
│   ├── agents/
│   │   ├── base.py          # Agent class
│   │   ├── prompts.py       # System prompts
│   │   ├── republican.py    # Republican personas
│   │   └── democrat.py      # Democrat personas
│   ├── graphs/
│   │   ├── main_graph.py    # Main orchestration
│   │   ├── party_graph.py   # Party deliberation
│   │   └── nodes.py         # Graph nodes
│   ├── voting/
│   │   └── consensus.py     # Voting logic
│   └── cli/
│       └── display.py       # Rich console output
├── examples/
│   └── sample_proposals.txt # Example proposals
├── requirements.txt
├── pyproject.toml
└── .env.example
```

## Tech Stack

- **[LangGraph](https://github.com/langchain-ai/langgraph)** - Multi-agent orchestration
- **[Claude API](https://www.anthropic.com/)** - LLM reasoning (Sonnet/Opus)
- **[Rich](https://github.com/Textualize/rich)** - Beautiful terminal output
- **[Pydantic](https://docs.pydantic.dev/)** - Data validation

## Sample Proposals

Try these proposals to see interesting debates:

**Social Issues:**
- "Should we legalize gay marriage nationwide?"
- "Should we implement stricter gun control measures?"

**Economic Policy:**
- "Should we raise the federal minimum wage to $15/hour?"
- "Should we implement a universal basic income?"

**Healthcare:**
- "Should we implement Medicare for All?"

**Climate:**
- "Should we implement a Green New Deal?"

**Criminal Justice:**
- "Should we abolish the death penalty?"

See `examples/sample_proposals.txt` for more ideas.

## How It Works

### 1. Party Deliberation Phase

Each party goes through internal deliberation:

1. **Party Head Introduction** - Frames the proposal and sets the agenda
2. **Advisor Analysis** - Each of 4 advisors analyzes from their expertise
3. **Assistant Research** - 6 assistants provide supporting data
4. **Position Synthesis** - Party head synthesizes into official position

### 2. Cross-Party Debate Phase

- Party heads present their positions
- Advisors engage in point/counterpoint
- Amendments may be proposed
- Multiple rounds possible (configurable)

### 3. Final Voting Phase

- All 22 agents vote: SUPPORT / OPPOSE / ABSTAIN
- Each provides reasoning based on their philosophy
- Votes can change based on debate (persuasion mechanic)
- Simple majority wins (50%+1 of non-abstaining votes)

## Performance Notes

- Each full negotiation takes 5-15 minutes depending on rounds
- ~50-100 API calls per session (22 agents × multiple phases)
- Claude Sonnet recommended for cost efficiency
- Claude Opus available for higher quality reasoning

## Contributing

Contributions are welcome! Some ideas:

- Add more agent personas
- Implement amendment negotiation logic
- Add historical voting record tracking
- Create a web interface
- Add more political parties (Libertarian, Green, etc.)

## License

MIT License - see LICENSE file for details.

## Acknowledgments

- Built with [Claude Code](https://claude.com/claude-code)
- Inspired by multi-agent debate research
- Uses LangGraph's powerful orchestration patterns
