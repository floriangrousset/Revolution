"""File-backed configuration store.

Lives at `data/settings.json` (gitignored). Both the CLI and the web server
consult this single file for:

- `anthropic_api_key`
- `default_model`, `default_temperature`
- editable `system_prompts` (each of the 8 prompt constants from
  `src/agents/prompts.py`)
- editable `reference_lists` (roles, negotiation_postures)

Boot behavior: on first import, if the file is missing it's created with
the Python defaults — and if `ANTHROPIC_API_KEY` is in `os.environ`, that
value is seeded into the file as a one-time migration from .env.

Subsequent edits go through the Settings page (HTTP API) for the web
layer; the CLI just reads. Both layers are protected against malformed
JSON: a corrupt file falls back to defaults rather than crashing the app.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_DATA_DIR = REPO_ROOT / "data"


# ---------------------------------------------------------------------------
# Hard defaults — used both to populate a missing settings.json and as the
# "Reset to default" target on the Settings page.
# ---------------------------------------------------------------------------

DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_TEMPERATURE = 0.8
DEFAULT_PASSAGE_RULE = "majority"

DEFAULT_REFERENCE_LISTS: dict[str, list[str]] = {
    "roles": ["party_head", "advisor", "assistant"],
    "negotiation_postures": [
        "dealmaker",
        "hardliner",
        "pragmatist",
        "bomb_thrower",
        "institutionalist",
    ],
}


def _default_prompts() -> dict[str, str]:
    """Snapshot the eight prompt constants from src/agents/prompts.py.

    Imported lazily because src.agents.prompts is meant to be edited and the
    settings_store loader needs to capture whatever the engine ships with.
    """
    from src.agents import prompts as _p

    return {
        "AGENT_SYSTEM_PROMPT": _p.AGENT_SYSTEM_PROMPT,
        "PARTY_HEAD_INTRO_PROMPT": _p.PARTY_HEAD_INTRO_PROMPT,
        "ADVISOR_ANALYSIS_PROMPT": _p.ADVISOR_ANALYSIS_PROMPT,
        "ASSISTANT_RESEARCH_PROMPT": _p.ASSISTANT_RESEARCH_PROMPT,
        "SYNTHESIS_PROMPT": _p.SYNTHESIS_PROMPT,
        "DEBATE_OPENING_PROMPT": _p.DEBATE_OPENING_PROMPT,
        "DEBATE_REBUTTAL_PROMPT": _p.DEBATE_REBUTTAL_PROMPT,
        "VOTING_PROMPT": _p.VOTING_PROMPT,
        "AMENDMENT_MARKUP_PROMPT": _p.AMENDMENT_MARKUP_PROMPT,
    }


def DEFAULTS() -> dict[str, Any]:
    """Build the full default settings payload (used at first boot)."""
    return {
        "anthropic_api_key": os.environ.get("ANTHROPIC_API_KEY") or "",
        "default_model": os.environ.get("MODEL_NAME") or DEFAULT_MODEL,
        "default_temperature": DEFAULT_TEMPERATURE,
        "system_prompts": _default_prompts(),
        "reference_lists": dict(DEFAULT_REFERENCE_LISTS),
        "voting": {"passage_rule": DEFAULT_PASSAGE_RULE, "quorum": None},
        "updated_at": _now(),
    }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Resolving the data directory: matches server.settings.Settings.data_dir
# semantics — DATA_DIR env override → ./data fallback.
# ---------------------------------------------------------------------------

def _resolve_data_dir() -> Path:
    raw = os.environ.get("DATA_DIR")
    if raw:
        return Path(raw)
    return DEFAULT_DATA_DIR


def _settings_path() -> Path:
    return _resolve_data_dir() / "settings.json"


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.write("\n")
    tmp.replace(path)


# ---------------------------------------------------------------------------
# The store itself.
# ---------------------------------------------------------------------------

class SettingsStore:
    """Thread-safe in-memory mirror of `data/settings.json`."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._data: dict[str, Any] | None = None
        self._path: Path | None = None

    def _ensure_loaded(self) -> dict[str, Any]:
        """Load (or first-time seed) the settings file."""
        with self._lock:
            if self._data is not None:
                return self._data
            path = _settings_path()
            self._path = path
            if path.exists():
                try:
                    with path.open("r", encoding="utf-8") as f:
                        self._data = json.load(f)
                except (json.JSONDecodeError, OSError) as e:
                    log.warning("settings.json malformed (%s); using defaults", e)
                    self._data = DEFAULTS()
                # Backfill any fields that were missing from older revisions.
                self._data = self._backfill(self._data)
            else:
                self._data = DEFAULTS()
                _atomic_write_json(path, self._data)
                log.info("seeded settings.json at %s", path)
            # One-time .env → settings.json migration: if the persisted store
            # has no key but `.env` has populated `ANTHROPIC_API_KEY`, fold
            # the env value into the file so the Settings page reflects it.
            stored_key = self._data.get("anthropic_api_key") or ""
            env_key = os.environ.get("ANTHROPIC_API_KEY") or ""
            if not stored_key and env_key:
                self._data["anthropic_api_key"] = env_key
                self._data["updated_at"] = _now()
                _atomic_write_json(path, self._data)
                log.info("migrated ANTHROPIC_API_KEY from env into settings.json")
                stored_key = env_key
            # Export the key to os.environ so the engine's get_model() and
            # any other os.environ readers see it without changes.
            if stored_key:
                os.environ.setdefault("ANTHROPIC_API_KEY", stored_key)
            return self._data

    def _backfill(self, current: dict[str, Any]) -> dict[str, Any]:
        """Add fields that are missing from older settings.json revisions."""
        defaults = DEFAULTS()
        changed = False
        for key, value in defaults.items():
            if key not in current:
                current[key] = value
                changed = True
            elif isinstance(value, dict) and isinstance(current[key], dict):
                for sub_key, sub_value in value.items():
                    if sub_key not in current[key]:
                        current[key][sub_key] = sub_value
                        changed = True
        if changed and self._path is not None:
            current["updated_at"] = _now()
            _atomic_write_json(self._path, current)
        return current

    # -- public API --------------------------------------------------------

    def load(self) -> dict[str, Any]:
        """Return the full settings payload (unredacted — caller decides)."""
        return dict(self._ensure_loaded())

    def get(self, dotted_key: str, fallback: Any = None) -> Any:
        """Dotted-path getter: `get('reference_lists.roles')`."""
        d: Any = self._ensure_loaded()
        for part in dotted_key.split("."):
            if not isinstance(d, dict) or part not in d:
                return fallback
            d = d[part]
        return d

    def save(self, patch: dict[str, Any]) -> dict[str, Any]:
        """Merge patch into the persisted settings. Returns the new state.

        Nested dicts are merged one level deep (so PATCHing
        `system_prompts: {VOTING_PROMPT: "…"}` doesn't wipe the other seven).
        """
        with self._lock:
            current = self._ensure_loaded()
            for key, value in patch.items():
                if (
                    isinstance(value, dict)
                    and isinstance(current.get(key), dict)
                    and key in {"system_prompts", "reference_lists", "voting"}
                ):
                    current[key] = {**current[key], **value}
                else:
                    current[key] = value
            current["updated_at"] = _now()
            if self._path is None:
                self._path = _settings_path()
            _atomic_write_json(self._path, current)
            # Keep os.environ in lockstep with the persisted key.
            key = current.get("anthropic_api_key") or ""
            if key:
                os.environ["ANTHROPIC_API_KEY"] = key
            elif "ANTHROPIC_API_KEY" in os.environ:
                # Explicit clear → drop from env too so the engine fails
                # fast rather than silently using a stale key.
                del os.environ["ANTHROPIC_API_KEY"]
            return dict(current)

    def reset_prompt(self, name: str) -> dict[str, Any]:
        """Restore a single system prompt to its Python-default value."""
        defaults = _default_prompts()
        if name not in defaults:
            raise KeyError(name)
        return self.save({"system_prompts": {name: defaults[name]}})

    def reload(self) -> None:
        """Drop the in-memory cache so the next read re-reads from disk."""
        with self._lock:
            self._data = None


