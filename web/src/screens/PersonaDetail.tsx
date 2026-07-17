import { useEffect, useState } from "react";
import type { CSSProperties, ReactNode } from "react";
import { api } from "../api";
import { Avatar } from "../components/Avatar";
import { Btn, IconBtn } from "../components/Btn";
import { Card } from "../components/Card";
import { TextArea, TextInput, inputStyle } from "../components/Form";
import { Icon } from "../components/Icon";
import { PersonaPicker } from "../components/PersonaPicker";
import { PartyTag, PostureTag, RoleTag } from "../components/Tags";
import { POSTURE_META } from "../meta";
import { partyColor } from "../theme";
import type { NegotiationPosture, PartyEntry, Persona, Role } from "../types";

interface PersonaDetailProps {
  id: string;
  nav: (route: string, param?: string) => void;
}

export function PersonaDetail({ id, nav }: PersonaDetailProps) {
  const [p, setP] = useState<Persona | null>(null);
  const [draft, setDraft] = useState<Persona | null>(null);
  const [parties, setParties] = useState<PartyEntry[]>([]);
  const [edit, setEdit] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setP(null);
    setDraft(null);
    setEdit(false);
    setError(null);
    void api
      .getPersona(id)
      .then((r) => {
        setP(r);
        setDraft(r);
      })
      .catch((e) => setError(String(e.message || e)));
    void api.listParties().then((r) => setParties(r.parties));
  }, [id]);

  if (error) {
    return (
      <div style={{ maxWidth: 1080, margin: "0 auto", padding: "26px 40px 60px" }}>
        <Card pad={20} style={{ borderLeft: "3px solid var(--reject)" }}>
          <div style={{ color: "var(--reject)" }}>Couldn't load persona: {error}</div>
        </Card>
      </div>
    );
  }
  if (!p || !draft) {
    return (
      <div style={{ maxWidth: 1080, margin: "0 auto", padding: "26px 40px 60px" }}>
        <div style={{ color: "var(--txt-faint)", fontSize: 14 }}>Loading persona…</div>
      </div>
    );
  }

  const set = <K extends keyof Persona>(k: K, v: Persona[K]) => setDraft((d) => ({ ...(d as Persona), [k]: v }));

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      const updated = await api.updatePersona(id, draft);
      setP(updated);
      setDraft(updated);
      setEdit(false);
    } catch (e) {
      setError((e as Error).message || String(e));
    } finally {
      setSaving(false);
    }
  };

  const cancel = () => {
    setDraft(p);
    setEdit(false);
    setError(null);
  };

  return (
    <div style={{ maxWidth: 1080, margin: "0 auto", padding: "26px 40px 60px" }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          marginBottom: 22,
          fontSize: 13,
          color: "var(--txt-mute)",
        }}
      >
        <button
          onClick={() => nav("personas")}
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
          <Icon name="chevL" size={16} /> Persona Manager
        </button>
      </div>

      <div
        className="ink-panel"
        style={{
          padding: "28px 32px",
          marginBottom: 22,
          position: "relative",
          overflow: "hidden",
          borderTop: `3px solid ${partyColor(draft.party)}`,
        }}
      >
        <div style={{ display: "flex", gap: 22, alignItems: "flex-start" }}>
          <Avatar p={draft} size={78} />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: "flex", gap: 8, marginBottom: 10, flexWrap: "wrap" }}>
              {edit ? (
                <>
                  <select
                    value={draft.party}
                    onChange={(e) => set("party", e.target.value)}
                    style={{
                      ...inputStyle,
                      width: "auto",
                      padding: "5px 10px",
                      fontSize: 12,
                    }}
                  >
                    {parties.map((pp) => (
                      <option key={pp.id} value={pp.id}>
                        {pp.label}
                      </option>
                    ))}
                  </select>
                  <select
                    value={draft.role}
                    onChange={(e) => set("role", e.target.value as Role)}
                    style={{
                      ...inputStyle,
                      width: "auto",
                      padding: "5px 10px",
                      fontSize: 12,
                    }}
                  >
                    <option value="party_head">Party Head</option>
                    <option value="advisor">Senior Advisor</option>
                    <option value="assistant">Policy Assistant</option>
                  </select>
                  <select
                    value={draft.negotiation_posture}
                    onChange={(e) =>
                      set("negotiation_posture", e.target.value as NegotiationPosture)
                    }
                    style={{
                      ...inputStyle,
                      width: "auto",
                      padding: "5px 10px",
                      fontSize: 12,
                    }}
                  >
                    {(Object.keys(POSTURE_META) as NegotiationPosture[]).map((k) => (
                      <option key={k} value={k}>
                        {POSTURE_META[k].label}
                      </option>
                    ))}
                  </select>
                </>
              ) : (
                <>
                  <PartyTag party={draft.party} />
                  <RoleTag role={draft.role} />
                  <PostureTag posture={draft.negotiation_posture} />
                </>
              )}
            </div>
            {edit ? (
              <TextInput
                value={draft.name}
                onChange={(e) => set("name", e.target.value)}
                style={{
                  fontSize: 24,
                  fontFamily: "var(--serif)",
                  fontWeight: 600,
                  marginBottom: 8,
                }}
              />
            ) : (
              <h1
                className="serif"
                style={{ fontSize: 30, fontWeight: 600, margin: "0 0 6px", whiteSpace: "nowrap" }}
              >
                {draft.name}
              </h1>
            )}
            {edit ? (
              <TextInput
                value={draft.title}
                onChange={(e) => set("title", e.target.value)}
              />
            ) : (
              <div style={{ fontSize: 15, color: "var(--txt-mute)" }}>{draft.title}</div>
            )}
            {edit && (
              <TextInput
                value={draft.image_url ?? ""}
                onChange={(e) => set("image_url", e.target.value)}
                placeholder="Portrait URL (optional — /portraits/<id>.jpg or https://…)"
                style={{ marginTop: 8 }}
              />
            )}
            <div
              className="mono"
              style={{ fontSize: 12, color: "var(--txt-faint)", marginTop: 10 }}
            >
              {draft.id}
              {draft.persona_last_updated ? ` · updated ${draft.persona_last_updated}` : ""}
            </div>
            {!edit && draft.image_attribution && (
              <div style={{ fontSize: 11, color: "var(--txt-faint)", marginTop: 6 }}>
                {draft.image_attribution}
              </div>
            )}
          </div>
          <div style={{ display: "flex", gap: 10, flexShrink: 0 }}>
            {edit ? (
              <>
                <Btn kind="ghost" onClick={cancel}>
                  Cancel
                </Btn>
                <Btn kind="primary" icon="check" onClick={save} disabled={saving}>
                  {saving ? "Saving…" : "Save"}
                </Btn>
              </>
            ) : (
              <Btn kind="solid" icon="edit" onClick={() => setEdit(true)}>
                Edit persona
              </Btn>
            )}
          </div>
        </div>
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
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1.6fr 1fr", gap: 22 }}>
        <div style={{ display: "grid", gap: 22 }}>
          <Block title="Specialty" icon="spark">
            {edit ? (
              <TextInput value={draft.specialty} onChange={(e) => set("specialty", e.target.value)} />
            ) : (
              <p style={pStyle}>{draft.specialty}</p>
            )}
          </Block>

          <Block title="Governing Philosophy" icon="feather">
            {edit ? (
              <TextArea
                value={draft.philosophy}
                onChange={(e) => set("philosophy", e.target.value)}
                style={{ minHeight: 120 }}
              />
            ) : (
              <p
                style={{
                  ...pStyle,
                  fontFamily: "var(--serif)",
                  fontSize: 16,
                  lineHeight: 1.65,
                  fontStyle: "italic",
                  color: "var(--txt)",
                }}
              >
                “{draft.philosophy}”
              </p>
            )}
          </Block>

          <Block title="Communication Style" icon="transcript">
            {edit ? (
              <TextArea
                value={draft.communication_style}
                onChange={(e) => set("communication_style", e.target.value)}
              />
            ) : (
              <p style={pStyle}>{draft.communication_style}</p>
            )}
          </Block>

          <Block title="Key Positions" icon="check">
            <EditList
              items={draft.key_positions}
              edit={edit}
              onChange={(v) => set("key_positions", v)}
              color="var(--support)"
              mark="check"
            />
          </Block>

          <Block title="Red Lines" icon="x">
            <EditList
              items={draft.red_lines}
              edit={edit}
              onChange={(v) => set("red_lines", v)}
              color="var(--oppose)"
              mark="x"
            />
          </Block>

          <Block title="Rhetorical Signatures" icon="feather">
            <EditList
              items={draft.rhetorical_signatures}
              edit={edit}
              onChange={(v) => set("rhetorical_signatures", v)}
              color="var(--gold-bright)"
              mark="dot"
            />
          </Block>
        </div>

        <div style={{ display: "grid", gap: 22, alignContent: "start" }}>
          <Block title="Negotiation Posture" icon="scale">
            {edit ? (
              <select
                value={draft.negotiation_posture}
                onChange={(e) => set("negotiation_posture", e.target.value as NegotiationPosture)}
                style={inputStyle}
              >
                {(Object.keys(POSTURE_META) as NegotiationPosture[]).map((k) => (
                  <option key={k} value={k}>
                    {POSTURE_META[k].label}
                  </option>
                ))}
              </select>
            ) : (
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
                  <span style={{ fontSize: 22, color: "var(--gold-bright)" }}>
                    {POSTURE_META[draft.negotiation_posture].glyph}
                  </span>
                  <span className="serif" style={{ fontSize: 17, fontWeight: 600 }}>
                    {POSTURE_META[draft.negotiation_posture].label}
                  </span>
                </div>
                <p style={{ ...pStyle, fontSize: 13 }}>
                  {POSTURE_META[draft.negotiation_posture].desc}
                </p>
              </div>
            )}
          </Block>

          <Block title="Constituency" icon="flag">
            {edit ? (
              <TextArea
                value={draft.constituency}
                onChange={(e) => set("constituency", e.target.value)}
              />
            ) : (
              <p style={pStyle}>{draft.constituency || "Not specified."}</p>
            )}
          </Block>

          <Block title="In-Room Relationships" icon="graph">
            {edit ? (
              <div style={{ display: "grid", gap: 16 }}>
                <div>
                  <div
                    style={{
                      fontSize: 11,
                      fontWeight: 600,
                      letterSpacing: ".1em",
                      textTransform: "uppercase",
                      color: "var(--support)",
                      marginBottom: 8,
                    }}
                  >
                    Allies
                  </div>
                  <PersonaPicker
                    party={draft.party}
                    selfId={draft.id}
                    value={draft.allies}
                    onChange={(v) => set("allies", v)}
                    accent="var(--support)"
                    placeholder="Add an ally from the same caucus…"
                  />
                </div>
                <div>
                  <div
                    style={{
                      fontSize: 11,
                      fontWeight: 600,
                      letterSpacing: ".1em",
                      textTransform: "uppercase",
                      color: "var(--oppose)",
                      marginBottom: 8,
                    }}
                  >
                    Rivals
                  </div>
                  <PersonaPicker
                    party={draft.party}
                    selfId={draft.id}
                    value={draft.rivals}
                    onChange={(v) => set("rivals", v)}
                    accent="var(--oppose)"
                    placeholder="Add a rival from the same caucus…"
                  />
                </div>
              </div>
            ) : (
              <Relationships allies={draft.allies} rivals={draft.rivals} nav={nav} />
            )}
          </Block>
        </div>
      </div>
    </div>
  );
}

