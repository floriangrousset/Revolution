"""Settings endpoints — exposed to the Settings page in the web UI.

`GET /api/settings` redacts the API key (only `api_key_set` + a 4-char
preview). The full key is never sent to the client.

`PATCH /api/settings` accepts a partial payload. Allowed top-level keys:
- `anthropic_api_key`
- `default_model`
- `default_temperature`
- `system_prompts` (merged per-prompt-name)
- `reference_lists` (merged per-list-name; additive only — removals raise)
"""
from __future__ import annotations

import re
from typing import Any

import anthropic
from fastapi import APIRouter, HTTPException

from src.config import DEFAULT_REFERENCE_LISTS, get_settings_store
from src.voting.consensus import PASSAGE_RULES

router = APIRouter(prefix="/api/settings", tags=["settings"])

# Required format-string placeholders per prompt — block saves that drop
# them so the engine doesn't crash on a malformed template.
_REQUIRED_PLACEHOLDERS: dict[str, set[str]] = {
    "AGENT_SYSTEM_PROMPT": {
        "agent_name", "agent_title", "party", "role_description", "negotiation_posture",
        "constituency", "philosophy", "specialty", "communication_style",
        "rhetorical_signatures", "key_positions", "red_lines", "relationships",
        "personality_assessment", "sources", "proposal_description", "party_position",
    },
    "VOTING_PROMPT": {"agent_name", "proposal_description", "debate_summary"},
    "PARTY_HEAD_INTRO_PROMPT": {"agent_name", "agent_title", "party"},
    "ADVISOR_ANALYSIS_PROMPT": {"specialty"},
    "ASSISTANT_RESEARCH_PROMPT": {"specialty"},
    "SYNTHESIS_PROMPT": {"party"},
    "DEBATE_OPENING_PROMPT": {"agent_name", "agent_title", "party"},
    "DEBATE_REBUTTAL_PROMPT": {"agent_name", "agent_title", "party"},
    "AMENDMENT_MARKUP_PROMPT": {"proposal_description", "amendment_text"},
}

_KNOWN_REFERENCE_LISTS = set(DEFAULT_REFERENCE_LISTS.keys())


def _redact(payload: dict[str, Any]) -> dict[str, Any]:
    """Strip the raw API key, expose only a length+preview for UI display."""
    key = payload.get("anthropic_api_key") or ""
    preview = key[:7] + "…" + key[-4:] if len(key) > 12 else ("…" if key else "")
    out = dict(payload)
    out.pop("anthropic_api_key", None)
    out["api_key_set"] = bool(key)
    out["api_key_preview"] = preview
    return out


def _validate_patch(patch: dict[str, Any]) -> None:
    """Reject obviously broken patches before touching disk."""
    if "default_temperature" in patch:
        try:
            t = float(patch["default_temperature"])
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=422,
                detail={"code": "invalid", "message": "default_temperature must be a number"},
            )
        if not 0 <= t <= 1:
            raise HTTPException(
                status_code=422,
                detail={"code": "invalid", "message": "default_temperature must be in [0, 1]"},
            )

    if "system_prompts" in patch:
        prompts = patch["system_prompts"]
        if not isinstance(prompts, dict):
            raise HTTPException(
                status_code=422,
                detail={"code": "invalid", "message": "system_prompts must be an object"},
            )
        for name, value in prompts.items():
            if name not in _REQUIRED_PLACEHOLDERS:
                raise HTTPException(
                    status_code=422,
                    detail={"code": "unknown_prompt", "message": f"unknown prompt {name!r}"},
                )
            if not isinstance(value, str) or not value.strip():
                raise HTTPException(
                    status_code=422,
                    detail={"code": "invalid", "message": f"{name} must be a non-empty string"},
                )
            placeholders = set(re.findall(r"{(\w+)}", value))
            missing = _REQUIRED_PLACEHOLDERS[name] - placeholders
            if missing:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "code": "missing_placeholder",
                        "message": (
                            f"{name} is missing required placeholders: "
                            f"{sorted(missing)}"
                        ),
                    },
                )

    if "voting" in patch:
        voting = patch["voting"]
        if not isinstance(voting, dict):
            raise HTTPException(
                status_code=422,
                detail={"code": "invalid", "message": "voting must be an object"},
            )
        rule = voting.get("passage_rule")
        if rule is not None and rule not in PASSAGE_RULES:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "invalid",
                    "message": f"voting.passage_rule must be one of {', '.join(PASSAGE_RULES)}",
                },
            )
        quorum = voting.get("quorum")
        if quorum is not None:
            try:
                q = float(quorum)
            except (TypeError, ValueError):
                raise HTTPException(
                    status_code=422,
                    detail={"code": "invalid", "message": "voting.quorum must be a number or null"},
                )
            if not 0 < q <= 1:
                raise HTTPException(
                    status_code=422,
                    detail={"code": "invalid", "message": "voting.quorum must be in (0, 1]"},
                )

    if "reference_lists" in patch:
        lists = patch["reference_lists"]
        if not isinstance(lists, dict):
            raise HTTPException(
                status_code=422,
                detail={"code": "invalid", "message": "reference_lists must be an object"},
            )
        for name, value in lists.items():
            if name not in _KNOWN_REFERENCE_LISTS:
                raise HTTPException(
                    status_code=422,
                    detail={"code": "unknown_list", "message": f"unknown reference list {name!r}"},
                )
            if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
                raise HTTPException(
                    status_code=422,
                    detail={"code": "invalid", "message": f"{name} must be a list of strings"},
                )
            current = get_settings_store().get(f"reference_lists.{name}") or []
            if isinstance(current, list):
                removed = set(current) - set(value)
                if removed:
                    raise HTTPException(
                        status_code=409,
                        detail={
                            "code": "removal_blocked",
                            "message": (
                                f"reference_lists.{name}: removing entries that may be in "
                                f"use is not supported in this release ({sorted(removed)})"
                            ),
                        },
                    )


@router.get("")
def get_settings() -> dict[str, Any]:
    return _redact(get_settings_store().load())


@router.patch("")
def patch_settings(body: dict[str, Any]) -> dict[str, Any]:
    _validate_patch(body)
    saved = get_settings_store().save(body)
    return _redact(saved)


@router.post("/reset-prompt")
def reset_prompt(body: dict[str, Any]) -> dict[str, Any]:
    name = body.get("name")
    if not isinstance(name, str) or not name:
        raise HTTPException(status_code=422, detail={"code": "invalid", "message": "name is required"})
    try:
        saved = get_settings_store().reset_prompt(name)
    except KeyError:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": f"unknown prompt {name!r}"})
    return _redact(saved)


@router.post("/test-key")
async def test_key(body: dict[str, Any]) -> dict[str, Any]:
    """Validate an API key candidate with a tiny throwaway message call.

    Accepts an optional `api_key` in the body; if absent, tests the saved one.
    """
    key = body.get("api_key")
    if not key:
        key = get_settings_store().get("anthropic_api_key") or ""
    key = (key or "").strip()
    if not key:
        return {"ok": False, "error": "No API key provided or saved."}
    model = body.get("model") or get_settings_store().get("default_model") or "claude-haiku-4-5-20251001"
    try:
        client = anthropic.AsyncAnthropic(api_key=key)
        # Smallest possible request — one user message, max 8 tokens of output.
        await client.messages.create(
            model=model,
            max_tokens=8,
            messages=[{"role": "user", "content": "ping"}],
        )
        return {"ok": True, "model": model}
    except Exception as e:
        return {"ok": False, "error": str(e)[:240]}
