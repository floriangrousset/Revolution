import type { CSSProperties, ReactNode } from "react";
import { partyBright, partyColor, partyLabel, partyWash } from "../theme";
import { POSTURE_META, ROLE_META } from "../meta";
import type { NegotiationPosture, Party, Role, VoteValue } from "../types";
import { Icon } from "./Icon";

export interface PillProps {
  children: ReactNode;
  color?: string;
  bg?: string;
  border?: string;
  style?: CSSProperties;
  title?: string;
}

export function Pill({
  children,
  color = "var(--txt-mute)",
  bg = "transparent",
  border,
  style,
  title,
}: PillProps) {
  return (
    <span
      title={title}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 5,
        padding: "3px 9px",
        borderRadius: 999,
        fontSize: 11,
        fontWeight: 600,
        letterSpacing: ".02em",
        color,
        background: bg,
        border: `1px solid ${border || "transparent"}`,
        whiteSpace: "nowrap",
        ...style,
      }}
    >
      {children}
    </span>
  );
}

export function PartyTag({ party, size }: { party: Party; size?: "sm" }) {
  return (
    <Pill
      color={partyBright(party)}
      bg={partyWash(party)}
      border={partyColor(party)}
      style={size === "sm" ? { fontSize: 10, padding: "2px 7px" } : undefined}
    >
      <span
        style={{
          width: 6,
          height: 6,
          borderRadius: "50%",
          background: partyColor(party),
        }}
      />
      {partyLabel(party)}
    </Pill>
  );
}

export function RoleTag({ role }: { role: Role }) {
  const m = ROLE_META[role];
  return (
    <Pill color="var(--gold-bright)" border="var(--gold-deep)" bg="rgba(194,161,77,0.08)">
      {m.label}
    </Pill>
  );
}

export function PostureTag({ posture }: { posture: NegotiationPosture }) {
  const m = POSTURE_META[posture];
  return (
    <Pill title={m.desc} color="var(--txt-mute)" border="var(--ink-line)" bg="var(--ink2)">
      <span style={{ color: "var(--gold)", fontWeight: 700 }}>{m.glyph}</span>
      {m.label}
    </Pill>
  );
}

export const VOTE_META: Record<VoteValue, { label: string; color: string; icon: string }> = {
  support: { label: "Support", color: "var(--support)", icon: "check" },
  oppose: { label: "Oppose", color: "var(--oppose)", icon: "x" },
  abstain: { label: "Abstain", color: "var(--abstain)", icon: "dot" },
};

export function VoteTag({ vote, sm = false }: { vote: VoteValue; sm?: boolean }) {
  const m = VOTE_META[vote];
  return (
    <Pill
      color={m.color}
      border={m.color}
      bg="rgba(0,0,0,0.18)"
      style={sm ? { fontSize: 10, padding: "2px 7px" } : undefined}
    >
      <Icon name={m.icon} size={sm ? 10 : 12} stroke={2.2} />
      {m.label}
    </Pill>
  );
}

const STATUS_MAP: Record<string, { c: string; l: string }> = {
  passed: { c: "var(--pass)", l: "Passed" },
  rejected: { c: "var(--reject)", l: "Rejected" },
  debating: { c: "var(--gold-bright)", l: "Debating" },
  voting: { c: "var(--gold-bright)", l: "Voting" },
  pending: { c: "var(--txt-mute)", l: "Pending" },
  amended: { c: "var(--dem-bright)", l: "Amended" },
  accepted: { c: "var(--pass)", l: "Accepted" },
  incorporated: { c: "var(--pass)", l: "Incorporated" },
  contested: { c: "var(--gold-bright)", l: "Contested" },
  running: { c: "var(--gold-bright)", l: "Running" },
  error: { c: "var(--reject)", l: "Error" },
};

export function StatusTag({ status }: { status: string }) {
  const m = STATUS_MAP[status] || STATUS_MAP.pending;
  return (
    <Pill color={m.c} border={m.c} bg="rgba(0,0,0,0.2)">
      {m.l}
    </Pill>
  );
}
