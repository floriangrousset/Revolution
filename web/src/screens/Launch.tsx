import { useEffect, useState } from "react";
import { api } from "../api";
import { Btn } from "../components/Btn";
import { Card, SectionTitle } from "../components/Card";
import { TextArea } from "../components/Form";
import { Icon } from "../components/Icon";
import { T, partyBright, partyColor, partyLabel, partyWash } from "../theme";
import type { PartyEntry } from "../types";

interface LaunchProps {
  nav: (route: string, param?: string) => void;
}

const SAMPLES = [
  "Should the federal minimum wage be raised to $17/hour?",
  "Should the United States adopt a single-payer Medicare for All system?",
  "Should Congress impose 12-year term limits via constitutional amendment?",
  "Should we implement a federal universal basic income of $1,200/month?",
  "Should the U.S. adopt a Green New Deal framework targeting net-zero by 2040?",
];

const PASSAGE_RULES: { id: "majority" | "three_fifths" | "two_thirds"; label: string; hint: string }[] = [
  { id: "majority", label: "Simple majority", hint: "More support than oppose" },
  { id: "three_fifths", label: "3⁄5 cloture", hint: "60% of decisive votes" },
  { id: "two_thirds", label: "2⁄3 supermajority", hint: "67% of decisive votes" },
];

