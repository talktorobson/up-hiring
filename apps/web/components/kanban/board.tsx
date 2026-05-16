"use client";

import {
  DndContext,
  DragOverlay,
  PointerSensor,
  TouchSensor,
  closestCenter,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import { useMutation, useQueryClient } from "@tanstack/react-query";
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
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import type {
  ApplicationListItem,
  PipelineRead,
  StageRead,
} from "@/lib/api-types";
import {
  qk,
  useApplication,
  useApplications,
  useJob,
  usePipeline,
} from "@/lib/hooks";
import { useApiClient } from "@/lib/use-api-client";
import { formatDate } from "@/lib/utils";

import { KanbanCard, KanbanCardPreview } from "./kanban-card";

function findApp(
  pipeline: PipelineRead | undefined,
  appId: string,
): ApplicationListItem | undefined {
  if (!pipeline) return undefined;
  for (const s of pipeline.stages) {
    const found = s.applications.find((a) => a.id === appId);
    if (found) return found;
  }
  return undefined;
}

/** Move otimista no cache da pipeline (sem refetch visual). */
function applyOptimisticMove(
  old: PipelineRead | undefined,
  appId: string,
  fromStageId: string,
  toStageId: string,
): PipelineRead | undefined {
  if (!old) return old;
  let moved: ApplicationListItem | undefined;
  const stages = old.stages.map((s) => {
    if (s.stage_id !== fromStageId) return s;
    const apps = s.applications.filter((a) => {
      if (a.id === appId) {
        moved = a;
        return false;
      }
      return true;
    });
    return {
      ...s,
      applications: apps,
      total_count: Math.max(0, s.total_count - 1),
    };
  });
  const withInsert = stages.map((s) => {
    if (s.stage_id !== toStageId || !moved) return s;
    return {
      ...s,
      applications: [
        { ...moved, current_stage_id: toStageId },
        ...s.applications,
      ],
      total_count: s.total_count + 1,
    };
  });
  return { ...old, stages: withInsert };
}

function Column({
  stageId,
  name,
  count,
  children,
}: {
  stageId: string;
  name: string;
  count: number;
  children: React.ReactNode;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: stageId });
  return (
    <div
      ref={setNodeRef}
      className={`flex w-72 shrink-0 flex-col rounded-lg border bg-slate-100/60 ${
        isOver ? "ring-2 ring-blue-500" : ""
      }`}
    >
      <div className="flex items-center justify-between border-b px-3 py-2">
        <span className="text-sm font-semibold">{name}</span>
        <Badge variant="secondary">{count}</Badge>
      </div>
      <div className="flex max-h-[60vh] flex-col gap-2 overflow-y-auto p-2">
        {children}
      </div>
    </div>
  );
}

function TerminalColumn({
  jobId,
  stage,
  onOpen,
}: {
  jobId: string;
  stage: StageRead;
  onOpen: (a: ApplicationListItem) => void;
}) {
  const { data } = useApplications({
    job_id: jobId,
    stage_id: stage.id,
    limit: 50,
  });
  const apps = data?.items ?? [];
  return (
    <Column stageId={stage.id} name={stage.name} count={apps.length}>
      {apps.length === 0 ? (
        <p className="px-1 py-4 text-center text-xs text-muted-foreground">
          Vazio
        </p>
      ) : (
        apps.map((a) => (
          <button
            key={a.id}
            type="button"
            onClick={() => onOpen(a)}
            className="rounded-md border bg-white p-2 text-left text-xs"
          >
            <span className="text-muted-foreground">
              {formatDate(a.created_at)}
            </span>
          </button>
        ))
      )}
    </Column>
  );
}

