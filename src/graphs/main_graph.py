"""Main orchestration graph for the negotiation system."""
from typing import Callable, Optional, Literal
from langgraph.graph import StateGraph, START, END

from ..state.types import NegotiationState, Proposal, AgentMessage, Vote
from .party_graph import run_party_deliberation
from .nodes import cross_party_debate, conduct_voting, initial_voting, markup, markup_debate
from ..voting.consensus import VotingResult, VotingRules, determine_final_result


def _compute_result(state: NegotiationState) -> VotingResult:
    """Tally the current votes under this debate's rules and weights.

    Shared by the post-vote routing decision and the resolution node so both
    apply identical passage rules — a divergence here would let a bill route
    to markup and then "pass" in resolution (or vice versa).
    """
    votes_by_party: dict[str, list[Vote]] = dict(state.get("votes_by_party") or {})
    # Back-fill from the legacy per-party fields if the dict is sparse.
    if not votes_by_party.get("republican") and state.get("republican_votes"):
        votes_by_party["republican"] = list(state["republican_votes"])
    if not votes_by_party.get("democrat") and state.get("democrat_votes"):
        votes_by_party["democrat"] = list(state["democrat_votes"])

    rules = VotingRules(rule=state.get("passage_rule") or "majority")
    return determine_final_result(
        votes_by_party,
        rules=rules,
        seat_weights=state.get("seat_config") or None,
    )

# Default participating parties for the CLI and any test caller that hasn't
# migrated to passing `parties=...` explicitly.
DEFAULT_PARTIES: list[str] = ["democrat", "republican"]


def build_main_graph(
    display_callback: Optional[Callable] = None,
    parties: Optional[list[str]] = None,
):
    """Build the main negotiation orchestration graph.

    Flow:
    1. Receive proposal
    2. One deliberation subgraph per participating party (in seating order)
    3. Initial vote (drives the persuasion timeline)
    4. Cross-party debate (loops while rounds remain)
    5. Final voting
    6. Resolution

    Args:
        display_callback: Optional callback for displaying messages.
        parties: Optional explicit list of party ids participating in the
            debate, in seating order (left → right). Defaults to
            ["democrat", "republican"] for back-compat.

    Returns:
        Compiled LangGraph for main negotiation.
    """
    party_ids = list(parties) if parties else list(DEFAULT_PARTIES)

    async def receive_proposal(state: NegotiationState) -> dict:
        """Initialize the negotiation with the proposal."""
        if display_callback:
            display_callback(AgentMessage(
                agent_id="system",
                agent_name="System",
                party="neutral",
                role="system",
                content=f"Proposal received: {state['proposal'].description}",
                phase="proposal_submission"
            ))
        # Surface the participating-parties list on the state so downstream
        # nodes can read it without us threading it through every call.
        return {"phase": "deliberation", "parties": party_ids}

    def make_deliberation_node(party_id: str):
        """Build a deliberation node bound to a specific party."""

        async def deliberation_node(state: NegotiationState) -> dict:
            if display_callback:
                display_callback(AgentMessage(
                    agent_id="system",
                    agent_name="System",
                    party=party_id,
                    role="system",
                    content=f"Beginning {party_id.capitalize()} Party deliberation...",
                    phase=f"{party_id}_deliberation",
                ))

            result = await run_party_deliberation(
                party=party_id,
                proposal=state["proposal"],
                display_callback=display_callback,
            )

            # Write to both the dict-keyed `positions` field and the legacy
            # per-party fields so back-compat consumers keep working.
            position = result.get("party_position")
            update: dict = {
                "positions": {party_id: position},
                "messages": result.get("discussion", []),
            }
            if party_id == "republican":
                update["republican_position"] = position
            elif party_id == "democrat":
                update["democrat_position"] = position
            return update

        return deliberation_node

    async def initial_voting_node(state: NegotiationState) -> dict:
        """Tentative pre-debate vote — feeds the persuasion timeline."""
        if display_callback:
            display_callback(AgentMessage(
                agent_id="system",
                agent_name="System",
                party="neutral",
                role="system",
                content="Calling tentative roll before cross-party debate...",
                phase="initial_voting",
            ))

        return await initial_voting(state, display_callback)

    async def debate_node(state: NegotiationState) -> dict:
        """Conduct cross-party debate."""
        if display_callback:
            display_callback(AgentMessage(
                agent_id="system",
                agent_name="System",
                party="neutral",
                role="system",
                content=f"Beginning Cross-Party Debate (Round {state['negotiation_round'] + 1}/{state['max_rounds']})...",
                phase="cross_party_debate",
            ))

        return await cross_party_debate(state, display_callback)

    async def voting_node(state: NegotiationState) -> dict:
        """Conduct final voting."""
        if display_callback:
            display_callback(AgentMessage(
                agent_id="system",
                agent_name="System",
                party="neutral",
                role="system",
                content="Beginning Final Voting...",
                phase="final_voting",
            ))

        return await conduct_voting(state, display_callback)

    async def resolution_node(state: NegotiationState) -> dict:
        """Calculate and announce final result."""
        result = _compute_result(state)
        if result.passed:
            # A bill that passed after at least one markup cycle passed "as
            # amended" — surface that as its own outcome.
            amended = state["proposal"].current_version > 1
            final_result = "amended" if amended else "passed"
        else:
            final_result = "rejected"

        if display_callback:
            rule_note = "" if result.rule == "majority" else f" [{result.rule}, {result.required} needed]"
            display_callback(AgentMessage(
                agent_id="system",
                agent_name="System",
                party="neutral",
                role="system",
                content=f"FINAL RESULT: {final_result.upper()} ({result.margin}){rule_note}",
                phase="resolution"
            ))

        return {
            "final_result": final_result,
            "voting_result": result,
            "phase": "resolution"
        }

    async def markup_node(state: NegotiationState) -> dict:
        """Apply the top amendment to the failed proposal."""
        return await markup(state, display_callback)

    async def markup_debate_node(state: NegotiationState) -> dict:
        """Heads-only exchange on the amended text before the re-vote."""
        if display_callback:
            display_callback(AgentMessage(
                agent_id="system",
                agent_name="System",
                party="neutral",
                role="system",
                content="Debating the motion as amended (party heads only)...",
                phase="markup_debate",
            ))
        return await markup_debate(state, display_callback)

    def after_final_vote_decision(state: NegotiationState) -> Literal["resolve", "markup"]:
        """After the final vote: run a markup cycle iff the vote FAILED,
        amendments were tabled, and markup rounds remain. A bill that passed
        never gets marked up — markup here is rescue, not embellishment."""
        if state.get("markup_rounds_done", 0) >= state.get("max_markup_rounds", 0):
            return "resolve"
        if not state.get("amendments_proposed"):
            return "resolve"
        if _compute_result(state).passed:
            return "resolve"
        return "markup"

    def after_debate_decision(state: NegotiationState) -> Literal["continue", "vote"]:
        """After a debate round, continue if rounds remain, otherwise vote."""
        current_round = state.get("negotiation_round", 0)
        max_rounds = state.get("max_rounds", 1)
        if current_round >= max_rounds:
            return "vote"
        return "continue"

    # Build the graph
    builder = StateGraph(NegotiationState)

    # Add nodes
    builder.add_node("receive_proposal", receive_proposal)
    deliberation_node_names: list[str] = []
    for party_id in party_ids:
        node_name = f"{party_id}_deliberation"
        builder.add_node(node_name, make_deliberation_node(party_id))
        deliberation_node_names.append(node_name)
    builder.add_node("initial_voting", initial_voting_node)
    builder.add_node("cross_party_debate", debate_node)
    builder.add_node("final_voting", voting_node)
    builder.add_node("markup", markup_node)
    builder.add_node("markup_debate", markup_debate_node)
    builder.add_node("resolution", resolution_node)

    # Define flow: receive → deliberation1 → deliberation2 → … → initial_voting
    builder.add_edge(START, "receive_proposal")
    prev_node = "receive_proposal"
    for node_name in deliberation_node_names:
        builder.add_edge(prev_node, node_name)
        prev_node = node_name
    builder.add_edge(prev_node, "initial_voting")
    builder.add_edge("initial_voting", "cross_party_debate")

    # After debate, either continue or vote
    builder.add_conditional_edges(
        "cross_party_debate",
        after_debate_decision,
        {
            "continue": "cross_party_debate",
            "vote": "final_voting"
        }
    )

    # After the final vote: resolve, or (failed + amendments + rounds left)
    # run one bounded markup cycle and re-vote.
    builder.add_conditional_edges(
        "final_voting",
        after_final_vote_decision,
        {
            "resolve": "resolution",
            "markup": "markup",
        }
    )
    builder.add_edge("markup", "markup_debate")
    builder.add_edge("markup_debate", "final_voting")
    builder.add_edge("resolution", END)

    return builder.compile()


