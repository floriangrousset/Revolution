import { useState } from "react";
import { partyBright, partyColor, partyWash } from "../theme";
import type { Persona, PersonaSummary } from "../types";
import { Icon } from "./Icon";

export function Avatar({
  p,
  size = 44,
  ring = true,
}: {
  p: Pick<Persona | PersonaSummary, "name" | "party" | "role" | "image_url">;
  size?: number;
  ring?: boolean;
}) {
  // Track WHICH url errored, so a reused (un-keyed) instance retries when
  // the persona — or a corrected portrait URL — changes under it.
  const [errorUrl, setErrorUrl] = useState<string | null>(null);
  const initials = p.name
    .split(" ")
    .filter(Boolean)
    .slice(-2)
    .map((s) => s[0])
    .join("");
  const head = p.role === "party_head";
  const showImage = !!p.image_url && errorUrl !== p.image_url;
  return (
    <div style={{ position: "relative", width: size, height: size, flex: "0 0 auto" }}>
      {showImage ? (
        <img
          src={p.image_url}
          alt={p.name}
          onError={() => setErrorUrl(p.image_url ?? null)}
          style={{
            width: size,
            height: size,
            borderRadius: "50%",
            objectFit: "cover",
            display: "block",
            border: `1.5px solid ${ring ? partyColor(p.party) : "var(--ink-line)"}`,
            background: `linear-gradient(160deg, ${partyWash(p.party)}, rgba(0,0,0,0.18))`,
          }}
        />
      ) : (
        <div
          style={{
            width: size,
            height: size,
            borderRadius: "50%",
            display: "grid",
            placeItems: "center",
            background: `linear-gradient(160deg, ${partyWash(p.party)}, rgba(0,0,0,0.18))`,
            border: `1.5px solid ${ring ? partyColor(p.party) : "var(--ink-line)"}`,
            color: partyBright(p.party),
            fontWeight: 700,
            fontSize: size * 0.34,
            fontFamily: "var(--sans)",
            letterSpacing: "-.02em",
          }}
        >
          {initials}
        </div>
      )}
      {head && (
        <div
          title="Party Head"
          style={{
            position: "absolute",
            top: -3,
            right: -3,
            width: size * 0.42,
            height: size * 0.42,
            borderRadius: "50%",
            background: "var(--ink)",
            display: "grid",
            placeItems: "center",
            border: "1.5px solid var(--gold)",
          }}
        >
          <Icon name="scale" size={size * 0.24} style={{ color: "var(--gold-bright)" }} />
        </div>
      )}
    </div>
  );
}
