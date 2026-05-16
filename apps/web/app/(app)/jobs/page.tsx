"use client";

import { useJobsInfinite } from "@/lib/hooks";

// Placeholder do PR1 (foundation). DataTable + filtros + form chegam no PR3 (#82).
export default function JobsPage() {
  const { data, isLoading, isError } = useJobsInfinite();
  const jobs = data?.pages.flatMap((p) => p.items) ?? [];

  return (
    <div className="mx-auto max-w-5xl p-8">
      <h1 className="mb-6 text-2xl font-bold tracking-tight">Vagas</h1>
      {isLoading && <p className="text-sm text-muted-foreground">Carregando…</p>}
      {isError && (
        <p className="text-sm text-destructive">Falha ao carregar vagas.</p>
      )}
      {!isLoading && !isError && jobs.length === 0 && (
        <p className="text-sm text-muted-foreground">
          Nenhuma vaga ainda. (UI completa chega no PR3.)
        </p>
      )}
      <ul className="space-y-2">
        {jobs.map((j) => (
          <li key={j.id} className="rounded-md border p-3 text-sm">
            {j.title}
          </li>
        ))}
      </ul>
    </div>
  );
}
