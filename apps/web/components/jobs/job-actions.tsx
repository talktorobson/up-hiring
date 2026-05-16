"use client";

import { MoreHorizontal } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { JobRead } from "@/lib/api-types";
import { useDeleteJob, useUpdateJob } from "@/lib/hooks";

import { JobForm } from "./job-form";

export function JobActions({ job }: { job: JobRead }) {
  const router = useRouter();
  const update = useUpdateJob(job.id);
  const del = useDeleteJob();
  const [editOpen, setEditOpen] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  async function setStatus(status: "open" | "paused" | "closed") {
    await update.mutateAsync({ status });
    toast.success(
      status === "paused"
        ? "Vaga pausada"
        : status === "closed"
          ? "Vaga fechada"
          : "Vaga reaberta",
    );
  }

  async function onDelete() {
    await del.mutateAsync(job.id);
    toast.success("Vaga excluída");
    router.push("/jobs");
  }

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="outline" size="icon" aria-label="Ações da vaga">
            <MoreHorizontal className="h-4 w-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem onClick={() => setEditOpen(true)}>
            Editar
          </DropdownMenuItem>
          {job.status !== "paused" && (
            <DropdownMenuItem onClick={() => setStatus("paused")}>
              Pausar
            </DropdownMenuItem>
          )}
          {job.status === "paused" && (
            <DropdownMenuItem onClick={() => setStatus("open")}>
              Reabrir
            </DropdownMenuItem>
          )}
          {job.status !== "closed" && (
            <DropdownMenuItem onClick={() => setStatus("closed")}>
              Fechar
            </DropdownMenuItem>
          )}
          <DropdownMenuSeparator />
          <DropdownMenuItem
            className="text-destructive focus:text-destructive"
            onClick={() => setConfirmDelete(true)}
          >
            Excluir
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent className="max-h-[90vh] overflow-auto sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>Editar vaga</DialogTitle>
          </DialogHeader>
          <JobForm
            mode="edit"
            job={job}
            onSaved={() => {
              setEditOpen(false);
            }}
          />
        </DialogContent>
      </Dialog>

      <AlertDialog open={confirmDelete} onOpenChange={setConfirmDelete}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Excluir esta vaga?</AlertDialogTitle>
            <AlertDialogDescription>
              A vaga será removida (soft delete). Esta ação some com a vaga
              das listagens.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={onDelete}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Excluir
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
