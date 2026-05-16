"use client";

import { useDraggable } from "@dnd-kit/core";
import { CSS } from "@dnd-kit/utilities";

import { Badge } from "@/components/ui/badge";
import type { ApplicationListItem } from "@/lib/api-types";
import { useCandidate } from "@/lib/hooks";
import { cn, formatDate } from "@/lib/utils";

export function KanbanCard({
  application,
  sourceStageId,
  onOpen,
}: {
  application: ApplicationListItem;
  sourceStageId: string;
  onOpen: (a: ApplicationListItem) => void;
}) {
  const { data: candidate } = useCandidate(application.candidate_id);
  const { attributes, listeners, setNodeRef, transform, isDragging } =
    useDraggable({
      id: application.id,
      data: { sourceStageId },
    });

  return (
    <button
      ref={setNodeRef}
      type="button"
      style={{ transform: CSS.Translate.toString(transform) }}
      className={cn(
        "w-full cursor-grab rounded-md border bg-white p-3 text-left shadow-sm transition active:cursor-grabbing hover:border-slate-300",
        isDragging && "opacity-50",
      )}
      onClick={() => onOpen(application)}
      {...listeners}
      {...attributes}
    >
      <p className="truncate text-sm font-medium">
        {candidate?.full_name ?? "Carregando…"}
      </p>
      <p className="truncate text-xs text-muted-foreground">
        {candidate?.email ?? "—"}
      </p>
      <div className="mt-2 flex items-center justify-between">
        {candidate?.source ? (
          <Badge variant="secondary" className="text-[10px]">
            {candidate.source}
          </Badge>
        ) : (
          <span />
        )}
        <span className="text-[10px] text-muted-foreground">
          {formatDate(application.created_at)}
        </span>
      </div>
    </button>
  );
}

/** Versão estática mostrada no <DragOverlay> durante o arrasto. */
export function KanbanCardPreview({
  application,
}: {
  application: ApplicationListItem;
}) {
  const { data: candidate } = useCandidate(application.candidate_id);
  return (
    <div className="w-64 rotate-2 rounded-md border bg-white p-3 shadow-lg">
      <p className="truncate text-sm font-medium">
        {candidate?.full_name ?? "Candidato"}
      </p>
      <p className="truncate text-xs text-muted-foreground">
        {candidate?.email ?? "—"}
      </p>
    </div>
  );
}
