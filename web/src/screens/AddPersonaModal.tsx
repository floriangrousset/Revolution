import { useEffect, useState } from "react";
import { api } from "../api";
import { Btn } from "../components/Btn";
import { Field, TextArea, TextInput, inputStyle } from "../components/Form";
import { Icon } from "../components/Icon";
import { Modal } from "../components/Modal";
import { POSTURE_META, ROLE_META } from "../meta";
import type { NegotiationPosture, PartyEntry, Persona, Role } from "../types";

interface AddPersonaModalProps {
  open: boolean;
  onClose: () => void;
  onCreated: () => void;
}

const NEW_PARTY = "__new__";

export function AddPersonaModal({ open, onClose, onCreated }: AddPersonaModalProps) {
  const [parties, setParties] = useState<PartyEntry[]>([]);
  const [partyChoice, setPartyChoice] = useState<string>("democrat");
  const [newPartyId, setNewPartyId] = useState("");
  const [newPartyLabel, setNewPartyLabel] = useState("");
  const [newPartyColor, setNewPartyColor] = useState("#C2A14D");
  const [name, setName] = useState("");
  const [title, setTitle] = useState("");
  const [role, setRole] = useState<Role>("advisor");
  const [posture, setPosture] = useState<NegotiationPosture>("pragmatist");
  const [philosophy, setPhilosophy] = useState("");
  const [portraitUrl, setPortraitUrl] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setError(null);
    void api.listParties().then((r) => setParties(r.parties));
  }, [open]);

  const reset = () => {
    setName("");
    setTitle("");
    setPartyChoice("democrat");
    setNewPartyId("");
    setNewPartyLabel("");
    setNewPartyColor("#C2A14D");
    setRole("advisor");
    setPosture("pragmatist");
    setPhilosophy("");
    setPortraitUrl("");
    setError(null);
  };

  const close = () => {
    reset();
    onClose();
  };

  const submit = async () => {
    setError(null);
    if (!name.trim() || !title.trim() || !philosophy.trim()) {
      setError("Name, title, and philosophy are required.");
      return;
    }
    setSaving(true);
    try {
      let party = partyChoice;
      if (partyChoice === NEW_PARTY) {
        const id = newPartyId.trim().toLowerCase().replace(/[^a-z0-9_]/g, "_");
        if (!id || !newPartyLabel.trim()) {
          throw new Error("New party id and label are required.");
        }
        await api.createParty({ id, label: newPartyLabel.trim(), color: newPartyColor });
        party = id;
      }
      const slug = name.trim().toLowerCase().split(/\s+/).slice(-1)[0].replace(/[^a-z0-9]/g, "");
      const persona: Persona = {
        id: `${party.slice(0, 3)}_${role === "party_head" ? "head" : role === "advisor" ? "adv" : "asst"}_${slug || "new"}`,
        name: name.trim(),
        title: title.trim(),
        party,
        role,
        specialty: "",
        philosophy: philosophy.trim(),
        communication_style: "",
        key_positions: [],
        red_lines: [],
        rhetorical_signatures: [],
        allies: [],
        rivals: [],
        negotiation_posture: posture,
        constituency: "",
        persona_last_updated: new Date().toISOString().slice(0, 10),
        image_url: portraitUrl.trim(),
        image_attribution: "",
      };
      await api.createPersona(persona);
      onCreated();
      close();
    } catch (e) {
      setError((e as Error).message || String(e));
    } finally {
      setSaving(false);
    }
  };

  const isNewParty = partyChoice === NEW_PARTY;

  return (
    <Modal open={open} onClose={close} eyebrow="Seat a new agent" title="Create Persona" width={620}>
      <div
        style={{
          padding: "10px 12px",
          borderRadius: "var(--r-md)",
          background: "rgba(194,161,77,0.07)",
          border: "1px solid var(--ink-line)",
          marginBottom: 18,
          fontSize: 12.5,
          color: "var(--txt-mute)",
          display: "flex",
          gap: 9,
        }}
      >
        <Icon name="spark" size={15} style={{ color: "var(--gold)", flexShrink: 0, marginTop: 1 }} />
        New personas can join an existing party or seed a new one. They persist to the local persona
        store and become available in the next debate.
      </div>

      <Field label="Full name">
        <TextInput value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Justin Amash" />
      </Field>
      <Field label="Title / office">
        <TextInput
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="e.g. Former Representative from Michigan"
        />
      </Field>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
        <Field label="Party">
          <select
            value={partyChoice}
            onChange={(e) => setPartyChoice(e.target.value)}
            style={inputStyle}
          >
            {parties.map((p) => (
              <option key={p.id} value={p.id}>
                {p.label}
              </option>
            ))}
            <option value={NEW_PARTY}>+ Create new party</option>
          </select>
        </Field>
        <Field label="Role">
          <select
            value={role}
            onChange={(e) => setRole(e.target.value as Role)}
            style={inputStyle}
          >
            {(Object.keys(ROLE_META) as Role[]).map((k) => (
              <option key={k} value={k}>
                {ROLE_META[k].label}
              </option>
            ))}
          </select>
        </Field>
      </div>

      {isNewParty && (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr 96px",
            gap: 14,
            padding: 14,
            borderRadius: "var(--r-md)",
            background: "var(--ink)",
            border: "1px dashed var(--gold-deep)",
            marginBottom: 16,
          }}
        >
          <Field label="Party id">
            <TextInput
              value={newPartyId}
              onChange={(e) => setNewPartyId(e.target.value)}
              placeholder="e.g. libertarian"
            />
          </Field>
          <Field label="Label">
            <TextInput
              value={newPartyLabel}
              onChange={(e) => setNewPartyLabel(e.target.value)}
              placeholder="e.g. Libertarian Caucus"
            />
          </Field>
          <Field label="Color">
            <input
              type="color"
              value={newPartyColor}
              onChange={(e) => setNewPartyColor(e.target.value)}
              style={{ ...inputStyle, padding: 4, height: 42 }}
            />
          </Field>
        </div>
      )}

      <Field label="Negotiation posture">
        <select
          value={posture}
          onChange={(e) => setPosture(e.target.value as NegotiationPosture)}
          style={inputStyle}
        >
          {(Object.keys(POSTURE_META) as NegotiationPosture[]).map((k) => (
            <option key={k} value={k}>
              {POSTURE_META[k].label} — {POSTURE_META[k].desc}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Governing philosophy">
        <TextArea
          value={philosophy}
          onChange={(e) => setPhilosophy(e.target.value)}
          placeholder="What does this agent fundamentally believe?"
        />
      </Field>
      <Field label="Portrait URL (optional)">
        <TextInput
          value={portraitUrl}
          onChange={(e) => setPortraitUrl(e.target.value)}
          placeholder="e.g. /portraits/lib_adv_amash.jpg or https://…"
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
      <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, marginTop: 6 }}>
        <Btn kind="ghost" onClick={close}>
          Cancel
        </Btn>
        <Btn kind="primary" icon="check" onClick={submit} disabled={saving}>
          {saving ? "Seating…" : "Seat persona"}
        </Btn>
      </div>
    </Modal>
  );
}
