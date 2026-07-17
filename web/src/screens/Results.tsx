import { useEffect, useMemo, useRef, useState } from "react";
import type { DebateDetail } from "../api";
import { api } from "../api";
import { Avatar } from "../components/Avatar";
import { Btn } from "../components/Btn";
import { Card } from "../components/Card";
import { TallyBar } from "../components/Card";
import { Icon } from "../components/Icon";
import { Seal } from "../components/Seal";
import { PartyTag, PostureTag, StatusTag, VOTE_META, VoteTag } from "../components/Tags";
import { useWindowWidth } from "../hooks";
import { ROLE_META } from "../meta";
import { T, partyBright, partyColor, partyLabel } from "../theme";
import type {
  Amendment,
  Persona,
  PersonaSummary,
  Turn,
  VoteRecord,
  VoteValue,
} from "../types";
import ReactMarkdown from "react-markdown";
import { ExportModal } from "./ExportModal";

interface ResultsProps {
  nav: (route: string, param?: string) => void;
  param?: string;
}

type Tab = "overview" | "breakdown" | "timeline" | "transcript" | "amendments";

const PHASE_LABEL: Record<string, string> = {
  intro: "Opening Remarks",
  advisor_discussion: "Caucus Analysis",
  assistant_research: "Staff Research",
  synthesis: "Position Synthesis",
  cross_party_debate: "Cross-Party Debate",
  markup: "Amendment Markup",
  markup_debate: "Debate on the Amended Motion",
};

