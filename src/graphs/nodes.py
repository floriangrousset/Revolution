"""Node implementations for the negotiation graphs."""
import logging
from contextvars import ContextVar
from typing import Any, Literal
from langchain_anthropic import ChatAnthropic
from langchain_core.exceptions import OutputParserException
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage
from pydantic import SecretStr, ValidationError

from ..state.types import PartyState, NegotiationState, AgentMessage, Vote
from ..voting.ballot import VoteBallot
from ..agents.base import Agent
from ..agents.loader import load_party_agents
from ..agents.prompts import (
    PARTY_HEAD_INTRO_PROMPT,
    ADVISOR_ANALYSIS_PROMPT,
    ASSISTANT_RESEARCH_PROMPT,
    SYNTHESIS_PROMPT,
    DEBATE_OPENING_PROMPT,
    DEBATE_REBUTTAL_PROMPT,
    AMENDMENT_MARKUP_PROMPT,
)

log = logging.getLogger(__name__)

# Per-run overrides for model and temperature. The CLI never touches these, so
# they fall back to env / default. The FastAPI debate runner sets them before
# kicking off `run_negotiation` so each debate honors the Launch screen's knobs
# without rewriting every node signature.
_model_override: ContextVar[str | None] = ContextVar("_model_override", default=None)
_temperature_override: ContextVar[float | None] = ContextVar(
    "_temperature_override", default=None
)

# Parties carried over for the two-party shape (back-compat with M1–M5 callers
# and the existing test suite). Anything not in this set goes through the
# generic dict-keyed state only.
_LEGACY_PARTIES = ("republican", "democrat")


def set_model_overrides(*, model: str | None = None, temperature: float | None = None) -> None:
    """Bind model/temperature for the current async task only."""
    _model_override.set(model)
    _temperature_override.set(temperature)


def _content_text(response: BaseMessage) -> str:
    """Narrow a chat-model response's content to a string.

    `BaseMessage.content` is typed `str | list[...]` to support multimodal
    payloads, but our text-only ChatAnthropic calls always return str.
    Asserting here keeps every call site simply typed.
    """
    content = response.content
    if isinstance(content, str):
        return content
    raise TypeError(
        f"Expected str content from model, got {type(content).__name__}"
    )


def get_model() -> ChatAnthropic:
    """Create the Claude model instance.

    Resolution order: per-run contextvar override → settings.json (via the
    shared `src.config` store) → env var override. The Settings page edits
    settings.json; the env var still wins for explicit CI overrides.
    """
    from src.config import get_api_key, get_default_model, get_default_temperature

    api_key = get_api_key()
    model_name = _model_override.get() or get_default_model()
    temperature = _temperature_override.get()
    if temperature is None:
        temperature = get_default_temperature()
    return ChatAnthropic(
        model_name=model_name,
        api_key=SecretStr(api_key),
        max_tokens_to_sample=2048,
        temperature=temperature,
        timeout=None,
        stop=None,
    )


def get_agents_by_party(party: str) -> list[Agent]:
    """Get all agents for a party. Cached after first call."""
    return load_party_agents(party)


def get_party_head(party: str) -> Agent:
    """Get the party head agent."""
    agents = get_agents_by_party(party)
    return next(a for a in agents if a.role == "party_head")


def get_advisors(party: str) -> list[Agent]:
    """Get all advisor agents for a party."""
    agents = get_agents_by_party(party)
    return [a for a in agents if a.role == "advisor"]


def get_assistants(party: str) -> list[Agent]:
    """Get all assistant agents for a party."""
    agents = get_agents_by_party(party)
    return [a for a in agents if a.role == "assistant"]


def format_discussion(messages: list[AgentMessage]) -> str:
    """Format discussion messages for prompt context."""
    if not messages:
        return "No discussion yet."

    formatted = []
    for msg in messages:
        formatted.append(f"**[{msg.agent_id}] {msg.agent_name} ({msg.role}):**\n{msg.content}\n")
    return "\n".join(formatted)


def _participating_parties(state: NegotiationState) -> list[str]:
    """Return the parties this debate is for, with a two-party default for
    callers that haven't migrated to the dict-keyed state yet."""
    parties = state.get("parties")
    if parties:
        return list(parties)
    return ["democrat", "republican"]


