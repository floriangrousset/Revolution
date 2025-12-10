"""State type definitions for the negotiation system."""
from typing import Annotated, TypedDict, Literal, Optional
from dataclasses import dataclass, field
import operator
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
    party: Literal["republican", "democrat"]
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


class PartyState(TypedDict):
    """State for party-level deliberation (subgraph)."""
    party_name: Literal["republican", "democrat"]
    proposal: Proposal
    discussion: Annotated[list[AgentMessage], add_messages]
    party_position: Optional[str]
    member_votes: Annotated[list[Vote], add_votes]
    current_speaker_index: int
    phase: Literal["intro", "advisor_discussion", "assistant_research", "synthesis", "voting"]


class NegotiationState(TypedDict):
    """Main orchestration state for the full negotiation."""
    proposal: Proposal
    messages: Annotated[list[AgentMessage], add_messages]
    debate_transcript: Annotated[list[AgentMessage], add_messages]
    republican_position: Optional[str]
    democrat_position: Optional[str]
    republican_votes: Annotated[list[Vote], add_votes]
    democrat_votes: Annotated[list[Vote], add_votes]
    negotiation_round: int
    max_rounds: int
    phase: Literal[
        "proposal_submission",
        "republican_deliberation",
        "democrat_deliberation",
        "cross_party_debate",
        "amendment_proposal",
        "final_voting",
        "resolution"
    ]
    final_result: Optional[Literal["passed", "rejected", "amended"]]
    amendments_proposed: list[str]
