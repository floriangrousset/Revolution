"""Base Agent class for political negotiation."""
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional, get_args


def _valid_roles() -> list[str]:
    """Live list of allowed roles (settings.json reference_lists.roles,
    falling back to the Literal type if the store hasn't been initialized yet)."""
    try:
        from src.config import get_reference_list
        return get_reference_list("roles")
    except Exception:
        return list(get_args(Role))


def _valid_postures() -> list[str]:
    """Live list of allowed negotiation postures."""
    try:
        from src.config import get_reference_list
        return get_reference_list("negotiation_postures")
    except Exception:
        return list(get_args(NegotiationPosture))

NegotiationPosture = Literal[
    "dealmaker",
    "hardliner",
    "pragmatist",
    "bomb_thrower",
    "institutionalist",
]

# Party is a registry-driven enum, not a closed literal. The engine ships with
# `republican` and `democrat` baked in, but the file-DB layer lets users register
# new parties (e.g. libertarian, green) at runtime. We validate "non-empty
# string" here; the parties registry is the canonical source of valid ids.
Party = str
Role = Literal["party_head", "advisor", "assistant"]

_AGENT_REGISTRY: dict[str, "Agent"] = {}


def register_agents(agents: list["Agent"]) -> None:
    """Register agents so allies/rivals can be resolved to names in prompts.

    Raises ValueError if any agent's id is already registered.
    """
    for agent in agents:
        if agent.id in _AGENT_REGISTRY:
            raise ValueError(
                f"Agent id {agent.id!r} is already registered "
                f"(existing: {_AGENT_REGISTRY[agent.id].name!r}, "
                f"new: {agent.name!r})"
            )
        _AGENT_REGISTRY[agent.id] = agent


def clear_registry() -> None:
    """Clear the agent registry. Intended for test isolation."""
    _AGENT_REGISTRY.clear()


def _resolve_id(agent_id: str) -> str:
    """Return 'Name (title)' for a registered ID, else the raw ID."""
    other = _AGENT_REGISTRY.get(agent_id)
    if other is None:
        return agent_id
    return f"{other.name} ({other.title})"


@dataclass
class Source:
    """A primary-source citation backing a persona's personality assessment."""
    title: str
    url: str
    date: str
    source_type: str
    description: str = ""