def _position_for(state: NegotiationState, party: str) -> str | None:
    """Read a party's synthesized position. Prefers the new `positions` dict;
    falls back to the legacy `republican_position` / `democrat_position`
    fields when present."""
    positions = state.get("positions") or {}
    if party in positions:
        return positions[party]
    if party == "republican":
        return state.get("republican_position")
    if party == "democrat":
        return state.get("democrat_position")
    return None


def _legacy_vote_writeback(votes_by_party: dict[str, list[Vote]]) -> dict[str, list[Vote]]:
    """Mirror dict-keyed votes onto the legacy `republican_votes` /
    `democrat_votes` keys when those parties are present. Keeps the CLI and
    the M1–M5 test suite working without a wholesale rewrite."""
    out: dict[str, list[Vote]] = {}
    for legacy in _LEGACY_PARTIES:
        if legacy in votes_by_party:
            out[f"{legacy}_votes"] = list(votes_by_party[legacy])
    return out


# ============================================================================
# Party Deliberation Nodes
# ============================================================================

async def party_head_intro(state: PartyState, display_callback=None) -> dict[str, Any]:
    """Party head introduces the proposal and sets the agenda."""
    party = state["party_name"]
    head = get_party_head(party)
    model = get_model()

    prompt = PARTY_HEAD_INTRO_PROMPT.format(
        proposal_description=state["proposal"].description,
        party=party.capitalize()
    )

    system_prompt = head.get_system_prompt(state["proposal"].description)

    response = await model.ainvoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=prompt)
    ])

    message = AgentMessage(
        agent_id=head.id,
        agent_name=head.name,
        party=party,
        role=head.role,
        content=_content_text(response),
        phase="intro"
    )

    if display_callback:
        display_callback(message)

    return {
        "discussion": [message],
        "phase": "advisor_discussion"
    }


async def advisor_discussion(state: PartyState, display_callback=None) -> dict[str, Any]:
    """Each advisor analyzes the proposal from their expertise."""
    party = state["party_name"]
    advisors = get_advisors(party)
    model = get_model()

    # Get leader's intro
    leader_intro = ""
    for msg in state["discussion"]:
        if msg.phase == "intro":
            leader_intro = msg.content
            break

    new_messages = []

    for advisor in advisors:
        prompt = ADVISOR_ANALYSIS_PROMPT.format(
            proposal_description=state["proposal"].description,
            leader_intro=leader_intro,
            previous_discussion=format_discussion(state["discussion"]),
            agent_name=advisor.name,
            agent_title=advisor.title,
            specialty=advisor.specialty
        )

        system_prompt = advisor.get_system_prompt(state["proposal"].description)

        response = await model.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=prompt)
        ])

        message = AgentMessage(
            agent_id=advisor.id,
            agent_name=advisor.name,
            party=party,
            role=advisor.role,
            content=_content_text(response),
            phase="advisor_discussion"
        )

        new_messages.append(message)

        if display_callback:
            display_callback(message)

    return {
        "discussion": new_messages,
        "phase": "assistant_research"
    }


async def assistant_research(state: PartyState, display_callback=None) -> dict[str, Any]:
    """Assistants provide supporting research and data."""
    party = state["party_name"]
    assistants = get_assistants(party)
    model = get_model()

    new_messages = []

    for assistant in assistants:
        prompt = ASSISTANT_RESEARCH_PROMPT.format(
            proposal_description=state["proposal"].description,
            discussion=format_discussion(state["discussion"]),
            agent_name=assistant.name,
            agent_title=assistant.title,
            specialty=assistant.specialty
        )

        system_prompt = assistant.get_system_prompt(state["proposal"].description)

        response = await model.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=prompt)
        ])

        message = AgentMessage(
            agent_id=assistant.id,
            agent_name=assistant.name,
            party=party,
            role=assistant.role,
            content=_content_text(response),
            phase="assistant_research"
        )

        new_messages.append(message)

        if display_callback:
            display_callback(message)

    return {
        "discussion": new_messages,
        "phase": "synthesis"
    }


