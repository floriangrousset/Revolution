import { useEffect, useState } from "react";
import { api } from "../api";
import { Btn } from "../components/Btn";
import { Card, SectionTitle, Stat, TallyBar } from "../components/Card";
import { Icon } from "../components/Icon";
import { Seal } from "../components/Seal";
import { StatusTag } from "../components/Tags";
import type { DebateSummary } from "../types";

interface DashboardProps {
  nav: (route: string, param?: string) => void;
}

export function Dashboard({ nav }: DashboardProps) {
  const [debates, setDebates] = useState<DebateSummary[]>([]);
  const [stats, setStats] = useState({ democrat: 0, republican: 0 });
  const [pendingDelete, setPendingDelete] = useState<string | null>(null);

  useEffect(() => {
    void api.listParties().then((r) => {
      const map: Record<string, number> = {};
      r.parties.forEach((p) => {
        map[p.id] = p.seats;
      });
      setStats({ democrat: map.democrat || 0, republican: map.republican || 0 });
    });
    void api.listDebates().then((r) => setDebates(r.debates)).catch(() => null);
  }, []);

  const passed = debates.filter((d) => d.status === "passed").length;
  const passRate = debates.length ? Math.round((passed / debates.length) * 100) : 0;
  const totalSeats = stats.democrat + stats.republican;
  const totalAmendments = debates.reduce((acc, d) => acc + (d.amendments || 0), 0);

  return (
    <div style={{ maxWidth: 1180, margin: "0 auto", padding: "34px 40px 60px" }}>
      <div style={{ display: "grid", gridTemplateColumns: "1.5fr 1fr", gap: 24, marginBottom: 30 }}>
        <div className="ink-panel" style={{ padding: "34px 36px", position: "relative", overflow: "hidden" }}>
          <div
            style={{
              position: "absolute",
              right: -40,
              top: -40,
              opacity: 0.06,
              pointerEvents: "none",
            }}
          >
            <Seal size={260} />
          </div>
          <div className="eyebrow" style={{ marginBottom: 14 }}>
            The Floor · Session 2026
          </div>
          <h1
            className="serif"
            style={{ fontSize: 40, fontWeight: 600, lineHeight: 1.08, margin: "0 0 14px", maxWidth: 520 }}
          >
            Simulate the outcome of any proposal before it reaches the floor.
          </h1>
          <p
            style={{
              fontSize: 15,
              color: "var(--txt-mute)",
              lineHeight: 1.6,
              maxWidth: 540,
              margin: "0 0 24px",
            }}
          >
            A chamber of agentic AI personas — organized into caucuses of party heads,
            advisors, and assistants — deliberates, debates across the aisle, and votes.
            Watch positions form, amendments emerge, and minds change in real time.
          </p>
          <div style={{ display: "flex", gap: 12 }}>
            <Btn kind="primary" icon="launch" size="lg" onClick={() => nav("launch")}>
              Convene a Debate
            </Btn>
            <Btn kind="ghost" icon="personas" size="lg" onClick={() => nav("personas")}>
              Manage the Floor
            </Btn>
          </div>
        </div>

        <div className="ink-panel" style={{ padding: "26px 28px", display: "flex", flexDirection: "column" }}>
          <div className="eyebrow" style={{ marginBottom: 18 }}>
            Chamber Composition
          </div>
          <ChamberMini />
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              marginTop: "auto",
              paddingTop: 20,
            }}
          >
            <div>
              <div className="serif" style={{ fontSize: 26, color: "var(--dem-bright)", fontWeight: 600 }}>
                {stats.democrat}
              </div>
              <div
                style={{
                  fontSize: 11,
                  color: "var(--txt-faint)",
                  letterSpacing: ".1em",
                  textTransform: "uppercase",
                  marginTop: 4,
                }}
              >
                Democrat
              </div>
            </div>
            <div style={{ textAlign: "center" }}>
              <div className="serif" style={{ fontSize: 26, color: "var(--gold-bright)", fontWeight: 600 }}>
                {totalSeats}
              </div>
              <div
                style={{
                  fontSize: 11,
                  color: "var(--txt-faint)",
                  letterSpacing: ".1em",
                  textTransform: "uppercase",
                  marginTop: 4,
                }}
              >
                Seated
              </div>
            </div>
            <div style={{ textAlign: "right" }}>
              <div className="serif" style={{ fontSize: 26, color: "var(--rep-bright)", fontWeight: 600 }}>
                {stats.republican}
              </div>
              <div
                style={{
                  fontSize: 11,
                  color: "var(--txt-faint)",
                  letterSpacing: ".1em",
                  textTransform: "uppercase",
                  marginTop: 4,
                }}
              >
                Republican
              </div>
            </div>
          </div>
        </div>
      </div>

      <div
        className="ink-panel"
        style={{
          padding: "24px 32px",
          display: "grid",
          gridTemplateColumns: "repeat(4,1fr)",
          gap: 24,
          marginBottom: 34,
        }}
      >
        <Stat value={debates.length} label="Debates Held" />
        <Stat value={`${passRate}%`} label="Passage Rate" color="var(--pass)" />
        <Stat value={totalAmendments} label="Amendments Tabled" color="var(--gold-bright)" />
        <Stat value={totalSeats} label="Agents Seated" color="var(--dem-bright)" />
      </div>

      <SectionTitle
        eyebrow="Legislative Record"
        title="Recent Deliberations"
        right={
          <Btn kind="ghost" iconR="arrowR" onClick={() => nav("launch")}>
            New debate
          </Btn>
        }
      />

      {debates.length === 0 ? (
        <Card pad={42} style={{ textAlign: "center", color: "var(--txt-mute)" }}>
          <Icon name="transcript" size={28} style={{ color: "var(--ink-line)", marginBottom: 12 }} />
          <div style={{ fontSize: 14 }}>
            No debates yet. Convene the first one to start the record.
          </div>
          <div style={{ marginTop: 16 }}>
            <Btn kind="primary" icon="launch" onClick={() => nav("launch")}>
              Convene a Debate
            </Btn>
          </div>
        </Card>
      ) : (
        <div style={{ display: "grid", gap: 14 }}>
          {debates.map((d) => (
            <Card
              key={d.id}
              hover
              onClick={() => nav("results", d.id)}
              style={{
                display: "grid",
                gridTemplateColumns: "minmax(0,1fr) 240px 150px 32px",
                gap: 24,
                alignItems: "center",
              }}
            >
              <div style={{ minWidth: 0 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 7 }}>
                  <StatusTag status={d.status} />
                  <span className="mono" style={{ fontSize: 11.5, color: "var(--txt-faint)" }}>
                    {d.rounds} round{d.rounds > 1 ? "s" : ""}
                  </span>
                </div>
                <div
                  className="serif"
                  style={{
                    fontSize: 18,
                    fontWeight: 600,
                    marginBottom: 4,
                    whiteSpace: "nowrap",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                  }}
                >
                  {d.title}
                </div>
              </div>
              <div>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    fontSize: 12,
                    marginBottom: 7,
                    fontWeight: 600,
                  }}
                >
                  <span style={{ color: "var(--support)" }}>{d.support} For</span>
                  {d.abstain > 0 && (
                    <span style={{ color: "var(--abstain)" }}>{d.abstain} Abs</span>
                  )}
                  <span style={{ color: "var(--oppose)" }}>{d.oppose} Against</span>
                </div>
                <TallyBar support={d.support} oppose={d.oppose} abstain={d.abstain} />
              </div>
              <div style={{ textAlign: "right" }}>
                <div className="mono" style={{ fontSize: 11.5, color: "var(--txt-faint)" }}>
                  {new Date(d.created_at).toLocaleDateString()}
                </div>
                <div
                  style={{
                    display: "flex",
                    gap: 6,
                    justifyContent: "flex-end",
                    marginTop: 8,
                    color: "var(--gold)",
                  }}
                >
                  <span style={{ fontSize: 12, fontWeight: 600 }}>Open</span>
                  <Icon name="arrowR" size={15} />
                </div>
              </div>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setPendingDelete(d.id);
                }}
                title="Delete debate"
                style={{
                  width: 28,
                  height: 28,
                  borderRadius: "var(--r-md)",
                  background: "transparent",
                  border: "1px solid transparent",
                  color: "var(--txt-faint)",
                  display: "grid",
                  placeItems: "center",
                  cursor: "pointer",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.color = "var(--rep-bright)";
                  e.currentTarget.style.borderColor = "var(--rep-deep)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.color = "var(--txt-faint)";
                  e.currentTarget.style.borderColor = "transparent";
                }}
              >
                <Icon name="x" size={14} stroke={2.2} />
              </button>
            </Card>
          ))}
        </div>
      )}

      {pendingDelete && (
        <DeleteDebateModal
          id={pendingDelete}
          onClose={() => setPendingDelete(null)}
          onDeleted={() => {
            setPendingDelete(null);
            void api.listDebates().then((r) => setDebates(r.debates)).catch(() => null);
          }}
        />
      )}
    </div>
  );
}

