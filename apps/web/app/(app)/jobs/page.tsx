"use client";

import { Briefcase } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { EmptyState } from "@/components/empty-state";
import { employmentLabel, StatusBadge } from "@/components/jobs/status-badge";
import { TableSkeleton } from "@/components/skeletons";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { JobStatus } from "@/lib/api-types";
import { useJobsInfinite } from "@/lib/hooks";
import { formatDate } from "@/lib/utils";

const STATUS_FILTERS: { value: string; label: string }[] = [
  { value: "all", label: "Todos os status" },
  { value: "draft", label: "Rascunho" },
  { value: "open", label: "Aberta" },
  { value: "paused", label: "Pausada" },
  { value: "closed", label: "Fechada" },
];

export default function JobsPage() {
  const router = useRouter();
  const [status, setStatus] = useState<string>("all");
  const {
    data,
    isLoading,
    isError,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useJobsInfinite(status === "all" ? undefined : (status as JobStatus));

  const jobs = data?.pages.flatMap((p) => p.items) ?? [];

  return (
    <div className="mx-auto max-w-6xl p-6 lg:p-8">
      <div className="mb-6 flex items-center justify-between gap-4">
        <h1 className="text-2xl font-bold tracking-tight">Vagas</h1>
        <div className="flex items-center gap-3">
          <Select value={status} onValueChange={setStatus}>
            <SelectTrigger className="w-44">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {STATUS_FILTERS.map((s) => (
                <SelectItem key={s.value} value={s.value}>
                  {s.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button asChild>
            <Link href="/jobs/new">Nova vaga</Link>
          </Button>
        </div>
      </div>

      {isLoading ? (
        <TableSkeleton rows={5} />
      ) : isError ? (
        <p className="text-sm text-destructive">
          Não foi possível carregar as vagas.
        </p>
      ) : jobs.length === 0 ? (
        <EmptyState
          icon={Briefcase}
          title="Nenhuma vaga ainda."
          description="Crie sua primeira vaga para começar o pipeline."
          action={
            <Button asChild>
              <Link href="/jobs/new">Criar primeira vaga</Link>
            </Button>
          }
        />
      ) : (
        <>
          <div className="rounded-lg border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Título</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Localização</TableHead>
                  <TableHead>Tipo</TableHead>
                  <TableHead>Candidatos</TableHead>
                  <TableHead>Criada em</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {jobs.map((j) => (
                  <TableRow
                    key={j.id}
                    className="cursor-pointer"
                    onClick={() => router.push(`/jobs/${j.id}`)}
                  >
                    <TableCell className="font-medium">{j.title}</TableCell>
                    <TableCell>
                      <StatusBadge status={j.status} />
                    </TableCell>
                    <TableCell>{j.location ?? "—"}</TableCell>
                    <TableCell>{employmentLabel(j.employment_type)}</TableCell>
                    <TableCell className="text-muted-foreground">—</TableCell>
                    <TableCell className="text-muted-foreground">
                      {formatDate(j.created_at)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          {hasNextPage && (
            <div className="mt-4 flex justify-center">
              <Button
                variant="outline"
                onClick={() => fetchNextPage()}
                disabled={isFetchingNextPage}
              >
                {isFetchingNextPage ? "Carregando…" : "Carregar mais"}
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
