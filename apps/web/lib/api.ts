import {
  ApiError,
  type ApiErrorDetail,
  type ApplicationCreate,
  type ApplicationListItem,
  type ApplicationListParams,
  type ApplicationRead,
  type ApplicationStageMove,
  type CandidateCreate,
  type CandidateListParams,
  type CandidateRead,
  type CandidateUpdate,
  type JobCreate,
  type JobListItem,
  type JobListParams,
  type JobRead,
  type JobUpdate,
  type Page,
  type PipelineRead,
} from "./api-types";

type GetToken = () => Promise<string | null>;

function qs(params?: object): string {
  if (!params) return "";
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "") sp.set(k, String(v));
  }
  const s = sp.toString();
  return s ? `?${s}` : "";
}

export class ApiClient {
  constructor(
    private readonly baseUrl: string,
    private readonly getToken: GetToken,
  ) {}

  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    const token = await this.getToken();
    const headers = new Headers(init?.headers);
    headers.set("Content-Type", "application/json");
    if (token) headers.set("Authorization", `Bearer ${token}`);

    const res = await fetch(`${this.baseUrl}/api/v1${path}`, {
      ...init,
      headers,
      cache: "no-store",
    });

    if (res.status === 204) return undefined as T;

    const text = await res.text();
    const body = text ? JSON.parse(text) : null;

    if (!res.ok) {
      const detail: ApiErrorDetail = body?.detail ?? "unknown_error";
      const code =
        typeof detail === "string"
          ? detail
          : Array.isArray(detail)
            ? "validation_error"
            : (detail.code ?? "error");
      throw new ApiError(res.status, code, detail);
    }
    return body as T;
  }

  jobs = {
    list: (params?: JobListParams) =>
      this.request<Page<JobListItem>>(`/jobs${qs(params)}`),
    get: (id: string) => this.request<JobRead>(`/jobs/${id}`),
    create: (payload: JobCreate) =>
      this.request<JobRead>("/jobs", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    update: (id: string, payload: JobUpdate) =>
      this.request<JobRead>(`/jobs/${id}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      }),
    delete: (id: string) =>
      this.request<void>(`/jobs/${id}`, { method: "DELETE" }),
    pipeline: (id: string) => this.request<PipelineRead>(`/jobs/${id}/pipeline`),
  };

  candidates = {
    list: (params?: CandidateListParams) =>
      this.request<Page<CandidateRead>>(`/candidates${qs(params)}`),
    get: (id: string) => this.request<CandidateRead>(`/candidates/${id}`),
    create: (payload: CandidateCreate) =>
      this.request<CandidateRead>("/candidates", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    update: (id: string, payload: CandidateUpdate) =>
      this.request<CandidateRead>(`/candidates/${id}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      }),
    delete: (id: string) =>
      this.request<void>(`/candidates/${id}`, { method: "DELETE" }),
  };

  applications = {
    list: (params?: ApplicationListParams) =>
      this.request<Page<ApplicationListItem>>(`/applications${qs(params)}`),
    get: (id: string) => this.request<ApplicationRead>(`/applications/${id}`),
    create: (payload: ApplicationCreate) =>
      this.request<ApplicationRead>("/applications", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    moveStage: (id: string, payload: ApplicationStageMove) =>
      this.request<ApplicationRead>(`/applications/${id}/stage`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      }),
  };
}