function DeleteDebateModal({
  id,
  onClose,
  onDeleted,
}: {
  id: string;
  onClose: () => void;
  onDeleted: () => void;
}) {
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const confirm = async () => {
    setWorking(true);
    try {
      await api.deleteDebate(id);
      onDeleted();
    } catch (e) {
      setError(String((e as Error).message || e));
    } finally {
      setWorking(false);
    }
  };
  return (
    <div
      onClick={onClose}
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
          Delete this deliberation?
        </div>
        <p style={{ fontSize: 13.5, color: "var(--txt-mute)", lineHeight: 1.6, margin: 0 }}>
          Transcript, votes, amendments, and the index row are permanently removed. This
          cannot be undone.
        </p>
        {error && (
          <div
            style={{
              marginTop: 14,
              padding: "10px 14px",
              borderRadius: "var(--r-md)",
              background: "rgba(192,57,43,0.12)",
              border: "1px solid var(--reject)",
              color: "var(--reject)",
              fontSize: 13,
            }}
          >
            {error}
          </div>
        )}
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, marginTop: 18 }}>
          <Btn kind="ghost" onClick={onClose}>
            Cancel
          </Btn>
          <Btn kind="danger" icon="x" onClick={confirm} disabled={working}>
            {working ? "Deleting…" : "Delete debate"}
          </Btn>
        </div>
      </div>
    </div>
  );
}

