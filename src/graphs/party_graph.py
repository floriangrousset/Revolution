"""Party deliberation subgraph."""
from typing import Callable, Optional
from langgraph.graph import StateGraph, START, END

from ..state.types import PartyState
from .nodes import (
    party_head_intro,
    advisor_discussion,
    assistant_research,
    form_party_position,
)


def build_party_graph(display_callback: Optional[Callable] = None):
    """Build the party deliberation subgraph.

    Flow:
    1. Party head introduces the proposal
    2. Advisors analyze from their expertise
    3. Assistants provide research and data
    4. Party head synthesizes into unified position

    Args:
        display_callback: Optional callback for displaying agent messages

    Returns:
        Compiled LangGraph for party deliberation
    """

    # Create node wrappers that include the callback
    async def intro_node(state: PartyState):
        return await party_head_intro(state, display_callback)

    async def advisor_node(state: PartyState):
        return await advisor_discussion(state, display_callback)

    async def assistant_node(state: PartyState):
        return await assistant_research(state, display_callback)

    async def synthesis_node(state: PartyState):
        return await form_party_position(state, display_callback)

    # Build the graph
    builder = StateGraph(PartyState)

    # Add nodes
    builder.add_node("party_head_intro", intro_node)
    builder.add_node("advisor_discussion", advisor_node)
    builder.add_node("assistant_research", assistant_node)
    builder.add_node("form_position", synthesis_node)

    # Define flow
    builder.add_edge(START, "party_head_intro")
    builder.add_edge("party_head_intro", "advisor_discussion")
    builder.add_edge("advisor_discussion", "assistant_research")
    builder.add_edge("assistant_research", "form_position")
    builder.add_edge("form_position", END)

    return builder.compile()


async def run_party_deliberation(
    party: str,
    proposal,
    display_callback: Optional[Callable] = None
) -> dict:
    """Run party deliberation and return the result.

    Args:
        party: 'republican' or 'democrat'
        proposal: The Proposal being deliberated
        display_callback: Optional callback for displaying messages

    Returns:
        Dict with party_position and discussion
    """
    graph = build_party_graph(display_callback)

    initial_state = PartyState(
        party_name=party,
        proposal=proposal,
        discussion=[],
        party_position=None,
        member_votes=[],
        current_speaker_index=0,
        phase="intro"
    )

    result = await graph.ainvoke(initial_state)
    return result
