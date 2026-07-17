"""Wrap the LangGraph engine so the web layer can launch debates, persist
their state to the file DB, and (in M4) stream events to the browser."""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.graphs.main_graph import run_negotiation
from src.state.types import AgentMessage, Vote
from src.voting.consensus import VotingRules, determine_final_result

from . import db
from .events import Event, broadcaster
from .settings import get_settings

log = logging.getLogger(__name__)


# Map the engine's `AgentMessage.phase` values to the API surface phases.
PHASE_MAP: dict[str, str] = {
    "intro": "intro",
    "advisor_discussion": "advisor_discussion",
    "assistant_research": "assistant_research",
    "synthesis": "synthesis",
    "cross_party_debate": "cross_party_debate",
    # The engine sometimes emits ad-hoc phases — fall through unchanged.
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _debate_dir(debate_id: str) -> Path:
    return get_settings().data_dir / "debates" / debate_id


def _index_path() -> Path:
    return get_settings().data_dir / "index.json"


def _read_index() -> list[dict[str, Any]]:
    p = _index_path()
    if not p.exists():
        return []
    try:
        with p.open("r", encoding="utf-8") as f:
            return json.load(f).get("debates", [])
    except (json.JSONDecodeError, OSError):
        return []


def _write_index(entries: list[dict[str, Any]]) -> None:
    p = _index_path()
    tmp = p.with_suffix(p.suffix + ".tmp")
    p.parent.mkdir(parents=True, exist_ok=True)
    with tmp.open("w", encoding="utf-8") as f:
        json.dump({"debates": entries}, f, indent=2, ensure_ascii=False)
        f.write("\n")
    tmp.replace(p)


def _upsert_index(entry: dict[str, Any]) -> None:
    entries = _read_index()
    entries = [e for e in entries if e["id"] != entry["id"]]
    entries.insert(0, entry)
    _write_index(entries)


def _patch_index(debate_id: str, **patches: Any) -> None:
    """Patch a single index.json row in place (no-op if id missing)."""
    entries = _read_index()
    changed = False
    for entry in entries:
        if entry["id"] == debate_id:
            entry.update(patches)
            changed = True
            break
    if changed:
        _write_index(entries)


def list_debates() -> list[dict[str, Any]]:
    """Sorted newest-first index of all debates."""
    return _read_index()


def get_debate(debate_id: str) -> dict[str, Any] | None:
    """Full debate record (config + status + result)."""
    p = _debate_dir(debate_id) / "debate.json"
    if not p.exists():
        return None
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def read_transcript(debate_id: str) -> list[dict[str, Any]]:
    p = _debate_dir(debate_id) / "transcript.jsonl"
    if not p.exists():
        return []
    out: list[dict[str, Any]] = []
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def read_votes(debate_id: str) -> list[dict[str, Any]]:
    p = _debate_dir(debate_id) / "votes.json"
    if not p.exists():
        return []
    with p.open("r", encoding="utf-8") as f:
        return json.load(f).get("votes", [])


def read_amendments(debate_id: str) -> list[dict[str, Any]]:
    p = _debate_dir(debate_id) / "amendments.json"
    if not p.exists():
        return []
    with p.open("r", encoding="utf-8") as f:
        return json.load(f).get("amendments", [])


def update_debate_title(debate_id: str, title: str) -> dict[str, Any]:
    """Rename a debate. The only mutable field on an already-running record."""
    record = get_debate(debate_id)
    if record is None:
        raise KeyError(debate_id)
    record["title"] = title
    _atomic_write_json(_debate_dir(debate_id) / "debate.json", record)
    _patch_index(debate_id, title=title)
    return record


def delete_debate(debate_id: str) -> bool:
    """Remove a debate's directory and its index row. Returns False if missing.

    Note: this does NOT cancel an in-flight run. The asyncio task will keep
    running in the background; its writes will be lost since the directory
    has been deleted. Stopping a debate cleanly is a future feature.
    """
    debate_dir = _debate_dir(debate_id)
    if not (debate_dir / "debate.json").exists():
        return False
    import shutil
    try:
        shutil.rmtree(debate_dir)
    except OSError as e:
        log.warning("failed to delete debate dir %s: %s", debate_dir, e)
        return False
    entries = [e for e in _read_index() if e["id"] != debate_id]
    _write_index(entries)
    return True


def _atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False, default=_default_encoder)
        f.write("\n")
    tmp.replace(path)


