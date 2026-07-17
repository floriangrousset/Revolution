"""Voting and consensus logic."""
import math
from dataclasses import dataclass, field

from ..state.types import Vote

# Passage rules modeled on real chamber thresholds: simple majority,
# 3/5 (Senate cloture), and 2/3 (veto override / constitutional supermajority).
PASSAGE_RULES: tuple[str, ...] = ("majority", "three_fifths", "two_thirds")


@dataclass(frozen=True)
class VotingRules:
    """How a vote passes.

    `rule` is one of PASSAGE_RULES. `quorum`, when set, is the fraction of
    ALL voters (including abstainers) who must cast a decisive
    (support/oppose) vote for the result to be valid — otherwise the motion
    fails regardless of the split.
    """
    rule: str = "majority"
    quorum: float | None = None


def _rule_passes(rule: str, support: int, oppose: int) -> bool:
    """Integer-only passage test — no float thresholds (2/3 of 435 must not
    fall to rounding)."""
    decisive = support + oppose
    if decisive <= 0:
        return False
    if rule == "three_fifths":
        return 5 * support >= 3 * decisive
    if rule == "two_thirds":
        return 3 * support >= 2 * decisive
    return support > oppose  # simple majority


def _required_support(rule: str, decisive: int) -> int:
    """Minimum support votes needed to pass, given the decisive total."""
    if decisive <= 0:
        return 0
    if rule == "three_fifths":
        return -(-3 * decisive // 5)  # ceil(3d/5)
    if rule == "two_thirds":
        return -(-2 * decisive // 3)  # ceil(2d/3)
    return decisive // 2 + 1


@dataclass
class VotingResult:
    """Result of the final vote.

    R2-C generalized this for N parties. The dict-keyed `by_party` field is
    the canonical source for N-party tallies; the per-party scalar fields
    (`republican_*`, `democrat_*`) are still populated when those parties
    appear so the CLI display, exports, and M1–M5 tests don't need rewriting.
    """
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
    by_party: dict[str, dict[str, int]] = field(default_factory=dict)
    # Passage rule applied ("majority" / "three_fifths" / "two_thirds") and
    # the support count that was needed to pass under it.
    rule: str = "majority"
    required: int = 0

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
    votes_by_party: dict[str, list[Vote]],
    threshold: float = 0.5,
    *,
    rules: VotingRules | None = None,
) -> VotingResult:
    """Determine if the proposal passes across all parties.

    Args:
        votes_by_party: Per-party vote lists keyed by party id.
        threshold: Legacy float threshold. Only honored when `rules` is not
            given and the value differs from the 0.5 default (deprecated path).
        rules: Passage rules to apply. When omitted, defaults to a simple
            majority — bit-for-bit the pre-rules behavior.

    Returns:
        VotingResult with full breakdown. Per-party scalars on the result are
        populated only for parties whose ids match (`republican`, `democrat`);
        the canonical N-party data lives in `result.by_party`.
    """
    by_party: dict[str, dict[str, int]] = {
        party: calculate_party_result(votes) for party, votes in votes_by_party.items()
    }

    total_support = sum(p["support"] for p in by_party.values())
    total_oppose = sum(p["oppose"] for p in by_party.values())
    total_abstain = sum(p["abstain"] for p in by_party.values())

    decisive = total_support + total_oppose
    total_votes = decisive + total_abstain

    quorum_failed = False
    if rules is None and threshold != 0.5:
        # Deprecated float-threshold path, kept for signature back-compat.
        rule_name = f"threshold>{threshold}"
        passed = (total_support / decisive) > threshold if decisive > 0 else False
        required = math.floor(decisive * threshold) + 1 if decisive > 0 else 0
    else:
        active = rules or VotingRules()
        rule_name = active.rule
        passed = _rule_passes(active.rule, total_support, total_oppose)
        required = _required_support(active.rule, decisive)
        if active.quorum is not None and total_votes > 0:
            quorum_failed = decisive < math.ceil(active.quorum * total_votes)
            if quorum_failed:
                passed = False

    # Bipartisan = at least two distinct parties contributed at least one
    # support vote each. Generalizes the old D+R definition to N parties.
    supporting_parties = [p for p, counts in by_party.items() if counts["support"] > 0]
    bipartisan = len(supporting_parties) >= 2

    margin = f"{total_support}-{total_oppose}"
    if total_abstain > 0:
        margin += f" ({total_abstain} abstention{'s' if total_abstain > 1 else ''})"
    if quorum_failed:
        margin += " (failed quorum)"

    rep = by_party.get("republican", {"support": 0, "oppose": 0, "abstain": 0})
    dem = by_party.get("democrat", {"support": 0, "oppose": 0, "abstain": 0})

    return VotingResult(
        total_support=total_support,
        total_oppose=total_oppose,
        total_abstain=total_abstain,
        republican_support=rep["support"],
        republican_oppose=rep["oppose"],
        republican_abstain=rep["abstain"],
        democrat_support=dem["support"],
        democrat_oppose=dem["oppose"],
        democrat_abstain=dem["abstain"],
        passed=passed,
        bipartisan=bipartisan,
        margin=margin,
        by_party=by_party,
        rule=rule_name,
        required=required,
    )


def determine_final_result_two_party(
    republican_votes: list[Vote],
    democrat_votes: list[Vote],
    threshold: float = 0.5,
) -> VotingResult:
    """Back-compat wrapper for the original two-party signature.

    Pre-R2-C code (CLI, server engine, tests) used to call
    `determine_final_result(rep_votes, dem_votes)`. The N-party rewrite
    moved to a dict-keyed signature; this helper keeps the old shape valid.
    """
    return determine_final_result(
        {"republican": republican_votes, "democrat": democrat_votes},
        threshold=threshold,
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

    for vote in sorted(votes, key=lambda v: (v.agent_role != "party_head", v.agent_role != "advisor", v.agent_id)):
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
