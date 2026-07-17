import { Icon } from "./Icon";

export function DisclaimerBar() {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 9,
        justifyContent: "center",
        padding: "7px 16px",
        background: "rgba(194,161,77,0.07)",
        borderTop: "1px solid var(--ink-line)",
        fontSize: 11.5,
        color: "var(--txt-faint)",
        letterSpacing: ".02em",
      }}
    >
      <Icon name="scale" size={13} style={{ color: "var(--gold)" }} />
      <span>
        <b style={{ color: "var(--gold)" }}>Simulation.</b> All personas are AI approximations of
        public political archetypes for research and modeling —{" "}
        <b style={{ color: "var(--txt-mute)" }}>not</b> the real individuals, and not statements of
        fact, endorsement, or prediction. Portraits are official public-domain or freely-licensed
        photos (see ATTRIBUTIONS) and imply no endorsement.
      </span>
    </div>
  );
}
