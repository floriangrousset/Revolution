"""Tests for the Agent dataclass, JSON loading, validation, and prompt rendering."""
import json
from dataclasses import asdict
from pathlib import Path

import pytest

from src.agents.base import (
    Agent,
    Source,
    clear_registry,
    load_agents,
    register_agents,
    validate_relationships,
)
from src.agents.democrat import DEMOCRAT_AGENTS
from src.agents.republican import REPUBLICAN_AGENTS


def _make_agent(**overrides) -> Agent:
    base = dict(
        id="test_agent",
        name="Test Agent",
        title="Test Title",
        party="republican",
        role="advisor",
        specialty="Testing",
        philosophy="I test things.",
        communication_style="Terse.",
    )
    base.update(overrides)
    return Agent(**base)


class TestLiteralValidation:
    def test_empty_party_raises(self):
        with pytest.raises(ValueError, match="invalid party"):
            _make_agent(party="")

    def test_custom_party_accepted(self):
        # Custom parties (libertarian, green, etc.) are first-class:
        # the dataclass accepts any non-empty string and the parties
        # registry decides which ids are recognized.
        agent = _make_agent(party="libertarian")
        assert agent.party == "libertarian"

    def test_invalid_role_raises(self):
        with pytest.raises(ValueError, match="invalid role"):
            _make_agent(role="intern")

    def test_invalid_negotiation_posture_raises(self):
        with pytest.raises(ValueError, match="invalid negotiation_posture"):
            _make_agent(negotiation_posture="hardliiner")

    def test_default_posture_is_pragmatist(self):
        agent = _make_agent()
        assert agent.negotiation_posture == "pragmatist"


class TestValidateRelationships:
    def test_unknown_ally_id_raises(self):
        agents = [_make_agent(id="a", allies=["nonexistent"])]
        with pytest.raises(ValueError, match="unknown ids"):
            validate_relationships(agents)

    def test_unknown_rival_id_raises(self):
        agents = [_make_agent(id="a", rivals=["nope"])]
        with pytest.raises(ValueError, match="unknown ids"):
            validate_relationships(agents)

    def test_self_reference_in_allies_raises(self):
        agents = [_make_agent(id="a", allies=["a"])]
        with pytest.raises(ValueError, match="lists itself"):
            validate_relationships(agents)

    def test_self_reference_in_rivals_raises(self):
        agents = [_make_agent(id="a", rivals=["a"])]
        with pytest.raises(ValueError, match="lists itself"):
            validate_relationships(agents)

    def test_cross_party_ally_raises(self):
        agents = [
            _make_agent(id="r", party="republican", allies=["d"]),
            _make_agent(id="d", party="democrat"),
        ]
        with pytest.raises(ValueError, match="cross-party"):
            validate_relationships(agents)

    def test_valid_in_party_relationships_pass(self):
        agents = [
            _make_agent(id="a", party="republican", allies=["b"], rivals=[]),
            _make_agent(id="b", party="republican"),
        ]
        validate_relationships(agents)


class TestFromJson:
    def test_round_trip(self, tmp_path: Path):
        data = {
            "id": "rt",
            "name": "Round Trip",
            "title": "Tester",
            "party": "democrat",
            "role": "advisor",
            "specialty": "JSON",
            "philosophy": "Persisted state.",
            "communication_style": "Structured.",
            "negotiation_posture": "dealmaker",
            "constituency": "Test suite",
        }
        path = tmp_path / "rt.json"
        path.write_text(json.dumps(data))
        agent = Agent.from_json(path)
        assert agent.id == "rt"
        assert agent.negotiation_posture == "dealmaker"

    def test_load_agents_sorts_by_id(self, tmp_path: Path):
        for agent_id in ("zeta", "alpha", "mu"):
            (tmp_path / f"x_{agent_id}.json").write_text(
                json.dumps(asdict(_make_agent(id=agent_id)))
            )
        loaded = load_agents(tmp_path)
        assert [a.id for a in loaded] == ["alpha", "mu", "zeta"]

    def test_from_json_error_includes_file_path(self, tmp_path: Path):
        path = tmp_path / "broken.json"
        path.write_text(json.dumps({"id": "x", "name": "X", "title": "T",
                                    "party": "republican", "role": "advisor",
                                    "specialty": "S", "philosophy": "P",
                                    "communication_style": "C",
                                    "negotiation_posture": "wrongposture"}))
        with pytest.raises(ValueError, match=str(path)):
            Agent.from_json(path)

    def test_from_json_unknown_field_includes_path(self, tmp_path: Path):
        path = tmp_path / "typo.json"
        path.write_text(json.dumps({"id": "x", "name": "X", "title": "T",
                                    "party": "republican", "role": "advisor",
                                    "specialty": "S", "philosophy": "P",
                                    "communication_style": "C",
                                    "red_lins": ["typo"]}))
        with pytest.raises(ValueError, match=str(path)):
            Agent.from_json(path)

    def test_load_agents_empty_dir_raises(self, tmp_path: Path):
        with pytest.raises(ValueError, match="No agent JSON files"):
            load_agents(tmp_path)

    def test_load_agents_missing_dir_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            load_agents(tmp_path / "does_not_exist")


