"""Voting and consensus logic."""
import math
from dataclasses import dataclass, field
from fractions import Fraction

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


def _rule_passes(rule: str, support: "int | Fraction", oppose: "int | Fraction") -> bool:
    """Exact-arithmetic passage test — int or Fraction, never float thresholds
    (2/3 of 435 must not fall to rounding)."""
    decisive = support + oppose
    if decisive <= 0:
        return False
    if rule == "three_fifths":
        return 5 * support >= 3 * decisive
    if rule == "two_thirds":
        return 3 * support >= 2 * decisive
    return support > oppose  # simple majority


def _required_support(rule: str, decisive: "int | Fraction") -> int:
    """Minimum support (votes, or weighted seats) needed to pass."""
    if decisive <= 0:
        return 0
    if rule == "three_fifths":
        return math.ceil(Fraction(3, 5) * decisive)
    if rule == "two_thirds":
        return math.ceil(Fraction(2, 3) * decisive)
    return math.floor(Fraction(decisive) / 2) + 1


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
    # the support count that was needed to pass under it. When seat weighting
    # is active, `required` is expressed in weighted-seat units.
    rule: str = "majority"
    required: int = 0
    # Seat weighting. `weights_by_party` is the per-VOTE weight applied to
    # each party's ballots (seats / ballots cast); the raw head-counts stay
    # in `by_party` so the roll call remains meaningful.
    weighted: bool = False
    weighted_support: float = 0.0
    weighted_oppose: float = 0.0
    weighted_abstain: float = 0.0
    weights_by_party: dict[str, float] = field(default_factory=dict)

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


def _fmt_weight(value: Fraction) -> str:
    """Render a weighted tally compactly: integers without decimals."""
    f = float(value)
    return str(int(f)) if f.is_integer() else f"{f:.1f}"


def determine_final_result(
    votes_by_party: dict[str, list[Vote]],
    threshold: float = 0.5,
    *,
    rules: VotingRules | None = None,
    seat_weights: dict[str, int] | None = None,
) -> VotingResult:
    """Determine if the proposal passes across all parties.

    Args:
        votes_by_party: Per-party vote lists keyed by party id.
        threshold: Legacy float threshold. Only honored when `rules` is not
            given and the value differs from the 0.5 default (deprecated path).
        rules: Passage rules to apply. When omitted, defaults to a simple
            majority — bit-for-bit the pre-rules behavior.
        seat_weights: Optional real-chamber seat counts per party id. Each
            ballot from a party then carries weight `seats / ballots_cast`
            (exact rational math), so party strength reflects configured
            seats rather than persona count. Parties absent from the map
            vote with weight 1.

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

    # Per-vote weights (exact fractions). Weight 1 unless the party has a
    # configured seat count and actually cast ballots.
    use_weights = bool(seat_weights)
    per_vote_weight: dict[str, Fraction] = {}
    if use_weights and seat_weights is not None:
        for party, votes in votes_by_party.items():
            seats = seat_weights.get(party)
            if seats and votes:
                per_vote_weight[party] = Fraction(seats, len(votes))
            else:
                per_vote_weight[party] = Fraction(1)
    else:
        per_vote_weight = {party: Fraction(1) for party in votes_by_party}

    w_support = sum(
        (per_vote_weight[p] * c["support"] for p, c in by_party.items()), Fraction(0)
    )
    w_oppose = sum(
        (per_vote_weight[p] * c["oppose"] for p, c in by_party.items()), Fraction(0)
    )
    w_abstain = sum(
        (per_vote_weight[p] * c["abstain"] for p, c in by_party.items()), Fraction(0)
    )
    w_decisive = w_support + w_oppose

    quorum_failed = False
    if rules is None and threshold != 0.5:
        # Deprecated float-threshold path, kept for signature back-compat.
        rule_name = f"threshold>{threshold}"
        passed = (total_support / decisive) > threshold if decisive > 0 else False
        required = math.floor(decisive * threshold) + 1 if decisive > 0 else 0
    else:
        active = rules or VotingRules()
        rule_name = active.rule
        if use_weights:
            passed = _rule_passes(active.rule, w_support, w_oppose)
            required = _required_support(active.rule, w_decisive)
        else:
            passed = _rule_passes(active.rule, total_support, total_oppose)
            required = _required_support(active.rule, decisive)
        # Quorum counts bodies in the room, not seat weight.
        if active.quorum is not None and total_votes > 0:
            quorum_failed = decisive < math.ceil(active.quorum * total_votes)
            if quorum_failed:
                passed = False

    # Bipartisan = at least two distinct parties contributed at least one
    # support vote each. Generalizes the old D+R definition to N parties.
    # Always computed from raw head-counts, never weighted.
    supporting_parties = [p for p, counts in by_party.items() if counts["support"] > 0]
    bipartisan = len(supporting_parties) >= 2

    if use_weights:
        margin = f"{_fmt_weight(w_support)}-{_fmt_weight(w_oppose)} weighted"
        margin += f" (raw {total_support}-{total_oppose})"
    else:
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
        weighted=use_weights,
        weighted_support=float(w_support),
        weighted_oppose=float(w_oppose),
        weighted_abstain=float(w_abstain),
        weights_by_party={p: float(w) for p, w in per_vote_weight.items()},
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
