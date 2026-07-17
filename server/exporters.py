"""Debate exporters — PDF, Markdown, JSON.

Each export carries the simulation disclaimer (hard requirement from the
handoff). The PDF uses reportlab so it stays pure-Python with no system deps.
"""
from __future__ import annotations

import io
import json
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from . import db


DISCLAIMER = (
    "Simulation. All personas are AI approximations of public political "
    "archetypes for research and modeling — not the real individuals, and "
    "not statements of fact, endorsement, or prediction. Portraits are "
    "official public-domain or freely-licensed photos (see ATTRIBUTIONS) "
    "and imply no endorsement."
)

PHASE_LABEL = {
    "intro": "Opening Remarks",
    "advisor_discussion": "Caucus Analysis",
    "assistant_research": "Staff Research",
    "synthesis": "Position Synthesis",
    "cross_party_debate": "Cross-Party Debate",
    "markup": "Amendment Markup",
    "markup_debate": "Debate on the Amended Motion",
}

_RULE_LABEL = {
    "majority": "Simple majority",
    "three_fifths": "3/5 cloture",
    "two_thirds": "2/3 supermajority",
}


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------

def to_markdown(
    *,
    debate: dict[str, Any],
    turns: list[dict[str, Any]],
    votes: list[dict[str, Any]],
    amendments: list[dict[str, Any]],
) -> str:
    lines: list[str] = []
    lines.append(f"# {debate['title']}")
    lines.append("")
    lines.append(f"> _{DISCLAIMER}_")
    lines.append("")
    lines.append(f"**Status:** {debate['status'].upper()}")
    cfg = debate.get("config", {})
    lines.append(
        f"**Model:** `{cfg.get('model', '?')}` · "
        f"**Temperature:** {cfg.get('temperature', '?')} · "
        f"**Rounds:** {cfg.get('max_rounds', '?')} · "
        f"**Passage rule:** {_RULE_LABEL.get(cfg.get('passage_rule', 'majority'), cfg.get('passage_rule'))}"
    )
    voting = debate.get("voting") or {}
    if voting.get("required"):
        lines.append(f"**Required to pass:** {voting['required']} support votes")
    if debate.get("created_at"):
        lines.append(f"**Created:** {debate['created_at']}")
    if debate.get("completed_at"):
        lines.append(f"**Completed:** {debate['completed_at']}")
    tally = debate.get("tally", {})
    lines.append(
        f"**Tally:** {tally.get('support', 0)} for · "
        f"{tally.get('abstain', 0)} abstain · "
        f"{tally.get('oppose', 0)} against"
    )
    lines.append("")
    versions = debate.get("proposal_versions") or []
    if versions:
        final_v = versions[-1]
        lines.append(f"## Proposal (as amended, v{final_v.get('version')})")
        lines.append(final_v.get("text", ""))
        lines.append("")
        lines.append("### As introduced")
        lines.append(debate.get("proposal", ""))
    else:
        lines.append("## Proposal")
        lines.append(debate.get("proposal", ""))
    lines.append("")

    if turns:
        lines.append("## Transcript")
        last_phase: str | None = None
        for t in turns:
            phase = t.get("phase", "")
            if phase != last_phase:
                lines.append("")
                lines.append(f"### {PHASE_LABEL.get(phase, phase or 'Phase')}")
                last_phase = phase
            who = t.get("name") or t.get("agent", "?")
            lines.append(f"**{who}** ({t.get('party', '?')}, {t.get('role', '?')}):")
            lines.append("")
            lines.append(t.get("content", "").strip())
            lines.append("")

    if votes:
        lines.append("## Vote Roll Call")
        for v in votes:
            who = v.get("name") or v.get("agent", "?")
            vote = v.get("vote", "?").upper()
            changed = ""
            if v.get("changed") and v.get("from"):
                changed = f" (changed from {v['from']})"
            reasoning = v.get("reasoning", "")
            lines.append(f"- **{who}** ({v.get('party', '?')}): {vote}{changed} — {reasoning}")
        lines.append("")

    if amendments:
        lines.append("## Amendments")
        for i, a in enumerate(amendments, 1):
            lines.append(f"{i}. _{a.get('status', 'proposed')}_ — {a.get('text', '')}")
        lines.append("")

    lines.append("---")
    lines.append(f"_{DISCLAIMER}_")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# JSON