class TestProductionAgents:
    def test_eleven_per_party(self):
        assert len(REPUBLICAN_AGENTS) == 11
        assert len(DEMOCRAT_AGENTS) == 11

    def test_all_ids_unique(self):
        all_ids = [a.id for a in REPUBLICAN_AGENTS + DEMOCRAT_AGENTS]
        assert len(all_ids) == len(set(all_ids))

    def test_relationships_resolve_to_names_in_prompt(self):
        speaker = next(a for a in REPUBLICAN_AGENTS if a.id == "rep_head")
        prompt = speaker.get_system_prompt("Test proposal.")
        for ally_id in speaker.allies:
            ally = next(a for a in REPUBLICAN_AGENTS if a.id == ally_id)
            assert f"{ally.name} ({ally.title})" in prompt, (
                f"Expected '{ally.name} ({ally.title})' in resolved prompt"
            )
            assert ally_id not in prompt, f"Raw id {ally_id} leaked into prompt"

    def test_prompt_contains_new_sections(self):
        speaker = next(a for a in REPUBLICAN_AGENTS if a.id == "rep_head")
        prompt = speaker.get_system_prompt("Test proposal.")
        for header in (
            "## Your Negotiation Posture",
            "## Who You Answer To",
            "## Your Red Lines",
            "## Your Relationships in This Room",
        ):
            assert header in prompt

    def test_prompt_renders_for_every_agent(self):
        for agent in REPUBLICAN_AGENTS + DEMOCRAT_AGENTS:
            prompt = agent.get_system_prompt("Test proposal.", "Party position TBD.")
            assert agent.name in prompt
            assert agent.philosophy[:40] in prompt

    def test_no_executive_branch_titles(self):
        """Every seeded persona must be a sitting member of Congress.

        Guards against executive-branch drift: when a member becomes Vice
        President or a cabinet Secretary (e.g. JD Vance, Marco Rubio after
        January 2025), the persona slot must be re-assigned to a sitting
        legislator rather than keeping the departed member.
        """
        for agent in REPUBLICAN_AGENTS + DEMOCRAT_AGENTS:
            for forbidden in ("Vice President", "Secretary of"):
                assert forbidden not in agent.title, (
                    f"{agent.id}: title {agent.title!r} contains {forbidden!r} -- "
                    "persona has drifted into the executive branch"
                )


class TestRegistry:
    def test_resolve_id_falls_back_to_raw_for_unregistered(self):
        # The autouse snapshot fixture restores the registry after each test;
        # clear_registry() is safe here.
        clear_registry()
        agent = _make_agent(id="solo", party="republican", allies=["ghost_id"])
        text = agent._format_relationships()
        assert "ghost_id" in text

    def test_register_agents_raises_on_duplicate_id(self):
        agent1 = _make_agent(id="dup", name="First")
        agent2 = _make_agent(id="dup", name="Second")
        clear_registry()
        register_agents([agent1])
        with pytest.raises(ValueError, match="already registered"):
            register_agents([agent2])

    def test_resolve_id_format_is_name_with_title(self):
        clear_registry()
        target = _make_agent(id="t", name="Senator Test", title="Chair of Testing")
        register_agents([target])
        ref = _make_agent(id="ref", party=target.party, allies=["t"])
        text = ref._format_relationships()
        assert "Senator Test (Chair of Testing)" in text

    def test_clear_registry_empties_the_registry(self):
        clear_registry()
        agent = _make_agent(id="lonely", allies=["anything"])
        # With an empty registry, the resolver returns the raw id.
        assert agent._format_relationships().endswith("anything")


