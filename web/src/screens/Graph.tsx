import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { Avatar } from "../components/Avatar";
import { Btn } from "../components/Btn";
import { Card, SectionTitle } from "../components/Card";
import { T, partyBright, partyColor } from "../theme";
import type {
  Persona,
  PersonaSummary,
  RelationshipEdge,
  RelationshipNode,
} from "../types";

interface GraphProps {
  nav: (route: string, param?: string) => void;
}

interface LayoutNode {
  x: number;
  y: number;
  p: RelationshipNode;
}

export function Graph({ nav }: GraphProps) {
  const [nodes, setNodes] = useState<RelationshipNode[]>([]);
  const [edges, setEdges] = useState<RelationshipEdge[]>([]);
  // Relationship nodes don't carry persona fields beyond id/name/party/role,
  // so portraits are threaded in from the persona summaries (id → image_url).
  const [imgById, setImgById] = useState<Record<string, string>>({});
  const [show, setShow] = useState<{ allies: boolean; rivals: boolean }>({
    allies: true,
    rivals: true,
  });
  const [hover, setHover] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void api
      .getRelationships()
      .then((r) => {
        setNodes(r.nodes);
        setEdges(r.edges);
      })
      .catch((e) => setError(String(e.message || e)));
    void api
      .listPersonas()
      .then((r) => {
        const map: Record<string, string> = {};
        r.personas.forEach((s) => {
          if (s.image_url) map[s.id] = s.image_url;
        });
        setImgById(map);
      })
      // Portraits are a progressive enhancement — initials still render.
      .catch(() => setImgById({}));
  }, []);

  const layout = useMemo<Record<string, LayoutNode>>(() => {
    const pos: Record<string, LayoutNode> = {};
    const groups = nodes.reduce<Record<string, RelationshipNode[]>>((acc, n) => {
      (acc[n.party] = acc[n.party] || []).push(n);
      return acc;
    }, {});
    const partyIds = Object.keys(groups);
    const radius = 200;
    const centerY = 310;
    const totalCenters = partyIds.length;
    partyIds.forEach((pid, i) => {
      const cx = totalCenters === 1 ? 600 : 300 + (i * 600) / (totalCenters - 1 || 1);
      const people = groups[pid];
      const head = people.find((n) => n.role === "party_head") || people[0];
      const rest = people.filter((n) => n.id !== head?.id);
      if (head) {
        pos[head.id] = { x: cx, y: centerY, p: head };
      }
      rest.forEach((n, idx) => {
        const a = (idx / Math.max(rest.length, 1)) * Math.PI * 2 - Math.PI / 2;
        pos[n.id] = { x: cx + Math.cos(a) * radius, y: centerY + Math.sin(a) * radius, p: n };
      });
    });
    return pos;
  }, [nodes]);

  const connectedSet = useMemo(() => {
    if (!hover) return new Set<string>();
    const set = new Set<string>([hover]);
    edges.forEach((e) => {
      if (e.from === hover) set.add(e.to);
      if (e.to === hover) set.add(e.from);
    });
    return set;
  }, [hover, edges]);

  const isDim = (id: string) => hover !== null && hover !== id && !connectedSet.has(id);

  return (
    <div style={{ maxWidth: 1180, margin: "0 auto", padding: "34px 40px 60px" }}>
      <SectionTitle
        eyebrow="Intra-party dynamics"
        title="Relationship Graph"
        sub="Allies tend to reinforce each other in deliberation; rivals create internal friction that shapes how a caucus position forms. Relationships are intra-party by design."
        right={
          <div style={{ display: "flex", gap: 9 }}>
            <Toggle
              active={show.allies}
              color="var(--support)"
              label="Allies"
              onClick={() => setShow((s) => ({ ...s, allies: !s.allies }))}
            />
            <Toggle
              active={show.rivals}
              color="var(--oppose)"
              label="Rivals"
              onClick={() => setShow((s) => ({ ...s, rivals: !s.rivals }))}
            />
          </div>
        }
      />

      {error && (
        <Card pad={16} style={{ marginBottom: 18, borderLeft: "3px solid var(--reject)" }}>
          <div style={{ color: "var(--reject)", fontSize: 13 }}>
            Couldn't load relationship graph: {error}
          </div>
        </Card>
      )}

      <div className="ink-panel" style={{ padding: 0, overflow: "hidden", position: "relative" }}>
        <svg viewBox="0 0 1200 620" style={{ width: "100%", height: "auto", display: "block" }}>
          {/* divider — only meaningful when exactly 2 parties */}
          {Object.keys(layout).length > 0 && (
            <line
              x1="600"
              y1="40"
              x2="600"
              y2="580"
              stroke="var(--ink-line)"
              strokeWidth="1"
              strokeDasharray="3 6"
            />
          )}
          {edges.map((e, i) => {
            if (e.type === "ally" && !show.allies) return null;
            if (e.type === "rival" && !show.rivals) return null;
            const a = layout[e.from];
            const b = layout[e.to];
            if (!a || !b) return null;
            const dim = hover !== null && hover !== e.from && hover !== e.to;
            const col = e.type === "ally" ? "var(--support)" : "var(--oppose)";
            return (
              <line
                key={i}
                x1={a.x}
                y1={a.y}
                x2={b.x}
                y2={b.y}
                stroke={col}
                strokeWidth={dim ? 1 : 2}
                strokeOpacity={dim ? 0.12 : 0.5}
                strokeDasharray={e.type === "rival" ? "5 5" : "none"}
              />
            );
          })}
          {Object.values(layout).map(({ x, y, p }) => {
            const initials = p.name
              .split(" ")
              .filter(Boolean)
              .slice(-2)
              .map((s) => s[0])
              .join("");
            const base = partyColor(p.party);
            const bright = partyBright(p.party);
            const dim = isDim(p.id);
            const r = p.role === "party_head" ? 28 : 20;
            const img = imgById[p.id];
            return (
              <g
                key={p.id}
                transform={`translate(${x},${y})`}
                style={{ cursor: "pointer", transition: "opacity .2s", opacity: dim ? 0.25 : 1 }}
                onMouseEnter={() => setHover(p.id)}
                onMouseLeave={() => setHover(null)}
                onClick={() => nav("personas", p.id)}
              >
                <circle
                  r={r}
                  fill={base}
                  fillOpacity={hover === p.id ? 0.95 : 0.4}
                  stroke={hover === p.id ? T.goldBright : bright}
                  strokeWidth={hover === p.id ? 2.5 : 1.5}
                />
                {p.role === "party_head" && (
                  <circle
                    r={r + 4}
                    fill="none"
                    stroke="var(--gold)"
                    strokeWidth="1"
                    strokeDasharray="2 3"
                    opacity="0.8"
                  />
                )}
                {/* Initials always render; a loaded portrait covers them, so
                    they remain the fallback when no image_url or on error. */}
                <text
                  textAnchor="middle"
                  dy={r * 0.34}
                  fontSize={r * 0.6}
                  fontWeight={700}
                  fill={hover === p.id ? "#0A1626" : bright}
                  fontFamily="var(--sans)"
                >
                  {initials}
                </text>
                {img && (
                  <>
                    <clipPath id={`graph-node-clip-${p.id}`}>
                      <circle r={r} />
                    </clipPath>
                    <image
                      href={img}
                      x={-r}
                      y={-r}
                      width={r * 2}
                      height={r * 2}
                      preserveAspectRatio="xMidYMid slice"
                      clipPath={`url(#graph-node-clip-${p.id})`}
                    />
                    {/* Re-draw the party-colored ring above the portrait. */}
                    <circle
                      r={r}
                      fill="none"
                      stroke={hover === p.id ? T.goldBright : bright}
                      strokeWidth={hover === p.id ? 2.5 : 1.5}
                    />
                  </>
                )}
                <text
                  textAnchor="middle"
                  y={r + 15}
                  fontSize="11.5"
                  fill={hover === p.id ? "var(--txt)" : "var(--txt-faint)"}
                  fontFamily="var(--sans)"
                  fontWeight={600}
                >
                  {p.name.split(" ").slice(-1)[0]}
                </text>
              </g>
            );
          })}
        </svg>
        <div
          style={{
            position: "absolute",
            bottom: 18,
            left: 24,
            display: "flex",
            gap: 20,
            fontSize: 12,
            color: "var(--txt-mute)",
          }}
        >
          <span style={{ display: "flex", alignItems: "center", gap: 7 }}>
            <span style={{ width: 20, height: 2, background: "var(--support)" }} />
            Ally
          </span>
          <span style={{ display: "flex", alignItems: "center", gap: 7 }}>
            <span
              style={{
                width: 20,
                height: 0,
                borderTop: "2px dashed var(--oppose)",
              }}
            />
            Rival
          </span>
          <span style={{ display: "flex", alignItems: "center", gap: 7 }}>
            <span
              style={{
                width: 12,
                height: 12,
                borderRadius: "50%",
                border: "1px dashed var(--gold)",
              }}
            />
            Party Head
          </span>
        </div>
      </div>

      {hover && <HoverDetail id={hover} nav={nav} edges={edges} />}
    </div>
  );
}

