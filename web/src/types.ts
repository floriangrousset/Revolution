/* Shared client types — mirror server/db.py + API_SPEC.md. */

export type Party = "republican" | "democrat" | string;
export type Role = "party_head" | "advisor" | "assistant";
export type NegotiationPosture =
  | "dealmaker"
  | "hardliner"
  | "pragmatist"
  | "bomb_thrower"
  | "institutionalist";
export type VoteValue = "support" | "oppose" | "abstain";
export type DebateStatus =
  | "pending"
  | "running"
  | "voting"
  | "passed"
  | "rejected"
  | "amended"
  | "error";

export interface Source {
  title: string;
  url: string;
  date: string;
  source_type: string;
  description?: string;
}

export interface PersonaSummary {
  id: string;
  name: string;
  title: string;
  party: Party;
  role: Role;
  specialty: string;
  negotiation_posture: NegotiationPosture;
  persona_last_updated: string;
  image_url?: string;
  image_attribution?: string;
}

export interface Persona extends PersonaSummary {
  philosophy: string;
  communication_style: string;
  key_positions: string[];
  red_lines: string[];
  rhetorical_signatures: string[];
  allies: string[];
  rivals: string[];
  constituency: string;
  personality_assessment?: string;
  sources?: Source[];
}

export interface PartyEntry {
  id: string;
  label: string;
  color: string;
  seats: number;
  description?: string;
  ideology?: string;
  founded_year?: number | null;
  motto?: string;
  /** Long-form paragraph describing origin and political evolution. */
  history?: string;
  /** Signature policy positions, rendered as bullets in the Party Detail page. */
  key_policies?: string[];
  /** Prominent current and historical figures, rendered as bullets. */
  notable_members?: string[];
  /** National committee chair (or equivalent — Director, Co-Chair, etc.). */
  national_committee_chair?: string;
  /** Short summary of the party's current electoral footprint. */
  electoral_strength?: string;
  /** Configured real-chamber seat count used for seat-weighted voting.
      Distinct from `seats`, which counts seated personas. */
  voting_seats?: number | null;
  created_at?: string | null;
}

export interface RelationshipNode {
  id: string;
  name: string;
  party: Party;
  role: Role;
}

export interface RelationshipEdge {
  from: string;
  to: string;
  type: "ally" | "rival";
}

export interface RelationshipGraph {
  nodes: RelationshipNode[];
  edges: RelationshipEdge[];
}

export interface DebateSummary {
  id: string;
  title: string;
  status: DebateStatus | "passed" | "rejected";
  rounds: number;
  support: number;
  oppose: number;
  abstain: number;
  amendments: number;
  model: string;
  temperature: number;
  duration_s: number;
  created_at: string;
}

export interface Turn {
  id: string;
  agent: string;
  party: Party;
  role: Role;
  phase:
    | "intro"
    | "advisor_discussion"
    | "assistant_research"
    | "synthesis"
    | "cross_party_debate"
    | "markup"
    | "markup_debate"
    | "advisor"
    | "research"
    | "debate";
  round: number | null;
  content: string;
  ts?: string;
}

export interface VoteRecord {
  agent: string;
  party: Party;
  role?: Role;
  vote: VoteValue;
  reasoning: string;
  changed: boolean;
  from?: VoteValue | null;
  amendments?: string[];
  /** Seat weight this ballot carried, when the debate was seat-weighted. */
  weight?: number;
}

export interface Amendment {
  id: string;
  text: string;
  /** Primary sponsor's agent id (first ballot that proposed it), or null. */
  by: string | null;
  /** All agent ids whose ballots proposed this amendment. */
  sponsors?: string[];
  status: "proposed" | "accepted" | "contested" | "rejected" | "incorporated";
}