def _default_encoder(obj: Any) -> Any:
    if is_dataclass(obj) and not isinstance(obj, type):
        return asdict(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _summarize_title(text: str, *, fallback: str = "Untitled proposal") -> str:
    text = text.strip()
    if not text:
        return fallback
    # First sentence or first 60 chars, whichever comes first.
    cut = text.split(".")[0].strip() or text
    if len(cut) > 60:
        cut = cut[:57].rstrip() + "…"
    return cut


def _serialize_message(msg: AgentMessage, *, turn_index: int) -> dict[str, Any]:
    return {
        "id": f"t{turn_index}",
        "agent": msg.agent_id,
        "name": msg.agent_name,
        "party": msg.party,
        "role": msg.role,
        "phase": PHASE_MAP.get(msg.phase, msg.phase),
        "round": None,
        "content": msg.content,
        "ts": _now(),
    }


def _serialize_vote(
    vote: Vote, *, previous: dict[str, str], weight: float | None = None
) -> dict[str, Any]:
    prior = previous.get(vote.agent_id)
    changed = prior is not None and prior != vote.vote
    payload = {
        "agent": vote.agent_id,
        "name": vote.agent_name,
        "party": vote.party,
        "role": vote.agent_role,
        "vote": vote.vote,
        "reasoning": vote.reasoning,
        "changed": changed,
        "from": prior if changed else None,
        "amendments": list(vote.amendments or []),
    }
    if weight is not None:
        payload["weight"] = weight
    return payload


def create_debate_record(
    *,
    proposal: str,
    title: str | None = None,
    max_rounds: int = 2,
    model: str | None = None,
    temperature: float | None = None,
    parties: list[str] | None = None,
    passage_rule: str | None = None,
    use_seat_weights: bool = False,
) -> dict[str, Any]:
    """Create the on-disk debate record (status=pending). Returns the record."""
    from src.config import get_default_model, get_default_passage_rule, get_default_temperature

    debate_id = f"deb_{uuid.uuid4().hex[:8]}"
    resolved_model = model or get_default_model()
    resolved_temp = temperature if temperature is not None else get_default_temperature()
    created_at = _now()
    title_resolved = title or _summarize_title(proposal)
    resolved_parties = parties or ["democrat", "republican"]
    # Snapshot the registry's configured seat counts at creation time so the
    # debate stays reproducible even if the registry changes later.
    seat_config: dict[str, int] | None = None
    if use_seat_weights:
        registry = {p["id"]: p for p in db.list_parties()}
        seat_config = {
            pid: registry[pid]["voting_seats"]
            for pid in resolved_parties
            if registry.get(pid, {}).get("voting_seats")
        }
    record: dict[str, Any] = {
        "id": debate_id,
        "title": title_resolved,
        "proposal": proposal,
        "config": {
            "max_rounds": max_rounds,
            "model": resolved_model,
            "temperature": resolved_temp,
            "parties": resolved_parties,
            "passage_rule": passage_rule or get_default_passage_rule(),
            "use_seat_weights": use_seat_weights,
            "seat_config": seat_config,
        },
        "status": "pending",
        "result": None,
        "tally": {"support": 0, "oppose": 0, "abstain": 0},
        "created_at": created_at,
        "completed_at": None,
    }
    _atomic_write_json(_debate_dir(debate_id) / "debate.json", record)
    _upsert_index(
        {
            "id": debate_id,
            "title": title_resolved,
            "status": "pending",
            "rounds": max_rounds,
            "support": 0,
            "oppose": 0,
            "abstain": 0,
            "amendments": 0,
            "model": resolved_model,
            "temperature": resolved_temp,
            "duration_s": 0,
            "created_at": created_at,
        }
    )
    return record


async def run_debate(debate_id: str) -> None:
    """Run the LangGraph engine to completion, persisting state as it goes.

    Errors are caught and persisted as `status=error`; this function never
    raises so a background task wrapper can fire-and-forget.
    """
    record = get_debate(debate_id)
    if record is None:
        log.error("run_debate: unknown debate id %s", debate_id)
        return

    started = time.monotonic()
    record["status"] = "running"
    _atomic_write_json(_debate_dir(debate_id) / "debate.json", record)
    _patch_index(debate_id, status="running")
    broadcaster.publish(debate_id, Event.phase("intro"))

    turn_counter = {"i": 0}
    # `first_votes` captures each agent's INITIAL vote (from the new
    # `initial_voting` graph node, before the cross-party debate). The
    # `previous_votes` running map is what each subsequent vote is compared
    # against on the fly so SSE `vote_change` events fire correctly. At the
    # end of the run, the persisted votes.json compares each final Vote
    # against `first_votes` so the Persuasion Timeline shows the initial →
    # final delta.
    first_votes: dict[str, str] = {}
    previous_votes: dict[str, str] = {}
    phase_state: dict[str, str | None] = {"current": None}
    transcript_path = _debate_dir(debate_id) / "transcript.jsonl"
    transcript_path.parent.mkdir(parents=True, exist_ok=True)

    async def append_transcript_line(payload: dict[str, Any]) -> None:
        async with db._debate_lock(debate_id):
            with transcript_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(payload, ensure_ascii=False) + "\n")

    loop = asyncio.get_running_loop()

    def emit(item: AgentMessage | Vote) -> None:
        """Sync callback invoked by graph nodes. Persist + publish SSE."""
        if isinstance(item, AgentMessage):
            turn_counter["i"] += 1
            payload = _serialize_message(item, turn_index=turn_counter["i"])
            # Phase transition?
            if phase_state["current"] != payload["phase"]:
                phase_state["current"] = payload["phase"]
                broadcaster.publish(debate_id, Event.phase(payload["phase"]))
            broadcaster.publish(
                debate_id,
                Event.turn_start(
                    agent=item.agent_id, party=item.party, phase=payload["phase"]
                ),
            )
            broadcaster.publish(debate_id, Event.turn_end(payload))
            asyncio.run_coroutine_threadsafe(append_transcript_line(payload), loop)
        elif isinstance(item, Vote):
            # Capture the first vote per agent — this is the "initial position"
            # used for the persuasion delta.
            first_votes.setdefault(item.agent_id, item.vote)
            payload = _serialize_vote(item, previous=previous_votes)
            if payload["changed"] and payload.get("from"):
                broadcaster.publish(
                    debate_id,
                    Event.vote_change(agent=item.agent_id, from_=payload["from"], to=item.vote),
                )
            broadcaster.publish(debate_id, Event.vote(payload))
            previous_votes[item.agent_id] = item.vote

    try:
        cfg: dict[str, Any] = record["config"]
        result = await run_negotiation(
            proposal_text=record["proposal"],
            max_rounds=int(cfg["max_rounds"]),
            display_callback=emit,
            model=cfg.get("model"),
            temperature=cfg.get("temperature"),
            parties=cfg.get("parties"),
            passage_rule=cfg.get("passage_rule"),
            seat_config=cfg.get("seat_config"),
        )
    except Exception as e:
        log.exception("debate %s failed", debate_id)
        record["status"] = "error"
        record["error"] = str(e)
        _atomic_write_json(_debate_dir(debate_id) / "debate.json", record)
        _patch_index(debate_id, status="error")
        broadcaster.mark_done(debate_id, Event.error(str(e)))
        broadcaster.publish(debate_id, Event.done())
        return

    # Pull per-party votes from the dict-keyed state, falling back to the
    # legacy republican_votes / democrat_votes fields when the engine ran in
    # back-compat mode.
    votes_by_party: dict[str, list[Vote]] = dict(result.get("votes_by_party") or {})
    if not votes_by_party.get("republican") and result.get("republican_votes"):
        votes_by_party["republican"] = list(result["republican_votes"])
    if not votes_by_party.get("democrat") and result.get("democrat_votes"):
        votes_by_party["democrat"] = list(result["democrat_votes"])

    # Prefer the VotingResult the resolution node already computed (it applied
    # the debate's passage rule); recompute only if an older engine state
    # didn't carry one.
    voting = result.get("voting_result") or determine_final_result(
        votes_by_party,
        rules=VotingRules(rule=cfg.get("passage_rule") or "majority"),
        seat_weights=cfg.get("seat_config"),
    )
    final_status = "passed" if voting.passed else "rejected"
    if result.get("final_result") == "amended":
        final_status = "amended"

    # Persist votes — serialize each FINAL vote against the agent's FIRST vote
    # so `changed` / `from` reflect the persuasion delta. (Re-using
    # `previous_votes` here was the M5 bug — by this point it equals the final
    # vote per agent and `changed` is always False.)
    votes_payload: list[dict[str, Any]] = []
    party_order = cfg.get("parties") or list(votes_by_party.keys())
    for party in party_order:
        party_weight = voting.weights_by_party.get(party) if voting.weighted else None
        for v in votes_by_party.get(party, []):
            votes_payload.append(
                _serialize_vote(v, previous=first_votes, weight=party_weight)
            )
    _atomic_write_json(
        _debate_dir(debate_id) / "votes.json",
        {"votes": votes_payload},
    )

    amendments = result.get("amendments_proposed") or []
    sponsors: dict[str, list[str]] = result.get("amendment_sponsors") or {}
    amendments_payload: list[dict[str, Any]] = []
    for i, text in enumerate(amendments):
        sponsor_ids = sponsors.get(text) or []
        amendments_payload.append(
            {
                "id": f"am{i + 1}",
                "text": text,
                "by": sponsor_ids[0] if sponsor_ids else None,
                "sponsors": sponsor_ids,
                "status": "proposed",
            }
        )
    _atomic_write_json(
        _debate_dir(debate_id) / "amendments.json",
        {"amendments": amendments_payload},
    )

    tally = {
        "support": voting.total_support,
        "oppose": voting.total_oppose,
        "abstain": voting.total_abstain,
    }
    duration = int(time.monotonic() - started)
    record["status"] = final_status
    record["result"] = final_status
    record["tally"] = tally
    record["voting"] = {
        "rule": voting.rule,
        "required": voting.required,
        "margin": voting.margin,
        "bipartisan": voting.bipartisan,
        "weighted": voting.weighted,
        "weighted_support": voting.weighted_support,
        "weighted_oppose": voting.weighted_oppose,
    }
    record["completed_at"] = _now()
    record["duration_s"] = duration
    _atomic_write_json(_debate_dir(debate_id) / "debate.json", record)
    _upsert_index(
        {
            "id": record["id"],
            "title": record["title"],
            "status": final_status,
            "rounds": int(cfg["max_rounds"]),
            "support": tally["support"],
            "oppose": tally["oppose"],
            "abstain": tally["abstain"],
            "amendments": len(amendments_payload),
            "model": cfg.get("model"),
            "temperature": cfg.get("temperature"),
            "duration_s": duration,
            "created_at": record["created_at"],
        }
    )

    broadcaster.mark_done(
        debate_id,
        Event.result({"result": final_status, "tally": tally}),
    )
    broadcaster.publish(debate_id, Event.done())
