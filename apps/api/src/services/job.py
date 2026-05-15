"""JobService — criar/atualizar Job mantendo invariantes (stages seedadas).

Service layer (não trigger Postgres) pra manter a lógica testável em pytest
sem precisar inspecionar SQL.
"""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.job import Job
from src.models.stage import Stage
from src.schemas.job import JobCreate
from src.services.stage_defaults import DEFAULT_STAGES


class JobService:
    @staticmethod
    async def create(
        session: AsyncSession,
        payload: JobCreate,
        *,
        tenant_id: UUID,
        actor_user_id: UUID | None,
    ) -> Job:
        """Cria Job + 7 stages padrão na mesma transação.

        Caller commita a sessão. Se qualquer INSERT falhar, o caller deve
        rollback (FastAPI dependency `get_db` faz isso automaticamente).
        """
        job = Job(
            tenant_id=tenant_id,
            title=payload.title,
            description=payload.description,
            location=payload.location,
            employment_type=payload.employment_type,
            salary_min=payload.salary_min,
            salary_max=payload.salary_max,
            status=payload.status,
            created_by=actor_user_id,
        )
        session.add(job)
        await session.flush()  # garante job.id pra Stage.job_id

        for name, position, kind in DEFAULT_STAGES:
            session.add(
                Stage(
                    tenant_id=tenant_id,
                    job_id=job.id,
                    name=name,
                    position=position,
                    kind=kind,
                )
            )

        await session.flush()
        # Re-load com selectinload pra retornar com stages anexados.
        result = await session.execute(
            select(Job).where(Job.id == job.id).options(selectinload(Job.stages))
        )
        return result.scalar_one()