function ChamberMini() {
  const seats: { x: number; y: number; party: "democrat" | "republican"; mid: boolean }[] = [];
  const rows = [
    { r: 46, n: 5 },
    { r: 62, n: 7 },
    { r: 78, n: 9 },
  ];
  rows.forEach((row) => {
    for (let i = 0; i < row.n; i++) {
      const frac = row.n === 1 ? 0.5 : i / (row.n - 1);
      const ang = Math.PI * (1 - frac);
      const cx = 100;
      const cy = 92;
      const x = cx + Math.cos(ang) * row.r;
      const y = cy - Math.sin(ang) * row.r;
      const isDem = frac < 0.5;
      seats.push({
        x,
        y,
        party: isDem ? "democrat" : "republican",
        mid: Math.abs(frac - 0.5) < 0.04,
      });
    }
  });
  return (
    <svg viewBox="0 0 200 100" style={{ width: "100%", height: "auto" }}>
      {seats.map((s, i) => (
        <circle
          key={i}
          cx={s.x}
          cy={s.y}
          r={s.mid ? 2.4 : 3.4}
          fill={
            s.mid ? "var(--gold)" : s.party === "democrat" ? "var(--dem)" : "var(--rep)"
          }
          opacity={s.mid ? 1 : 0.85}
        />
      ))}
      <path
        d="M100 92 m-9 0 a9 9 0 0 1 18 0"
        fill="none"
        stroke="var(--gold-deep)"
        strokeWidth="1"
      />
    </svg>
  );
}