const pStyle: CSSProperties = {
  fontSize: 14,
  color: "var(--txt-mute)",
  lineHeight: 1.65,
  margin: 0,
};

function Block({ title, icon, children }: { title: string; icon: string; children: ReactNode }) {
  return (
    <div className="ink-panel" style={{ padding: "20px 22px" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 9, marginBottom: 14 }}>
        <Icon name={icon} size={15} style={{ color: "var(--gold)" }} />
        <span
          style={{
            fontSize: 11.5,
            fontWeight: 700,
            letterSpacing: ".14em",
            textTransform: "uppercase",
            color: "var(--txt-faint)",
          }}
        >
          {title}
        </span>
      </div>
      {children}
    </div>
  );
}

function EditList({
  items,
  edit,
  onChange,
  color,
  mark,
}: {
  items: string[];
  edit: boolean;
  onChange: (v: string[]) => void;
  color: string;
  mark: string;
}) {
  if (!edit) {
    if (!items?.length) {
      return <span style={{ fontSize: 13, color: "var(--txt-faint)" }}>None recorded</span>;
    }
    return (
      <div style={{ display: "grid", gap: 10 }}>
        {items.map((it, i) => (
          <div key={i} style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
            <Icon name={mark} size={14} stroke={2.2} style={{ color, marginTop: 3 }} />
            <span style={{ fontSize: 13.5, color: "var(--txt-mute)", lineHeight: 1.55 }}>{it}</span>
          </div>
        ))}
      </div>
    );
  }
  return (
    <div style={{ display: "grid", gap: 8 }}>
      {(items || []).map((it, i) => (
        <div key={i} style={{ display: "flex", gap: 8 }}>
          <TextInput
            value={it}
            onChange={(e) => {
              const n = [...items];
              n[i] = e.target.value;
              onChange(n);
            }}
          />
          <IconBtn name="close" onClick={() => onChange(items.filter((_, j) => j !== i))} />
        </div>
      ))}
      <Btn
        kind="ghost"
        size="sm"
        icon="plus"
        onClick={() => onChange([...(items || []), ""])}
      >
        Add item
      </Btn>
    </div>
  );
}