class TestPersonaEnrichmentFields:
    def test_defaults_are_empty(self):
        agent = _make_agent()
        assert agent.personality_assessment == ""
        assert agent.sources == []
        assert agent.persona_last_updated == ""

    def test_sources_coerced_from_dict_in_post_init(self):
        agent = _make_agent(sources=[
            {"title": "Op-ed", "url": "https://example.com/a",
             "date": "2025-01-15", "source_type": "op-ed"},
        ])
        assert len(agent.sources) == 1
        assert isinstance(agent.sources[0], Source)
        assert agent.sources[0].title == "Op-ed"

    def test_sources_passthrough_when_already_dataclass(self):
        src = Source(title="Speech", url="https://example.com/b",
                     date="2025-02-01", source_type="speech")
        agent = _make_agent(sources=[src])
        assert agent.sources[0] is src

    def test_from_json_round_trips_enrichment_fields(self, tmp_path: Path):
        data = {
            "id": "enriched", "name": "E", "title": "T",
            "party": "democrat", "role": "advisor", "specialty": "S",
            "philosophy": "P", "communication_style": "C",
            "personality_assessment": "Detail-oriented and patient.",
            "sources": [
                {"title": "Floor Speech", "url": "https://example.com/s1",
                 "date": "2025-03-10", "source_type": "speech",
                 "description": "Stated red line on X."}
            ],
            "persona_last_updated": "2025-03-15",
        }
        path = tmp_path / "e.json"
        path.write_text(json.dumps(data))
        agent = Agent.from_json(path)
        assert agent.personality_assessment == "Detail-oriented and patient."
        assert agent.persona_last_updated == "2025-03-15"
        assert isinstance(agent.sources[0], Source)
        assert agent.sources[0].url == "https://example.com/s1"

    def test_prompt_renders_personality_and_sources_when_populated(self):
        agent = _make_agent(
            personality_assessment="Pragmatic, deal-oriented, low ego.",
            sources=[Source(
                title="2024 Senate Floor Speech",
                url="https://example.com/floor",
                date="2024-09-12",
                source_type="speech",
                description="Articulated red lines on entitlement reform.",
            )],
        )
        prompt = agent.get_system_prompt("Test proposal.")
        assert "## Personality Assessment" in prompt
        assert "Pragmatic, deal-oriented, low ego." in prompt
        assert "## Primary Sources Backing This Persona" in prompt
        assert "2024 Senate Floor Speech" in prompt
        assert "https://example.com/floor" in prompt

    def test_prompt_renders_placeholders_when_empty(self):
        agent = _make_agent()
        prompt = agent.get_system_prompt("Test proposal.")
        assert "## Personality Assessment" in prompt
        assert "Not yet researched." in prompt
        assert "## Primary Sources Backing This Persona" in prompt
        assert "None cited yet." in prompt

    def test_sources_null_raises_clear_error(self):
        with pytest.raises(ValueError, match="sources must be a list"):
            _make_agent(sources=None)

    def test_sources_non_list_raises_clear_error(self):
        with pytest.raises(ValueError, match="sources must be a list"):
            _make_agent(sources={"title": "x"})

    def test_sources_non_dict_item_raises_with_index(self):
        with pytest.raises(ValueError, match=r"sources\[0\] must be a dict or Source"):
            _make_agent(sources=["just a string"])

    def test_sources_malformed_dict_raises_with_index_and_agent_id(self):
        with pytest.raises(ValueError, match=r"Agent 'test_agent': sources\[1\] is invalid"):
            _make_agent(sources=[
                {"title": "ok", "url": "u", "date": "d", "source_type": "t"},
                {"title": "missing rest"},
            ])

    def test_from_json_malformed_source_includes_path_and_index(self, tmp_path: Path):
        path = tmp_path / "bad_src.json"
        path.write_text(json.dumps({
            "id": "x", "name": "X", "title": "T",
            "party": "republican", "role": "advisor",
            "specialty": "S", "philosophy": "P", "communication_style": "C",
            "sources": [{"title": "incomplete"}],
        }))
        with pytest.raises(ValueError) as exc_info:
            Agent.from_json(path)
        msg = str(exc_info.value)
        assert str(path) in msg
        assert "sources[0]" in msg

    def test_production_json_files_declare_enrichment_keys(self):
        """Every shipped persona should declare the enrichment keys (even if empty)
        so the JSON 'schema' is consistent across the roster."""
        roots = [
            Path("src/agents/data/republican"),
            Path("src/agents/data/democrat"),
        ]
        for root in roots:
            for p in sorted(root.glob("*.json")):
                data = json.loads(p.read_text())
                for key in ("personality_assessment", "sources", "persona_last_updated"):
                    assert key in data, f"{p} is missing key {key!r}"