function ApplicationSheet({
  application,
  onClose,
}: {
  application: ApplicationListItem | null;
  onClose: () => void;
}) {
  const { data } = useApplication(application?.id ?? "", !!application);
  return (
    <Sheet open={!!application} onOpenChange={(o) => !o && onClose()}>
      <SheetContent>
        <SheetHeader>
          <SheetTitle>Application</SheetTitle>
          <SheetDescription>
            {application ? `Status: ${data?.status ?? "—"}` : ""}
          </SheetDescription>
        </SheetHeader>
        <div className="mt-4 space-y-3 text-sm">
          <div>
            <p className="font-medium">Histórico de stage</p>
            {data?.stage_history?.length ? (
              <ul className="mt-1 space-y-1">
                {data.stage_history.map((h) => (
                  <li key={h.id} className="text-muted-foreground">
                    {formatDate(h.created_at)} — {h.action}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-muted-foreground">Sem movimentações.</p>
            )}
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}

export function KanbanBoard({ jobId }: { jobId: string }) {
  const pipeline = usePipeline(jobId);
  const jobQ = useJob(jobId);
  const qc = useQueryClient();
  const api = useApiClient();

  const [draggingId, setDraggingId] = useState<string | null>(null);
  const [detail, setDetail] = useState<ApplicationListItem | null>(null);
  const [pending, setPending] = useState<{
    app: ApplicationListItem;
    fromStageId: string;
    toStage: StageRead;
  } | null>(null);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(TouchSensor, {
      activationConstraint: { delay: 150, tolerance: 8 },
    }),
  );

  const move = useMutation({
    mutationFn: (v: {
      applicationId: string;
      target_stage_id: string;
      fromStageId: string;
    }) =>
      api.applications.moveStage(v.applicationId, {
        target_stage_id: v.target_stage_id,
      }),
    onMutate: async (v) => {
      await qc.cancelQueries({ queryKey: qk.pipeline(jobId) });
      const prev = qc.getQueryData<PipelineRead>(qk.pipeline(jobId));
      qc.setQueryData<PipelineRead | undefined>(qk.pipeline(jobId), (old) =>
        applyOptimisticMove(
          old,
          v.applicationId,
          v.fromStageId,
          v.target_stage_id,
        ),
      );
      return { prev };
    },
    onError: (_e, _v, ctx) => {
      if (ctx?.prev) qc.setQueryData(qk.pipeline(jobId), ctx.prev);
      toast.error("Não foi possível mover. Tente novamente.");
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: qk.pipeline(jobId) });
      qc.invalidateQueries({ queryKey: ["applications"] });
    },
  });

  if (pipeline.isLoading || jobQ.isLoading) {
    return (
      <div className="flex gap-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-64 w-72" />
        ))}
      </div>
    );
  }

  if (pipeline.isError || !pipeline.data || !jobQ.data) {
    return (
      <p className="text-sm text-destructive">
        Não foi possível carregar o pipeline.
      </p>
    );
  }

  const activeStages = pipeline.data.stages;
  const terminalStages = jobQ.data.stages.filter(
    (s) => s.kind !== "active",
  );
  const terminalIds = new Set(terminalStages.map((s) => s.id));
  const draggingApp = draggingId
    ? findApp(pipeline.data, draggingId)
    : undefined;

  function onDragStart(e: DragStartEvent) {
    setDraggingId(String(e.active.id));
  }

  function onDragEnd(e: DragEndEvent) {
    setDraggingId(null);
    const overId = e.over ? String(e.over.id) : null;
    const fromStageId = e.active.data.current?.sourceStageId as
      | string
      | undefined;
    if (!overId || !fromStageId || overId === fromStageId) return;

    const app = findApp(pipeline.data, String(e.active.id));
    if (!app) return;

    if (terminalIds.has(overId)) {
      const toStage = terminalStages.find((s) => s.id === overId);
      if (toStage) setPending({ app, fromStageId, toStage });
      return;
    }
    move.mutate({
      applicationId: app.id,
      target_stage_id: overId,
      fromStageId,
    });
  }

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCenter}
      onDragStart={onDragStart}
      onDragEnd={onDragEnd}
      onDragCancel={() => setDraggingId(null)}
    >
      <div className="space-y-6">
        <div className="flex gap-4 overflow-x-auto pb-2">
          {activeStages.map((s) => (
            <Column
              key={s.stage_id}
              stageId={s.stage_id}
              name={s.name}
              count={s.total_count}
            >
              {s.applications.length === 0 ? (
                <p className="px-1 py-6 text-center text-xs text-muted-foreground">
                  Arraste candidatos para cá
                </p>
              ) : (
                s.applications.map((a) => (
                  <KanbanCard
                    key={a.id}
                    application={a}
                    sourceStageId={s.stage_id}
                    onOpen={setDetail}
                  />
                ))
              )}
            </Column>
          ))}
        </div>

        {terminalStages.length > 0 && (
          <div>
            <p className="mb-2 text-xs font-semibold uppercase text-muted-foreground">
              Encerradas
            </p>
            <div className="flex gap-4 overflow-x-auto pb-2">
              {terminalStages.map((s) => (
                <TerminalColumn
                  key={s.id}
                  jobId={jobId}
                  stage={s}
                  onOpen={setDetail}
                />
              ))}
            </div>
          </div>
        )}
      </div>

      <DragOverlay>
        {draggingApp ? <KanbanCardPreview application={draggingApp} /> : null}
      </DragOverlay>

      <ApplicationSheet
        application={detail}
        onClose={() => setDetail(null)}
      />

      <AlertDialog
        open={!!pending}
        onOpenChange={(o) => !o && setPending(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              Mover para {pending?.toStage.name}?
            </AlertDialogTitle>
            <AlertDialogDescription>
              {pending?.toStage.kind === "terminal_hired"
                ? "A application será marcada como contratada."
                : "A application será marcada como rejeitada."}{" "}
              Isso encerra o candidato neste pipeline.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (!pending) return;
                move.mutate({
                  applicationId: pending.app.id,
                  target_stage_id: pending.toStage.id,
                  fromStageId: pending.fromStageId,
                });
                setPending(null);
              }}
            >
              Confirmar
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </DndContext>
  );
}
