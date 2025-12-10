"""Voting and consensus logic."""
from dataclasses import dataclass
from typing import Literal

from ..state.types import Vote


@dataclass
class VotingResult:
    """Result of the final vote."""
    total_support: int
    total_oppose: int
    total_abstain: int
    republican_support: int
    republican_oppose: int
    republican_abstain: int
    democrat_support: int
    democrat_oppose: int
    democrat_abstain: int
    passed: bool
    bipartisan: bool
    margin: str

    def __str__(self) -> str:
        status = "PASSED" if self.passed else "REJECTED"
        bipartisan_str = " (Bipartisan)" if self.bipartisan else ""
        return f"{status}{bipartisan_str} - {self.margin}"


def calculate_party_result(votes: list[Vote]) -> dict[str, int]:
    """Calculate vote counts for a party.

    Args:
        votes: List of Vote objects from a party

    Returns:
        Dict with counts for support, oppose, abstain
    """
    result = {"support": 0, "oppose": 0, "abstain": 0}
    for vote in votes:
        result[vote.vote] += 1
    return result


def determine_final_result(
    republican_votes: list[Vote],
    democrat_votes: list[Vote],
    threshold: float = 0.5
) -> VotingResult:
    """Determine if proposal passes based on overall majority.

    Args:
        republican_votes: Votes from Republican agents
        democrat_votes: Votes from Democrat agents
        threshold: Percentage needed to pass (default 50%)

    Returns:
        VotingResult with full breakdown
    """
    rep_result = calculate_party_result(republican_votes)
    dem_result = calculate_party_result(democrat_votes)

    total_support = rep_result["support"] + dem_result["support"]
    total_oppose = rep_result["oppose"] + dem_result["oppose"]
    total_abstain = rep_result["abstain"] + dem_result["abstain"]

    # Only count non-abstaining votes for passage determination
    total_votes = total_support + total_oppose

    if total_votes > 0:
        passed = (total_support / total_votes) > threshold
    else:
        passed = False

    # Check if bipartisan (at least some support from both parties)
    bipartisan = rep_result["support"] > 0 and dem_result["support"] > 0

    # Create margin string
    margin = f"{total_support}-{total_oppose}"
    if total_abstain > 0:
        margin += f" ({total_abstain} abstention{'s' if total_abstain > 1 else ''})"

    return VotingResult(
        total_support=total_support,
        total_oppose=total_oppose,
        total_abstain=total_abstain,
        republican_support=rep_result["support"],
        republican_oppose=rep_result["oppose"],
        republican_abstain=rep_result["abstain"],
        democrat_support=dem_result["support"],
        democrat_oppose=dem_result["oppose"],
        democrat_abstain=dem_result["abstain"],
        passed=passed,
        bipartisan=bipartisan,
        margin=margin
    )


def get_vote_summary(votes: list[Vote], party: str) -> str:
    """Get a formatted summary of votes for a party.

    Args:
        votes: List of Vote objects
        party: Party name for header

    Returns:
        Formatted string with vote breakdown
    """
    lines = [f"\n{party.upper()} PARTY VOTES:"]
    lines.append("-" * 40)

    for vote in sorted(votes, key=lambda v: (v.role != "party_head", v.role != "advisor", v.agent_id)):
        vote_symbol = {
            "support": "YES",
            "oppose": "NO",
            "abstain": "---"
        }[vote.vote]

        lines.append(f"  {vote.agent_name:30} {vote_symbol}")
        if vote.reasoning:
            # Truncate reasoning for display
            reasoning = vote.reasoning[:100] + "..." if len(vote.reasoning) > 100 else vote.reasoning
            lines.append(f"    Reason: {reasoning}")

    result = calculate_party_result(votes)
    lines.append("-" * 40)
    lines.append(f"  TOTAL: {result['support']} Support | {result['oppose']} Oppose | {result['abstain']} Abstain")

    return "\n".join(lines)
