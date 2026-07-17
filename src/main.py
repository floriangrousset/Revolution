"""Main entry point for the Revolution negotiation system."""
import asyncio
import os
import sys
from dotenv import load_dotenv
from rich.console import Console
from rich.prompt import Prompt

from .cli.display import NegotiationDisplay
from .graphs.main_graph import run_negotiation
from .voting.consensus import determine_final_result


def check_api_key() -> bool:
    """Check if the Anthropic API key is set."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key or api_key == "your-api-key-here":
        return False
    return True


async def run_interactive_session(display: NegotiationDisplay):
    """Run an interactive negotiation session."""
    console = display.console

    # Get proposal from user
    console.print()
    console.print("[bold cyan]Enter your proposal for negotiation:[/bold cyan]")
    console.print("[dim](Examples: 'Should we legalize marijuana?', 'Should we implement universal basic income?')[/dim]")
    console.print()

    proposal_text = Prompt.ask("[bold yellow]Your proposal[/bold yellow]")

    if not proposal_text.strip():
        console.print("[red]No proposal entered. Exiting.[/red]")
        return

    # Get max rounds
    max_rounds_input = Prompt.ask(
        "[bold yellow]Maximum negotiation rounds[/bold yellow]",
        default="1"
    )
    try:
        max_rounds = max(1, min(int(max_rounds_input), 5))  # Clamp between 1-5
    except ValueError:
        max_rounds = 1

    console.print()
    console.print(f"[dim]Starting negotiation with max {max_rounds} round(s)...[/dim]")
    console.print()

    # Run the negotiation
    try:
        result = await run_negotiation(
            proposal_text=proposal_text,
            max_rounds=max_rounds,
            display_callback=display.display_callback
        )

        # Show final voting breakdown
        votes_by_party = dict(result.get("votes_by_party") or {})
        # Back-fill from the legacy per-party fields for older shapes.
        if not votes_by_party.get("republican") and result.get("republican_votes"):
            votes_by_party["republican"] = result["republican_votes"]
        if not votes_by_party.get("democrat") and result.get("democrat_votes"):
            votes_by_party["democrat"] = result["democrat_votes"]

        # The resolution node already applied the debate's passage rule;
        # recompute only for older result shapes that lack it.
        voting_result = result.get("voting_result") or determine_final_result(votes_by_party)

        display.show_phase("Final Voting Results", "neutral")
        for party in result.get("parties") or list(votes_by_party.keys()):
            display.show_party_votes(votes_by_party.get(party, []), party)
        display.show_voting_results(voting_result)
        display.show_final_result(voting_result, final_status=result.get("final_result"))
        display.show_amendments(result.get("amendments_proposed", []))

    except Exception as e:
        console.print(f"[red bold]Error during negotiation: {e}[/red bold]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")


def main():
    """Main entry point."""
    # Load environment variables
    load_dotenv()

    console = Console()
    display = NegotiationDisplay(console=console)

    # Show header
    display.show_header()

    # Check API key
    if not check_api_key():
        console.print("[red bold]Error: ANTHROPIC_API_KEY not set![/red bold]")
        console.print()
        console.print("Please set your API key:")
        console.print("  1. Copy .env.example to .env")
        console.print("  2. Add your Anthropic API key to the .env file")
        console.print()
        console.print("Or set it directly:")
        console.print("  export ANTHROPIC_API_KEY=your-key-here")
        console.print()
        sys.exit(1)

    # Run the interactive session
    try:
        asyncio.run(run_interactive_session(display))
    except KeyboardInterrupt:
        console.print("\n[yellow]Negotiation interrupted by user.[/yellow]")
        sys.exit(0)


if __name__ == "__main__":
    main()
