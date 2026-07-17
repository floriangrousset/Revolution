"""State type definitions for the negotiation system."""
from typing import Annotated, Any, TypedDict, Literal, Optional
from dataclasses import dataclass, field
import uuid


@dataclass
class Proposal:
    """A proposal submitted for negotiation."""
    id: str
    title: str
    description: str
    submitted_by: str = "user"
    status: Literal["pending", "debating", "voting", "passed", "rejected", "amended"] = "pending"
    amendments: list[str] = field(default_factory=list)
    current_version: int = 1

    @classmethod
    def from_user_input(cls, text: str) -> "Proposal":
        """Create a proposal from user input text."""
        return cls(
            id=f"prop_{uuid.uuid4().hex[:8]}",
            title="User Proposal",
            description=text.strip(),
            submitted_by="user",
            status="pending",
        )


@dataclass
class Vote:
    """A vote cast by an agent."""
    agent_id: str
    agent_name: str
    agent_role: str
    # `party` is the persona's party id. Loosened from Literal to str in R2-C so
    # custom caucuses (libertarian, green, …) can debate too.
    party: str
    vote: Literal["support", "oppose", "abstain"]
    reasoning: str
    amendments: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        return f"{self.agent_id} ({self.party}): {self.vote.upper()} - {self.reasoning}"


@dataclass
class AgentMessage:
    """A message from an agent during deliberation."""
    agent_id: str
    agent_name: str
    party: str
    role: str
    content: str
    phase: str

    def __str__(self) -> str:
        return f"[{self.agent_id}] {self.agent_name}: {self.content}"


def add_messages(left: list[AgentMessage], right: list[AgentMessage]) -> list[AgentMessage]:
    """Reducer to accumulate messages."""
    return left + right


def add_votes(left: list[Vote], right: list[Vote]) -> list[Vote]:
    """Reducer to accumulate votes, updating existing votes from same agent."""
    # Create a dict keyed by agent_id to allow vote changes
    votes_dict = {v.agent_id: v for v in left}
    for v in right:
        votes_dict[v.agent_id] = v  # Overwrites if agent already voted
    return list(votes_dict.values())


def merge_positions(
    left: dict[str, Optional[str]], right: dict[str, Optional[str]]
) -> dict[str, Optional[str]]:
    """Reducer for `positions` — right wins per party."""
    out = dict(left)
    out.update(right)
    return out


def merge_votes_by_party(
    left: dict[str, list[Vote]], right: dict[str, list[Vote]]
) -> dict[str, list[Vote]]:
    """Reducer for `votes_by_party` — per-party list gets the add_votes treatment."""
    out: dict[str, list[Vote]] = {k: list(v) for k, v in left.items()}
    for party, votes in right.items():
        existing = {v.agent_id: v for v in out.get(party, [])}
        for v in votes:
            existing[v.agent_id] = v
        out[party] = list(existing.values())
    return out


class PartyState(TypedDict):
    """State for party-level deliberation (subgraph)."""
    # `party_name` is the party id (e.g. "democrat", "republican", "libertarian").
    party_name: str
    proposal: Proposal
    discussion: Annotated[list[AgentMessage], add_messages]
    party_position: Optional[str]
    member_votes: Annotated[list[Vote], add_votes]
    current_speaker_index: int
    phase: Literal["intro", "advisor_discussion", "assistant_research", "synthesis", "voting"]


class NegotiationState(TypedDict, total=False):
    """Main orchestration state for the full negotiation.

    R2-C generalized this to support any 2+ participating parties via the
    dict-keyed `positions` and `votes_by_party` fields. The legacy
    `republican_*` / `democrat_*` fields are still populated when those two
    parties are present, for backward-compat with CLI callers and tests
    written against the M1–M5 shape.
    """
    proposal: Proposal
    messages: Annotated[list[AgentMessage], add_messages]
    debate_transcript: Annotated[list[AgentMessage], add_messages]
    # List of party ids participating in this negotiation, in seating order
    # (left → right in the chamber). Set at run_negotiation() entry.
    parties: list[str]
    # Per-party synthesized position after deliberation.
    positions: Annotated[dict[str, Optional[str]], merge_positions]
    # Per-party agent votes — keyed by party id.
    votes_by_party: Annotated[dict[str, list[Vote]], merge_votes_by_party]
    # ---- Back-compat shims, populated when the relevant party is in `parties` ----
    republican_position: Optional[str]
    democrat_position: Optional[str]
    republican_votes: Annotated[list[Vote], add_votes]
    democrat_votes: Annotated[list[Vote], add_votes]
    # ---------------------------------------------------------------------------
    negotiation_round: int
    max_rounds: int
    phase: str
    # Passage rule for this debate ("majority" / "three_fifths" / "two_thirds").
    passage_rule: str
    # Optional seat-weighting snapshot: party id → configured seat count,
    # captured when the debate was created. Empty dict = unweighted.
    seat_config: dict[str, int]
    # The full `src.voting.consensus.VotingResult` computed by the resolution
    # node, so callers (the web engine, CLI) read the tally off the state
    # instead of recomputing it with possibly-different rules. Typed as Any
    # because LangGraph evaluates these annotations at runtime and a real
    # import here would be circular (consensus imports Vote from this module).
    voting_result: Optional[Any]
    final_result: Optional[Literal["passed", "rejected", "amended"]]
    amendments_proposed: list[str]
    # Amendment text → ids of the agents whose ballots proposed it. Rebuilt on
    # every voting pass (plain overwrite, no reducer).
    amendment_sponsors: dict[str, list[str]]
    # ---- Markup loop (amendment lifecycle) ----
    # How many markup cycles this debate may run (0 = amendments are recorded
    # but never applied — the pre-markup behavior).
    max_markup_rounds: int
    # Cycles completed so far. The loop bound lives in state, not config, so
    # a reducer mistake can't spin the graph forever.
    markup_rounds_done: int
    # Amendment texts that have been incorporated into the proposal.
    applied_amendments: list[str]
