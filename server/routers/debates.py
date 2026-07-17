"""Debate endpoints — launch, list, detail, transcript, votes, amendments."""
from __future__ import annotations

import asyncio
import re
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from fastapi.responses import Response

from src.voting.consensus import PASSAGE_RULES

from .. import db, engine, exporters

router = APIRouter(prefix="/api/debates", tags=["debates"])

_EXPORT_MEDIA = {
    "pdf": "application/pdf",
    "md": "text/markdown; charset=utf-8",
    "json": "application/json",
}


@router.get("")
def list_debates() -> dict[str, list[dict[str, Any]]]:
    return {"debates": engine.list_debates()}


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def create_debate(body: dict[str, Any], background_tasks: BackgroundTasks) -> dict[str, Any]:
    proposal = (body.get("proposal") or "").strip()
    if not proposal:
        raise HTTPException(status_code=422, detail={"code": "missing_field", "message": "proposal is required"})
    max_rounds = int(body.get("max_rounds", 2))
    if not 1 <= max_rounds <= 5:
        raise HTTPException(status_code=422, detail={"code": "out_of_range", "message": "max_rounds must be 1..5"})

    passage_rule = body.get("passage_rule")
    if passage_rule is not None and passage_rule not in PASSAGE_RULES:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "invalid",
                "message": f"passage_rule must be one of {', '.join(PASSAGE_RULES)}",
            },
        )

    parties = body.get("parties")
    if parties is not None:
        if not isinstance(parties, list) or not all(isinstance(p, str) and p for p in parties):
            raise HTTPException(
                status_code=422,
                detail={"code": "invalid", "message": "parties must be a list of party ids"},
            )
        if len(parties) < 2:
            raise HTTPException(
                status_code=422,
                detail={"code": "invalid", "message": "at least two parties are required"},
            )
        known = {p["id"] for p in db.list_parties()}
        unknown = [p for p in parties if p not in known]
        if unknown:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "unknown_party",
                    "message": f"unknown party ids: {', '.join(unknown)}",
                },
            )

    record = engine.create_debate_record(
        proposal=proposal,
        title=body.get("title"),
        max_rounds=max_rounds,
        model=body.get("model"),
        temperature=body.get("temperature"),
        parties=parties,
        passage_rule=passage_rule,
    )

    # Kick off the debate as a fire-and-forget asyncio task. This keeps the
    # POST response fast (202 Accepted) so the client can connect to the
    # results endpoint or (in M4) the SSE stream immediately.
    asyncio.create_task(engine.run_debate(record["id"]))

    return {
        "id": record["id"],
        "status": "running",
        "stream": f"/api/debates/{record['id']}/stream",
    }


@router.get("/{debate_id}")
def get_debate(debate_id: str) -> dict[str, Any]:
    record = engine.get_debate(debate_id)
    if record is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": f"debate {debate_id!r} not found"})
    return record


@router.patch("/{debate_id}")
def update_debate(debate_id: str, body: dict[str, Any]) -> dict[str, Any]:
    """Allow renaming a debate's title. Other fields are engine-owned and not patchable."""
    record = engine.get_debate(debate_id)
    if record is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": f"debate {debate_id!r} not found"})
    title = body.get("title")
    if title is None or not isinstance(title, str) or not title.strip():
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid", "message": "only `title` (non-empty string) can be patched"},
        )
    return engine.update_debate_title(debate_id, title.strip())


@router.delete("/{debate_id}", status_code=204)
def delete_debate(debate_id: str) -> Response:
    if not engine.delete_debate(debate_id):
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": f"debate {debate_id!r} not found"})
    return Response(status_code=204)


@router.get("/{debate_id}/transcript")
def get_transcript(debate_id: str) -> dict[str, list[dict[str, Any]]]:
    return {"turns": engine.read_transcript(debate_id)}


@router.get("/{debate_id}/votes")
def get_votes(debate_id: str) -> dict[str, list[dict[str, Any]]]:
    return {"votes": engine.read_votes(debate_id)}


@router.get("/{debate_id}/amendments")
def get_amendments(debate_id: str) -> dict[str, list[dict[str, Any]]]:
    return {"amendments": engine.read_amendments(debate_id)}


@router.post("/{debate_id}/export")
def export_debate(debate_id: str, body: dict[str, Any]) -> Response:
    fmt = (body.get("format") or "pdf").lower()
    if fmt not in _EXPORT_MEDIA:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_format", "message": "format must be pdf, md, or json"},
        )
    record = engine.get_debate(debate_id)
    if record is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": f"debate {debate_id!r} not found"})

    turns = engine.read_transcript(debate_id)
    votes = engine.read_votes(debate_id)
    amendments = engine.read_amendments(debate_id)
    if fmt == "pdf":
        payload: bytes = exporters.to_pdf(
            debate=record, turns=turns, votes=votes, amendments=amendments
        )
    elif fmt == "md":
        payload = exporters.to_markdown(
            debate=record, turns=turns, votes=votes, amendments=amendments
        ).encode("utf-8")
    else:
        payload = exporters.to_json(
            debate=record, turns=turns, votes=votes, amendments=amendments
        ).encode("utf-8")

    filename = _safe_filename(record.get("title", debate_id), fmt)
    return Response(
        content=payload,
        media_type=_EXPORT_MEDIA[fmt],
        headers={"content-disposition": f'attachment; filename="{filename}"'},
    )


def _safe_filename(title: str, fmt: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "_", title.strip()) or "debate"
    return f"{slug.lower()[:60]}.{fmt}"
