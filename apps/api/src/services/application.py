"""ApplicationService — criação + movimento de stage com activity log."""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from src.models.application import Application
from src.models.enums import ActivityEntityType, ApplicationStatus, StageKind
from src.models.stage import Stage
from src.services.activity import ActivityService

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession


class ApplicationDomainError(ValueError):
    """Erro de domínio com `code` HTTP-friendly."""

    def __init__(self, code: str, *, extra: dict | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.extra = extra or {}


class ApplicationService:
    @staticmethod
    async def create(
        session: AsyncSession,
        *,
        tenant_id: UUID,
        job_id: UUID,
        candidate_id: UUID,
        actor_user_id: UUID | None,
    ) -> Application:
        """Cria Application no primeiro stage ACTIVE do job.

        Erros:
        - job_not_found / candidate_not_found (404 na API)
        - duplicate_application: candidato já tem app no mesmo job (409)
        """
        first_stage = await session.scalar(
            select(Stage)
            .where(Stage.job_id == job_id, Stage.kind == StageKind.ACTIVE)
            .order_by(Stage.position)
            .limit(1)
        )
        if first_stage is None:
            # Sem stages active = job de outro tenant (RLS escondeu) ou job sem stages.
            raise ApplicationDomainError("job_not_found")

        existing = await session.scalar(
            select(Application.id).where(
                Application.tenant_id == tenant_id,
                Application.job_id == job_id,
                Application.candidate_id == candidate_id,
            )
        )
        if existing is not None:
            raise ApplicationDomainError(
                "duplicate_application", extra={"existing_id": str(existing)}
            )

        app = Application(
            tenant_id=tenant_id,
            job_id=job_id,
            candidate_id=candidate_id,
            current_stage_id=first_stage.id,
        )
        session.add(app)
        await session.flush()

        await ActivityService.log(
            session,
            tenant_id=tenant_id,
            entity_type=ActivityEntityType.APPLICATION,
            entity_id=app.id,
            action="application.created",
            actor_user_id=actor_user_id,
            payload={
                "job_id": str(job_id),
                "candidate_id": str(candidate_id),
                "stage_id": str(first_stage.id),
                "stage_name": first_stage.name,
            },
        )
        return app

    @staticmethod
    async def move_stage(
        session: AsyncSession,
        application: Application,
        *,
        target_stage_id: UUID,
        actor_user_id: UUID | None,
    ) -> Application:
        """Move application para `target_stage_id` se pertencer ao mesmo job.

        Stages terminais setam o status do application (hired/rejected).
        Activity application.stage_changed registra from/to com nomes.
        """
        target = await session.scalar(
            select(Stage).where(Stage.id == target_stage_id)
        )
        if target is None or target.job_id != application.job_id:
            raise ApplicationDomainError("stage_not_in_job")

        if target.id == application.current_stage_id:
            return application  # no-op, sem activity

        from_stage = await session.scalar(
            select(Stage).where(Stage.id == application.current_stage_id)
        )

        application.current_stage_id = target.id
        if target.kind == StageKind.TERMINAL_HIRED:
            application.status = ApplicationStatus.HIRED
        elif target.kind == StageKind.TERMINAL_REJECTED:
            application.status = ApplicationStatus.REJECTED
        # Saindo de terminal pra active reverte pro ACTIVE? Não — caso de
        # uso é re-abrir candidato. Mantemos status atual; UX trata.

        await session.flush()

        await ActivityService.log(
            session,
            tenant_id=application.tenant_id,
            entity_type=ActivityEntityType.APPLICATION,
            entity_id=application.id,
            action="application.stage_changed",
            actor_user_id=actor_user_id,
            payload={
                "from_stage_id": str(from_stage.id) if from_stage else None,
                "from_stage_name": from_stage.name if from_stage else None,
                "to_stage_id": str(target.id),
                "to_stage_name": target.name,
            },
        )
        return application