function HoverDetail({
  id,
  nav,
  edges,
}: {
  id: string;
  nav: GraphProps["nav"];
  edges: RelationshipEdge[];
}) {
  const [p, setP] = useState<Persona | null>(null);
  const [allies, setAllies] = useState<PersonaSummary[]>([]);
  const [rivals, setRivals] = useState<PersonaSummary[]>([]);

  useEffect(() => {
    setP(null);
    void api.getPersona(id).then(setP);
    const ids = new Set<string>();
    edges.forEach((e) => {
      if (e.from === id) ids.add(e.to);
      if (e.to === id) ids.add(e.from);
    });
    void api.listPersonas().then((r) => {
      const byId = new Map(r.personas.map((s) => [s.id, s]));
      const allyIds = new Set(
        edges.filter((e) => e.type === "ally" && (e.from === id || e.to === id)).map((e) => (e.from === id ? e.to : e.from)),
      );
      const rivalIds = new Set(
        edges.filter((e) => e.type === "rival" && (e.from === id || e.to === id)).map((e) => (e.from === id ? e.to : e.from)),
      );
      setAllies(Array.from(allyIds).map((x) => byId.get(x)).filter((x): x is PersonaSummary => !!x));
      setRivals(Array.from(rivalIds).map((x) => byId.get(x)).filter((x): x is PersonaSummary => !!x));
    });
  }, [id, edges]);

  if (!p) {
    return (
      <Card style={{ marginTop: 18 }}>
        <span style={{ fontSize: 13, color: "var(--txt-faint)" }}>Loading…</span>
      </Card>
    );
  }

  return (
    <Card style={{ marginTop: 18, display: "flex", gap: 18, alignItems: "center" }}>
      <Avatar p={p} size={48} />
      <div style={{ flex: 1 }}>
        <div className="serif" style={{ fontSize: 17, fontWeight: 600 }}>
          {p.name}
        </div>
        <div style={{ fontSize: 12.5, color: "var(--txt-mute)" }}>{p.title}</div>
      </div>
      <div style={{ display: "flex", gap: 24 }}>
        <div>
          <div
            style={{
              fontSize: 10.5,
              fontWeight: 700,
              letterSpacing: ".12em",
              textTransform: "uppercase",
              color: "var(--support)",
              marginBottom: 6,
            }}
          >
            Allies
          </div>
          <div style={{ display: "flex", gap: 6 }}>
            {allies.length ? (
              allies.map((a) => <Avatar key={a.id} p={a} size={28} ring={false} />)
            ) : (
              <span style={{ fontSize: 12, color: "var(--txt-faint)" }}>—</span>
            )}
          </div>
        </div>
        <div>
          <div
            style={{
              fontSize: 10.5,
              fontWeight: 700,
              letterSpacing: ".12em",
              textTransform: "uppercase",
              color: "var(--oppose)",
              marginBottom: 6,
            }}
          >
            Rivals
          </div>
          <div style={{ display: "flex", gap: 6 }}>
            {rivals.length ? (
              rivals.map((a) => <Avatar key={a.id} p={a} size={28} ring={false} />)
            ) : (
              <span style={{ fontSize: 12, color: "var(--txt-faint)" }}>—</span>
            )}
          </div>
        </div>
      </div>
      <Btn kind="ghost" size="sm" iconR="arrowR" onClick={() => nav("personas", p.id)}>
        Open
      </Btn>
    </Card>
  );
}

function Toggle({
  active,
  color,
  label,
  onClick,
}: {
  active: boolean;
  color: string;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        padding: "7px 13px",
        borderRadius: 999,
        fontSize: 12.5,
        fontWeight: 600,
        background: active ? "var(--ink3)" : "transparent",
        color: active ? color : "var(--txt-faint)",
        border: `1px solid ${active ? color : "var(--ink-line)"}`,
        transition: "all .15s ease",
      }}
    >
      <span
        style={{
          width: 8,
          height: 8,
          borderRadius: "50%",
          background: active ? color : "var(--ink-line)",
        }}
      />
      {label}
    </button>
  );
}
