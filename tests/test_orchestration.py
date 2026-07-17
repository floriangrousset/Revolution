"""Smoke tests for the main negotiation graph using a stub LLM.

These tests run the full orchestration end-to-end without hitting the Anthropic
API. They verify multi-round debate actually loops and that amendments
extracted from votes are aggregated into NegotiationState.
"""
import pytest

from src.graphs import nodes as nodes_module
from src.graphs.main_graph import run_negotiation


class _StubResponse:
    def __init__(self, content: str):
        self.content = content


class _StubModel:
    """Pattern-matches the HumanMessage prompt to return a plausible canned
    response for each prompt template used by the graph."""

    def __init__(self):
        self.calls: list[str] = []

    async def ainvoke(self, messages):
        # The HumanMessage is always last.
        prompt = messages[-1].content
        self.calls.append(prompt)

        if "cast your final vote" in prompt:
            return _StubResponse(
                "VOTE: SUPPORT\n"
                "REASONING: Aligns with core principles.\n"
                "AMENDMENTS: Add a sunset clause after 5 years."
            )
        if "Continue the cross-party debate" in prompt:
            return _StubResponse("Rebuttal: I disagree with the framing.")
        if "about to engage in cross-party debate" in prompt:
            return _StubResponse("Opening statement: here is our case.")
        if "synthesize the discussion" in prompt:
            return _StubResponse("Party position: conditional support.")
        if "provide your analysis" in prompt:
            return _StubResponse("Analysis: significant tradeoffs.")
        if "provide supporting research" in prompt:
            return _StubResponse("Research: relevant precedent exists.")
        if "introduce this proposal" in prompt:
            return _StubResponse("Intro: team, here is the proposal.")
        return _StubResponse("Generic response.")


class _MarkupStubModel(_StubModel):
    """Votes OPPOSE (with an amendment) on the original text and SUPPORT once
    the markup clerk has incorporated it — exercising the full rescue loop."""

    REVISED = "REVISED PROPOSAL vNEXT with the sunset clause incorporated."

    async def ainvoke(self, messages):
        prompt = messages[-1].content
        if "chamber clerk" in prompt and "Amendment to incorporate" in prompt:
            self.calls.append(prompt)
            return _StubResponse(self.REVISED)
        if "cast your final vote" in prompt:
            self.calls.append(prompt)
            if self.REVISED in prompt:
                return _StubResponse(
                    "VOTE: SUPPORT\nREASONING: The sunset clause fixes it.\nAMENDMENTS: None"
                )
            return _StubResponse(
                "VOTE: OPPOSE\n"
                "REASONING: Unacceptable without a sunset clause.\n"
                "AMENDMENTS: Add a sunset clause after 5 years."
            )
        return await super().ainvoke(messages)


@pytest.fixture
def stub_model(monkeypatch):
    stub = _StubModel()
    monkeypatch.setattr(nodes_module, "get_model", lambda: stub)
    return stub


@pytest.fixture
def markup_stub_model(monkeypatch):
    stub = _MarkupStubModel()
    monkeypatch.setattr(nodes_module, "get_model", lambda: stub)
    return stub


async def test_two_round_debate_actually_loops(stub_model):
    """With max_rounds=2 the debate node must run twice and increment the
    round counter accordingly."""
    result = await run_negotiation(
        proposal_text="Test proposal.",
        max_rounds=2,
    )

    assert result["negotiation_round"] == 2, (
        f"Expected 2 rounds, got {result['negotiation_round']}"
    )

    debate_msgs = [
        m for m in result["debate_transcript"]
        if m.phase == "cross_party_debate"
    ]
    # Per round: 2 heads + 2 rep advisors + 2 dem advisors = 6 messages.
    # Two rounds therefore produce 12 cross-party messages.
    assert len(debate_msgs) == 12, (
        f"Expected 12 debate messages across 2 rounds, got {len(debate_msgs)}"
    )


async def test_single_round_debate_stops_after_one(stub_model):
    """max_rounds=1 must produce exactly one debate round."""
    result = await run_negotiation(
        proposal_text="Test proposal.",
        max_rounds=1,
    )
    assert result["negotiation_round"] == 1
    debate_msgs = [
        m for m in result["debate_transcript"]
        if m.phase == "cross_party_debate"
    ]
    assert len(debate_msgs) == 6


async def test_round_two_uses_rebuttal_not_opening(stub_model):
    """Round 2 heads must use the rebuttal prompt referencing prior transcript,
    not the opening prompt as if the debate were starting fresh."""
    await run_negotiation(proposal_text="Test proposal.", max_rounds=2)

    opening_calls = [c for c in stub_model.calls if "about to engage in cross-party debate" in c]
    rebuttal_calls = [c for c in stub_model.calls if "Continue the cross-party debate" in c]

    # Round 1: 2 heads use opening, 4 advisors use rebuttal.
    # Round 2: 2 heads use rebuttal, 4 advisors use rebuttal.
    # So total: 2 opening, 4+6=10 rebuttal.
    assert len(opening_calls) == 2, f"Expected 2 opening prompts, got {len(opening_calls)}"
    assert len(rebuttal_calls) == 10, f"Expected 10 rebuttal prompts, got {len(rebuttal_calls)}"


