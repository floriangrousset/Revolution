import { useEffect, useMemo, useState } from "react";
import type { CSSProperties, ReactNode } from "react";
import { api } from "../api";
import { Btn, IconBtn } from "../components/Btn";
import { Card, SectionTitle, Stat } from "../components/Card";
import { Field, TextArea, TextInput, inputStyle } from "../components/Form";
import { Icon } from "../components/Icon";
import { Modal } from "../components/Modal";
import { partyBright, partyColor, partyWash, setPartyRegistry } from "../theme";
import type { PartyEntry, PersonaSummary } from "../types";

interface PartiesProps {
  nav: (route: string, param?: string) => void;
  param?: string;
}

const PROTECTED_IDS = new Set(["democrat", "republican"]);

export function Parties({ nav, param }: PartiesProps) {
  if (param) return <PartyDetail id={param} nav={nav} />;
  return <PartyManager nav={nav} />;
}

// ---------------------------------------------------------------------------
// Manager — overview of all parties as cards.
// ---------------------------------------------------------------------------

function PartyManager({ nav }: { nav: PartiesProps["nav"] }) {
  const [parties, setParties] = useState<PartyEntry[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [addOpen, setAddOpen] = useState(false);

  const refresh = () => {
    void api
      .listParties()
      .then((r) => {
        setParties(r.parties);
        setPartyRegistry(r.parties);
      })
      .catch((e) => setError(String(e.message || e)));
  };

  useEffect(refresh, []);

  const totalSeats = parties.reduce((acc, p) => acc + p.seats, 0);
  const oldest = useMemo(() => {
    const dated = parties.filter((p) => p.founded_year != null);
    if (!dated.length) return null;
    return dated.reduce((a, b) =>
      (a.founded_year || Infinity) < (b.founded_year || Infinity) ? a : b,
    );
  }, [parties]);

  return (
    <div style={{ maxWidth: 1180, margin: "0 auto", padding: "34px 40px 60px" }}>
      <SectionTitle
        eyebrow={`${parties.length} caucus${parties.length === 1 ? "" : "es"} registered`}
        title="Party Manager"
        sub="Each party carries an ideology, founding year, motto, and color identity. Democrats and Republicans ship as the seeded chamber; every registered caucus can seat personas and take the floor in any debate you convene."
        right={
          <Btn kind="primary" icon="plus" onClick={() => setAddOpen(true)}>
            New party
          </Btn>
        }
      />

      {error && (
        <Card pad={16} style={{ marginBottom: 18, borderLeft: "3px solid var(--reject)" }}>
          <div style={{ color: "var(--reject)", fontSize: 13 }}>
            Couldn't load parties: {error}
          </div>
        </Card>
      )}

      <div
        className="ink-panel"
        style={{
          padding: "20px 28px",
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
          gap: 24,
          marginBottom: 30,
        }}
      >
        <Stat value={parties.length} label="Registered parties" />
        <Stat value={totalSeats} label="Total seated personas" color="var(--gold-bright)" />
        <Stat
          value={oldest ? `${oldest.founded_year}` : "—"}
          label="Oldest caucus"
          sub={oldest ? oldest.label : undefined}
        />
        <Stat
          value={parties.filter((p) => !PROTECTED_IDS.has(p.id)).length}
          label="Custom parties"
          color="var(--dem-bright)"
        />
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))",
          gap: 18,
        }}
      >
        {parties.map((p) => (
          <PartyCard key={p.id} p={p} onOpen={() => nav("parties", p.id)} />
        ))}
      </div>

      <AddPartyModal
        open={addOpen}
        onClose={() => setAddOpen(false)}
        onCreated={refresh}
      />
    </div>
  );
}