export function Results({ nav, param }: ResultsProps) {
  const id = param;
  const [debate, setDebate] = useState<DebateDetail | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [votes, setVotes] = useState<VoteRecord[]>([]);
  const [amendments, setAmendments] = useState<Amendment[]>([]);
  const [showOriginalMotion, setShowOriginalMotion] = useState(false);
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [composingAgent, setComposingAgent] = useState<string | null>(null);
  const [livePhase, setLivePhase] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("overview");
  const [error, setError] = useState<string | null>(null);
  const [exportOpen, setExportOpen] = useState(false);
  const [editingTitle, setEditingTitle] = useState(false);
  const [titleDraft, setTitleDraft] = useState("");
  const [showDelete, setShowDelete] = useState(false);

  const persistTitle = async () => {
    setEditingTitle(false);
    if (!debate || !titleDraft.trim() || titleDraft.trim() === debate.title) return;
    try {
      const updated = await api.updateDebate(debate.id, { title: titleDraft.trim() });
      setDebate(updated);
    } catch (e) {
      setError(String((e as Error).message || e));
    }
  };

  const handleDelete = async () => {
    if (!debate) return;
    try {
      await api.deleteDebate(debate.id);
      nav("dashboard");
    } catch (e) {
      setError(String((e as Error).message || e));
    }
  };

  // Initial fetch + auto-refresh while the debate is still running.
  useEffect(() => {
    if (!id) return;
    setError(null);
    let cancelled = false;
    const fetchAll = async (): Promise<DebateDetail | null> => {
      try {
        const [d, t, v, a] = await Promise.all([
          api.getDebate(id),
          api.getTranscript(id),
          api.getVotes(id),
          api.getAmendments(id),
        ]);
        if (cancelled) return null;
        setDebate(d);
        setTurns(t.turns);
        setVotes(v.votes);
        setAmendments(a.amendments);
        return d;
      } catch (e) {
        if (!cancelled) setError(String((e as Error).message || e));
        return null;
      }
    };
    let timer: ReturnType<typeof setInterval> | null = null;
    void fetchAll().then((d) => {
      if (!d) return;
      if (d.status === "running" || d.status === "pending") {
        timer = setInterval(() => {
          void fetchAll().then((next) => {
            if (next && next.status !== "running" && next.status !== "pending" && timer) {
              clearInterval(timer);
              timer = null;
            }
          });
        }, 5000);
      }
    });
    return () => {
      cancelled = true;
      if (timer) clearInterval(timer);
    };
  }, [id]);

  // Lazy-load all persona records once — needed by the chamber visualization
  // (seat lookup) and the recent-activity feed.
  useEffect(() => {
    let cancelled = false;
    void api.listPersonas().then(async (r) => {
      const detailed = await Promise.all(
        r.personas.map((s: PersonaSummary) => api.getPersona(s.id).catch(() => null)),
      );
      if (cancelled) return;
      setPersonas(detailed.filter((p): p is Persona => p !== null));
    });
    return () => {
      cancelled = true;
    };
  }, []);

  // Live "who's speaking right now" signal from SSE. The polling loop above
  // catches completed turns at 5s resolution; SSE turn_start gives the chamber
  // sub-second feedback the moment the LLM begins generating.
  useEffect(() => {
    if (!id || !debate) return;
    if (debate.status !== "running" && debate.status !== "pending") {
      setComposingAgent(null);
      setLivePhase(null);
      return;
    }
    const es = new EventSource(`/api/debates/${id}/stream`);
    const onTurnStart = (e: MessageEvent) => {
      const data = JSON.parse(e.data) as { agent: string; phase: string };
      if (data.agent !== "system") setComposingAgent(data.agent);
      setLivePhase(data.phase);
    };
    const onTurnEnd = () => setComposingAgent(null);
    const onPhase = (e: MessageEvent) => {
      const data = JSON.parse(e.data) as { phase: string };
      setLivePhase(data.phase);
    };
    const onDone = () => {
      setComposingAgent(null);
      es.close();
    };
    es.addEventListener("phase", onPhase);
    es.addEventListener("turn_start", onTurnStart);
    es.addEventListener("turn_end", onTurnEnd);
    es.addEventListener("done", onDone);
    es.addEventListener("error", onDone);
    return () => {
      es.close();
    };
  }, [id, debate?.status]);

  if (!id) {
    return (
      <div style={{ maxWidth: 1080, margin: "0 auto", padding: "26px 40px 60px" }}>
        <Card pad={20}>No debate selected.</Card>
      </div>
    );
  }
  if (error) {
    return (
      <div style={{ maxWidth: 1080, margin: "0 auto", padding: "26px 40px 60px" }}>
        <Card pad={20} style={{ borderLeft: "3px solid var(--reject)" }}>
          <div style={{ color: "var(--reject)" }}>{error}</div>
        </Card>
      </div>
    );
  }
  if (!debate) {
    return (
      <div style={{ maxWidth: 1080, margin: "0 auto", padding: "26px 40px 60px" }}>
        <div style={{ color: "var(--txt-faint)", fontSize: 14 }}>Loading results…</div>
      </div>
    );
  }

  const tally = debate.tally;
  const amended = debate.status === "amended";
  const passed = debate.status === "passed" || amended;
  const changes = votes.filter((v) => v.changed);
  const versions = debate.proposal_versions ?? [];
  const finalVersion = versions.length ? versions[versions.length - 1] : null;

  const TABS: { id: Tab; label: string; icon: string; badge?: number }[] = [
    { id: "overview", label: "Overview", icon: "dashboard" },
    { id: "breakdown", label: "Vote Breakdown", icon: "results" },
    { id: "timeline", label: "Persuasion Timeline", icon: "refresh", badge: changes.length },
    { id: "transcript", label: "Transcript", icon: "transcript" },
    { id: "amendments", label: "Amendments", icon: "doc", badge: amendments.length },
  ];

  return (
    <div style={{ maxWidth: 1120, margin: "0 auto", padding: "26px 40px 60px" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 18, fontSize: 13 }}>
        <button
          onClick={() => nav("dashboard")}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            background: "none",
            border: "none",
            color: "var(--txt-mute)",
            fontSize: 13,
            fontWeight: 600,
          }}
        >
          <Icon name="chevL" size={16} /> Dashboard
        </button>
      </div>

      <div
        className="ink-panel"
        style={{
          padding: "30px 34px",
          marginBottom: 24,
          borderTop: `3px solid ${amended ? "var(--gold-bright)" : passed ? "var(--pass)" : "var(--reject)"}`,
          position: "relative",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            position: "absolute",
            right: -30,
            top: -30,
            opacity: 0.05,
            pointerEvents: "none",
          }}
        >
          <Seal size={220} />
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 24, alignItems: "flex-start" }}>
          <div style={{ flex: 1 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 11, marginBottom: 12 }}>
              <StatusTag status={debate.status} />
              <span className="mono" style={{ fontSize: 12, color: "var(--txt-faint)" }}>
                {new Date(debate.created_at).toLocaleDateString()} · {debate.config.max_rounds} round
                {debate.config.max_rounds > 1 ? "s" : ""} · {debate.config.model}
                {debate.config.passage_rule === "three_fifths" && " · 3⁄5 cloture rule"}
                {debate.config.passage_rule === "two_thirds" && " · 2⁄3 supermajority rule"}
                {debate.config.use_seat_weights && " · seat-weighted"}
                {debate.voting && debate.voting.required > 0 && ` · ${debate.voting.required} to pass`}
                {debate.voting?.weighted &&
                  ` · weighted ${debate.voting.weighted_support ?? 0}–${debate.voting.weighted_oppose ?? 0}`}
              </span>
            </div>
            {editingTitle ? (
              <input
                value={titleDraft}
                autoFocus
                onChange={(e) => setTitleDraft(e.target.value)}
                onBlur={() => void persistTitle()}
                onKeyDown={(e) => {
                  if (e.key === "Enter") void persistTitle();
                  if (e.key === "Escape") {
                    setTitleDraft(debate.title);
                    setEditingTitle(false);
                  }
                }}
                style={{
                  fontFamily: "var(--serif)",
                  fontSize: 28,
                  fontWeight: 600,
                  width: "100%",
                  maxWidth: 640,
                  background: "var(--ink)",
                  border: "1px solid var(--gold-deep)",
                  borderRadius: "var(--r-md)",
                  color: "var(--txt)",
                  padding: "4px 10px",
                  margin: "0 0 8px",
                  outline: "none",
                }}
              />
            ) : (
              <h1
                className="serif"
                style={{
                  fontSize: 28,
                  fontWeight: 600,
                  margin: "0 0 8px",
                  maxWidth: 640,
                  lineHeight: 1.15,
                  cursor: "text",
                }}
                title="Click to rename"
                onClick={() => {
                  setTitleDraft(debate.title);
                  setEditingTitle(true);
                }}
              >
                {debate.title}
              </h1>
            )}
            {finalVersion ? (
              <>
                <div style={{ display: "flex", alignItems: "center", gap: 8, margin: "0 0 6px" }}>
                  <span
                    className="mono"
                    style={{
                      fontSize: 11,
                      color: "var(--gold-bright)",
                      border: "1px solid var(--gold-deep)",
                      borderRadius: 999,
                      padding: "2px 9px",
                    }}
                  >
                    v{finalVersion.version} — as amended
                  </span>
                  <button
                    onClick={() => setShowOriginalMotion((s) => !s)}
                    style={{
                      background: "none",
                      border: "none",
                      color: "var(--txt-faint)",
                      fontSize: 11.5,
                      textDecoration: "underline",
                      cursor: "pointer",
                    }}
                  >
                    {showOriginalMotion ? "show as amended" : "show as introduced"}
                  </button>
                </div>
                <p style={{ fontSize: 14, color: "var(--txt-mute)", maxWidth: 660, lineHeight: 1.6, margin: 0 }}>
                  {showOriginalMotion ? debate.proposal : finalVersion.text}
                </p>
              </>
            ) : (
              <p style={{ fontSize: 14, color: "var(--txt-mute)", maxWidth: 660, lineHeight: 1.6, margin: 0 }}>
                {debate.proposal}
              </p>
            )}
          </div>
          <div style={{ display: "flex", gap: 10, flexShrink: 0 }}>
            <Btn kind="primary" icon="download" onClick={() => setExportOpen(true)}>
              Export
            </Btn>
            <Btn kind="danger" icon="x" onClick={() => setShowDelete(true)}>
              Delete
            </Btn>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 30, marginTop: 26 }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: 16 }}>
            <div>
              <span className="serif" style={{ fontSize: 46, fontWeight: 600, color: "var(--support)" }}>
                {tally.support}
              </span>
              <span style={{ fontSize: 13, color: "var(--txt-faint)", marginLeft: 8, letterSpacing: ".1em" }}>
                FOR
              </span>
            </div>
            <span className="serif" style={{ fontSize: 30, color: "var(--txt-faint)" }}>–</span>
            <div>
              <span className="serif" style={{ fontSize: 46, fontWeight: 600, color: "var(--oppose)" }}>
                {tally.oppose}
              </span>
              <span style={{ fontSize: 13, color: "var(--txt-faint)", marginLeft: 8, letterSpacing: ".1em" }}>
                AGAINST
              </span>
            </div>
            {tally.abstain > 0 && (
              <div style={{ marginLeft: 8 }}>
                <span className="serif" style={{ fontSize: 30, fontWeight: 600, color: "var(--abstain)" }}>
                  {tally.abstain}
                </span>
                <span style={{ fontSize: 12, color: "var(--txt-faint)", marginLeft: 6, letterSpacing: ".1em" }}>
                  ABSTAIN
                </span>
              </div>
            )}
          </div>
          <div style={{ flex: 1, maxWidth: 420 }}>
            <TallyBar
              support={tally.support}
              oppose={tally.oppose}
              abstain={tally.abstain}
              height={12}
            />
          </div>
        </div>
      </div>

      <div
        style={{
          display: "flex",
          gap: 4,
          marginBottom: 24,
          borderBottom: "1px solid var(--ink-line)",
          overflowX: "auto",
          flexWrap: "nowrap",
        }}
      >
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              padding: "12px 18px",
              background: "none",
              border: "none",
              borderBottom: `2px solid ${tab === t.id ? "var(--gold)" : "transparent"}`,
              marginBottom: -1,
              color: tab === t.id ? "var(--txt)" : "var(--txt-faint)",
              fontSize: 13.5,
              fontWeight: 600,
              transition: "all .15s ease",
              whiteSpace: "nowrap",
              flexShrink: 0,
            }}
          >
            <Icon name={t.icon} size={15} />
            {t.label}
            {t.badge !== undefined && t.badge > 0 && (
              <span
                style={{
                  fontSize: 11,
                  padding: "1px 7px",
                  borderRadius: 999,
                  background: "var(--ink3)",
                  color: "var(--gold-bright)",
                }}
              >
                {t.badge}
              </span>
            )}
          </button>
        ))}
      </div>

      {tab === "overview" && (
        <Overview
          debate={debate}
          turns={turns}
          votes={votes}
          amendments={amendments}
          personas={personas}
          composingAgent={composingAgent}
          livePhase={livePhase}
          nav={nav}
        />
      )}
      {tab === "breakdown" && <Breakdown votes={votes} />}
      {tab === "timeline" && <Timeline changes={changes} />}
      {tab === "transcript" && <FullTranscript turns={turns} />}
      {tab === "amendments" && <Amendments amendments={amendments} />}

      <ExportModal
        open={exportOpen}
        onClose={() => setExportOpen(false)}
        debateId={debate.id}
        debateTitle={debate.title}
      />

      {showDelete && (
        <div
          onClick={() => setShowDelete(false)}
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 200,
            background: "rgba(5,10,18,0.72)",
            backdropFilter: "blur(6px)",
            display: "grid",
            placeItems: "center",
            padding: 24,
          }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="ink-panel rise"
            style={{ width: 420, padding: "22px 24px" }}
          >
            <div className="eyebrow" style={{ marginBottom: 8, color: "var(--reject)" }}>
              Remove debate
            </div>
            <div className="serif" style={{ fontSize: 19, fontWeight: 600, marginBottom: 12 }}>
              Delete “{debate.title}”?
            </div>
            <p
              style={{
                fontSize: 13.5,
                color: "var(--txt-mute)",
                lineHeight: 1.6,
                margin: 0,
              }}
            >
              Transcript, votes, amendments, and the dashboard row are permanently removed.
              This cannot be undone.
            </p>
            <div
              style={{
                display: "flex",
                justifyContent: "flex-end",
                gap: 10,
                marginTop: 18,
              }}
            >
              <Btn kind="ghost" onClick={() => setShowDelete(false)}>
                Cancel
              </Btn>
              <Btn kind="danger" icon="x" onClick={handleDelete}>
                Delete debate
              </Btn>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Chamber visualization — the legislative hemicycle. Used inside Overview as
// the centerpiece: seats light up live while a debate runs, and once it's
// finished each seat is colored by the agent's final vote.
// ---------------------------------------------------------------------------

interface ChamberSeat {
  agentId: string;
  x: number;
  y: number;
  r: number;
  head: boolean;
}

function describeArc(cx: number, cy: number, r: number, a1: number, a2: number): string {
  const p1 = {
    x: cx + Math.cos((a1 * Math.PI) / 180) * r,
    y: cy - Math.sin((a1 * Math.PI) / 180) * r,
  };
  const p2 = {
    x: cx + Math.cos((a2 * Math.PI) / 180) * r,
    y: cy - Math.sin((a2 * Math.PI) / 180) * r,
  };
  return `M ${p1.x} ${p1.y} A ${r} ${r} 0 0 1 ${p2.x} ${p2.y}`;
}

// Hand-tuned spans for the original D+R hemicycle. When the debate uses
// only those two parties we re-use these exact values so the look matches
// the M4–M5 chamber. For N>2 (or unknown party ids) we generate equal
// wedges procedurally.
const TWO_PARTY_LAYOUTS: Record<string, { head: number; span: [number, number] }> = {
  democrat: { head: 109, span: [173, 118] },
  republican: { head: 71, span: [62, 7] },
};

function buildChamber(personas: Persona[], partyIds: string[]): ChamberSeat[] {
  const seats: ChamberSeat[] = [];
  const cx = 500;
  const cy = 470;

  const useTwoPartyLayout =
    partyIds.length === 2 && partyIds.every((p) => p in TWO_PARTY_LAYOUTS);

  partyIds.forEach((party, partyIdx) => {
    const list = personas.filter((p) => p.party === party);
    const head = list.find((p) => p.role === "party_head");
    const rest = list.filter((p) => p.role !== "party_head").slice(0, 10);
    if (!head) return;

    let headDeg: number;
    let span: [number, number];
    if (useTwoPartyLayout) {
      const layout = TWO_PARTY_LAYOUTS[party];
      headDeg = layout.head;
      span = layout.span;
    } else {
      // Equal-width wedges across the 180° hemicycle, leftmost party first.
      const wedge = 180 / partyIds.length;
      const inner = wedge * 0.78; // small visual gap between adjacent wedges
      const center = 180 - (partyIdx + 0.5) * wedge;
      headDeg = center;
      span = [center + inner / 2, center - inner / 2];
    }

    const ha = (headDeg * Math.PI) / 180;
    seats.push({
      agentId: head.id,
      x: cx + Math.cos(ha) * 150,
      y: cy - Math.sin(ha) * 150,
      r: 30,
      head: true,
    });
    const rings = [
      { n: 3, r: 250 },
      { n: 3, r: 340 },
      { n: 4, r: 430 },
    ];
    let idx = 0;
    rings.forEach((ring) => {
      for (let i = 0; i < ring.n; i++) {
        const agent = rest[idx++];
        if (!agent) continue;
        const f = ring.n === 1 ? 0.5 : i / (ring.n - 1);
        const deg = span[0] + (span[1] - span[0]) * f;
        const a = (deg * Math.PI) / 180;
        seats.push({
          agentId: agent.id,
          x: cx + Math.cos(a) * ring.r,
          y: cy - Math.sin(a) * ring.r,
          r: 22,
          head: false,
        });
      }
    });
  });
  return seats;
}

function ChamberSvg({
  seats,
  personaById,
  activeId,
  voteMap,
  resolved,
  daisLabel,
  onSeat,
}: {
  seats: ChamberSeat[];
  personaById: Record<string, Persona>;
  activeId: string | null;
  voteMap: Record<string, VoteValue>;
  resolved: boolean;
  daisLabel: string;
  onSeat: (id: string) => void;
}) {
  return (
    <svg
      viewBox="0 0 1000 520"
      preserveAspectRatio="xMidYMid meet"
      style={{ width: "100%", height: "100%", display: "block" }}
    >
      <defs>
        <radialGradient id="daisGlow" cx="50%" cy="100%" r="80%">
          <stop offset="0%" stopColor="rgba(226,195,107,0.20)" />
          <stop offset="100%" stopColor="rgba(226,195,107,0)" />
        </radialGradient>
      </defs>
      <rect x="0" y="0" width="1000" height="520" fill="url(#daisGlow)" />
      {[250, 340, 430].map((r) => (
        <path
          key={r}
          d={describeArc(500, 470, r, 180, 0)}
          fill="none"
          stroke="var(--ink-line-soft)"
          strokeWidth="1"
          opacity="0.5"
        />
      ))}
      <g>
        <rect
          x="455"
          y="446"
          width="90"
          height="46"
          rx="6"
          fill="var(--ink2)"
          stroke="var(--gold-deep)"
          strokeWidth="1.2"
        />
        <rect
          x="470"
          y="436"
          width="60"
          height="14"
          rx="3"
          fill="var(--ink3)"
          stroke="var(--gold-deep)"
          strokeWidth="1"
        />
        <text
          x="500"
          y="474"
          textAnchor="middle"
          fontSize="11"
          fill="var(--gold)"
          fontFamily="var(--mono)"
          letterSpacing="1"
        >
          {resolved ? "RESOLVED" : daisLabel.toUpperCase().slice(0, 14)}
        </text>
      </g>
      {seats.map((s) => (
        <ChamberSeatNode
          key={s.agentId}
          seat={s}
          persona={personaById[s.agentId]}
          active={activeId === s.agentId}
          vote={voteMap[s.agentId]}
          onSeat={onSeat}
        />
      ))}
    </svg>
  );
}

function ChamberSeatNode({
  seat,
  persona,
  active,
  vote,
  onSeat,
}: {
  seat: ChamberSeat;
  persona: Persona | undefined;
  active: boolean;
  vote: VoteValue | undefined;
  onSeat: (id: string) => void;
}) {
  if (!persona) return null;
  const initials = persona.name
    .split(" ")
    .filter(Boolean)
    .slice(-2)
    .map((s) => s[0])
    .join("");
  const base = partyColor(persona.party);
  const bright = partyBright(persona.party);
  const voteCol =
    vote === "support"
      ? T.support
      : vote === "oppose"
        ? T.oppose
        : vote === "abstain"
          ? T.abstain
          : null;
  const ringCol = voteCol || (active ? T.goldBright : base);
  return (
    <g
      style={{ cursor: "pointer", transition: "all .3s ease" }}
      onClick={() => onSeat(persona.id)}
      transform={`translate(${seat.x},${seat.y})`}
    >
      {active && (
        <circle
          r={seat.r + 9}
          fill="none"
          stroke={T.goldBright}
          strokeWidth="2"
          opacity="0.8"
          style={{ animation: "ring 1.3s ease-out infinite" }}
        />
      )}
      <circle
        r={seat.r}
        fill={active ? bright : base}
        fillOpacity={active ? 0.9 : 0.32}
        stroke={ringCol}
        strokeWidth={active || voteCol ? 2.4 : 1.4}
        style={{
          transition: "all .3s ease",
          filter: active ? "drop-shadow(0 0 10px rgba(226,195,107,.5))" : "none",
        }}
      />
      {seat.head && (
        <circle
          r={seat.r + 4}
          fill="none"
          stroke={T.gold}
          strokeWidth="1"
          opacity="0.7"
          strokeDasharray="2 3"
        />
      )}
      <text
        textAnchor="middle"
        dy={seat.r * 0.34}
        fontSize={seat.r * 0.62}
        fontWeight={700}
        fill={active ? "#0A1626" : bright}
        fontFamily="var(--sans)"
      >
        {initials}
      </text>
      {persona.image_url && (
        <>
          <clipPath id={`seat-clip-${persona.id}`}>
            <circle r={seat.r - 1} />
          </clipPath>
          <image
            href={persona.image_url}
            x={-seat.r}
            y={-seat.r}
            width={seat.r * 2}
            height={seat.r * 2}
            preserveAspectRatio="xMidYMid slice"
            clipPath={`url(#seat-clip-${persona.id})`}
            opacity={active ? 1 : 0.88}
            style={{ pointerEvents: "none" }}
          />
          <circle
            r={seat.r}
            fill="none"
            stroke={ringCol}
            strokeWidth={active || voteCol ? 2.4 : 1.4}
            style={{ transition: "all .3s ease" }}
          />
        </>
      )}
      {voteCol && (
        <g transform={`translate(${seat.r * 0.62},${-seat.r * 0.62})`}>
          <circle r="7.5" fill="var(--ink)" stroke={voteCol} strokeWidth="1.6" />
          <path
            d={
              vote === "support"
                ? "M-3 0l2 2 4-4"
                : vote === "oppose"
                  ? "M-3 -3l6 6M3 -3l-6 6"
                  : "M0 0"
            }
            fill="none"
            stroke={voteCol}
            strokeWidth="1.8"
            strokeLinecap="round"
            transform="scale(0.9)"
          />
          {vote === "abstain" && <circle r="2" fill={voteCol} />}
        </g>
      )}
    </g>
  );
}

// ---------------------------------------------------------------------------
// Overview — at-a-glance live dashboard of the debate's state.
// ---------------------------------------------------------------------------

const PHASE_SEQ: { key: string; label: string }[] = [
  { key: "intro", label: "Opening" },
  { key: "advisor_discussion", label: "Caucus" },
  { key: "assistant_research", label: "Research" },
  { key: "synthesis", label: "Synthesis" },
  { key: "cross_party_debate", label: "Debate" },
  { key: "final_voting", label: "Vote" },
];

const PHASE_ORDER: { key: string; label: string; expected: (d: DebateDetail) => number }[] = [
  { key: "intro", label: "Opening Remarks", expected: () => 2 },
  { key: "advisor_discussion", label: "Caucus Analysis", expected: () => 8 },
  { key: "assistant_research", label: "Staff Research", expected: () => 12 },
  { key: "synthesis", label: "Position Synthesis", expected: () => 2 },
  {
    key: "cross_party_debate",
    label: "Cross-Party Debate",
    // Roughly a half-dozen turns per round (party heads + advisors).
    expected: (d) => Math.max(6, d.config.max_rounds * 4),
  },
  { key: "final_voting", label: "Final Vote", expected: () => 22 },
];

function Overview({
  debate,
  turns,
  votes,
  amendments,
  personas,
  composingAgent,
  livePhase,
  nav,
}: {
  debate: DebateDetail;
  turns: Turn[];
  votes: VoteRecord[];
  amendments: Amendment[];
  personas: Persona[];
  composingAgent: string | null;
  livePhase: string | null;
  nav: ResultsProps["nav"];
}) {
  const isLive = debate.status === "running" || debate.status === "pending";
  const resolved = !isLive;
  const width = useWindowWidth();
  const speakerTurns = useMemo(() => turns.filter((t) => t.agent !== "system"), [turns]);
  const turnsByPhase = useMemo(() => {
    const m: Record<string, Turn[]> = {};
    for (const t of speakerTurns) {
      (m[t.phase] = m[t.phase] || []).push(t);
    }
    return m;
  }, [speakerTurns]);

  // Chamber-specific derived state.
  const partyIds = useMemo(
    () => (debate.config.parties && debate.config.parties.length > 0
      ? debate.config.parties
      : ["democrat", "republican"]),
    [debate.config.parties],
  );
  const seats = useMemo(() => buildChamber(personas, partyIds), [personas, partyIds]);
  const personaById = useMemo(
    () => Object.fromEntries(personas.map((p) => [p.id, p])),
    [personas],
  );
  const voteMap = useMemo(
    () => Object.fromEntries(votes.map((v) => [v.agent, v.vote])),
    [votes],
  );
  // The "on the floor" agent — prefer the SSE live signal, fall back to the
  // last completed speaker turn (so the chamber doesn't go dark between
  // polling intervals).
  const lastSpeakerTurn = speakerTurns[speakerTurns.length - 1];
  const activeAgent = composingAgent || (isLive ? lastSpeakerTurn?.agent || null : null);
  const activeAgentPersona = activeAgent ? personaById[activeAgent] : null;
  const activeTurnForSpeaker = activeAgent
    ? speakerTurns.filter((t) => t.agent === activeAgent).slice(-1)[0]
    : undefined;
  const activePhase =
    livePhase || activeTurnForSpeaker?.phase || lastSpeakerTurn?.phase || "intro";
  const daisLabel = PHASE_LABEL[activePhase] || activePhase || "The Floor";

  const totalDelivered = speakerTurns.length;
  const totalExpected =
    PHASE_ORDER.reduce((acc, ph) => acc + ph.expected(debate), 0) - 22; // expected speech turns (excl. votes)
  const currentPhase = (() => {
    // The "active" phase is the one whose count is still below expected.
    for (const ph of PHASE_ORDER) {
      if (ph.key === "final_voting") continue;
      const done = (turnsByPhase[ph.key] || []).length;
      const expected = ph.expected(debate);
      if (done < expected) return ph.key;
    }
    return "final_voting";
  })();
  const currentPhaseLabel =
    PHASE_ORDER.find((p) => p.key === currentPhase)?.label || currentPhase;

  const elapsed = useMemo(() => {
    if (debate.duration_s != null) return debate.duration_s;
    const t0 = new Date(debate.created_at).getTime();
    return Math.max(0, Math.floor((Date.now() - t0) / 1000));
  }, [debate.created_at, debate.duration_s]);

  const persuasionCount = votes.filter((v) => v.changed).length;
  const tally = debate.tally;

  return (
    <div style={{ display: "grid", gap: 22 }}>
      {/* Chamber + active speaker -------------------------------------- */}
      <ChamberPanel
        debate={debate}
        seats={seats}
        personaById={personaById}
        activeAgent={activeAgent}
        activeAgentPersona={activeAgentPersona}
        activeTurnForSpeaker={activeTurnForSpeaker}
        activePhase={activePhase}
        daisLabel={daisLabel}
        voteMap={voteMap}
        resolved={resolved}
        composing={!!composingAgent && !activeTurnForSpeaker}
        nav={nav}
      />

      {/* Top stat tiles ------------------------------------------------- */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
          gap: 14,
        }}
      >
        <StatTile
          label="Current phase"
          value={isLive ? currentPhaseLabel : "Resolved"}
          accent={isLive ? "var(--gold-bright)" : "var(--pass)"}
          icon={isLive ? "clock" : "check"}
        />
        <StatTile
          label="Turns delivered"
          value={`${totalDelivered}`}
          sub={`of ~${totalExpected} expected`}
          icon="transcript"
        />
        <StatTile
          label="Votes cast"
          value={`${votes.length}`}
          sub={`of ${debate.config.parties.length * 11} agents`}
          icon="vote"
          accent={votes.length > 0 ? "var(--gold-bright)" : undefined}
        />
        <StatTile
          label="Runtime"
          value={fmtDuration(elapsed)}
          sub={isLive ? "ticking…" : `model ${debate.config.model}`}
          icon="bolt"
        />
      </div>

      {/* Middle row: phase progress + tally / persuasion ----------------- */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: width < 880 ? "1fr" : "1.4fr 1fr",
          gap: 22,
        }}
      >
        <Card pad={22}>
          <div className="eyebrow" style={{ marginBottom: 16 }}>
            Deliberation progress
          </div>
          <div style={{ display: "grid", gap: 12 }}>
            {PHASE_ORDER.map((ph) => {
              const done =
                ph.key === "final_voting" ? votes.length : (turnsByPhase[ph.key] || []).length;
              const expected = ph.expected(debate);
              const active = ph.key === currentPhase && isLive;
              const complete = done >= expected;
              const pct = Math.min(100, Math.round((done / Math.max(1, expected)) * 100));
              return (
                <div key={ph.key}>
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      fontSize: 13,
                      marginBottom: 5,
                    }}
                  >
                    <span
                      style={{
                        color: active
                          ? "var(--gold-bright)"
                          : complete
                            ? "var(--txt)"
                            : "var(--txt-mute)",
                        fontWeight: 600,
                        display: "flex",
                        alignItems: "center",
                        gap: 8,
                      }}
                    >
                      <span
                        style={{
                          width: 8,
                          height: 8,
                          borderRadius: "50%",
                          background: active
                            ? "var(--gold-bright)"
                            : complete
                              ? "var(--pass)"
                              : "var(--ink-line)",
                          boxShadow: active ? "0 0 8px var(--gold-bright)" : "none",
                          animation: active ? "blink 1.4s step-end infinite" : "none",
                        }}
                      />
                      {ph.label}
                    </span>
                    <span
                      className="mono"
                      style={{ color: "var(--txt-faint)", fontSize: 11.5 }}
                    >
                      {done}/{expected}
                    </span>
                  </div>
                  <div
                    style={{
                      height: 4,
                      borderRadius: 999,
                      background: "var(--ink)",
                      overflow: "hidden",
                    }}
                  >
                    <div
                      style={{
                        width: `${pct}%`,
                        height: "100%",
                        background: active
                          ? "linear-gradient(90deg, var(--gold), var(--gold-bright))"
                          : complete
                            ? "var(--pass)"
                            : "var(--ink-line)",
                        transition: "width .3s ease",
                      }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </Card>

        <div style={{ display: "grid", gap: 22 }}>
          <Card pad={22}>
            <div className="eyebrow" style={{ marginBottom: 14 }}>
              Live tally
            </div>
            {votes.length === 0 ? (
              <div
                style={{
                  color: "var(--txt-faint)",
                  fontSize: 13,
                  padding: "20px 0",
                  textAlign: "center",
                  lineHeight: 1.5,
                }}
              >
                {isLive ? "Voting hasn't begun." : "No votes recorded."}
                <div style={{ fontSize: 11.5, marginTop: 6 }}>
                  Final tallies appear as the chamber votes.
                </div>
              </div>
            ) : (
              <>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    fontSize: 12,
                    marginBottom: 9,
                    fontWeight: 600,
                  }}
                >
                  <span style={{ color: "var(--support)" }}>{tally.support} For</span>
                  <span style={{ color: "var(--abstain)" }}>{tally.abstain} Abstain</span>
                  <span style={{ color: "var(--oppose)" }}>{tally.oppose} Against</span>
                </div>
                <TallyBar
                  support={tally.support}
                  oppose={tally.oppose}
                  abstain={tally.abstain}
                  height={12}
                />
                <div
                  style={{
                    marginTop: 14,
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    fontSize: 12,
                    color: "var(--txt-mute)",
                  }}
                >
                  <span>Persuasion shifts</span>
                  <span
                    style={{
                      color: persuasionCount > 0 ? "var(--gold-bright)" : "var(--txt-faint)",
                      fontWeight: 600,
                    }}
                  >
                    {persuasionCount} flipped
                  </span>
                </div>
              </>
            )}
          </Card>

          <Card pad={22}>
            <div className="eyebrow" style={{ marginBottom: 14 }}>
              Caucus split
            </div>
            <CaucusBars votes={votes} debate={debate} />
          </Card>
        </div>
      </div>

      {/* Recent activity feed ------------------------------------------- */}
      <Card pad={22}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: 14,
          }}
        >
          <div className="eyebrow">Recent activity</div>
          {isLive && (
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 7,
                fontSize: 11,
                color: "var(--gold-bright)",
                fontWeight: 700,
                letterSpacing: ".1em",
                textTransform: "uppercase",
              }}
            >
              <span
                style={{
                  width: 7,
                  height: 7,
                  borderRadius: "50%",
                  background: "var(--gold-bright)",
                  animation: "blink 1.4s step-end infinite",
                }}
              />
              Live
            </span>
          )}
        </div>
        {speakerTurns.length === 0 ? (
          <div
            style={{
              color: "var(--txt-faint)",
              fontSize: 13,
              padding: "24px 0",
              textAlign: "center",
            }}
          >
            The chamber hasn't spoken yet.
          </div>
        ) : (
          <div style={{ display: "grid", gap: 12 }}>
            {speakerTurns.slice(-5).reverse().map((t) => (
              <RecentTurn key={t.id} t={t} />
            ))}
          </div>
        )}
      </Card>

      {/* Amendments preview --------------------------------------------- */}
      {amendments.length > 0 && (
        <Card pad={22}>
          <div className="eyebrow" style={{ marginBottom: 14 }}>
            Amendments ({amendments.length})
          </div>
          <div style={{ display: "grid", gap: 10 }}>
            {amendments.slice(0, 3).map((a, i) => (
              <div
                key={a.id}
                style={{
                  display: "flex",
                  gap: 14,
                  alignItems: "center",
                  padding: "10px 12px",
                  borderRadius: "var(--r-md)",
                  background: "var(--ink)",
                  border: "1px solid var(--ink-line)",
                }}
              >
                <span
                  className="serif"
                  style={{
                    fontSize: 15,
                    fontWeight: 600,
                    color: "var(--gold-deep)",
                    width: 22,
                  }}
                >
                  {String(i + 1).padStart(2, "0")}
                </span>
                <p
                  style={{
                    flex: 1,
                    fontSize: 13,
                    margin: 0,
                    color: "var(--txt-mute)",
                    lineHeight: 1.5,
                  }}
                >
                  {a.text}
                </p>
                <StatusTag status={a.status} />
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}

function ChamberPanel({
  debate,
  seats,
  personaById,
  activeAgent,
  activeAgentPersona,
  activeTurnForSpeaker,
  activePhase,
  daisLabel,
  voteMap,
  resolved,
  composing,
  nav,
}: {
  debate: DebateDetail;
  seats: ChamberSeat[];
  personaById: Record<string, Persona>;
  activeAgent: string | null;
  activeAgentPersona: Persona | null;
  activeTurnForSpeaker: Turn | undefined;
  activePhase: string;
  daisLabel: string;
  voteMap: Record<string, VoteValue>;
  resolved: boolean;
  composing: boolean;
  nav: ResultsProps["nav"];
}) {
  // Either show the current turn's text, or — when we know who's about to
  // speak but the LLM is still composing — show a "Composing remarks…"
  // placeholder with the persona's avatar and posture.
  const showComposing = composing && activeAgentPersona;
  const showTurn = !showComposing && activeTurnForSpeaker && activeAgentPersona;
  const width = useWindowWidth();
  const stacked = width < 1024;

  return (
    <Card pad={0} style={{ overflow: "hidden" }}>
      {/* Phase rail */}
      <PhaseRail currentPhase={activePhase} resolved={resolved} />
      <div
        style={{
          display: "grid",
          gridTemplateColumns: stacked ? "1fr" : "minmax(0, 1.6fr) minmax(0, 1fr)",
          gap: 0,
        }}
      >
        {/* Chamber column */}
        <div
          style={{
            position: "relative",
            padding: "16px 16px 12px 22px",
            borderRight: stacked ? "none" : "1px solid var(--ink-line)",
            borderBottom: stacked ? "1px solid var(--ink-line)" : "none",
            display: "flex",
            flexDirection: "column",
            gap: 10,
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 12,
            }}
          >
            <div className="eyebrow" style={{ margin: 0 }}>
              The Chamber
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              {!resolved && (
                <span
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 6,
                    fontSize: 10.5,
                    fontWeight: 700,
                    color: "var(--gold-bright)",
                    textTransform: "uppercase",
                    letterSpacing: ".12em",
                  }}
                >
                  <span
                    style={{
                      width: 7,
                      height: 7,
                      borderRadius: "50%",
                      background: "var(--gold-bright)",
                      animation: "blink 1.4s step-end infinite",
                    }}
                  />
                  Live
                </span>
              )}
            </div>
          </div>
          <div
            style={{
              position: "relative",
              width: "100%",
              aspectRatio: "1000 / 520",
              maxHeight: 380,
            }}
          >
            <ChamberSvg
              seats={seats}
              personaById={personaById}
              activeId={activeAgent}
              voteMap={voteMap}
              resolved={resolved}
              daisLabel={daisLabel}
              onSeat={(pid) => nav("personas", pid)}
            />
          </div>
        </div>

        {/* Speaker spotlight column */}
        <div
          style={{
            padding: "16px 22px 16px 22px",
            display: "flex",
            flexDirection: "column",
            gap: 12,
            minWidth: 0,
            background: "var(--ink2)",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 10,
            }}
          >
            <div className="eyebrow">
              {resolved
                ? "Final motion"
                : showComposing
                  ? "Now composing"
                  : activeAgentPersona
                    ? "Now speaking"
                    : "Convening"}
            </div>
          </div>

          {resolved ? (
            <FinalMotionCard debate={debate} />
          ) : showComposing && activeAgentPersona ? (
            <SpeakerCard
              persona={activeAgentPersona}
              phase={activePhase}
              content={null}
              composing
            />
          ) : showTurn && activeAgentPersona ? (
            <SpeakerCard
              persona={activeAgentPersona}
              phase={activeTurnForSpeaker.phase}
              content={activeTurnForSpeaker.content}
              composing={false}
            />
          ) : (
            <div
              style={{
                fontSize: 13,
                color: "var(--txt-faint)",
                padding: "30px 0",
                textAlign: "center",
              }}
            >
              The chamber will come to order shortly…
            </div>
          )}
        </div>
      </div>
    </Card>
  );
}

function PhaseRail({
  currentPhase,
  resolved,
}: {
  currentPhase: string;
  resolved: boolean;
}) {
  const curIdx = PHASE_SEQ.findIndex((x) => x.key === currentPhase);
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 6,
        padding: "12px 22px",
        borderBottom: "1px solid var(--ink-line)",
        background: "var(--ink1)",
        overflowX: "auto",
      }}
    >
      {PHASE_SEQ.map((ph, i) => {
        const done = (resolved && ph.key !== "final_voting") || i < curIdx || resolved;
        const active = !resolved && ph.key === currentPhase;
        return (
          <div key={ph.key} style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <div
              style={{
                padding: "5px 11px",
                borderRadius: 999,
                fontSize: 11,
                fontWeight: 600,
                whiteSpace: "nowrap",
                background: active
                  ? "var(--gold)"
                  : done
                    ? "rgba(194,161,77,0.1)"
                    : "var(--ink)",
                color: active ? "#1B1405" : done ? "var(--gold-bright)" : "var(--txt-faint)",
                border: `1px solid ${
                  active ? "var(--gold-deep)" : done ? "var(--gold-deep)" : "var(--ink-line)"
                }`,
              }}
            >
              {ph.label}
            </div>
            {i < PHASE_SEQ.length - 1 && (
              <div
                style={{
                  width: 10,
                  height: 1,
                  background: done ? "var(--gold-deep)" : "var(--ink-line)",
                }}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

function SpeakerCard({
  persona,
  phase,
  content,
  composing,
}: {
  persona: Persona;
  phase: string;
  content: string | null;
  composing: boolean;
}) {
  return (
    <div
      style={{
        borderLeft: `3px solid ${partyColor(persona.party)}`,
        background: "var(--ink1)",
        borderRadius: "var(--r-md)",
        padding: "14px 16px",
        display: "flex",
        flexDirection: "column",
        gap: 12,
        minHeight: 0,
      }}
    >
      <div style={{ display: "flex", gap: 14, alignItems: "center", minWidth: 0 }}>
        <Avatar p={persona} size={48} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div
            className="serif"
            style={{
              fontSize: 16,
              fontWeight: 600,
              color: "var(--txt)",
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
            }}
          >
            {persona.name}
          </div>
          <div
            style={{
              fontSize: 12,
              color: "var(--txt-faint)",
              marginTop: 2,
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
            }}
          >
            {persona.title}
          </div>
        </div>
      </div>
      <div style={{ display: "flex", gap: 7, flexWrap: "wrap" }}>
        <PartyTag party={persona.party} size="sm" />
        <PostureTag posture={persona.negotiation_posture} />
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            padding: "3px 9px",
            borderRadius: 999,
            fontSize: 11,
            fontWeight: 600,
            color: "var(--gold)",
            background: "rgba(194,161,77,0.08)",
            border: "1px solid var(--gold-deep)",
            whiteSpace: "nowrap",
          }}
        >
          {PHASE_LABEL[phase] || phase}
        </span>
      </div>
      {composing ? (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 9,
            fontSize: 13,
            fontStyle: "italic",
            color: "var(--txt-mute)",
            padding: "6px 0",
          }}
        >
          <span
            style={{
              width: 8,
              height: 8,
              borderRadius: "50%",
              background: "var(--gold-bright)",
              animation: "blink 1.4s step-end infinite",
            }}
          />
          Composing remarks…
        </div>
      ) : (
        content && (
          <div
            style={{
              fontSize: 13.5,
              lineHeight: 1.6,
              color: "var(--txt)",
              overflowY: "auto",
              maxHeight: 200,
              paddingRight: 4,
            }}
          >
            {content}
          </div>
        )
      )}
    </div>
  );
}

function FinalMotionCard({ debate }: { debate: DebateDetail }) {
  const amended = debate.status === "amended";
  const passed = debate.status === "passed" || amended;
  const tally = debate.tally;
  const color = amended ? "var(--gold-bright)" : passed ? "var(--pass)" : "var(--reject)";
  return (
    <div
      style={{
        borderLeft: `3px solid ${color}`,
        background: "var(--ink1)",
        borderRadius: "var(--r-md)",
        padding: "18px 18px",
        display: "flex",
        gap: 16,
        alignItems: "center",
      }}
    >
      <div
        style={{
          width: 50,
          height: 50,
          borderRadius: "50%",
          display: "grid",
          placeItems: "center",
          background: passed ? "rgba(62,155,110,0.15)" : "rgba(192,57,43,0.15)",
          border: `2px solid ${color}`,
          flexShrink: 0,
        }}
      >
        <Icon
          name={passed ? "check" : "x"}
          size={22}
          stroke={2.4}
          style={{ color }}
        />
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          className="eyebrow"
          style={{ color, marginBottom: 4, whiteSpace: "nowrap" }}
        >
          Motion {amended ? "Carries as Amended" : passed ? "Carries" : "Fails"}
        </div>
        <div
          className="serif"
          style={{
            fontSize: 19,
            fontWeight: 600,
            color: "var(--txt)",
            whiteSpace: "nowrap",
          }}
        >
          {tally.support}–{tally.oppose}
        </div>
        {tally.abstain > 0 && (
          <div
            style={{ fontSize: 12, color: "var(--txt-faint)", marginTop: 2 }}
          >
            {tally.abstain} abstaining
          </div>
        )}
      </div>
    </div>
  );
}

function StatTile({
  label,
  value,
  sub,
  accent,
  icon,
}: {
  label: string;
  value: string;
  sub?: string;
  accent?: string;
  icon: string;
}) {
  return (
    <Card pad={18}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          color: "var(--txt-faint)",
          fontSize: 10.5,
          fontWeight: 700,
          textTransform: "uppercase",
          letterSpacing: ".12em",
          marginBottom: 10,
        }}
      >
        <Icon name={icon} size={12} style={{ color: "var(--gold)" }} />
        {label}
      </div>
      <div
        className="serif"
        style={{
          fontSize: 22,
          fontWeight: 600,
          color: accent || "var(--txt)",
          lineHeight: 1.1,
        }}
      >
        {value}
      </div>
      {sub && (
        <div style={{ fontSize: 11.5, color: "var(--txt-faint)", marginTop: 6 }}>{sub}</div>
      )}
    </Card>
  );
}

function CaucusBars({ votes, debate }: { votes: VoteRecord[]; debate: DebateDetail }) {
  // Show every party that either (a) was on the launch's `parties` list, or
  // (b) actually cast a vote. This way custom parties surface here too if
  // they ever start voting in the engine.
  const partyIds = useMemo(() => {
    const ids = new Set<string>(debate.config.parties || []);
    votes.forEach((v) => ids.add(v.party));
    if (ids.size === 0) {
      ids.add("democrat");
      ids.add("republican");
    }
    return Array.from(ids);
  }, [debate.config.parties, votes]);
  return (
    <div style={{ display: "grid", gap: 14 }}>
      {partyIds.map((party) => {
        const list = votes.filter((v) => v.party === party);
        const t = { support: 0, oppose: 0, abstain: 0 };
        list.forEach((v) => t[v.vote]++);
        const seated = list.length > 0 ? Math.max(11, list.length) : 11;
        return (
          <div key={party}>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                fontSize: 12.5,
                marginBottom: 6,
              }}
            >
              <span style={{ color: partyBright(party), fontWeight: 600 }}>
                {partyLabel(party)}
              </span>
              <span className="mono" style={{ color: "var(--txt-faint)", fontSize: 11 }}>
                {list.length}/{seated}
              </span>
            </div>
            <div
              style={{
                display: "flex",
                height: 8,
                borderRadius: 999,
                overflow: "hidden",
                background: "var(--ink)",
              }}
            >
              <div
                style={{
                  width: `${(t.support / seated) * 100}%`,
                  background: "var(--support)",
                }}
              />
              <div
                style={{
                  width: `${(t.abstain / seated) * 100}%`,
                  background: "var(--abstain)",
                }}
              />
              <div
                style={{
                  width: `${(t.oppose / seated) * 100}%`,
                  background: "var(--oppose)",
                }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function RecentTurn({ t }: { t: Turn }) {
  const [p, setP] = useState<Persona | null>(null);
  useEffect(() => {
    void api.getPersona(t.agent).then(setP).catch(() => null);
  }, [t.agent]);
  if (!p) return null;
  // Strip simple markdown syntax so the preview reads cleanly when the agent's
  // content is full markdown. The full Transcript tab still renders it richly.
  const plain = stripMarkdownLite(t.content);
  const snippet = plain.length > 220 ? plain.slice(0, 220).trim() + "…" : plain;
  return (
    <div style={{ display: "flex", gap: 12 }}>
      <Avatar p={p} size={36} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
          <span
            className="serif"
            style={{
              fontSize: 14,
              fontWeight: 600,
              color: partyBright(p.party),
              whiteSpace: "nowrap",
            }}
          >
            {p.name}
          </span>
          <PartyTag party={p.party} size="sm" />
          <span
            style={{
              fontSize: 11,
              color: "var(--txt-faint)",
              whiteSpace: "nowrap",
            }}
          >
            {PHASE_LABEL[t.phase] || t.phase}
          </span>
        </div>
        <p
          style={{
            fontSize: 12.5,
            color: "var(--txt-mute)",
            margin: 0,
            lineHeight: 1.55,
          }}
        >
          {snippet}
        </p>
      </div>
    </div>
  );
}

/** Strip the small subset of markdown syntax that turns up in agent turns so
 * a short snippet reads naturally. Not a full parser — the Transcript tab
 * uses react-markdown for the rich rendering. */
function stripMarkdownLite(s: string): string {
  return s
    .replace(/```[\s\S]*?```/g, " ")          // fenced code blocks
    .replace(/`([^`]+)`/g, "$1")              // inline code
    .replace(/^#{1,6}\s+/gm, "")              // ATX headers
    .replace(/^\s*[-*+]\s+/gm, "")            // bullet markers
    .replace(/^\s*\d+\.\s+/gm, "")            // ordered list markers
    .replace(/^\s*>\s?/gm, "")                // blockquotes
    .replace(/^---+\s*$/gm, "")               // horizontal rules
    .replace(/\*\*([^*]+)\*\*/g, "$1")        // bold
    .replace(/\*([^*]+)\*/g, "$1")            // italic
    .replace(/_([^_]+)_/g, "$1")              // italic (underscore)
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")  // links → label
    .replace(/\s+/g, " ")
    .trim();
}

function fmtDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  if (m === 0) return `${s}s`;
  return `${m}m ${String(s).padStart(2, "0")}s`;
}

// ---------------------------------------------------------------------------

function Breakdown({ votes }: { votes: VoteRecord[] }) {
  const grouped = votes.reduce<Record<string, VoteRecord[]>>((acc, v) => {
    (acc[v.party] = acc[v.party] || []).push(v);
    return acc;
  }, {});
  const parties = Object.keys(grouped);
  if (!parties.length) {
    return <EmptyState icon="results" text="Votes will appear here once the chamber casts them." />;
  }
  return (
    <div style={{ display: "grid", gridTemplateColumns: `repeat(${Math.min(parties.length, 2)}, 1fr)`, gap: 30 }}>
      {parties.map((party) => {
        const list = grouped[party];
        const t = { support: 0, oppose: 0, abstain: 0 };
        list.forEach((v) => t[v.vote]++);
        return (
          <div key={party}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                marginBottom: 14,
                paddingBottom: 11,
                borderBottom: `2px solid ${partyColor(party)}`,
              }}
            >
              <span
                style={{
                  width: 9,
                  height: 9,
                  borderRadius: "50%",
                  background: partyColor(party),
                }}
              />
              <span className="serif" style={{ fontSize: 17, fontWeight: 600 }}>
                {partyLabel(party)} Caucus
              </span>
              <span
                className="mono"
                style={{
                  marginLeft: "auto",
                  fontSize: 12,
                  color: "var(--txt-faint)",
                }}
              >
                {t.support}·{t.abstain}·{t.oppose}
              </span>
            </div>
            <div style={{ display: "grid", gap: 9 }}>
              {list.map((v) => (
                <VoteCard key={v.agent} v={v} />
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function VoteCard({ v }: { v: VoteRecord }) {
  const [p, setP] = useState<Persona | null>(null);
  useEffect(() => {
    void api
      .getPersona(v.agent)
      .then(setP)
      .catch(() => null);
  }, [v.agent]);
  if (!p) {
    return (
      <div className="ink-panel" style={{ padding: "12px 14px", color: "var(--txt-faint)" }}>
        {v.agent} · {v.vote}
      </div>
    );
  }
  return (
    <div
      className="ink-panel"
      style={{
        padding: "12px 14px",
        borderLeft: `3px solid ${VOTE_META[v.vote].color}`,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 11 }}>
        <Avatar p={p} size={34} ring={false} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 7, minWidth: 0 }}>
            <span
              style={{
                fontSize: 13.5,
                fontWeight: 600,
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
              }}
            >
              {p.name}
            </span>
            {v.changed && (
              <span title={`Changed from ${v.from}`} style={{ color: "var(--gold)" }}>
                <Icon name="refresh" size={12} />
              </span>
            )}
          </div>
          <div style={{ fontSize: 11, color: "var(--txt-faint)" }}>
            {ROLE_META[p.role]?.label || p.role}
          </div>
        </div>
        {v.weight != null && (
          <span
            className="mono"
            title="Seat weight this ballot carried"
            style={{ fontSize: 11, color: "var(--txt-faint)" }}
          >
            ×{v.weight.toFixed(1)}
          </span>
        )}
        <VoteTag vote={v.vote} sm />
      </div>
      {v.reasoning && (
        <p
          style={{
            fontSize: 12.5,
            color: "var(--txt-mute)",
            lineHeight: 1.5,
            margin: "10px 0 0",
            paddingLeft: 45,
          }}
        >
          “{v.reasoning}”
        </p>
      )}
    </div>
  );
}

function Timeline({ changes }: { changes: VoteRecord[] }) {
  if (!changes.length) {
    return (
      <EmptyState icon="refresh" text="No agents changed their vote in this debate." />
    );
  }
  return (
    <div>
      <div
        style={{
          display: "flex",
          gap: 9,
          alignItems: "center",
          marginBottom: 22,
          fontSize: 13.5,
          color: "var(--txt-mute)",
        }}
      >
        <Icon name="spark" size={16} style={{ color: "var(--gold)" }} />
        <span>
          <b style={{ color: "var(--txt)" }}>{changes.length} agents</b> shifted their position over
          the course of deliberation — the persuasion mechanic at work.
        </span>
      </div>
      <div style={{ position: "relative", paddingLeft: 30 }}>
        <div
          style={{
            position: "absolute",
            left: 9,
            top: 6,
            bottom: 6,
            width: 2,
            background: "var(--ink-line)",
          }}
        />
        <div style={{ display: "grid", gap: 16 }}>
          {changes.map((v) => (
            <ChangeCard key={v.agent} v={v} />
          ))}
        </div>
      </div>
    </div>
  );
}

function ChangeCard({ v }: { v: VoteRecord }) {
  const [p, setP] = useState<Persona | null>(null);
  useEffect(() => {
    void api
      .getPersona(v.agent)
      .then(setP)
      .catch(() => null);
  }, [v.agent]);
  if (!p) return <div className="ink-panel" style={{ padding: 16 }} />;
  return (
    <div className="ink-panel" style={{ padding: "16px 18px", position: "relative" }}>
      <div
        style={{
          position: "absolute",
          left: -29,
          top: 20,
          width: 14,
          height: 14,
          borderRadius: "50%",
          background: "var(--gold)",
          border: "3px solid var(--ink)",
        }}
      />
      <div style={{ display: "flex", alignItems: "center", gap: 13 }}>
        <Avatar p={p} size={40} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span className="serif" style={{ fontSize: 16, fontWeight: 600, whiteSpace: "nowrap" }}>
              {p.name}
            </span>
            <PartyTag party={p.party} size="sm" />
          </div>
          <div style={{ fontSize: 12, color: "var(--txt-faint)" }}>{p.title}</div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          {v.from && <VoteTag vote={v.from} sm />}
          <Icon name="arrowR" size={18} style={{ color: "var(--gold)" }} />
          <VoteTag vote={v.vote} sm />
        </div>
      </div>
      <p
        style={{
          fontSize: 13,
          color: "var(--txt-mute)",
          lineHeight: 1.55,
          margin: "12px 0 0",
          paddingLeft: 53,
        }}
      >
        “{v.reasoning}”
      </p>
    </div>
  );
}

function FullTranscript({ turns }: { turns: Turn[] }) {
  if (!turns.length) {
    return (
      <EmptyState
        icon="transcript"
        text="Transcript is empty (debate may have failed before any turns)."
      />
    );
  }
  // System "phase banner" turns (agent=system) have no persona, so TurnRow
  // skips them. Drop those phases here too — otherwise the transcript shows
  // an empty "REPUBLICAN_DELIBERATION" header between Proposal and Opening
  // Remarks. Speaker turns are what actually structures the transcript.
  const speakerTurns = turns.filter((t) => t.agent !== "system");
  const phases = Array.from(new Set(speakerTurns.map((t) => t.phase)));
  return (
    <div style={{ display: "grid", gap: 26 }}>
      {phases.map((ph) => (
        <div key={ph}>
          <div className="gold-rule" style={{ marginBottom: 16 }}>
            <span className="eyebrow">{PHASE_LABEL[ph] || ph}</span>
          </div>
          <div style={{ display: "grid", gap: 14 }}>
            {speakerTurns
              .filter((t) => t.phase === ph)
              .map((t) => (
                <TurnRow key={t.id} t={t} />
              ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function TurnRow({ t }: { t: Turn }) {
  const [p, setP] = useState<Persona | null>(null);
  useEffect(() => {
    void api
      .getPersona(t.agent)
      .then(setP)
      .catch(() => null);
  }, [t.agent]);
  if (!p) return null;
  return (
    <div style={{ display: "flex", gap: 14 }}>
      <Avatar p={p} size={40} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 5 }}>
          <span
            className="serif"
            style={{
              fontSize: 15.5,
              fontWeight: 600,
              color: partyBright(p.party),
              whiteSpace: "nowrap",
            }}
          >
            {p.name}
          </span>
          <span style={{ fontSize: 11.5, color: "var(--txt-faint)" }}>
            {p.title}
            {t.round ? ` · Round ${t.round}` : ""}
          </span>
        </div>
        <TurnMarkdown content={t.content} />
      </div>
    </div>
  );
}

/** Renders an agent turn's markdown content with chamber styling.
 *
 * react-markdown is safe-by-default — it converts markdown to React elements
 * and never parses raw HTML, so an agent who writes `<script>` just sees the
 * tag rendered as text. We map each markdown element to a styled component so
 * headers, bold text, lists, and rules visually match the rest of the UI. */
function TurnMarkdown({ content }: { content: string }) {
  return (
    <div
      style={{
        fontSize: 14,
        color: "var(--txt-mute)",
        lineHeight: 1.65,
      }}
    >
      <ReactMarkdown
        components={{
          h1: ({ children }) => (
            <h3
              className="serif"
              style={{
                fontSize: 17,
                color: "var(--txt)",
                fontWeight: 600,
                margin: "10px 0 6px",
              }}
            >
              {children}
            </h3>
          ),
          h2: ({ children }) => (
            <h4
              className="serif"
              style={{
                fontSize: 15,
                color: "var(--txt)",
                fontWeight: 600,
                margin: "10px 0 4px",
              }}
            >
              {children}
            </h4>
          ),
          h3: ({ children }) => (
            <h5
              style={{
                fontSize: 13,
                color: "var(--gold-bright)",
                fontWeight: 600,
                letterSpacing: ".04em",
                textTransform: "uppercase",
                margin: "10px 0 4px",
              }}
            >
              {children}
            </h5>
          ),
          p: ({ children }) => (
            <p style={{ margin: "0 0 8px" }}>{children}</p>
          ),
          strong: ({ children }) => (
            <strong style={{ color: "var(--txt)", fontWeight: 600 }}>{children}</strong>
          ),
          em: ({ children }) => (
            <em style={{ color: "var(--txt-faint)" }}>{children}</em>
          ),
          ul: ({ children }) => (
            <ul style={{ margin: "4px 0 8px", paddingLeft: 20 }}>{children}</ul>
          ),
          ol: ({ children }) => (
            <ol style={{ margin: "4px 0 8px", paddingLeft: 20 }}>{children}</ol>
          ),
          li: ({ children }) => <li style={{ marginBottom: 3 }}>{children}</li>,
          hr: () => (
            <hr
              style={{
                border: "none",
                borderTop: "1px solid var(--ink-line)",
                margin: "12px 0",
              }}
            />
          ),
          blockquote: ({ children }) => (
            <blockquote
              style={{
                borderLeft: "3px solid var(--gold-deep)",
                margin: "8px 0",
                padding: "2px 0 2px 12px",
                color: "var(--txt-faint)",
                fontStyle: "italic",
              }}
            >
              {children}
            </blockquote>
          ),
          code: ({ children }) => (
            <code
              className="mono"
              style={{
                fontSize: 12.5,
                background: "var(--ink2)",
                padding: "1px 5px",
                borderRadius: 4,
              }}
            >
              {children}
            </code>
          ),
          a: ({ href, children }) => (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              style={{ color: "var(--gold-bright)", textDecoration: "underline" }}
            >
              {children}
            </a>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}

function Amendments({ amendments }: { amendments: Amendment[] }) {
  if (!amendments.length) {
    return <EmptyState icon="doc" text="No amendments were tabled in this debate." />;
  }
  return (
    <div style={{ display: "grid", gap: 14 }}>
      {amendments.map((a, i) => (
        <div
          key={a.id}
          className="ink-panel"
          style={{ padding: "18px 22px", display: "flex", gap: 18, alignItems: "center" }}
        >
          <div className="serif" style={{ fontSize: 24, fontWeight: 600, color: "var(--gold-deep)", width: 32 }}>
            {String(i + 1).padStart(2, "0")}
          </div>
          <div style={{ flex: 1 }}>
            <p
              style={{
                fontSize: 15,
                fontFamily: "var(--serif)",
                lineHeight: 1.5,
                margin: "0 0 8px",
                color: "var(--txt)",
              }}
            >
              {a.text}
            </p>
          </div>
          <StatusTag status={a.status} />
        </div>
      ))}
    </div>
  );
}

function EmptyState({
  icon,
  text,
  action,
}: {
  icon: string;
  text: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="ink-panel" style={{ padding: "50px 30px", textAlign: "center" }}>
      <Icon name={icon} size={30} style={{ color: "var(--ink-line)", margin: "0 auto 14px" }} />
      <div style={{ fontSize: 14, color: "var(--txt-mute)", marginBottom: action ? 16 : 0 }}>
        {text}
      </div>
      {action}
    </div>
  );
}
