/** Type-safe API client targeting the FastAPI backend. */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export interface JobResponse {
  job_id: string;
  status: "PENDING" | "STARTED" | "COMPLETED" | "FAILED" | "RETRYING";
  created_at?: string;
  updated_at?: string;
  result_url?: string;
  caption?: string;
  cost_usd?: number;
  error?: string;
  progress?: number;
}

export interface GenerateRequest {
  prompt_seed: string;
  pillar?: string;
  wardrobe?: string;
  mood?: string;
  style_override?: string;
  aspect_ratio?: string;
  content_type?: "image" | "video" | "carousel";
  generate_caption?: boolean;
  cta_kind?: string;
  hashtags?: string[];
  seed?: number;
}

export interface InfluencerProfile {
  name: string;
  version: string;
  niche: string;
  bio: string;
  visual_dna: Record<string, string>;
  content_mix: Record<string, number>;
  lora_url: string;
  lora_scale: number;
}

export interface HealthResponse {
  status: string;
  scheduler_running: boolean;
  bot_running: boolean;
  celery_running: boolean;
  redis_connected: boolean;
}

export interface PresignedUpload {
  upload_url: string;
  object_key: string;
  expires_in: number;
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => apiFetch<HealthResponse>("/api/v1/health"),

  generate: (req: GenerateRequest) =>
    apiFetch<JobResponse>("/api/v1/generations", {
      method: "POST",
      body: JSON.stringify(req),
    }),

  getJob: (jobId: string) => apiFetch<JobResponse>(`/api/v1/jobs/${jobId}`),

  streamJob: (jobId: string) =>
    new EventSource(`${API_BASE}/api/v1/jobs/${jobId}/stream`),

  listInfluencers: () => apiFetch<InfluencerProfile[]>("/api/v1/influencers"),

  getInfluencer: (name: string) =>
    apiFetch<InfluencerProfile>(`/api/v1/influencers/${name}`),

  presignUpload: (contentType = "image/png", folder = "uploads") =>
    apiFetch<PresignedUpload>("/api/v1/uploads/presign", {
      method: "POST",
      body: JSON.stringify({ content_type: contentType, folder }),
    }),
};