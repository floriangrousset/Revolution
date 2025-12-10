"""Base Agent class for political negotiation."""
from dataclasses import dataclass, field
from typing import Literal, Optional


@dataclass
class Agent:
    """A political agent with a defined persona."""
    id: str
    name: str
    title: str
    party: Literal["republican", "democrat"]
    role: Literal["party_head", "advisor", "assistant"]
    specialty: str
    philosophy: str
    communication_style: str
    key_positions: list[str] = field(default_factory=list)

    def get_system_prompt(self, proposal_description: str, party_position: Optional[str] = None) -> str:
        """Generate the system prompt for this agent."""
        from .prompts import AGENT_SYSTEM_PROMPT

        positions_text = "\n".join(f"- {pos}" for pos in self.key_positions) if self.key_positions else "Not specified"

        return AGENT_SYSTEM_PROMPT.format(
            agent_name=self.name,
            agent_title=self.title,
            agent_id=self.id,
            party=self.party.capitalize(),
            role_description=self._get_role_description(),
            philosophy=self.philosophy,
            specialty=self.specialty,
            communication_style=self.communication_style,
            key_positions=positions_text,
            proposal_description=proposal_description,
            party_position=party_position or "Not yet formed - you are helping to shape it"
        )

    def _get_role_description(self) -> str:
        """Get role-specific description."""
        descriptions = {
            "party_head": (
                "You are the LEADER of your party. You set the strategic direction, "
                "coordinate discussions among your team, synthesize member opinions into a unified position, "
                "and represent the party in cross-party debates. Your word carries significant weight. "
                "You must listen to your advisors and assistants, but ultimately you shape the party's official stance."
            ),
            "advisor": (
                "You are a SENIOR ADVISOR with deep expertise in your specialty area. "
                "You provide detailed analysis and strategic recommendations to the party head. "
                "Your opinion matters greatly in shaping the party's position. "
                "Be thorough in your analysis and consider multiple angles."
            ),
            "assistant": (
                "You are a POLICY ASSISTANT who supports the advisors with research, data analysis, "
                "and detailed policy information. You provide factual grounding for the party's arguments "
                "and help identify potential issues or opportunities. Be concise and data-driven."
            )
        }
        return descriptions.get(self.role, "")

    def get_voting_prompt(self, proposal_description: str, debate_summary: str) -> str:
        """Generate the prompt for voting phase."""
        from .prompts import VOTING_PROMPT

        return VOTING_PROMPT.format(
            agent_name=self.name,
            proposal_description=proposal_description,
            debate_summary=debate_summary
        )

    def __repr__(self) -> str:
        return f"Agent({self.id}, {self.name}, {self.party})"