async def run_negotiation(
    proposal_text: str,
    max_rounds: int = 5,
    display_callback: Optional[Callable] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    parties: Optional[list[str]] = None,
    passage_rule: Optional[str] = None,
    seat_config: Optional[dict[str, int]] = None,
    markup_rounds: int = 0,
) -> NegotiationState:
    """Run a full negotiation on a proposal.

    Args:
        proposal_text: The proposal text from the user
        max_rounds: Maximum negotiation rounds
        display_callback: Optional callback for displaying messages
        model: Optional Claude model id to override the env default.
        temperature: Optional temperature in [0, 1] to override the engine default.
        parties: Optional explicit party-id list, in seating order. Defaults to
            ["democrat", "republican"] for back-compat with the CLI and tests.
        passage_rule: "majority" (default), "three_fifths", or "two_thirds".
            Falls back to the settings-store default when omitted.
        seat_config: Optional party id → seat count map for seat-weighted
            voting. Omitted/empty = one agent, one vote (unweighted).
        markup_rounds: How many markup cycles a FAILED vote may trigger
            (top-sponsored amendment incorporated, heads-only debate,
            re-vote). 0 = record amendments but never apply them.

    Returns:
        Final NegotiationState with results
    """
    from .nodes import set_model_overrides
    from ..config import get_default_passage_rule
    set_model_overrides(model=model, temperature=temperature)

    party_ids = list(parties) if parties else list(DEFAULT_PARTIES)
    graph = build_main_graph(display_callback, parties=party_ids)

    proposal = Proposal.from_user_input(proposal_text)

    initial_state: NegotiationState = {
        "proposal": proposal,
        "messages": [],
        "debate_transcript": [],
        "parties": party_ids,
        "positions": {},
        "votes_by_party": {},
        "republican_position": None,
        "democrat_position": None,
        "republican_votes": [],
        "democrat_votes": [],
        "negotiation_round": 0,
        "max_rounds": max_rounds,
        "phase": "proposal_submission",
        "passage_rule": passage_rule or get_default_passage_rule(),
        "seat_config": dict(seat_config) if seat_config else {},
        "voting_result": None,
        "final_result": None,
        "amendments_proposed": [],
        "amendment_sponsors": {},
        "max_markup_rounds": max(0, markup_rounds),
        "markup_rounds_done": 0,
        "applied_amendments": [],
    }

    result = await graph.ainvoke(initial_state)
    return result
