"""Rich console display for the negotiation system."""
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.box import ROUNDED, DOUBLE
from typing import Union

from ..state.types import AgentMessage, Vote, Proposal
from ..voting.consensus import VotingResult


class NegotiationDisplay:
    """Handles all console output for the negotiation system."""

    def __init__(self, console: Console = None, verbose: bool = True):
        self.console = console or Console()
        self.verbose = verbose
        self.party_colors = {
            "republican": "red",
            "democrat": "blue",
            "neutral": "white"
        }
        self.role_styles = {
            "party_head": "bold",
            "advisor": "",
            "assistant": "dim",
            "system": "italic yellow"
        }
        self.current_phase = ""

    def show_header(self):
        """Display the system header."""
        header = Text()
        header.append("REVOLUTION", style="bold white")
        header.append("\n")
        header.append("Multi-Agent Political Negotiation System", style="dim")

        self.console.print(Panel(
            header,
            box=DOUBLE,
            border_style="bright_white",
            padding=(1, 2)
        ))
        self.console.print()

    def show_proposal(self, proposal: Proposal):
        """Display the proposal being debated."""
        self.console.print(Panel(
            f"[bold]{proposal.description}[/bold]",
            title="[yellow]Proposal Under Consideration[/yellow]",
            border_style="yellow",
            box=ROUNDED,
            padding=(1, 2)
        ))
        self.console.print()

    def show_phase(self, phase: str, party: str = "neutral"):
        """Display current negotiation phase."""
        if phase == self.current_phase:
            return

        self.current_phase = phase
        phase_display = phase.replace("_", " ").title()
        color = self.party_colors.get(party, "white")

        self.console.print()
        self.console.rule(f"[bold {color}]{phase_display}[/bold {color}]", style=color)
        self.console.print()

    def show_agent_message(self, message: AgentMessage):
        """Display an agent's message with party-colored formatting."""
        # Show phase header if changed
        if message.phase and message.phase != self.current_phase:
            party = message.party if message.party != "neutral" else "neutral"
            self.show_phase(message.phase, party)

        color = self.party_colors.get(message.party, "white")
        role_style = self.role_styles.get(message.role, "")

        if message.role == "system":
            self.console.print(f"[italic yellow]{message.content}[/italic yellow]")
            return

        # Create title with agent info
        title = f"[{color}][{message.agent_id}] {message.agent_name}[/{color}]"
        if message.role != "party_head":
            title += f" [dim]({message.role})[/dim]"

        # Format content
        content = message.content
        if role_style:
            content = f"[{role_style}]{content}[/{role_style}]"

        panel = Panel(
            content,
            title=title,
            border_style=color,
            box=ROUNDED,
            padding=(0, 1)
        )
        self.console.print(panel)
        self.console.print()

    def show_vote(self, vote: Vote):
        """Display a vote with visual indicator."""
        color = self.party_colors.get(vote.party, "white")
        vote_colors = {
            "support": "green",
            "oppose": "red",
            "abstain": "yellow"
        }
        vote_color = vote_colors.get(vote.vote, "white")
        vote_symbol = {
            "support": "YES",
            "oppose": "NO ",
            "abstain": "---"
        }[vote.vote]

        self.console.print(
            f"  [{color}]{vote.agent_name:30}[/{color}] "
            f"[{vote_color} bold]{vote_symbol}[/{vote_color} bold] "
            f"[dim]{vote.reasoning[:60]}...[/dim]" if len(vote.reasoning) > 60 else
            f"  [{color}]{vote.agent_name:30}[/{color}] "
            f"[{vote_color} bold]{vote_symbol}[/{vote_color} bold] "
            f"[dim]{vote.reasoning}[/dim]"
        )

    def show_voting_results(self, result: VotingResult):
        """Display voting results table."""
        self.console.print()

        table = Table(title="[bold]Voting Results[/bold]", box=ROUNDED)
        table.add_column("Party", style="cyan", justify="center")
        table.add_column("Support", style="green", justify="center")
        table.add_column("Oppose", style="red", justify="center")
        table.add_column("Abstain", style="yellow", justify="center")

        table.add_row(
            "[red]Republican[/red]",
            str(result.republican_support),
            str(result.republican_oppose),
            str(result.republican_abstain)
        )
        table.add_row(
            "[blue]Democrat[/blue]",
            str(result.democrat_support),
            str(result.democrat_oppose),
            str(result.democrat_abstain)
        )
        table.add_row(
            "[bold]TOTAL[/bold]",
            f"[bold]{result.total_support}[/bold]",
            f"[bold]{result.total_oppose}[/bold]",
            f"[bold]{result.total_abstain}[/bold]",
            style="bold"
        )

        self.console.print(table)
        self.console.print()

    def show_final_result(self, result: VotingResult):
        """Display final negotiation result."""
        if result.passed:
            status_style = "bold green"
            status_text = "PASSED"
            border_style = "green"
        else:
            status_style = "bold red"
            status_text = "REJECTED"
            border_style = "red"

        bipartisan_text = " (Bipartisan)" if result.bipartisan else ""

        content = Text()
        content.append(f"{status_text}{bipartisan_text}\n\n", style=status_style)
        content.append(f"Final Vote: {result.margin}", style="white")

        self.console.print()
        self.console.print(Panel(
            content,
            title="[bold]Final Result[/bold]",
            border_style=border_style,
            box=DOUBLE,
            padding=(1, 2)
        ))
        self.console.print()

    def display_callback(self, item: Union[AgentMessage, Vote]):
        """Callback function for displaying items during negotiation."""
        if isinstance(item, AgentMessage):
            self.show_agent_message(item)
        elif isinstance(item, Vote):
            self.show_vote(item)

    def show_party_votes(self, votes: list[Vote], party: str):
        """Display all votes for a party."""
        color = self.party_colors.get(party, "white")

        self.console.print(f"\n[{color} bold]{party.upper()} PARTY VOTES:[/{color} bold]")
        self.console.print("-" * 60)

        # Sort by role importance
        sorted_votes = sorted(
            votes,
            key=lambda v: (v.agent_role != "party_head", v.agent_role != "advisor", v.agent_id)
        )

        for vote in sorted_votes:
            self.show_vote(vote)

        self.console.print()
