"""Main orchestration graph for the negotiation system."""
import asyncio
from typing import Callable, Optional, Literal
from langgraph.graph import StateGraph, START, END

from ..state.types import NegotiationState, Proposal, AgentMessage
from .party_graph import run_party_deliberation
from .nodes import cross_party_debate, conduct_voting
from ..voting.consensus import determine_final_result


def build_main_graph(display_callback: Optional[Callable] = None):
    """Build the main negotiation orchestration graph.

    Flow:
    1. Receive proposal
    2. Republican deliberation (subgraph)
    3. Democrat deliberation (subgraph)
    4. Cross-party debate
    5. Check if more rounds needed
    6. Final voting
    7. Announce result

    Args:
        display_callback: Optional callback for displaying messages

    Returns:
        Compiled LangGraph for main negotiation
    """

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
        return {"phase": "republican_deliberation"}

    async def republican_deliberation(state: NegotiationState) -> dict:
        """Run Republican party deliberation."""
        if display_callback:
            display_callback(AgentMessage(
                agent_id="system",
                agent_name="System",
                party="republican",
                role="system",
                content="Beginning Republican Party deliberation...",
                phase="republican_deliberation"
            ))

        result = await run_party_deliberation(
            party="republican",
            proposal=state["proposal"],
            display_callback=display_callback
        )

        return {
            "republican_position": result.get("party_position"),
            "messages": result.get("discussion", []),
            "phase": "democrat_deliberation"
        }

    async def democrat_deliberation(state: NegotiationState) -> dict:
        """Run Democrat party deliberation."""
        if display_callback:
            display_callback(AgentMessage(
                agent_id="system",
                agent_name="System",
                party="democrat",
                role="system",
                content="Beginning Democrat Party deliberation...",
                phase="democrat_deliberation"
            ))

        result = await run_party_deliberation(
            party="democrat",
            proposal=state["proposal"],
            display_callback=display_callback
        )

        return {
            "democrat_position": result.get("party_position"),
            "messages": result.get("discussion", []),
            "phase": "cross_party_debate"
        }

    async def debate_node(state: NegotiationState) -> dict:
        """Conduct cross-party debate."""
        if display_callback:
            display_callback(AgentMessage(
                agent_id="system",
                agent_name="System",
                party="neutral",
                role="system",
                content=f"Beginning Cross-Party Debate (Round {state['negotiation_round'] + 1}/{state['max_rounds']})...",
                phase="cross_party_debate"
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
                phase="final_voting"
            ))

        return await conduct_voting(state, display_callback)

    async def resolution_node(state: NegotiationState) -> dict:
        """Calculate and announce final result."""
        result = determine_final_result(
            state.get("republican_votes", []),
            state.get("democrat_votes", [])
        )

        final_result = "passed" if result.passed else "rejected"

        if display_callback:
            display_callback(AgentMessage(
                agent_id="system",
                agent_name="System",
                party="neutral",
                role="system",
                content=f"FINAL RESULT: {final_result.upper()} ({result.margin})",
                phase="resolution"
            ))

        return {
            "final_result": final_result,
            "phase": "resolution"
        }

    def should_continue_debate(state: NegotiationState) -> Literal["debate", "vote"]:
        """Determine if debate should continue or proceed to voting."""
        current_round = state.get("negotiation_round", 0)
        max_rounds = state.get("max_rounds", 5)

        if current_round >= max_rounds:
            return "vote"

        # Could add more sophisticated logic here to detect consensus
        return "debate"

    def after_debate_decision(state: NegotiationState) -> Literal["continue", "vote"]:
        """After debate, decide whether to continue or vote."""
        current_round = state.get("negotiation_round", 0)
        max_rounds = state.get("max_rounds", 5)

        # For simplicity, we do one debate round then vote
        # In a more complex system, we could check for consensus
        if current_round >= 1:  # After first debate round
            return "vote"
        return "continue"

    # Build the graph
    builder = StateGraph(NegotiationState)

    # Add nodes
    builder.add_node("receive_proposal", receive_proposal)
    builder.add_node("republican_deliberation", republican_deliberation)
    builder.add_node("democrat_deliberation", democrat_deliberation)
    builder.add_node("cross_party_debate", debate_node)
    builder.add_node("final_voting", voting_node)
    builder.add_node("resolution", resolution_node)

    # Define flow
    builder.add_edge(START, "receive_proposal")
    builder.add_edge("receive_proposal", "republican_deliberation")
    builder.add_edge("republican_deliberation", "democrat_deliberation")
    builder.add_edge("democrat_deliberation", "cross_party_debate")

    # After debate, either continue or vote
    builder.add_conditional_edges(
        "cross_party_debate",
        after_debate_decision,
        {
            "continue": "cross_party_debate",
            "vote": "final_voting"
        }
    )

    builder.add_edge("final_voting", "resolution")
    builder.add_edge("resolution", END)

    return builder.compile()


async def run_negotiation(
    proposal_text: str,
    max_rounds: int = 5,
    display_callback: Optional[Callable] = None
) -> NegotiationState:
    """Run a full negotiation on a proposal.

    Args:
        proposal_text: The proposal text from the user
        max_rounds: Maximum negotiation rounds
        display_callback: Optional callback for displaying messages

    Returns:
        Final NegotiationState with results
    """
    graph = build_main_graph(display_callback)

    proposal = Proposal.from_user_input(proposal_text)

    initial_state = NegotiationState(
        proposal=proposal,
        messages=[],
        debate_transcript=[],
        republican_position=None,
        democrat_position=None,
        republican_votes=[],
        democrat_votes=[],
        negotiation_round=0,
        max_rounds=max_rounds,
        phase="proposal_submission",
        final_result=None,
        amendments_proposed=[]
    )

    result = await graph.ainvoke(initial_state)
    return result