function PartyCard({ p, onOpen }: { p: PartyEntry; onOpen: () => void }) {
  return (
    <Card
      hover
      pad={0}
      onClick={onOpen}
      style={{ overflow: "hidden", borderTop: `3px solid ${p.color}` }}
    >
      <div
        style={{
          padding: "20px 22px 16px",
          display: "flex",
          flexDirection: "column",
          gap: 12,
          background: `linear-gradient(180deg, ${partyWash(p.id)}, transparent)`,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div
            style={{
              width: 40,
              height: 40,
              borderRadius: "50%",
              background: `linear-gradient(160deg, ${p.color}, rgba(0,0,0,0.2))`,
              border: `1.5px solid ${p.color}`,
              display: "grid",
              placeItems: "center",
              color: partyBright(p.id),
              fontWeight: 700,
              fontSize: 14,
              flexShrink: 0,
            }}
          >
            {p.label
              .replace(/Caucus|Conference|Party/gi, "")
              .trim()
              .split(/\s+/)
              .slice(0, 2)
              .map((s) => s[0])
              .filter(Boolean)
              .join("")
              .toUpperCase()}
          </div>
          <div style={{ minWidth: 0, flex: 1 }}>
            <div
              className="serif"
              style={{
                fontSize: 17,
                fontWeight: 600,
                color: "var(--txt)",
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
              }}
            >
              {p.label}
            </div>
            <div
              className="mono"
              style={{ fontSize: 11.5, color: "var(--txt-faint)", marginTop: 2 }}
            >
              {p.id}
              {p.founded_year ? ` · est. ${p.founded_year}` : ""}
            </div>
          </div>
        </div>
        {p.ideology && (
          <div style={{ fontSize: 13, color: "var(--txt-mute)" }}>{p.ideology}</div>
        )}
      </div>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "12px 22px",
          borderTop: "1px solid var(--ink-line)",
          background: "var(--ink1)",
        }}
      >
        <div
          style={{
            fontSize: 11.5,
            color: "var(--txt-faint)",
            display: "flex",
            alignItems: "center",
            gap: 8,
          }}
        >
          <Icon name="personas" size={13} /> {p.seats} seated
        </div>
        <Icon name="chevR" size={16} style={{ color: "var(--txt-faint)" }} />
      </div>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Detail / editor.
// ---------------------------------------------------------------------------

function PartyDetail({ id, nav }: { id: string; nav: PartiesProps["nav"] }) {
  const [party, setParty] = useState<PartyEntry | null>(null);
  const [draft, setDraft] = useState<PartyEntry | null>(null);
  const [seated, setSeated] = useState<PersonaSummary[]>([]);
  const [edit, setEdit] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const load = () => {
    setError(null);
    setEdit(false);
    void api
      .getParty(id)
      .then((p) => {
        setParty(p);
        setDraft(p);
      })
      .catch((e) => setError(String(e.message || e)));
    void api
      .listPersonas({ party: id })
      .then((r) => setSeated(r.personas))
      .catch(() => null);
  };

  useEffect(load, [id]);

  const set = <K extends keyof PartyEntry>(k: K, v: PartyEntry[K]) =>
    setDraft((d) => (d ? { ...d, [k]: v } : d));

  const save = async () => {
    if (!draft) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await api.updateParty(id, {
        label: draft.label,
        color: draft.color,
        ideology: draft.ideology,
        motto: draft.motto,
        description: draft.description,
        founded_year: draft.founded_year,
        history: draft.history,
        key_policies: draft.key_policies,
        notable_members: draft.notable_members,
        national_committee_chair: draft.national_committee_chair,
        electoral_strength: draft.electoral_strength,
      });
      setParty(updated);
      setDraft(updated);
      setEdit(false);
      const all = await api.listParties();
      setPartyRegistry(all.parties);
    } catch (e) {
      setError(String((e as Error).message || e));
    } finally {
      setSaving(false);
    }
  };

  const remove = async (force: boolean) => {
    setSaving(true);
    try {
      await api.deleteParty(id, force);
      const all = await api.listParties();
      setPartyRegistry(all.parties);
      nav("parties");
    } catch (e) {
      setError(String((e as Error).message || e));
    } finally {
      setSaving(false);
      setConfirmDelete(false);
    }
  };

  if (error && !party) {
    return (
      <div style={{ maxWidth: 980, margin: "0 auto", padding: "26px 40px 60px" }}>
        <Card pad={20} style={{ borderLeft: "3px solid var(--reject)" }}>
          <div style={{ color: "var(--reject)" }}>{error}</div>
        </Card>
      </div>
    );
  }
  if (!party || !draft) {
    return (
      <div style={{ maxWidth: 980, margin: "0 auto", padding: "26px 40px 60px" }}>
        <div style={{ color: "var(--txt-faint)", fontSize: 14 }}>Loading party…</div>
      </div>
    );
  }

  const protectedRow = PROTECTED_IDS.has(id);

  return (
    <div style={{ maxWidth: 980, margin: "0 auto", padding: "26px 40px 60px" }}>
      <div style={{ marginBottom: 22 }}>
        <button
          onClick={() => nav("parties")}
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
          <Icon name="chevL" size={16} /> Party Manager
        </button>
      </div>

      <div
        className="ink-panel"
        style={{
          padding: "28px 32px",
          marginBottom: 22,
          position: "relative",
          overflow: "hidden",
          borderTop: `3px solid ${draft.color}`,
        }}
      >
        <div style={{ display: "flex", gap: 22, alignItems: "flex-start" }}>
          <div
            style={{
              width: 70,
              height: 70,
              borderRadius: "50%",
              background: `linear-gradient(160deg, ${draft.color}, rgba(0,0,0,0.2))`,
              border: `2px solid ${draft.color}`,
              display: "grid",
              placeItems: "center",
              color: partyBright(id),
              fontWeight: 700,
              fontSize: 20,
              flexShrink: 0,
            }}
          >
            {draft.label
              .replace(/Caucus|Conference|Party/gi, "")
              .trim()
              .split(/\s+/)
              .slice(0, 2)
              .map((s) => s[0])
              .filter(Boolean)
              .join("")
              .toUpperCase()}
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            {edit ? (
              <TextInput
                value={draft.label}
                onChange={(e) => set("label", e.target.value)}
                style={{
                  fontSize: 24,
                  fontFamily: "var(--serif)",
                  fontWeight: 600,
                }}
              />
            ) : (
              <h1
                className="serif"
                style={{ fontSize: 28, fontWeight: 600, margin: "0 0 6px" }}
              >
                {draft.label}
              </h1>
            )}
            {!edit && draft.motto && (
              <div
                className="serif"
                style={{
                  fontSize: 15,
                  fontStyle: "italic",
                  color: "var(--gold-bright)",
                  marginTop: 4,
                }}
              >
                “{draft.motto}”
              </div>
            )}
            <div
              className="mono"
              style={{
                fontSize: 12,
                color: "var(--txt-faint)",
                marginTop: 10,
                display: "flex",
                gap: 14,
                flexWrap: "wrap",
              }}
            >
              <span>{draft.id}</span>
              {draft.founded_year && <span>founded {draft.founded_year}</span>}
              {draft.created_at && (
                <span>registered {new Date(draft.created_at).toLocaleDateString()}</span>
              )}
              <span>{party.seats} seated</span>
            </div>
          </div>
          <div style={{ display: "flex", gap: 10, flexShrink: 0 }}>
            {edit ? (
              <>
                <Btn
                  kind="ghost"
                  onClick={() => {
                    setDraft(party);
                    setEdit(false);
                  }}
                >
                  Cancel
                </Btn>
                <Btn kind="primary" icon="check" onClick={save} disabled={saving}>
                  {saving ? "Saving…" : "Save"}
                </Btn>
              </>
            ) : (
              <>
                {!protectedRow && (
                  <Btn kind="danger" icon="x" onClick={() => setConfirmDelete(true)}>
                    Delete
                  </Btn>
                )}
                <Btn kind="solid" icon="edit" onClick={() => setEdit(true)}>
                  Edit party
                </Btn>
              </>
            )}
          </div>
        </div>
        {error && (
          <div
            style={{
              marginTop: 16,
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

      <div style={{ display: "grid", gridTemplateColumns: "1.5fr 1fr", gap: 22 }}>
        <div style={{ display: "grid", gap: 22 }}>
          <Block title="Description" icon="doc">
            {edit ? (
              <TextArea
                value={draft.description || ""}
                onChange={(e) => set("description", e.target.value)}
                style={{ minHeight: 140 }}
              />
            ) : (
              <p style={pStyle}>
                {draft.description || "No description recorded yet."}
              </p>
            )}
          </Block>

          <Block title="Ideology" icon="feather">
            {edit ? (
              <TextInput
                value={draft.ideology || ""}
                onChange={(e) => set("ideology", e.target.value)}
              />
            ) : (
              <p style={pStyle}>{draft.ideology || "Unspecified."}</p>
            )}
          </Block>

          <Block title="Motto" icon="spark">
            {edit ? (
              <TextInput
                value={draft.motto || ""}
                onChange={(e) => set("motto", e.target.value)}
              />
            ) : (
              <p style={pStyle}>{draft.motto || "No motto recorded."}</p>
            )}
          </Block>

          <Block title="History" icon="scroll">
            {edit ? (
              <TextArea
                value={draft.history || ""}
                onChange={(e) => set("history", e.target.value)}
                style={{ minHeight: 160 }}
                placeholder="A paragraph on origins, realignments, and modern coalition…"
              />
            ) : (
              <p style={pStyle}>{draft.history || "No history recorded yet."}</p>
            )}
          </Block>

          <Block title="Key Policies" icon="check">
            {edit ? (
              <TextArea
                value={(draft.key_policies || []).join("\n")}
                onChange={(e) =>
                  set(
                    "key_policies",
                    e.target.value.split("\n").map((s) => s.trim()).filter(Boolean),
                  )
                }
                style={{ minHeight: 130 }}
                placeholder="One policy per line"
              />
            ) : (draft.key_policies || []).length > 0 ? (
              <ul style={listStyle}>
                {draft.key_policies!.map((p, i) => (
                  <li key={i} style={liStyle}>{p}</li>
                ))}
              </ul>
            ) : (
              <p style={pStyle}>No key policies recorded.</p>
            )}
          </Block>

          <Block title="Notable Members" icon="personas">
            {edit ? (
              <TextArea
                value={(draft.notable_members || []).join("\n")}
                onChange={(e) =>
                  set(
                    "notable_members",
                    e.target.value.split("\n").map((s) => s.trim()).filter(Boolean),
                  )
                }
                style={{ minHeight: 110 }}
                placeholder="One member per line — current or historical"
              />
            ) : (draft.notable_members || []).length > 0 ? (
              <ul style={listStyle}>
                {draft.notable_members!.map((m, i) => (
                  <li key={i} style={liStyle}>{m}</li>
                ))}
              </ul>
            ) : (
              <p style={pStyle}>No notable members recorded.</p>
            )}
          </Block>
        </div>

        <div style={{ display: "grid", gap: 22, alignContent: "start" }}>
          <Block title="Identity" icon="flag">
            <div style={{ display: "grid", gap: 14 }}>
              <KV
                label="Color"
                value={
                  edit ? (
                    <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                      <input
                        type="color"
                        value={draft.color}
                        onChange={(e) => set("color", e.target.value)}
                        style={{
                          ...inputStyle,
                          width: 56,
                          height: 36,
                          padding: 3,
                        }}
                      />
                      <span className="mono" style={{ fontSize: 13 }}>
                        {draft.color}
                      </span>
                    </div>
                  ) : (
                    <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                      <span
                        style={{
                          width: 22,
                          height: 22,
                          borderRadius: "50%",
                          background: draft.color,
                          border: "1px solid var(--ink-line)",
                        }}
                      />
                      <span className="mono" style={{ fontSize: 13 }}>
                        {draft.color}
                      </span>
                    </div>
                  )
                }
              />
              <KV
                label="Founded"
                value={
                  edit ? (
                    <TextInput
                      type="number"
                      value={draft.founded_year ?? ""}
                      placeholder="e.g. 1828"
                      onChange={(e) => {
                        const n = parseInt(e.target.value, 10);
                        set("founded_year", isNaN(n) ? null : n);
                      }}
                      style={{ maxWidth: 140 }}
                    />
                  ) : (
                    <span style={pStyle}>
                      {draft.founded_year ?? "Unknown"}
                    </span>
                  )
                }
              />
              <KV label="Registered" value={
                <span style={pStyle}>
                  {draft.created_at
                    ? new Date(draft.created_at).toLocaleString()
                    : "Unknown"}
                </span>
              } />
              <KV
                label="National Chair"
                value={
                  edit ? (
                    <TextInput
                      value={draft.national_committee_chair || ""}
                      onChange={(e) =>
                        set("national_committee_chair", e.target.value)
                      }
                      placeholder="e.g. Jaime Harrison (DNC)"
                    />
                  ) : (
                    <span style={pStyle}>
                      {draft.national_committee_chair || "Not recorded."}
                    </span>
                  )
                }
              />
            </div>
          </Block>

          <Block title="Electoral Strength" icon="results">
            {edit ? (
              <TextArea
                value={draft.electoral_strength || ""}
                onChange={(e) => set("electoral_strength", e.target.value)}
                style={{ minHeight: 90 }}
                placeholder="Federal seats, governorships, ballot access…"
              />
            ) : (
              <p style={pStyle}>
                {draft.electoral_strength || "No footprint recorded."}
              </p>
            )}
          </Block>

          <Block title={`Seated personas (${seated.length})`} icon="personas">
            {seated.length === 0 ? (
              <span style={{ fontSize: 13, color: "var(--txt-faint)" }}>
                No personas seated yet.
              </span>
            ) : (
              <div style={{ display: "grid", gap: 8 }}>
                {seated.map((s) => (
                  <button
                    key={s.id}
                    onClick={() => nav("personas", s.id)}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 10,
                      padding: "8px 10px",
                      borderRadius: "var(--r-md)",
                      background: "var(--ink)",
                      border: "1px solid var(--ink-line)",
                      color: "var(--txt)",
                      textAlign: "left",
                      width: "100%",
                    }}
                  >
                    <span
                      style={{
                        width: 6,
                        height: 6,
                        borderRadius: "50%",
                        background: partyColor(s.party),
                      }}
                    />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div
                        style={{
                          fontSize: 13,
                          fontWeight: 600,
                          whiteSpace: "nowrap",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                        }}
                      >
                        {s.name}
                      </div>
                      <div style={{ fontSize: 11.5, color: "var(--txt-faint)" }}>
                        {s.title}
                      </div>
                    </div>
                    <Icon name="chevR" size={14} style={{ color: "var(--txt-faint)" }} />
                  </button>
                ))}
              </div>
            )}
          </Block>
        </div>
      </div>

      <DeleteConfirm
        open={confirmDelete}
        partyLabel={party.label}
        seated={seated.length}
        saving={saving}
        onClose={() => setConfirmDelete(false)}
        onConfirm={(force) => remove(force)}
      />
    </div>
  );
}

const pStyle: CSSProperties = {
  fontSize: 14,
  color: "var(--txt-mute)",
  lineHeight: 1.65,
  margin: 0,
};

const listStyle: CSSProperties = {
  margin: 0,
  paddingLeft: 18,
  display: "grid",
  gap: 6,
};

const liStyle: CSSProperties = {
  fontSize: 14,
  color: "var(--txt-mute)",
  lineHeight: 1.55,
};

function Block({
  title,
  icon,
  children,
}: {
  title: string;
  icon: string;
  children: ReactNode;
}) {
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

function KV({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div>
      <div
        style={{
          fontSize: 11,
          textTransform: "uppercase",
          letterSpacing: ".12em",
          color: "var(--txt-faint)",
          fontWeight: 600,
          marginBottom: 6,
        }}
      >
        {label}
      </div>
      <div>{value}</div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Add modal — used by both this screen and (indirectly) AddPersonaModal.
// ---------------------------------------------------------------------------

function AddPartyModal({
  open,
  onClose,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: () => void;
}) {
  const [id, setId] = useState("");
  const [label, setLabel] = useState("");
  const [color, setColor] = useState("#C2A14D");
  const [ideology, setIdeology] = useState("");
  const [founded, setFounded] = useState<number | "">("");
  const [motto, setMotto] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const reset = () => {
    setId("");
    setLabel("");
    setColor("#C2A14D");
    setIdeology("");
    setFounded("");
    setMotto("");
    setDescription("");
    setError(null);
  };

  const close = () => {
    reset();
    onClose();
  };

  const submit = async () => {
    setError(null);
    const cleanId = id.trim().toLowerCase().replace(/[^a-z0-9_]+/g, "_");
    if (!cleanId || !label.trim()) {
      setError("Id and label are required.");
      return;
    }
    setSaving(true);
    try {
      await api.createParty({
        id: cleanId,
        label: label.trim(),
        color,
        ideology: ideology.trim(),
        motto: motto.trim(),
        description: description.trim(),
        founded_year: typeof founded === "number" ? founded : null,
      });
      onCreated();
      close();
    } catch (e) {
      setError(String((e as Error).message || e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal open={open} onClose={close} eyebrow="Seat a new caucus" title="Create Party" width={620}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
        <Field label="Id (slug)">
          <TextInput
            value={id}
            onChange={(e) => setId(e.target.value)}
            placeholder="e.g. green"
          />
        </Field>
        <Field label="Label">
          <TextInput
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            placeholder="e.g. Green Caucus"
          />
        </Field>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "120px 1fr 1fr", gap: 14 }}>
        <Field label="Color">
          <input
            type="color"
            value={color}
            onChange={(e) => setColor(e.target.value)}
            style={{ ...inputStyle, height: 42, padding: 4 }}
          />
        </Field>
        <Field label="Founded year">
          <TextInput
            type="number"
            value={founded}
            placeholder="2001"
            onChange={(e) => {
              const n = parseInt(e.target.value, 10);
              setFounded(isNaN(n) ? "" : n);
            }}
          />
        </Field>
        <Field label="Motto">
          <TextInput
            value={motto}
            onChange={(e) => setMotto(e.target.value)}
            placeholder="e.g. Ecology, justice, peace"
          />
        </Field>
      </div>
      <Field label="Ideology">
        <TextInput
          value={ideology}
          onChange={(e) => setIdeology(e.target.value)}
          placeholder="e.g. Classical liberalism"
        />
      </Field>
      <Field label="Description">
        <TextArea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="A paragraph on the caucus's history and platform…"
        />
      </Field>
      {error && (
        <div
          style={{
            marginBottom: 12,
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
      <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
        <Btn kind="ghost" onClick={close}>
          Cancel
        </Btn>
        <Btn kind="primary" icon="check" onClick={submit} disabled={saving}>
          {saving ? "Creating…" : "Create party"}
        </Btn>
      </div>
    </Modal>
  );
}

function DeleteConfirm({
  open,
  partyLabel,
  seated,
  saving,
  onClose,
  onConfirm,
}: {
  open: boolean;
  partyLabel: string;
  seated: number;
  saving: boolean;
  onClose: () => void;
  onConfirm: (force: boolean) => void;
}) {
  const blocked = seated > 0;
  return (
    <Modal
      open={open}
      onClose={onClose}
      eyebrow="Remove caucus"
      title={`Delete ${partyLabel}?`}
      width={460}
    >
      {blocked ? (
        <p style={pStyle}>
          This caucus still has <b style={{ color: "var(--gold)" }}>{seated}</b> seated
          {seated === 1 ? " persona" : " personas"}. Removing the caucus will permanently
          delete those personas too.
        </p>
      ) : (
        <p style={pStyle}>
          The caucus has no personas seated. This action removes its registry entry.
        </p>
      )}
      <div
        style={{
          display: "flex",
          justifyContent: "flex-end",
          gap: 10,
          marginTop: 18,
        }}
      >
        <Btn kind="ghost" onClick={onClose}>
          Cancel
        </Btn>
        <Btn kind="danger" icon="x" onClick={() => onConfirm(blocked)} disabled={saving}>
          {saving ? "Removing…" : blocked ? "Delete with personas" : "Delete caucus"}
        </Btn>
      </div>
    </Modal>
  );
}
