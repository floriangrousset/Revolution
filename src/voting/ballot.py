"""Structured ballot schema for agent votes.

Voting replies are forced into this shape via `with_structured_output`
(Anthropic tool calling) so a malformed free-text reply can't silently
become an abstention. The legacy `VOTE:` / `REASONING:` text format remains
as a fallback parse path in `src.graphs.nodes.cast_ballot`.
"""
from typing import Literal

from pydantic import BaseModel, Field


class VoteBallot(BaseModel):
    """One agent's vote, as returned by the model."""

    vote: Literal["support", "oppose", "abstain"]
    reasoning: str = Field(
        description="2-3 sentences, in character, explaining why you voted this way",
    )
    amendments: list[str] = Field(
        default_factory=list,
        description=(
            "Amendments you would require for your support, each as its own "
            "short clause. Empty list if none."
        ),
    )
