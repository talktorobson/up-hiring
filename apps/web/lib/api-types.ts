/**
 * Tipos espelhados manualmente dos schemas Pydantic em
 * `apps/api/src/schemas/*` e `apps/api/src/models/enums.py` (Opção B do #80 —
 * OpenAPI generation fica pra Fase 1). Mantenha em sincronia ao mudar a API.
 */

export type JobStatus = "draft" | "open" | "paused" | "closed";
export type EmploymentType = "clt" | "pj" | "estagio" | "temp" | "freelancer";
export type StageKind = "active" | "terminal_hired" | "terminal_rejected";
export type ApplicationStatus = "active" | "hired" | "rejected" | "withdrawn";
export type ActivityEntityType = "job" | "candidate" | "application";

export interface Page<T> {
  items: T[];
  next_cursor: string | null;
  has_more: boolean;
}

export interface StageRead {
  id: string;
  job_id: string;
  name: string;
  position: number;
  kind: StageKind;
}

export interface JobListItem {
  id: string;
  title: string;
  status: JobStatus;
  employment_type: EmploymentType;
  location: string | null;
  created_at: string;
  updated_at: string;
}

export interface JobRead {
  id: string;
  title: string;
  description: string | null;
  location: string | null;
  employment_type: EmploymentType;
  salary_min: number | null;
  salary_max: number | null;
  status: JobStatus;
  created_by: string | null;
  created_at: string;
  updated_at: string;
  stages: StageRead[];
}

export interface JobCreate {
  title: string;
  description?: string | null;
  location?: string | null;
  employment_type?: EmploymentType;
  salary_min?: number | null;
  salary_max?: number | null;
  status?: JobStatus;
}

export type JobUpdate = Partial<JobCreate>;

export interface CandidateRead {
  id: string;
  full_name: string;
  email: string;
  phone: string | null;
  cpf: string | null;
  linkedin_url: string | null;
  source: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface CandidateCreate {
  full_name: string;
  email: string;
  phone?: string | null;
  cpf?: string | null;
  linkedin_url?: string | null;
  source?: string | null;
  notes?: string | null;
}

export type CandidateUpdate = Partial<CandidateCreate>;

export interface ActivityRead {
  id: string;
  entity_type: ActivityEntityType;
  entity_id: string;
  action: string;
  actor_user_id: string | null;
  payload: Record<string, unknown> | null;
  created_at: string;
}

export interface ApplicationListItem {
  id: string;
  job_id: string;
  candidate_id: string;
  current_stage_id: string;
  status: ApplicationStatus;
  created_at: string;
  updated_at: string;
}

export interface ApplicationRead extends ApplicationListItem {
  stage_history: ActivityRead[];
}

export interface ApplicationCreate {
  job_id: string;
  candidate_id: string;
}

export interface ApplicationStageMove {
  target_stage_id: string;
}

export interface PipelineStage {
  stage_id: string;
  name: string;
  position: number;
  applications: ApplicationListItem[];
  total_count: number;
}

export interface PipelineRead {
  job_id: string;
  stages: PipelineStage[];
}

export interface JobListParams {
  cursor?: string;
  limit?: number;
  status?: JobStatus;
}

export interface CandidateListParams {
  cursor?: string;
  limit?: number;
  q?: string;
}

export interface ApplicationListParams {
  cursor?: string;
  limit?: number;
  job_id?: string;
  stage_id?: string;
  candidate_id?: string;
}

/**
 * FastAPI devolve `{ detail }` onde detail é string (`"job_not_found"`),
 * objeto (`{ code, existing_id }` / `{ code, ...extra }`) ou lista de
 * validação Pydantic (`[{ loc, msg, type }]`).
 */
export type ApiErrorDetail =
  | string
  | { code: string; [k: string]: unknown }
  | Array<{ loc: (string | number)[]; msg: string; type: string }>;

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    readonly detail: ApiErrorDetail,
  ) {
    super(`API ${status}: ${code}`);
    this.name = "ApiError";
  }

  /** Mapa campo→mensagem quando detail é lista de validação Pydantic (422). */
  fieldErrors(): Record<string, string> {
    if (!Array.isArray(this.detail)) return {};
    const out: Record<string, string> = {};
    for (const issue of this.detail) {
      const field = issue.loc.filter((p) => p !== "body").join(".");
      if (field) out[field] = issue.msg;
    }
    return out;
  }
}