# Module-level singleton — instantiated lazily.
_INSTANCE: SettingsStore | None = None


def get_settings_store() -> SettingsStore:
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = SettingsStore()
    return _INSTANCE


# ---------------------------------------------------------------------------
# Convenience helpers (used by src/ and server/ callsites).
# ---------------------------------------------------------------------------

def load() -> dict[str, Any]:
    return get_settings_store().load()


def save(patch: dict[str, Any]) -> dict[str, Any]:
    return get_settings_store().save(patch)


def get_prompt(name: str) -> str:
    """Look up a system prompt from the store, falling back to the Python
    constant if the store doesn't have one for this name."""
    store = get_settings_store()
    value = store.get(f"system_prompts.{name}")
    if isinstance(value, str) and value:
        return value
    return _default_prompts().get(name, "")


def get_reference_list(name: str) -> list[str]:
    """Look up a reference list (e.g. 'roles', 'negotiation_postures')."""
    value = get_settings_store().get(f"reference_lists.{name}")
    if isinstance(value, list) and all(isinstance(x, str) for x in value):
        return value
    return list(DEFAULT_REFERENCE_LISTS.get(name, []))


def get_api_key() -> str:
    """Resolution order: explicit env override → settings.json → empty."""
    explicit = os.environ.get("ANTHROPIC_API_KEY")
    if explicit:
        return explicit
    return get_settings_store().get("anthropic_api_key", "") or ""


def get_default_model() -> str:
    explicit = os.environ.get("MODEL_NAME")
    if explicit:
        return explicit
    return get_settings_store().get("default_model", DEFAULT_MODEL) or DEFAULT_MODEL


def get_default_temperature() -> float:
    raw = get_settings_store().get("default_temperature", DEFAULT_TEMPERATURE)
    try:
        return float(raw)
    except (TypeError, ValueError):
        return DEFAULT_TEMPERATURE


def get_default_quorum() -> float | None:
    """The configured quorum fraction (voting.quorum), or None when unset."""
    raw = get_settings_store().get("voting.quorum")
    try:
        value = float(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None
    if value is not None and 0 < value <= 1:
        return value
    return None


def get_default_passage_rule() -> str:
    """Default passage rule for debates that don't pin one explicitly."""
    from src.voting.consensus import PASSAGE_RULES

    raw = get_settings_store().get("voting.passage_rule", DEFAULT_PASSAGE_RULE)
    return raw if raw in PASSAGE_RULES else DEFAULT_PASSAGE_RULE