async def form_party_position(state: PartyState, display_callback=None) -> dict[str, Any]:
    """Party head synthesizes discussion into official party position."""
    party = state["party_name"]
    head = get_party_head(party)
    model = get_model()

    prompt = SYNTHESIS_PROMPT.format(
        party=party.capitalize(),
        proposal_description=state["proposal"].description,
        full_discussion=format_discussion(state["discussion"])
    )

    system_prompt = head.get_system_prompt(state["proposal"].description)

    response = await model.ainvoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=prompt)
    ])

    message = AgentMessage(
        agent_id=head.id,
        agent_name=head.name,
        party=party,
        role=head.role,
        content=_content_text(response),
        phase="synthesis"
    )

    if display_callback:
        display_callback(message)

    return {
        "discussion": [message],
        "party_position": _content_text(response),
        "phase": "voting"
    }


# ============================================================================
# Cross-Party Debate Nodes
# ============================================================================

async def cross_party_debate(state: NegotiationState, display_callback=None) -> dict[str, Any]:
    """Conduct cross-party debate across all participating parties.

    Each round, every party head delivers a turn (opening prompt on round 0,
    rebuttal on subsequent rounds). Then up to two advisors per party rebut
    in round-robin order. Earlier R2-A versions of this node hardcoded a
    Republican-then-Democrat sequence; R2-C reads the participating parties
    from the state so any 2+ caucuses can debate.
    """
    model = get_model()

    parties = _participating_parties(state)
    current_round = state["negotiation_round"]
    is_opening_round = current_round == 0

    debate_messages: list[AgentMessage] = []

    # --- Head turns (one per party, in seating order) -----------------------
    for party in parties:
        head = get_party_head(party)
        own_position = _position_for(state, party) or "Not yet formed"

        if is_opening_round:
            opposing_positions = []
            for other in parties:
                if other == party:
                    continue
                pos = _position_for(state, other) or "Not yet formed"
                opposing_positions.append(f"{other.capitalize()}: {pos}")
            opposing_summary = "\n".join(opposing_positions) if opposing_positions else "Not yet formed"
            head_prompt = DEBATE_OPENING_PROMPT.format(
                proposal_description=state["proposal"].description,
                own_position=own_position,
                opposing_position=opposing_summary,
                round_number=current_round + 1,
                max_rounds=state["max_rounds"],
                agent_name=head.name,
            )
        else:
            debate_so_far = format_discussion(
                list(state.get("debate_transcript", [])) + debate_messages
            )
            head_prompt = DEBATE_REBUTTAL_PROMPT.format(
                proposal_description=state["proposal"].description,
                debate_transcript=debate_so_far,
                agent_name=head.name,
            )

        response = await model.ainvoke([
            SystemMessage(content=head.get_system_prompt(
                state["proposal"].description, _position_for(state, party)
            )),
            HumanMessage(content=head_prompt),
        ])
        msg = AgentMessage(
            agent_id=head.id,
            agent_name=head.name,
            party=party,
            role=head.role,
            content=_content_text(response),
            phase="cross_party_debate",
        )
        debate_messages.append(msg)
        if display_callback:
            display_callback(msg)

    # --- Advisor rebuttals (up to 2 per party, interleaved across parties) --
    advisor_pool = {p: get_advisors(p)[:2] for p in parties}
    max_advisors = max((len(v) for v in advisor_pool.values()), default=0)

    for index in range(max_advisors):
        for party in parties:
            advisors = advisor_pool[party]
            if index >= len(advisors):
                continue
            advisor = advisors[index]
            debate_so_far = format_discussion(
                list(state.get("debate_transcript", [])) + debate_messages
            )
            rebuttal_prompt = DEBATE_REBUTTAL_PROMPT.format(
                proposal_description=state["proposal"].description,
                debate_transcript=debate_so_far,
                agent_name=advisor.name,
            )
            response = await model.ainvoke([
                SystemMessage(content=advisor.get_system_prompt(
                    state["proposal"].description, _position_for(state, party)
                )),
                HumanMessage(content=rebuttal_prompt),
            ])
            msg = AgentMessage(
                agent_id=advisor.id,
                agent_name=advisor.name,
                party=party,
                role=advisor.role,
                content=_content_text(response),
                phase="cross_party_debate",
            )
            debate_messages.append(msg)
            if display_callback:
                display_callback(msg)

    return {
        "debate_transcript": debate_messages,
        "negotiation_round": state["negotiation_round"] + 1,
    }