# ---------------------------------------------------------------------------

def to_json(
    *,
    debate: dict[str, Any],
    turns: list[dict[str, Any]],
    votes: list[dict[str, Any]],
    amendments: list[dict[str, Any]],
) -> str:
    payload = {
        "disclaimer": DISCLAIMER,
        "debate": debate,
        "transcript": turns,
        "votes": votes,
        "amendments": amendments,
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------

GOLD = colors.HexColor("#9A7C32")
INK = colors.HexColor("#0A1626")
INK_MUTE = colors.HexColor("#5A6478")
DEM_BLUE = colors.HexColor("#2E5AA8")
REP_RED = colors.HexColor("#C0392B")
NEUTRAL_PARTY = colors.HexColor("#9A8C6B")


def _party_color(party_id: str | None) -> colors.Color:
    """Look up a party's color in the registry, with a neutral fallback so
    custom parties get their configured palette in the PDF too."""
    if not party_id:
        return NEUTRAL_PARTY
    try:
        record = db.get_party(party_id)
    except Exception:
        record = None
    raw = (record or {}).get("color")
    if isinstance(raw, str) and raw.startswith("#") and len(raw) == 7:
        try:
            return colors.HexColor(raw)
        except ValueError:
            return NEUTRAL_PARTY
    return NEUTRAL_PARTY
PASS_GREEN = colors.HexColor("#3E9B6E")


def _make_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    h1 = ParagraphStyle(
        "RevTitle",
        parent=base["Heading1"],
        fontName="Times-Bold",
        fontSize=22,
        leading=26,
        textColor=INK,
        spaceAfter=10,
    )
    eyebrow = ParagraphStyle(
        "RevEyebrow",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=GOLD,
        spaceAfter=6,
    )
    body = ParagraphStyle(
        "RevBody",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=INK,
        spaceAfter=8,
    )
    h2 = ParagraphStyle(
        "RevH2",
        parent=base["Heading2"],
        fontName="Times-Bold",
        fontSize=14,
        leading=18,
        textColor=INK,
        spaceBefore=10,
        spaceAfter=8,
    )
    quote = ParagraphStyle(
        "RevQuote",
        parent=base["Normal"],
        fontName="Times-Italic",
        fontSize=11,
        leading=16,
        leftIndent=18,
        rightIndent=18,
        textColor=INK,
        spaceAfter=10,
    )
    small = ParagraphStyle(
        "RevSmall",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=INK_MUTE,
    )
    return {"h1": h1, "h2": h2, "eyebrow": eyebrow, "body": body, "quote": quote, "small": small}


def to_pdf(
    *,
    debate: dict[str, Any],
    turns: list[dict[str, Any]],
    votes: list[dict[str, Any]],
    amendments: list[dict[str, Any]],
) -> bytes:
    buf = io.BytesIO()

    def _footer(canvas: Any, doc: Any) -> None:
        canvas.saveState()
        canvas.setFont("Helvetica-Oblique", 7.5)
        canvas.setFillColor(INK_MUTE)
        canvas.drawString(0.75 * inch, 0.5 * inch, DISCLAIMER)
        canvas.setFont("Helvetica", 7.5)
        canvas.drawRightString(
            LETTER[0] - 0.75 * inch, 0.5 * inch, f"Page {doc.page}"
        )
        canvas.restoreState()

    doc = SimpleDocTemplate(
        buf,
        pagesize=LETTER,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        title=f"Revolution — {debate.get('title', 'Debate')}",
    )
    styles = _make_styles()
    flow: list[Any] = []

    flow.append(Paragraph("Revolution · Deliberation Engine", styles["eyebrow"]))
    flow.append(Paragraph(_html_escape(debate.get("title", "Untitled")), styles["h1"]))

    status_color = (
        PASS_GREEN
        if debate.get("status") in ("passed", "amended")
        else REP_RED
        if debate.get("status") == "rejected"
        else INK_MUTE
    )
    cfg = debate.get("config", {})
    tally = debate.get("tally", {})
    summary = (
        f"<font color='{_hex(status_color)}'><b>{debate.get('status', '?').upper()}</b></font> · "
        f"Tally <b>{tally.get('support', 0)}–{tally.get('oppose', 0)}</b>"
        + (f" ({tally.get('abstain', 0)} abstaining)" if tally.get("abstain") else "")
        + f" · Model <font name='Helvetica-Bold'>{cfg.get('model', '?')}</font>"
        f" · Temperature {cfg.get('temperature', '?')}"
        f" · {cfg.get('max_rounds', '?')} round(s)"
        f" · {_RULE_LABEL.get(cfg.get('passage_rule', 'majority'), cfg.get('passage_rule'))}"
    )
    voting = debate.get("voting") or {}
    if voting.get("required"):
        summary += f" · {voting['required']} needed to pass"
    flow.append(Paragraph(summary, styles["body"]))
    flow.append(Spacer(1, 8))

    versions = debate.get("proposal_versions") or []
    if versions:
        final_v = versions[-1]
        flow.append(Paragraph(f"The Motion (as amended, v{final_v.get('version')})", styles["h2"]))
        flow.append(Paragraph(_html_escape(final_v.get("text", "")), styles["quote"]))
        flow.append(Paragraph("As introduced", styles["h2"]))
        flow.append(Paragraph(_html_escape(debate.get("proposal", "")), styles["quote"]))
    else:
        flow.append(Paragraph("The Motion", styles["h2"]))
        flow.append(Paragraph(_html_escape(debate.get("proposal", "")), styles["quote"]))

    if turns:
        flow.append(Paragraph("Transcript", styles["h2"]))
        last_phase: str | None = None
        for t in turns:
            phase = t.get("phase", "")
            if phase != last_phase:
                flow.append(Spacer(1, 4))
                flow.append(
                    Paragraph(
                        PHASE_LABEL.get(phase, phase or "Phase").upper(), styles["eyebrow"]
                    )
                )
                last_phase = phase
            who = t.get("name") or t.get("agent", "?")
            party_color = _party_color(t.get("party"))
            header = (
                f"<font color='{_hex(party_color)}'><b>{_html_escape(who)}</b></font>"
                f" <font color='{_hex(INK_MUTE)}'>· {t.get('role', '?')}</font>"
            )
            flow.append(Paragraph(header, styles["body"]))
            flow.append(Paragraph(_html_escape(t.get("content", "")), styles["body"]))

    if votes:
        flow.append(Paragraph("Vote Roll Call", styles["h2"]))
        rows: list[list[str]] = [["Agent", "Party", "Vote", "Reasoning"]]
        for v in votes:
            who = v.get("name") or v.get("agent", "?")
            vote = v.get("vote", "?").upper()
            if v.get("changed"):
                vote = f"{vote} ←"
            rows.append(
                [
                    who,
                    v.get("party", "?"),
                    vote,
                    v.get("reasoning", "")[:120],
                ]
            )
        table = Table(rows, colWidths=[1.6 * inch, 0.9 * inch, 0.7 * inch, 3.5 * inch])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EBE4D4")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), INK),
                    ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 9),
                    ("FONT", (0, 1), (-1, -1), "Helvetica", 8.5),
                    ("LINEBELOW", (0, 0), (-1, 0), 1, INK),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F3E8")]),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        flow.append(table)

    if amendments:
        flow.append(Spacer(1, 12))
        flow.append(Paragraph("Amendments", styles["h2"]))
        for i, a in enumerate(amendments, 1):
            line = f"<b>{i:02d}.</b> {_html_escape(a.get('text', ''))} <i>({a.get('status', 'proposed')})</i>"
            flow.append(Paragraph(line, styles["body"]))

    doc.build(flow, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()


def _hex(c: colors.Color) -> str:
    return "#" + c.hexval()[2:]


def _html_escape(s: str) -> str:
    if not s:
        return ""
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br/>")
    )
