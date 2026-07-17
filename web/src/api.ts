/* Thin fetch wrappers around the backend. Paths are relative so Vite's
   /api proxy (vite.config.ts) forwards them to the FastAPI server. */

import type {
  Amendment,
  DebateSummary,
  Persona,
  PersonaSummary,
  PartyEntry,
  RelationshipGraph,
  Turn,
  VoteRecord,
} from "./types";

export interface DebateDetail {
  id: string;
  title: string;
  proposal: string;
  config: {
    max_rounds: number;
    model: string;
    temperature: number;
    parties: string[];
    passage_rule?: "majority" | "three_fifths" | "two_thirds";
  };
  status: DebateSummary["status"];
  result: string | null;
  tally: { support: number; oppose: number; abstain: number };
  /** Written at completion: the rule applied and the support needed to pass. */
  voting?: { rule: string; required: number; margin: string; bipartisan: boolean };
  created_at: string;
  completed_at: string | null;
  duration_s?: number;
  error?: string;
}

export interface CreateDebateRequest {
  proposal: string;
  title?: string;
  max_rounds: number;
  /** Optional; falls back to Settings.default_model on the server. */
  model?: string;
  /** Optional; falls back to Settings.default_temperature on the server. */
  temperature?: number;
  parties?: string[];
  /** Optional; falls back to the settings-store default (majority). */
  passage_rule?: "majority" | "three_fifths" | "two_thirds";
}

export interface CreateDebateResponse {
  id: string;
  status: "running";
  stream: string;
}

class ApiError extends Error {
  status: number;
  code?: string;
  constructor(message: string, status: number, code?: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { "content-type": "application/json", ...(init?.headers || {}) },
  });
  if (!res.ok) {
    let detail: { code?: string; message?: string } | undefined;
    try {
      const body = await res.json();
      detail = body?.detail ?? body?.error;
    } catch {
      // not JSON — fall through
    }
    throw new ApiError(detail?.message || res.statusText, res.status, detail?.code);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export interface SettingsPayload {
  default_model: string;
  default_temperature: number;
  system_prompts: Record<string, string>;
  reference_lists: { roles: string[]; negotiation_postures: string[] };
  api_key_set: boolean;
  api_key_preview: string;
  updated_at?: string;
}

export interface HealthSnapshot {
  status: "ok" | "error";
  api_key_set: boolean;
  default_model: string;
  active_debates: number;
  total_debates: number;
  uptime_s: number;
  server_time: string;
  version: string;
  // legacy field kept for back-compat with the M1 sidebar
  model?: string;
}

export const api = {
  health: () => request<HealthSnapshot>("/api/health"),

  // personas
  listPersonas: (params?: { party?: string; role?: string; q?: string }) => {
    const qs = new URLSearchParams();
    if (params?.party) qs.set("party", params.party);
    if (params?.role) qs.set("role", params.role);
    if (params?.q) qs.set("q", params.q);
    const suffix = qs.toString() ? `?${qs}` : "";
    return request<{ personas: PersonaSummary[] }>(`/api/personas${suffix}`);
  },
  getPersona: (id: string) => request<Persona>(`/api/personas/${id}`),
  createPersona: (body: Persona) =>
    request<Persona>("/api/personas", { method: "POST", body: JSON.stringify(body) }),
  updatePersona: (id: string, patch: Partial<Persona>) =>
    request<Persona>(`/api/personas/${id}`, { method: "PATCH", body: JSON.stringify(patch) }),
  deletePersona: (id: string, force = false) =>
    request<void>(`/api/personas/${id}${force ? "?force=true" : ""}`, { method: "DELETE" }),

  // parties
  listParties: () => request<{ parties: PartyEntry[] }>("/api/parties"),
  getParty: (id: string) => request<PartyEntry>(`/api/parties/${id}`),
  createParty: (body: Partial<PartyEntry> & { id: string; label: string; color: string }) =>
    request<PartyEntry>("/api/parties", { method: "POST", body: JSON.stringify(body) }),
  updateParty: (id: string, patch: Partial<PartyEntry>) =>
    request<PartyEntry>(`/api/parties/${id}`, {
      method: "PATCH",
      body: JSON.stringify(patch),
    }),
  deleteParty: (id: string, force = false) =>
    request<void>(`/api/parties/${id}${force ? "?force=true" : ""}`, { method: "DELETE" }),

  // relationships
  getRelationships: () => request<RelationshipGraph>("/api/relationships"),

  // debates
  listDebates: () => request<{ debates: DebateSummary[] }>("/api/debates"),
  getDebate: (id: string) => request<DebateDetail>(`/api/debates/${id}`),
  createDebate: (body: CreateDebateRequest) =>
    request<CreateDebateResponse>("/api/debates", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updateDebate: (id: string, patch: { title?: string }) =>
    request<DebateDetail>(`/api/debates/${id}`, {
      method: "PATCH",
      body: JSON.stringify(patch),
    }),
  deleteDebate: (id: string) =>
    request<void>(`/api/debates/${id}`, { method: "DELETE" }),
  getTranscript: (id: string) => request<{ turns: Turn[] }>(`/api/debates/${id}/transcript`),
  getVotes: (id: string) => request<{ votes: VoteRecord[] }>(`/api/debates/${id}/votes`),
  getAmendments: (id: string) =>
    request<{ amendments: Amendment[] }>(`/api/debates/${id}/amendments`),
  // settings
  getSettings: () => request<SettingsPayload>("/api/settings"),
  updateSettings: (
    patch: Partial<{
      anthropic_api_key: string;
      default_model: string;
      default_temperature: number;
      system_prompts: Record<string, string>;
      reference_lists: { roles?: string[]; negotiation_postures?: string[] };
    }>,
  ) =>
    request<SettingsPayload>("/api/settings", {
      method: "PATCH",
      body: JSON.stringify(patch),
    }),
  resetPrompt: (name: string) =>
    request<SettingsPayload>("/api/settings/reset-prompt", {
      method: "POST",
      body: JSON.stringify({ name }),
    }),
  testApiKey: (api_key?: string) =>
    request<{ ok: boolean; model?: string; error?: string }>("/api/settings/test-key", {
      method: "POST",
      body: JSON.stringify(api_key ? { api_key } : {}),
    }),

  exportDebate: async (id: string, format: "pdf" | "md" | "json"): Promise<Blob> => {
    const res = await fetch(`/api/debates/${id}/export`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ format }),
    });
    if (!res.ok) throw new Error(`Export failed (${res.status})`);
    return res.blob();
  },
};

export { ApiError };