# ============================================================================
# Markup Nodes (amendment lifecycle)
# ============================================================================

def select_top_amendment(
    amendments: list[str], sponsors: dict[str, list[str]]
) -> str | None:
    """Pick the amendment to mark up: most sponsors wins, first-seen breaks
    ties (Python's sort is stable, so equal counts keep list order)."""
    if not amendments:
        return None
    return sorted(amendments, key=lambda a: -len(sponsors.get(a, [])))[0]


async def markup(state: NegotiationState, display_callback=None) -> dict[str, Any]:
    """Incorporate the top-sponsored amendment into the proposal text.

    Runs only when the final vote FAILED, amendments were tabled, and markup
    rounds remain (see `after_final_vote_decision` in main_graph). Bumps
    `Proposal.current_version` so resolution can report "amended" when the
    revised text later passes.
    """
    from dataclasses import replace

    proposal = state["proposal"]
    already_applied = set(state.get("applied_amendments") or [])
    # Never re-incorporate an amendment from an earlier markup cycle — pick
    # the top-sponsored one that hasn't been folded into the text yet.
    candidates = [
        a for a in (state.get("amendments_proposed") or []) if a not in already_applied
    ]
    chosen = select_top_amendment(candidates, state.get("amendment_sponsors") or {})
    if chosen is None:
        # Defensive: the decision edge shouldn't route here without amendments.
        return {"markup_rounds_done": state.get("markup_rounds_done", 0) + 1}

    model = get_model()
    response = await model.ainvoke([
        HumanMessage(content=AMENDMENT_MARKUP_PROMPT.format(
            proposal_description=proposal.description,
            amendment_text=chosen,
        )),
    ])
    revised_text = _content_text(response).strip()

    if not revised_text or revised_text == proposal.description:
        # The clerk produced no actual change — burn the round honestly
        # instead of fabricating a new version that is byte-identical.
        log.warning("markup produced no textual change; skipping version bump")
        message = AgentMessage(
            agent_id="system",
            agent_name="Chamber Clerk",
            party="neutral",
            role="system",
            content=(
                "Markup attempted but the revised text was unchanged; the "
                "motion returns to the floor as written."
            ),
            phase="markup",
        )
        if display_callback:
            display_callback(message)
        return {
            "markup_rounds_done": state.get("markup_rounds_done", 0) + 1,
            "messages": [message],
            "phase": "markup",
        }

    amended_proposal = replace(
        proposal,
        description=revised_text,
        amendments=list(proposal.amendments) + [chosen],
        current_version=proposal.current_version + 1,
        status="debating",
    )
    applied = list(state.get("applied_amendments") or []) + [chosen]

    message = AgentMessage(
        agent_id="system",
        agent_name="Chamber Clerk",
        party="neutral",
        role="system",
        content=(
            f"The motion failed and returns for markup. Incorporating the "
            f"amendment with the most sponsors:\n\n“{chosen}”\n\n"
            f"Revised proposal (v{amended_proposal.current_version}):\n{revised_text}"
        ),
        phase="markup",
    )
    if display_callback:
        display_callback(message)

    return {
        "proposal": amended_proposal,
        "applied_amendments": applied,
        "markup_rounds_done": state.get("markup_rounds_done", 0) + 1,
        "messages": [message],
        "phase": "markup",
    }