function Relationships({
  allies,
  rivals,
  nav,
}: {
  allies: string[];
  rivals: string[];
  nav: (route: string, param?: string) => void;
}) {
  const [a, setA] = useState<Persona[]>([]);
  const [r, setR] = useState<Persona[]>([]);

  useEffect(() => {
    const lookup = (ids: string[]) =>
      Promise.all(ids.map((aid) => api.getPersona(aid).catch(() => null))).then((rs) =>
        rs.filter((x): x is Persona => x !== null),
      );
    void lookup(allies).then(setA);
    void lookup(rivals).then(setR);
  }, [allies.join("|"), rivals.join("|")]);

  const row: CSSProperties = {
    display: "flex",
    alignItems: "center",
    gap: 10,
    padding: "7px 9px",
    borderRadius: "var(--r-md)",
    background: "var(--ink)",
    border: "1px solid var(--ink-line)",
    color: "var(--txt)",
    width: "100%",
    textAlign: "left",
  };

  return (
    <>
      <div
        style={{
          fontSize: 11,
          fontWeight: 600,
          letterSpacing: ".1em",
          textTransform: "uppercase",
          color: "var(--support)",
          marginBottom: 8,
        }}
      >
        Allies
      </div>
      <div style={{ display: "grid", gap: 8, marginBottom: 16 }}>
        {a.length ? (
          a.map((ally) => (
            <button key={ally.id} onClick={() => nav("personas", ally.id)} style={row}>
              <Avatar p={ally} size={30} ring={false} />
              <span style={{ fontSize: 13, fontWeight: 600 }}>{ally.name}</span>
              <Icon
                name="chevR"
                size={14}
                style={{ marginLeft: "auto", color: "var(--txt-faint)" }}
              />
            </button>
          ))
        ) : (
          <span style={{ fontSize: 13, color: "var(--txt-faint)" }}>None recorded</span>
        )}
      </div>
      <div
        style={{
          fontSize: 11,
          fontWeight: 600,
          letterSpacing: ".1em",
          textTransform: "uppercase",
          color: "var(--oppose)",
          marginBottom: 8,
        }}
      >
        Rivals
      </div>
      <div style={{ display: "grid", gap: 8 }}>
        {r.length ? (
          r.map((rival) => (
            <button key={rival.id} onClick={() => nav("personas", rival.id)} style={row}>
              <Avatar p={rival} size={30} ring={false} />
              <span style={{ fontSize: 13, fontWeight: 600 }}>{rival.name}</span>
              <Icon
                name="chevR"
                size={14}
                style={{ marginLeft: "auto", color: "var(--txt-faint)" }}
              />
            </button>
          ))
        ) : (
          <span style={{ fontSize: 13, color: "var(--txt-faint)" }}>None recorded</span>
        )}
      </div>
    </>
  );
}
