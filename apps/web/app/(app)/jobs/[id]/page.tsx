"use client";

import DOMPurify from "isomorphic-dompurify";
import { toast } from "sonner";

import { JobActions } from "@/components/jobs/job-actions";
import {
  employmentLabel,
  StatusBadge,
} from "@/components/jobs/status-badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useJob } from "@/lib/hooks";
import { formatSalaryRange } from "@/lib/utils";

export default function JobDetailPage({
  params,
}: {
  params: { id: string };
}) {
  const { data: job, isLoading, isError } = useJob(params.id);

  if (isLoading) {
    return (
      <div className="mx-auto max-w-5xl space-y-4 p-6 lg:p-8">
        <Skeleton className="h-8 w-1/2" />
        <Skeleton className="h-5 w-1/3" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (isError || !job) {
    return (
      <div className="mx-auto max-w-5xl p-6 lg:p-8">
        <div className="rounded-lg border border-dashed py-16 text-center">
          <p className="text-sm font-medium">Vaga não encontrada</p>
          <p className="text-sm text-muted-foreground">
            Ela não existe ou você não tem acesso (outra organização).
          </p>
        </div>
      </div>
    );
  }

  // Descrição vem do Tiptap (HTML). Sanitiza antes de renderizar — DOMPurify
  // remove script/handlers, então só markup seguro chega ao DOM.
  const safeDescription = job.description
    ? DOMPurify.sanitize(job.description)
    : "";

  return (
    <div className="mx-auto max-w-5xl p-6 lg:p-8">
      <div className="mb-6 flex items-start justify-between gap-4">
        <div className="space-y-2">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight">{job.title}</h1>
            <StatusBadge status={job.status} />
          </div>
          <p className="text-sm text-muted-foreground">
            {job.location ?? "Local não informado"} ·{" "}
            {employmentLabel(job.employment_type)} ·{" "}
            {formatSalaryRange(job.salary_min, job.salary_max)}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            onClick={() =>
              toast.info("Adicionar candidato chega no PR5 (#85).")
            }
          >
            Adicionar candidato
          </Button>
          <JobActions job={job} />
        </div>
      </div>

      <Tabs defaultValue="sobre">
        <TabsList>
          <TabsTrigger value="sobre">Sobre</TabsTrigger>
          <TabsTrigger value="pipeline">Pipeline</TabsTrigger>
          <TabsTrigger value="atividade">Atividade</TabsTrigger>
        </TabsList>

        <TabsContent value="sobre" className="pt-4">
          {safeDescription ? (
            <div
              className="prose prose-sm max-w-none"
              dangerouslySetInnerHTML={{ __html: safeDescription }}
            />
          ) : (
            <p className="text-sm text-muted-foreground">Sem descrição.</p>
          )}
        </TabsContent>

        <TabsContent value="pipeline" className="pt-4">
          <div className="rounded-lg border border-dashed py-12 text-center text-sm text-muted-foreground">
            Kanban do pipeline chega no PR4 (#84). Stages já vêm da API:{" "}
            {job.stages.length} configurados.
          </div>
        </TabsContent>

        <TabsContent value="atividade" className="pt-4">
          <p className="text-sm text-muted-foreground">
            Feed de atividade completo entra na Fase 1.
          </p>
        </TabsContent>
      </Tabs>
    </div>
  );
}