async def markup_debate(state: NegotiationState, display_callback=None) -> dict[str, Any]:
    """Abbreviated floor debate on the amended text — party heads only, one
    exchange each, before the chamber re-votes."""
    model = get_model()
    parties = _participating_parties(state)

    applied = state.get("applied_amendments") or []
    amendment_note = (
        (
            "NOTE: The motion FAILED its first vote and has been amended in "
            f"markup. Amendment incorporated:\n“{applied[-1]}”\n\n"
            "Speak to the motion AS AMENDED — does the incorporated amendment "
            "change your caucus's position?\n\n"
        )
        if applied
        else ""
    )

    debate_messages: list[AgentMessage] = []
    for party in parties:
        head = get_party_head(party)
        debate_so_far = format_discussion(
            list(state.get("debate_transcript", [])) + debate_messages
        )
        prompt = amendment_note + DEBATE_REBUTTAL_PROMPT.format(
            proposal_description=state["proposal"].description,
            debate_transcript=debate_so_far,
            agent_name=head.name,
        )
        response = await model.ainvoke([
            SystemMessage(content=head.get_system_prompt(
                state["proposal"].description, _position_for(state, party)
            )),
            HumanMessage(content=prompt),
        ])
        msg = AgentMessage(
            agent_id=head.id,
            agent_name=head.name,
            party=party,
            role=head.role,
            content=_content_text(response),
            phase="markup_debate",
        )
        debate_messages.append(msg)
        if display_callback:
            display_callback(msg)

    return {
        "debate_transcript": debate_messages,
        "phase": "markup_debate",
    }


# ============================================================================
# Voting Nodes
# ============================================================================

async def initial_voting(state: NegotiationState, display_callback=None) -> dict[str, Any]:
    """Agents cast a tentative vote based ONLY on their party's synthesized position,
    before the cross-party debate. Pairs with the final `conduct_voting` to expose
    the persuasion mechanic — agents whose minds change between these two passes
    populate the Persuasion Timeline on the Results page.

    Kept lighter than `conduct_voting`: shorter prompt, no amendment proposals, and
    agents within a party are dispatched in parallel via `asyncio.gather` so the
    extra LLM pass adds ~30–60 s rather than minutes."""
    import asyncio
    parties = _participating_parties(state)

    votes_by_party: dict[str, list[Vote]] = {}

    for party in parties:
        agents = get_agents_by_party(party)
        party_position = _position_for(state, party) or ""

        async def cast_initial(agent: Agent, p: str = party, position: str = party_position) -> Vote:
            initial_prompt = (
                f"PROPOSAL UNDER CONSIDERATION:\n{state['proposal'].description}\n\n"
                f"YOUR PARTY'S SYNTHESIZED POSITION:\n{position}\n\n"
                "Before the cross-party debate begins, give your INITIAL vote based on your "
                "convictions and your party's stated position alone. You have not yet heard "
                "the opposing party's argument. No amendments at this stage.\n\n"
                "Reply in this EXACT format on two lines and nothing else:\n"
                "VOTE: SUPPORT (or OPPOSE or ABSTAIN)\n"
                "REASONING: One sentence stating your initial stance.\n"
            )
            return await cast_ballot(
                agent,
                p,
                agent.get_system_prompt(state["proposal"].description, position),
                initial_prompt,
            )

        cast_votes = await asyncio.gather(*(cast_initial(a) for a in agents))
        votes_by_party[party] = list(cast_votes)
        # Emit in stable order so the SSE feed mirrors the seating order.
        if display_callback:
            for vote in cast_votes:
                display_callback(vote)

    return {
        "votes_by_party": votes_by_party,
        **_legacy_vote_writeback(votes_by_party),
        "phase": "cross_party_debate",
    }


async def conduct_voting(state: NegotiationState, display_callback=None) -> dict[str, Any]:
    """All agents cast their votes."""
    parties = _participating_parties(state)

    # Prepare debate summary
    debate_summary = format_discussion(state.get("debate_transcript", []))

    votes_by_party: dict[str, list[Vote]] = {}

    for party in parties:
        agents = get_agents_by_party(party)
        party_position = _position_for(state, party) or ""
        party_votes: list[Vote] = []

        for agent in agents:
            voting_prompt = agent.get_voting_prompt(
                state["proposal"].description,
                f"Party Position:\n{party_position}\n\nDebate:\n{debate_summary}"
            )

            vote = await cast_ballot(
                agent,
                party,
                agent.get_system_prompt(state["proposal"].description, party_position),
                voting_prompt,
            )
            party_votes.append(vote)

            if display_callback:
                display_callback(vote)

        votes_by_party[party] = party_votes

    # Aggregate unique amendments across all voters, preserving first-seen
    # order, and record which agents sponsored each one. Seeded from the
    # existing state so a markup re-vote ACCUMULATES onto the round-1 docket
    # instead of erasing it (amendments and their sponsors are part of the
    # permanent record even when the re-vote doesn't re-table them).
    aggregated_amendments: list[str] = list(state.get("amendments_proposed") or [])
    amendment_sponsors: dict[str, list[str]] = {
        text: list(ids) for text, ids in (state.get("amendment_sponsors") or {}).items()
    }
    seen: set[str] = set(aggregated_amendments)
    for party in parties:
        for vote in votes_by_party.get(party, []):
            for amendment in vote.amendments:
                normalized = amendment.strip()
                if not normalized:
                    continue
                if normalized not in seen:
                    seen.add(normalized)
                    aggregated_amendments.append(normalized)
                sponsors_for = amendment_sponsors.setdefault(normalized, [])
                if vote.agent_id not in sponsors_for:
                    sponsors_for.append(vote.agent_id)

    return {
        "votes_by_party": votes_by_party,
        **_legacy_vote_writeback(votes_by_party),
        "amendments_proposed": aggregated_amendments,
        "amendment_sponsors": amendment_sponsors,
        "phase": "resolution",
    }


