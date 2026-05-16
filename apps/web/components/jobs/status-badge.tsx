import { Badge } from "@/components/ui/badge";
import type { EmploymentType, JobStatus } from "@/lib/api-types";

const STATUS: Record<
  JobStatus,
  { label: string; variant: "default" | "secondary" | "success" | "warning" }
> = {
  draft: { label: "Rascunho", variant: "secondary" },
  open: { label: "Aberta", variant: "success" },
  paused: { label: "Pausada", variant: "warning" },
  closed: { label: "Fechada", variant: "default" },
};

const EMPLOYMENT: Record<EmploymentType, string> = {
  clt: "CLT",
  pj: "PJ",
  estagio: "Estágio",
  temp: "Temporário",
  freelancer: "Freelancer",
};

export function StatusBadge({ status }: { status: JobStatus }) {
  const s = STATUS[status];
  return <Badge variant={s.variant}>{s.label}</Badge>;
}

export function employmentLabel(t: EmploymentType): string {
  return EMPLOYMENT[t];
}

export const EMPLOYMENT_OPTIONS = Object.entries(EMPLOYMENT).map(
  ([value, label]) => ({ value: value as EmploymentType, label }),
);