export function Launch({ nav }: LaunchProps) {
  const [text, setText] = useState("");
  const [rounds, setRounds] = useState(2);
  const [temp, setTemp] = useState(0.8);
  const [passageRule, setPassageRule] = useState<"majority" | "three_fifths" | "two_thirds">("majority");
  const [seatWeights, setSeatWeights] = useState(false);
  const [markupRound, setMarkupRound] = useState(false);
  const [parties, setParties] = useState<Record<string, boolean>>({
    democrat: true,
    republican: true,
  });
  const [allParties, setAllParties] = useState<PartyEntry[]>([]);
  const [defaultModel, setDefaultModel] = useState<string>("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void api.listParties().then((r) => setAllParties(r.parties));
    void api
      .getSettings()
      .then((s) => {
        setDefaultModel(s.default_model);
        if (typeof s.default_temperature === "number") setTemp(s.default_temperature);
      })
      .catch(() => null);
  }, []);

  const apiCalls = 24 + rounds * 6;

  const submit = async () => {
    setError(null);
    if (!text.trim()) {
      setError("Enter a motion to begin.");
      return;
    }
    setSubmitting(true);
    try {
      const chosenParties = Object.entries(parties)
        .filter(([, on]) => on)
        .map(([k]) => k);
      const resp = await api.createDebate({
        proposal: text.trim(),
        max_rounds: rounds,
        temperature: temp,
        parties: chosenParties,
        passage_rule: passageRule,
        use_seat_weights: seatWeights,
        markup_rounds: markupRound ? 1 : 0,
      });
      nav("results", resp.id);
    } catch (e) {
      setError((e as Error).message || String(e));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div style={{ maxWidth: 1080, margin: "0 auto", padding: "34px 40px 60px" }}>
      <SectionTitle
        eyebrow="Convene the Floor"
        title="Launch a Debate"
        sub="Submit a proposal, set the terms of deliberation, and the chamber will form positions, debate across the aisle, and vote."
      />

      <div style={{ display: "grid", gridTemplateColumns: "1.55fr 1fr", gap: 24 }}>
        <div style={{ display: "grid", gap: 22 }}>
          <Card pad={26}>
            <div className="eyebrow" style={{ marginBottom: 14 }}>
              The Motion
            </div>
            <TextArea
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Resolved: that the United States shall…"
              style={{
                minHeight: 130,
                fontSize: 16,
                fontFamily: "var(--serif)",
                lineHeight: 1.6,
              }}
            />
            <div style={{ marginTop: 16 }}>
              <div
                style={{
                  fontSize: 11.5,
                  color: "var(--txt-faint)",
                  letterSpacing: ".1em",
                  textTransform: "uppercase",
                  fontWeight: 600,
                  marginBottom: 10,
                }}
              >
                Or start from a sample
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 9 }}>
                {SAMPLES.map((s, i) => (
                  <button
                    key={i}
                    onClick={() => setText(s)}
                    style={{
                      padding: "8px 13px",
                      borderRadius: 999,
                      fontSize: 12.5,
                      background: "var(--ink)",
                      border: "1px solid var(--ink-line)",
                      color: "var(--txt-mute)",
                      textAlign: "left",
                      transition: "all .15s ease",
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.borderColor = "var(--gold-deep)";
                      e.currentTarget.style.color = "var(--txt)";
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.borderColor = "var(--ink-line)";
                      e.currentTarget.style.color = "var(--txt-mute)";
                    }}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          </Card>

          <Card pad={26}>
            <div className="eyebrow" style={{ marginBottom: 18 }}>
              Deliberation Terms
            </div>
            <div style={{ marginBottom: 24 }}>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  marginBottom: 11,
                }}
              >
                <span style={{ fontSize: 13.5, fontWeight: 600 }}>
                  Cross-party debate rounds
                </span>
                <span className="mono" style={{ fontSize: 13, color: "var(--gold-bright)" }}>
                  {rounds} round{rounds > 1 ? "s" : ""}
                </span>
              </div>
              <div style={{ display: "flex", gap: 8 }}>
                {[1, 2, 3, 4, 5].map((r) => (
                  <button
                    key={r}
                    onClick={() => setRounds(r)}
                    style={{
                      flex: 1,
                      padding: "12px 0",
                      borderRadius: "var(--r-md)",
                      fontWeight: 700,
                      fontSize: 15,
                      fontFamily: "var(--serif)",
                      background:
                        rounds === r
                          ? "linear-gradient(180deg,var(--gold),var(--gold-deep))"
                          : "var(--ink)",
                      color: rounds === r ? "#1B1405" : "var(--txt-mute)",
                      border: `1px solid ${rounds === r ? "var(--gold-deep)" : "var(--ink-line)"}`,
                      transition: "all .15s ease",
                    }}
                  >
                    {r}
                  </button>
                ))}
              </div>
              <div style={{ fontSize: 12, color: "var(--txt-faint)", marginTop: 10 }}>
                More rounds mean deeper rebuttals and more opportunities for agents to change
                their votes.
              </div>
            </div>

            <div style={{ marginBottom: 24 }}>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  marginBottom: 11,
                }}
              >
                <span style={{ fontSize: 13.5, fontWeight: 600 }}>Passage rule</span>
                <span className="mono" style={{ fontSize: 13, color: "var(--gold-bright)" }}>
                  {PASSAGE_RULES.find((r) => r.id === passageRule)?.label}
                </span>
              </div>
              <div style={{ display: "flex", gap: 8 }}>
                {PASSAGE_RULES.map((r) => (
                  <button
                    key={r.id}
                    onClick={() => setPassageRule(r.id)}
                    style={{
                      flex: 1,
                      padding: "10px 0",
                      borderRadius: "var(--r-md)",
                      fontWeight: 700,
                      fontSize: 13,
                      fontFamily: "var(--serif)",
                      background:
                        passageRule === r.id
                          ? "linear-gradient(180deg,var(--gold),var(--gold-deep))"
                          : "var(--ink)",
                      color: passageRule === r.id ? "#1B1405" : "var(--txt-mute)",
                      border: `1px solid ${passageRule === r.id ? "var(--gold-deep)" : "var(--ink-line)"}`,
                      transition: "all .15s ease",
                    }}
                    title={r.hint}
                  >
                    {r.label}
                  </button>
                ))}
              </div>
              <div style={{ fontSize: 12, color: "var(--txt-faint)", marginTop: 10 }}>
                {passageRule === "majority"
                  ? "The motion passes when support outnumbers opposition."
                  : passageRule === "three_fifths"
                    ? "Modeled on Senate cloture — 3⁄5 of decisive votes must support."
                    : "Modeled on veto-override votes — 2⁄3 of decisive votes must support."}
              </div>
            </div>

            <div style={{ marginBottom: 24 }}>
              <label
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  cursor: "pointer",
                  fontSize: 13.5,
                  fontWeight: 600,
                }}
              >
                <input
                  type="checkbox"
                  checked={seatWeights}
                  onChange={(e) => setSeatWeights(e.target.checked)}
                  style={{ accentColor: T.gold, width: 15, height: 15 }}
                />
                Seat-weighted voting
              </label>
              <div style={{ fontSize: 12, color: "var(--txt-faint)", marginTop: 8, paddingLeft: 25 }}>
                Weight each caucus's ballots by its real chamber strength (the party's
                configured seat count) instead of one agent, one vote. Parties without a
                configured seat count vote unweighted.
              </div>
            </div>

            <div style={{ marginBottom: 24 }}>
              <label
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  cursor: "pointer",
                  fontSize: 13.5,
                  fontWeight: 600,
                }}
              >
                <input
                  type="checkbox"
                  checked={markupRound}
                  onChange={(e) => setMarkupRound(e.target.checked)}
                  style={{ accentColor: T.gold, width: 15, height: 15 }}
                />
                Allow one markup round
              </label>
              <div style={{ fontSize: 12, color: "var(--txt-faint)", marginTop: 8, paddingLeft: 25 }}>
                If the motion fails and amendments were tabled, the clerk incorporates the
                most-sponsored amendment, the heads debate the amended text, and the chamber
                re-votes. A motion that then passes is recorded as “amended”.
              </div>
            </div>

            <div>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  marginBottom: 11,
                }}
              >
                <span style={{ fontSize: 13.5, fontWeight: 600 }}>Temperature</span>
                <span className="mono" style={{ fontSize: 13, color: "var(--gold-bright)" }}>
                  {temp.toFixed(2)}
                </span>
              </div>
              <input
                type="range"
                min={0}
                max={1}
                step={0.05}
                value={temp}
                onChange={(e) => setTemp(parseFloat(e.target.value))}
                style={{ width: "100%", accentColor: T.gold }}
              />
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  fontSize: 11.5,
                  color: "var(--txt-faint)",
                  marginTop: 7,
                }}
              >
                <span>Disciplined · on-message</span>
                <span>Volatile · unpredictable</span>
              </div>
            </div>
          </Card>

          <Card pad={20}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 12,
                fontSize: 12.5,
                color: "var(--txt-mute)",
                lineHeight: 1.5,
              }}
            >
              <Icon name="settings" size={16} style={{ color: "var(--gold)", flexShrink: 0 }} />
              <div>
                The reasoning model is configured globally in{" "}
                <a
                  href="#/settings"
                  style={{ color: "var(--gold-bright)", textDecoration: "underline" }}
                >
                  Settings
                </a>
                . Temperature stays per-debate so you can dial volatility for each motion.
              </div>
            </div>
          </Card>
        </div>

        <div style={{ display: "grid", gap: 22, alignContent: "start", position: "sticky", top: 24 }}>
          <Card pad={24}>
            <div className="eyebrow" style={{ marginBottom: 16 }}>
              Participating Caucuses
            </div>
            {allParties.map((p) => {
              const on = parties[p.id] ?? false;
              return (
                <button
                  key={p.id}
                  onClick={() => setParties((s) => ({ ...s, [p.id]: !s[p.id] }))}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 13,
                    width: "100%",
                    padding: "13px 14px",
                    borderRadius: "var(--r-md)",
                    marginBottom: 10,
                    background: on ? partyWash(p.id) : "var(--ink)",
                    border: `1px solid ${on ? partyColor(p.id) : "var(--ink-line)"}`,
                    transition: "all .15s ease",
                  }}
                >
                  <span
                    style={{
                      width: 9,
                      height: 9,
                      borderRadius: "50%",
                      background: partyColor(p.id),
                    }}
                  />
                  <span style={{ fontSize: 14, fontWeight: 600, color: "var(--txt)" }}>
                    {p.label || partyLabel(p.id)} ({p.seats})
                  </span>
                  <span style={{ marginLeft: "auto", color: on ? partyBright(p.id) : "var(--txt-faint)" }}>
                    <Icon name={on ? "check" : "plus"} size={16} stroke={2.2} />
                  </span>
                </button>
              );
            })}
            <div style={{ fontSize: 12, color: "var(--txt-faint)", marginTop: 6, lineHeight: 1.5 }}>
              Custom parties you create in the Persona Manager will appear here automatically.
              (Note: the engine currently runs the deliberation flow for democrat & republican
              only.)
            </div>
          </Card>

          <Card pad={24}>
            <div className="eyebrow" style={{ marginBottom: 16 }}>
              Session Forecast
            </div>
            <div style={{ display: "grid", gap: 14 }}>
              <SummaryRow
                label="Agents seated"
                value={String(allParties.reduce((acc, p) => acc + p.seats, 0))}
              />
              <SummaryRow
                label="Reasoning model"
                value={defaultModel || "from settings"}
              />
              <SummaryRow label="Debate rounds" value={rounds} />
              <SummaryRow label="Est. API calls" value={`~${apiCalls}`} />
              <SummaryRow label="Est. runtime" value={`${5 + rounds * 3}–${9 + rounds * 4} min`} />
            </div>
          </Card>

          <Btn
            kind="primary"
            size="lg"
            icon="launch"
            full
            disabled={!text.trim() || submitting}
            onClick={submit}
          >
            {submitting ? "Convening…" : "Convene the Debate"}
          </Btn>
          {error && (
            <div
              style={{
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
          <div
            style={{
              display: "flex",
              gap: 8,
              alignItems: "flex-start",
              fontSize: 11.5,
              color: "var(--txt-faint)",
              lineHeight: 1.5,
            }}
          >
            <Icon
              name="scale"
              size={13}
              style={{ color: "var(--gold)", flexShrink: 0, marginTop: 2 }}
            />
            This is a simulation. Outcomes model how AI personas reason — they are not predictions
            of how any real body would vote.
          </div>
        </div>
      </div>
    </div>
  );
}

function SummaryRow({
  label,
  value,
  accent,
}: {
  label: string;
  value: string | number;
  accent?: boolean;
}) {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        paddingBottom: 12,
        borderBottom: "1px solid var(--ink-line-soft)",
      }}
    >
      <span style={{ fontSize: 13, color: "var(--txt-mute)" }}>{label}</span>
      <span
        style={{
          fontSize: 13.5,
          fontWeight: 600,
          color: accent ? "var(--gold-bright)" : "var(--txt)",
        }}
      >
        {value}
      </span>
    </div>
  );
}
