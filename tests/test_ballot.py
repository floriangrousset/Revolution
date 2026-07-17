"""Tests for the structured `cast_ballot` voting seam.

Covers the resolution tiers: structured success, retry on schema garbage,
legacy free-text fallback — and that infrastructure errors PROPAGATE so a
dead API ends the debate in status='error' instead of a fabricated
all-abstain tally.
"""
import pytest
from langchain_core.exceptions import OutputParserException

from src.graphs import nodes as nodes_module
from src.graphs.nodes import cast_ballot
from src.voting.ballot import VoteBallot
from src.agents.loader import load_party_agents


@pytest.fixture
def agent():
    return load_party_agents("republican")[0]


class _StructuredRunnable:
    def __init__(self, outcomes: list):
        # Each entry is either a VoteBallot to return or an Exception to raise.
        self.outcomes = outcomes
        self.calls = 0

    async def ainvoke(self, messages):
        outcome = self.outcomes[min(self.calls, len(self.outcomes) - 1)]
        self.calls += 1
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class _StructuredModel:
    """Stub with `with_structured_output`, like the real ChatAnthropic."""

    def __init__(self, outcomes: list, text_response: str = "VOTE: OPPOSE\nREASONING: No."):
        self.runnable = _StructuredRunnable(outcomes)
        self.text_response = text_response
        self.text_calls = 0

    def with_structured_output(self, schema):
        assert schema is VoteBallot
        return self.runnable

    async def ainvoke(self, messages):
        self.text_calls += 1

        class _Resp:
            content = self.text_response

        return _Resp()


class _TextOnlyModel:
    """Stub without `with_structured_output` — the legacy test-stub shape."""

    def __init__(self, text_response: str):
        self.text_response = text_response

    async def ainvoke(self, messages):
        class _Resp:
            content = self.text_response

        return _Resp()


class _ApiDownModel:
    """Simulates an infrastructure failure — errors must PROPAGATE."""

    def with_structured_output(self, schema):
        return _StructuredRunnable([RuntimeError("api down")])

    async def ainvoke(self, messages):
        raise RuntimeError("api down")


def _patch(monkeypatch, model):
    monkeypatch.setattr(nodes_module, "get_model", lambda: model)


async def test_structured_ballot_success(monkeypatch, agent):
    ballot = VoteBallot(
        vote="support",
        reasoning="Fits the caucus agenda.",
        amendments=["Add a sunset clause.", "  ", "Cap spending."],
    )
    model = _StructuredModel([ballot])
    _patch(monkeypatch, model)

    vote = await cast_ballot(agent, "republican", "sys", "human")

    assert vote.vote == "support"
    assert vote.reasoning == "Fits the caucus agenda."
    # Blank amendments are dropped, real ones kept as separate entries.
    assert vote.amendments == ["Add a sunset clause.", "Cap spending."]
    assert model.text_calls == 0, "structured success must not hit the text path"


async def test_structured_ballot_retries_once_then_succeeds(monkeypatch, agent):
    ballot = VoteBallot(vote="oppose", reasoning="Crosses a red line.")
    model = _StructuredModel([OutputParserException("parse error"), ballot])
    _patch(monkeypatch, model)

    vote = await cast_ballot(agent, "republican", "sys", "human")

    assert vote.vote == "oppose"
    assert model.runnable.calls == 2
    assert model.text_calls == 0


async def test_schema_failure_falls_back_to_text_parsing(monkeypatch, agent):
    model = _StructuredModel(
        [OutputParserException("boom"), OutputParserException("boom again")],
        text_response="VOTE: OPPOSE\nREASONING: Fallback path works.\nAMENDMENTS: None",
    )
    _patch(monkeypatch, model)

    vote = await cast_ballot(agent, "republican", "sys", "human")

    assert vote.vote == "oppose"
    assert vote.reasoning == "Fallback path works."
    assert model.text_calls == 1


async def test_text_only_model_uses_legacy_parser(monkeypatch, agent):
    """Stubs without with_structured_output (the orchestration-test shape)
    must go straight to the legacy parse path."""
    model = _TextOnlyModel("VOTE: SUPPORT\nREASONING: Legacy stub.\nAMENDMENTS: None")
    _patch(monkeypatch, model)

    vote = await cast_ballot(agent, "republican", "sys", "human")

    assert vote.vote == "support"
    assert vote.reasoning == "Legacy stub."


async def test_api_failure_propagates(monkeypatch, agent):
    """Infrastructure errors must NOT become silent abstains — they bubble up
    so the debate runner records status='error'."""
    _patch(monkeypatch, _ApiDownModel())

    with pytest.raises(RuntimeError, match="api down"):
        await cast_ballot(agent, "republican", "sys", "human")
