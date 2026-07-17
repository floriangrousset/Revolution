"""Unit tests for vote tallying and passage rules.

The consensus layer had no direct tests before configurable passage rules
landed; these pin down both the legacy default behavior and the new
three-fifths / two-thirds / quorum mechanics with integer-exact assertions.
"""
from src.state.types import Vote
from src.voting.consensus import VotingRules, determine_final_result


def _votes(party: str, support: int = 0, oppose: int = 0, abstain: int = 0) -> list[Vote]:
    out: list[Vote] = []
    counts = [("support", support), ("oppose", oppose), ("abstain", abstain)]
    for value, n in counts:
        for i in range(n):
            out.append(
                Vote(
                    agent_id=f"{party}_{value}_{i}",
                    agent_name=f"{party} {value} {i}",
                    agent_role="assistant",
                    party=party,
                    vote=value,  # type: ignore[arg-type]
                    reasoning="test",
                )
            )
    return out


def test_majority_tie_fails():
    result = determine_final_result({"a": _votes("a", support=11), "b": _votes("b", oppose=11)})
    assert not result.passed
    assert result.rule == "majority"
    assert result.required == 12
    assert result.margin == "11-11"


def test_majority_one_vote_margin_passes():
    result = determine_final_result({"a": _votes("a", support=12), "b": _votes("b", oppose=11)})
    assert result.passed


def test_default_rules_none_matches_legacy_majority():
    votes = {"a": _votes("a", support=6, oppose=5, abstain=3)}
    legacy = determine_final_result(votes)
    explicit = determine_final_result(votes, rules=VotingRules())
    assert legacy.passed == explicit.passed is True
    assert legacy.margin == explicit.margin == "6-5 (3 abstentions)"


def test_three_fifths_boundary():
    # 60 of 100 decisive votes passes cloture exactly; 59 fails.
    passing = determine_final_result(
        {"a": _votes("a", support=60, oppose=40)}, rules=VotingRules(rule="three_fifths")
    )
    failing = determine_final_result(
        {"a": _votes("a", support=59, oppose=41)}, rules=VotingRules(rule="three_fifths")
    )
    assert passing.passed
    assert passing.required == 60
    assert not failing.passed


def test_two_thirds_boundary_no_float_rounding():
    # 66 of 99 decisive votes is exactly 2/3 — must pass without float slop.
    passing = determine_final_result(
        {"a": _votes("a", support=66, oppose=33)}, rules=VotingRules(rule="two_thirds")
    )
    failing = determine_final_result(
        {"a": _votes("a", support=65, oppose=34)}, rules=VotingRules(rule="two_thirds")
    )
    assert passing.passed
    assert passing.required == 66
    assert not failing.passed


def test_abstentions_excluded_from_decisive_total():
    # 6-4 with 12 abstaining: 3/5 of the 10 decisive votes is 6 — passes.
    result = determine_final_result(
        {"a": _votes("a", support=6, oppose=4, abstain=12)},
        rules=VotingRules(rule="three_fifths"),
    )
    assert result.passed
    assert result.required == 6


def test_quorum_failure_blocks_passage():
    # 3-0 unanimous but 19 of 22 abstained: under a 50% quorum the motion dies.
    result = determine_final_result(
        {"a": _votes("a", support=3, abstain=19)},
        rules=VotingRules(rule="majority", quorum=0.5),
    )
    assert not result.passed
    assert "failed quorum" in result.margin


def test_quorum_met_passes():
    result = determine_final_result(
        {"a": _votes("a", support=12, oppose=2, abstain=8)},
        rules=VotingRules(rule="majority", quorum=0.5),
    )
    assert result.passed


def test_no_votes_fails():
    result = determine_final_result({})
    assert not result.passed
    assert result.required == 0


def test_bipartisan_requires_two_supporting_parties():
    single = determine_final_result(
        {"a": _votes("a", support=10), "b": _votes("b", oppose=5)}
    )
    dual = determine_final_result(
        {"a": _votes("a", support=10), "b": _votes("b", support=1, oppose=4)}
    )
    assert not single.bipartisan
    assert dual.bipartisan


def test_legacy_two_party_scalars_still_populated():
    result = determine_final_result(
        {
            "republican": _votes("republican", support=7, oppose=3, abstain=1),
            "democrat": _votes("democrat", support=2, oppose=8, abstain=1),
        }
    )
    assert result.republican_support == 7
    assert result.democrat_oppose == 8
    assert result.total_abstain == 2