@dataclass
class Agent:
    """A political agent with a defined persona."""
    id: str
    name: str
    title: str
    party: Party
    role: Role
    specialty: str
    philosophy: str
    communication_style: str
    key_positions: list[str] = field(default_factory=list)
    red_lines: list[str] = field(default_factory=list)
    rhetorical_signatures: list[str] = field(default_factory=list)
    allies: list[str] = field(default_factory=list)
    rivals: list[str] = field(default_factory=list)
    negotiation_posture: NegotiationPosture = "pragmatist"
    constituency: str = ""
    personality_assessment: str = ""
    sources: list[Source] = field(default_factory=list)
    persona_last_updated: str = ""
    # Portrait: web path (e.g. "/portraits/<id>.jpg") or absolute URL.
    # Empty string = no portrait; the UI falls back to an initials avatar.
    image_url: str = ""
    image_attribution: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.party, str) or not self.party.strip():
            raise ValueError(f"Agent '{self.id}': invalid party {self.party!r}")
        valid_roles = _valid_roles()
        if self.role not in valid_roles:
            raise ValueError(
                f"Agent '{self.id}': invalid role {self.role!r}; "
                f"expected one of {valid_roles}"
            )
        valid_postures = _valid_postures()
        if self.negotiation_posture not in valid_postures:
            raise ValueError(
                f"Agent '{self.id}': invalid negotiation_posture {self.negotiation_posture!r}; "
                f"expected one of {valid_postures}"
            )
        if not isinstance(self.image_url, str) or not isinstance(self.image_attribution, str):
            raise ValueError(
                f"Agent '{self.id}': image_url and image_attribution must be strings"
            )
        url = self.image_url.strip()
        if url and not url.startswith(("/", "http://", "https://")):
            raise ValueError(
                f"Agent '{self.id}': image_url must be a web path (/...) or http(s) URL"
            )
        if len(url) > 2048:
            raise ValueError(f"Agent '{self.id}': image_url is too long")
        self.image_url = url
        if not isinstance(self.sources, list):
            raise ValueError(
                f"Agent '{self.id}': sources must be a list, got {type(self.sources).__name__}"
            )
        coerced: list[Source] = []
        for index, s in enumerate(self.sources):
            if isinstance(s, Source):
                coerced.append(s)
                continue
            if not isinstance(s, dict):
                raise ValueError(
                    f"Agent '{self.id}': sources[{index}] must be a dict or Source, "
                    f"got {type(s).__name__}"
                )
            try:
                coerced.append(Source(**s))
            except TypeError as e:
                raise ValueError(
                    f"Agent '{self.id}': sources[{index}] is invalid: {e}"
                ) from e
        self.sources = coerced

    @classmethod
    def from_json(cls, path: Path) -> "Agent":
        """Load an Agent from a JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        try:
            return cls(**data)
        except (TypeError, ValueError) as e:
            raise ValueError(f"Failed to load agent from {path}: {e}") from e

    def get_system_prompt(self, proposal_description: str, party_position: Optional[str] = None) -> str:
        """Generate the system prompt for this agent."""
        from .prompts import AGENT_SYSTEM_PROMPT

        positions_text = (
            "\n".join(f"- {pos}" for pos in self.key_positions)
            if self.key_positions else "Not specified"
        )
        red_lines_text = (
            "\n".join(f"- {line}" for line in self.red_lines)
            if self.red_lines else "None publicly declared"
        )
        signatures_text = (
            "\n".join(f"- {sig}" for sig in self.rhetorical_signatures)
            if self.rhetorical_signatures else "None recorded"
        )
        relationships_text = self._format_relationships()
        constituency_text = self.constituency or "Not specified"
        personality_text = self.personality_assessment or "Not yet researched."
        sources_text = self._format_sources()

        return AGENT_SYSTEM_PROMPT.format(
            agent_name=self.name,
            agent_title=self.title,
            party=self.party.capitalize(),
            role_description=self._get_role_description(),
            negotiation_posture=self._get_posture_description(),
            constituency=constituency_text,
            philosophy=self.philosophy,
            specialty=self.specialty,
            communication_style=self.communication_style,
            rhetorical_signatures=signatures_text,
            key_positions=positions_text,
            red_lines=red_lines_text,
            relationships=relationships_text,
            personality_assessment=personality_text,
            sources=sources_text,
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

    def _get_posture_description(self) -> str:
        """Get a one-line description of the agent's negotiation posture."""
        descriptions = {
            "dealmaker": (
                "You actively seek cross-aisle compromise and propose concrete amendments "
                "to bring opponents on board."
            ),
            "hardliner": (
                "You defend your stated positions firmly and rarely concede ground; "
                "compromise must come to you, not the other way around."
            ),
            "pragmatist": (
                "You weigh trade-offs and accept incremental wins where they advance your goals."
            ),
            "bomb_thrower": (
                "You reject the framing of bad proposals outright, prefer scorched-earth "
                "rhetoric, and are willing to break with your own party's leadership."
            ),
            "institutionalist": (
                "You respect process, party discipline, and the dignity of the chamber; "
                "you build consensus through procedure rather than confrontation."
            ),
        }
        return descriptions[self.negotiation_posture]

    def _format_sources(self) -> str:
        """Format primary-source citations into a readable bullet list."""
        if not self.sources:
            return "None cited yet."
        lines = []
        for s in self.sources:
            label = f"{s.title} ({s.source_type}, {s.date})"
            if s.description:
                lines.append(f"- {label}: {s.description} -- {s.url}")
            else:
                lines.append(f"- {label} -- {s.url}")
        return "\n".join(lines)

    def _format_relationships(self) -> str:
        """Format allies and rivals into a readable block, resolving IDs to names."""
        parts = []
        if self.allies:
            resolved = [_resolve_id(aid) for aid in self.allies]
            parts.append("Allies (figures in this room you tend to align with): " + "; ".join(resolved))
        if self.rivals:
            resolved = [_resolve_id(rid) for rid in self.rivals]
            parts.append("Rivals (figures in this room you frequently clash with): " + "; ".join(resolved))
        if not parts:
            return "No notable in-room alignments."
        return "\n".join(parts)

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


def load_agents(directory: Path) -> list[Agent]:
    """Load every JSON agent file from the given directory, sorted by agent id."""
    directory = Path(directory)
    if not directory.is_dir():
        raise FileNotFoundError(f"Agent data directory not found: {directory}")
    agents = [Agent.from_json(path) for path in directory.glob("*.json")]
    if not agents:
        raise ValueError(f"No agent JSON files found in {directory}")
    agents.sort(key=lambda a: a.id)
    return agents


def validate_relationships(agents: list[Agent]) -> None:
    """Validate ally/rival references on the given agents.

    Catches: unknown IDs, self-references, and cross-party references
    (allies/rivals must be in the same party as the agent listing them).
    """
    by_id = {agent.id: agent for agent in agents}
    for agent in agents:
        unknown_allies = [aid for aid in agent.allies if aid not in by_id]
        unknown_rivals = [rid for rid in agent.rivals if rid not in by_id]
        if unknown_allies or unknown_rivals:
            raise ValueError(
                f"Agent '{agent.id}' references unknown ids -- "
                f"allies: {unknown_allies}, rivals: {unknown_rivals}"
            )
        if agent.id in agent.allies or agent.id in agent.rivals:
            raise ValueError(f"Agent '{agent.id}' lists itself as an ally or rival")
        wrong_party = [
            other_id for other_id in agent.allies + agent.rivals
            if by_id[other_id].party != agent.party
        ]
        if wrong_party:
            raise ValueError(
                f"Agent '{agent.id}' (party={agent.party}) references cross-party "
                f"allies/rivals: {wrong_party}"
            )
