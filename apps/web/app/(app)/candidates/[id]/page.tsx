"use client";

import Link from "next/link";
import { useState } from "react";

import { CandidateForm } from "@/components/candidates/candidate-form";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import type { ApplicationListItem } from "@/lib/api-types";
import { useApplications, useCandidate, useJob } from "@/lib/hooks";
import { formatDate, maskCpf } from "@/lib/utils";

function ApplicationRow({ app }: { app: ApplicationListItem }) {
  const { data: job } = useJob(app.job_id);
  const stage = job?.stages.find((s) => s.id === app.current_stage_id);
  return (
    <Link
      href={`/jobs/${app.job_id}?tab=pipeline#application-${app.id}`}
      className="flex items-center justify-between rounded-md border p-3 text-sm hover:bg-accent"
    >
      <div>
        <p className="font-medium">{job?.title ?? "Vaga"}</p>
        <p className="text-muted-foreground">
          {stage?.name ?? "—"} · {app.status}
        </p>
      </div>
      <span className="text-xs text-muted-foreground">
        {formatDate(app.created_at)}
      </span>
    </Link>
  );
}

export default function CandidateDetailPage({
  params,
}: {
  params: { id: string };
}) {
  const { data: candidate, isLoading, isError } = useCandidate(params.id);
  const apps = useApplications({ candidate_id: params.id });
  const [editOpen, setEditOpen] = useState(false);

  if (isLoading) {
    return (
      <div className="mx-auto max-w-3xl space-y-4 p-6 lg:p-8">
        <Skeleton className="h-10 w-1/2" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  if (isError || !candidate) {
    return (
      <div className="mx-auto max-w-3xl p-6 lg:p-8">
        <div className="rounded-lg border border-dashed py-16 text-center">
          <p className="text-sm font-medium">Candidato não encontrado</p>
          <p className="text-sm text-muted-foreground">
            Não existe ou pertence a outra organização.
          </p>
        </div>
      </div>
    );
  }

  const initial = candidate.full_name.charAt(0).toUpperCase();

  return (
    <div className="mx-auto max-w-3xl p-6 lg:p-8">
      <div className="mb-6 flex items-start justify-between gap-4">
        <div className="flex items-center gap-4">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-slate-200 text-lg font-semibold">
            {initial}
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">
              {candidate.full_name}
            </h1>
            <p className="text-sm text-muted-foreground">
              {candidate.email}
              {candidate.phone ? ` · ${candidate.phone}` : ""}
            </p>
            <div className="mt-2 flex gap-2">
              <Badge variant={candidate.cpf ? "success" : "secondary"}>
                {candidate.cpf
                  ? `CPF ${maskCpf(candidate.cpf)}`
                  : "Sem CPF"}
              </Badge>
              <Badge
                variant={candidate.linkedin_url ? "success" : "secondary"}
              >
                {candidate.linkedin_url ? "LinkedIn" : "Sem LinkedIn"}
              </Badge>
            </div>
          </div>
        </div>
        <Button variant="outline" onClick={() => setEditOpen(true)}>
          Editar
        </Button>
      </div>

      <section>
        <h2 className="mb-3 text-lg font-semibold">Aplicações</h2>
        {apps.isLoading ? (
          <Skeleton className="h-24 w-full" />
        ) : (apps.data?.items.length ?? 0) === 0 ? (
          <p className="text-sm text-muted-foreground">
            Este candidato ainda não está em nenhuma vaga.
          </p>
        ) : (
          <div className="space-y-2">
            {apps.data?.items.map((a) => (
              <ApplicationRow key={a.id} app={a} />
            ))}
          </div>
        )}
      </section>

      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent className="max-h-[90vh] overflow-auto sm:max-w-xl">
          <DialogHeader>
            <DialogTitle>Editar candidato</DialogTitle>
          </DialogHeader>
          <CandidateForm
            mode="edit"
            candidate={candidate}
            onSaved={() => setEditOpen(false)}
          />
        </DialogContent>
      </Dialog>
    </div>
  );
}