async def cast_ballot(
    agent: Agent,
    party: str,
    system_prompt: str,
    human_prompt: str,
) -> Vote:
    """Cast one agent's vote, preferring structured output over text parsing.

    Resolution order:
    1. `with_structured_output(VoteBallot)` — tool-forced schema, one retry
       on OUTPUT problems (schema/validation garbage) only.
    2. Plain completion + legacy `parse_vote` (also the path taken by test
       stubs that don't implement `with_structured_output`).

    Infrastructure errors (API down, key revoked, network) propagate so the
    debate ends in status='error' instead of a fabricated all-abstain tally.
    """
    model = get_model()
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=human_prompt),
    ]

    structured_factory = getattr(model, "with_structured_output", None)
    if structured_factory is not None:
        for attempt in range(2):
            try:
                ballot = await structured_factory(VoteBallot).ainvoke(messages)
            except (OutputParserException, ValidationError) as e:
                # The model answered but not in schema — retry, then fall
                # back to text parsing. Anything else (API/auth/network)
                # propagates to the runner's error handler.
                log.warning(
                    "structured ballot failed for %s (attempt %d): %s",
                    agent.id, attempt + 1, e,
                )
                continue
            if isinstance(ballot, VoteBallot):
                amendments = [a.strip() for a in ballot.amendments if a.strip()]
                return Vote(
                    agent_id=agent.id,
                    agent_name=agent.name,
                    agent_role=agent.role,
                    party=party,
                    vote=ballot.vote,
                    reasoning=ballot.reasoning.strip()[:500]
                    or f"Voted {ballot.vote} based on party principles",
                    amendments=amendments,
                )

    response = await model.ainvoke(messages)
    return parse_vote(_content_text(response), agent, party)


def parse_vote(response: str, agent: Agent, party: str) -> Vote:
    """Parse vote from agent response."""
    content = response.upper()

    vote_value: Literal["support", "oppose", "abstain"]
    if "VOTE: SUPPORT" in content or "VOTE:SUPPORT" in content:
        vote_value = "support"
    elif "VOTE: OPPOSE" in content or "VOTE:OPPOSE" in content:
        vote_value = "oppose"
    else:
        vote_value = "abstain"

    reasoning = ""
    if "REASONING:" in response:
        parts = response.split("REASONING:", 1)
        if len(parts) > 1:
            reasoning_part = parts[1]
            if "AMENDMENTS:" in reasoning_part:
                reasoning = reasoning_part.split("AMENDMENTS:")[0].strip()
            else:
                reasoning = reasoning_part.strip()

    amendments = []
    if "AMENDMENTS:" in response:
        parts = response.split("AMENDMENTS:", 1)
        if len(parts) > 1:
            amendments_text = parts[1].strip()
            if amendments_text.lower() != "none" and amendments_text:
                amendments = [amendments_text]

    return Vote(
        agent_id=agent.id,
        agent_name=agent.name,
        agent_role=agent.role,
        party=party,
        vote=vote_value,
        reasoning=reasoning[:500] if reasoning else f"Voted {vote_value} based on party principles",
        amendments=amendments,
    )