async def test_amendments_aggregated_into_state(stub_model):
    """Amendments extracted from each vote must be aggregated and de-duplicated
    into NegotiationState.amendments_proposed."""
    result = await run_negotiation(
        proposal_text="Test proposal.",
        max_rounds=1,
    )
    amendments = result.get("amendments_proposed", [])
    assert amendments == ["Add a sunset clause after 5 years."], (
        f"Expected single de-duplicated amendment, got {amendments}"
    )
    # Every voter proposed the same amendment, so all 22 agents sponsor it.
    sponsors = result.get("amendment_sponsors", {})
    assert len(sponsors.get("Add a sunset clause after 5 years.", [])) == 22


async def test_negotiation_produces_final_result(stub_model):
    """End-to-end the graph reaches resolution with a final_result string."""
    result = await run_negotiation(
        proposal_text="Test proposal.",
        max_rounds=1,
    )
    assert result["final_result"] in {"passed", "rejected"}
    assert result["phase"] == "resolution"
    # 11 agents per party, all stubbed to SUPPORT
    assert len(result["republican_votes"]) == 11
    assert len(result["democrat_votes"]) == 11


async def test_passage_rule_flows_to_voting_result(stub_model):
    """A per-debate passage_rule must reach the resolution node's tally."""
    result = await run_negotiation(
        proposal_text="Test proposal.",
        max_rounds=1,
        passage_rule="two_thirds",
    )
    voting = result.get("voting_result")
    assert voting is not None
    assert voting.rule == "two_thirds"
    # 22 stubbed SUPPORT votes clear a 2/3 bar as well.
    assert voting.passed
    assert result["passage_rule"] == "two_thirds"


async def test_seat_config_flows_to_voting_result(stub_model):
    """A per-debate seat snapshot must weight the resolution tally."""
    result = await run_negotiation(
        proposal_text="Test proposal.",
        max_rounds=1,
        seat_config={"republican": 218, "democrat": 212},
    )
    voting = result.get("voting_result")
    assert voting is not None
    assert voting.weighted
    # All 22 stubbed agents SUPPORT → weighted support is the full 430 seats.
    assert voting.weighted_support == 430.0
    assert voting.by_party["republican"]["support"] == 11  # raw roll call intact


async def test_markup_round_rescues_failed_vote_as_amended(markup_stub_model):
    """Failed vote + amendments + markup_rounds=1 → clerk applies the top
    amendment, heads debate, the chamber re-votes, and the motion passes
    'as amended' at version 2."""
    result = await run_negotiation(
        proposal_text="Test proposal.",
        max_rounds=1,
        markup_rounds=1,
    )

    assert result["final_result"] == "amended"
    proposal = result["proposal"]
    assert proposal.current_version == 2
    assert proposal.description == _MarkupStubModel.REVISED
    assert result["applied_amendments"] == ["Add a sunset clause after 5 years."]
    assert result["markup_rounds_done"] == 1

    # Voting ran exactly twice (22 agents each), markup clerk once.
    voting_calls = [c for c in markup_stub_model.calls if "cast your final vote" in c]
    assert len(voting_calls) == 44
    clerk_calls = [c for c in markup_stub_model.calls if "Amendment to incorporate" in c]
    assert len(clerk_calls) == 1

    # Markup phases made it into the record.
    markup_msgs = [m for m in result["messages"] if m.phase == "markup"]
    assert len(markup_msgs) == 1
    head_turns = [m for m in result["debate_transcript"] if m.phase == "markup_debate"]
    assert len(head_turns) == 2  # heads only, one each


async def test_markup_disabled_keeps_failed_vote_rejected(markup_stub_model):
    """Same failing stub with markup_rounds=0 (the default) must reject and
    never invoke the clerk — guarding the pre-markup behavior."""
    result = await run_negotiation(
        proposal_text="Test proposal.",
        max_rounds=1,
    )
    assert result["final_result"] == "rejected"
    assert result["proposal"].current_version == 1
    voting_calls = [c for c in markup_stub_model.calls if "cast your final vote" in c]
    assert len(voting_calls) == 22
    clerk_calls = [c for c in markup_stub_model.calls if "Amendment to incorporate" in c]
    assert len(clerk_calls) == 0


async def test_markup_loop_terminates_when_still_failing(monkeypatch):
    """If agents keep opposing even after markup, the loop must stop at
    max_markup_rounds and resolve 'rejected' — never spin."""

    class _AlwaysOpposeStub(_MarkupStubModel):
        async def ainvoke(self, messages):
            prompt = messages[-1].content
            if "cast your final vote" in prompt:
                self.calls.append(prompt)
                return _StubResponse(
                    "VOTE: OPPOSE\nREASONING: Never.\nAMENDMENTS: Add a sunset clause after 5 years."
                )
            return await super().ainvoke(messages)

    stub = _AlwaysOpposeStub()
    monkeypatch.setattr(nodes_module, "get_model", lambda: stub)

    result = await run_negotiation(
        proposal_text="Test proposal.",
        max_rounds=1,
        markup_rounds=1,
    )
    assert result["final_result"] == "rejected"
    assert result["markup_rounds_done"] == 1
    voting_calls = [c for c in stub.calls if "cast your final vote" in c]
    assert len(voting_calls) == 44  # exactly one re-vote, then resolution


async def test_after_debate_decision_routes_continue_then_vote(stub_model):
    """The conditional edge must take 'continue' on round 1 of 2, then 'vote'
    on round 2 of 2. We assert this indirectly via the call sequence: voting
    only runs once, after the second debate round."""
    await run_negotiation(proposal_text="Test proposal.", max_rounds=2)

    voting_calls = [c for c in stub_model.calls if "cast your final vote" in c]
    # 22 agents vote exactly once.
    assert len(voting_calls) == 22, (
        f"Voting must happen once, after final debate round; got {len(voting_calls)} calls"
    )
