"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { CandidateForm } from "@/components/candidates/candidate-form";
import {
  Alert,
  AlertDescription,
  AlertTitle,
} from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { ApiError, type CandidateRead } from "@/lib/api-types";
import { qk, useCreateApplication } from "@/lib/hooks";
import { useApiClient } from "@/lib/use-api-client";
import { maskCpf } from "@/lib/utils";

type Step = "search" | "new" | "selected";

export function AddCandidateDialog({
  jobId,
  onCreated,
}: {
  jobId: string;
  onCreated?: () => void;
}) {
  const api = useApiClient();
  const qc = useQueryClient();
  const createApp = useCreateApplication();

  const [open, setOpen] = useState(false);
  const [step, setStep] = useState<Step>("search");
  const [term, setTerm] = useState("");
  const [debounced, setDebounced] = useState("");
  const [selected, setSelected] = useState<CandidateRead | null>(null);
  const [dupExistingId, setDupExistingId] = useState<string | null>(null);
  const [appError, setAppError] = useState<string | null>(null);

  useEffect(() => {
    const t = setTimeout(() => setDebounced(term.trim()), 300);
    return () => clearTimeout(t);
  }, [term]);

  const search = useQuery({
    queryKey: ["candidate-search", debounced],
    queryFn: () => api.candidates.list({ q: debounced, limit: 5 }),
    enabled: open && debounced.length >= 2,
  });

  function reset() {
    setStep("search");
    setTerm("");
    setDebounced("");
    setSelected(null);
    setDupExistingId(null);
    setAppError(null);
  }

  async function attachApplication(candidateId: string) {
    setAppError(null);
    try {
      await createApp.mutateAsync({ job_id: jobId, candidate_id: candidateId });
      qc.invalidateQueries({ queryKey: qk.pipeline(jobId) });
      toast.success("Candidato adicionado");
      onCreated?.();
      setOpen(false);
      reset();
    } catch (err) {
      if (err instanceof ApiError && err.code === "duplicate_application") {
        setAppError("Candidato já está aplicado nesta vaga.");
        return;
      }
      // demais erros → toast global
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        if (!o) reset();
      }}
    >
      <DialogTrigger asChild>
        <Button>Adicionar candidato</Button>
      </DialogTrigger>
      <DialogContent className="max-h-[90vh] overflow-auto sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>Adicionar candidato à vaga</DialogTitle>
        </DialogHeader>

        {appError && (
          <Alert variant="destructive">
            <AlertTitle>Não foi possível adicionar</AlertTitle>
            <AlertDescription>{appError}</AlertDescription>
          </Alert>
        )}

        {step === "search" && (
          <div className="space-y-3">
            <Input
              autoFocus
              placeholder="Buscar por nome ou e-mail…"
              value={term}
              onChange={(e) => setTerm(e.target.value)}
            />
            {search.isFetching && (
              <p className="text-sm text-muted-foreground">Buscando…</p>
            )}
            <ul className="space-y-1">
              {(search.data?.items ?? []).map((c) => (
                <li key={c.id}>
                  <button
                    type="button"
                    className="w-full rounded-md border p-2 text-left text-sm hover:bg-accent"
                    onClick={() => {
                      setSelected(c);
                      setStep("selected");
                    }}
                  >
                    <span className="font-medium">{c.full_name}</span>{" "}
                    <span className="text-muted-foreground">{c.email}</span>
                  </button>
                </li>
              ))}
            </ul>
            {debounced.length >= 2 &&
              !search.isFetching &&
              (search.data?.items.length ?? 0) === 0 && (
                <p className="text-sm text-muted-foreground">
                  Nenhum candidato encontrado.
                </p>
              )}
            <Button
              variant="outline"
              className="w-full"
              onClick={() => setStep("new")}
            >
              Criar novo candidato
            </Button>
          </div>
        )}

        {step === "new" && (
          <div className="space-y-3">
            {dupExistingId && (
              <Alert>
                <AlertTitle>Candidato já existe</AlertTitle>
                <AlertDescription>
                  Já há um candidato com esse CPF/e-mail.{" "}
                  <Link
                    href={`/candidates/${dupExistingId}`}
                    className="font-medium underline"
                  >
                    Abrir candidato existente
                  </Link>
                </AlertDescription>
              </Alert>
            )}
            <CandidateForm
              mode="create"
              onSaved={(c) => attachApplication(c.id)}
              onDuplicate={(err) => {
                const id = (
                  err.detail as { existing_id?: string }
                )?.existing_id;
                setDupExistingId(id ?? null);
              }}
            />
            <Button variant="ghost" onClick={() => setStep("search")}>
              ← Voltar para busca
            </Button>
          </div>
        )}

        {step === "selected" && selected && (
          <div className="space-y-4">
            <div className="rounded-md border p-3 text-sm">
              <p className="font-medium">{selected.full_name}</p>
              <p className="text-muted-foreground">{selected.email}</p>
              <p className="text-muted-foreground">
                CPF: {maskCpf(selected.cpf)}
              </p>
            </div>
            <div className="flex justify-between">
              <Button
                variant="ghost"
                onClick={() => {
                  setSelected(null);
                  setStep("search");
                }}
              >
                Trocar
              </Button>
              <Button
                disabled={createApp.isPending}
                onClick={() => attachApplication(selected.id)}
              >
                {createApp.isPending ? "Adicionando…" : "Adicionar à vaga"}
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
