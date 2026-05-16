"use client";

import { Users } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { EmptyState } from "@/components/empty-state";
import { TableSkeleton } from "@/components/skeletons";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useCandidatesInfinite } from "@/lib/hooks";
import { formatDate, maskCpf } from "@/lib/utils";

export default function CandidatesPage() {
  const router = useRouter();
  const [term, setTerm] = useState("");
  const [q, setQ] = useState("");

  useEffect(() => {
    const t = setTimeout(() => setQ(term.trim()), 300);
    return () => clearTimeout(t);
  }, [term]);

  const {
    data,
    isLoading,
    isError,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useCandidatesInfinite(q || undefined);

  const candidates = data?.pages.flatMap((p) => p.items) ?? [];

  return (
    <div className="mx-auto max-w-6xl p-6 lg:p-8">
      <div className="mb-6 flex items-center justify-between gap-4">
        <h1 className="text-2xl font-bold tracking-tight">Candidatos</h1>
      </div>

      <Input
        placeholder="Buscar por nome ou e-mail…"
        value={term}
        onChange={(e) => setTerm(e.target.value)}
        className="mb-4 max-w-sm"
      />

      {isLoading ? (
        <TableSkeleton rows={5} />
      ) : isError ? (
        <p className="text-sm text-destructive">
          Não foi possível carregar os candidatos.
        </p>
      ) : candidates.length === 0 ? (
        <EmptyState
          icon={Users}
          title={q ? "Nenhum candidato encontrado." : "Nenhum candidato ainda."}
          description="Candidatos são criados ao adicioná-los a uma vaga."
        />
      ) : (
        <>
          <div className="rounded-lg border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Nome</TableHead>
                  <TableHead>E-mail</TableHead>
                  <TableHead>Telefone</TableHead>
                  <TableHead>CPF</TableHead>
                  <TableHead>Vagas</TableHead>
                  <TableHead>Criado em</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {candidates.map((c) => (
                  <TableRow
                    key={c.id}
                    className="cursor-pointer"
                    onClick={() => router.push(`/candidates/${c.id}`)}
                  >
                    <TableCell className="font-medium">
                      {c.full_name}
                    </TableCell>
                    <TableCell>{c.email}</TableCell>
                    <TableCell>{c.phone ?? "—"}</TableCell>
                    <TableCell>{maskCpf(c.cpf)}</TableCell>
                    <TableCell className="text-muted-foreground">—</TableCell>
                    <TableCell className="text-muted-foreground">
                      {formatDate(c.created_at)}
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
