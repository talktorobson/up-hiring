"""CRUD de Job tenant-scoped + listagem cursor based."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID  # noqa: TC003 — runtime use by FastAPI DI

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from src.api.v1._deps import get_actor_user_id, require_tenant
from src.db.session import get_db
from src.models.activity import Activity
from src.models.application import Application
from src.models.enums import ActivityEntityType, JobStatus, StageKind
from src.models.job import Job
from src.models.stage import Stage
from src.schemas.application import ApplicationListItem
from src.schemas.job import JobCreate, JobListItem, JobRead, JobUpdate
from src.schemas.pagination import Page
from src.schemas.pipeline import PipelineRead, PipelineStage
from src.services.activity import ActivityService
from src.services.job import JobService
from src.utils.pagination import InvalidCursorError, paginate

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.get(
    "",
    response_model=Page[JobListItem],
    summary="Listar jobs (paginação cursor-based)",
)
async def list_jobs(
    cursor: str | None = Query(default=None, description="Token opaco do paginate."),
    limit: int | None = Query(default=None, ge=1, le=100),
    status_filter: JobStatus | None = Query(default=None, alias="status"),
    tenant_id: UUID = Depends(require_tenant),
    session: AsyncSession = Depends(get_db),
) -> Page[JobListItem]:
    stmt = select(Job).where(Job.deleted_at.is_(None))
    if status_filter is not None:
        stmt = stmt.where(Job.status == status_filter)
    try:
        rows, next_cursor, has_more = await paginate(
            session, stmt, Job, cursor=cursor, limit=limit
        )
    except InvalidCursorError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_cursor"
        ) from exc
    items = [JobListItem.model_validate(j) for j in rows]
    return Page[JobListItem](items=items, next_cursor=next_cursor, has_more=has_more)


@router.get(
    "/{job_id}",
    response_model=JobRead,
    responses={404: {"description": "Job não existe ou RLS escondeu"}},
)
async def get_job(
    job_id: UUID,
    tenant_id: UUID = Depends(require_tenant),
    session: AsyncSession = Depends(get_db),
) -> JobRead:
    job = await session.scalar(
        select(Job)
        .where(Job.id == job_id, Job.deleted_at.is_(None))
        .options(selectinload(Job.stages))
    )
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job_not_found")
    return JobRead.model_validate(job)


@router.post(
    "",
    response_model=JobRead,
    status_code=status.HTTP_201_CREATED,
    summary="Criar Job (semeia 7 stages padrão)",
)
async def create_job(
    payload: JobCreate,
    tenant_id: UUID = Depends(require_tenant),
    actor_user_id: UUID = Depends(get_actor_user_id),
    session: AsyncSession = Depends(get_db),
) -> JobRead:
    job = await JobService.create(
        session, payload, tenant_id=tenant_id, actor_user_id=actor_user_id
    )
    await ActivityService.log(
        session,
        tenant_id=tenant_id,
        entity_type=ActivityEntityType.JOB,
        entity_id=job.id,
        action="job.created",
        actor_user_id=actor_user_id,
        payload={"title": job.title, "status": job.status.value},
    )
    await session.commit()
    return JobRead.model_validate(job)


@router.patch(
    "/{job_id}",
    response_model=JobRead,
    responses={404: {"description": "Job não existe"}},
)
async def update_job(
    job_id: UUID,
    payload: JobUpdate,
    tenant_id: UUID = Depends(require_tenant),
    actor_user_id: UUID = Depends(get_actor_user_id),
    session: AsyncSession = Depends(get_db),
) -> JobRead:
    job = await session.scalar(
        select(Job)
        .where(Job.id == job_id, Job.deleted_at.is_(None))
        .options(selectinload(Job.stages))
    )
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job_not_found")

    diff: dict[str, object] = {}
    for key, value in payload.model_dump(exclude_unset=True).items():
        old = getattr(job, key)
        if old != value:
            diff[key] = {"from": str(old) if old is not None else None, "to": str(value) if value is not None else None}
            setattr(job, key, value)

    await session.flush()

    if diff:
        await ActivityService.log(
            session,
            tenant_id=tenant_id,
            entity_type=ActivityEntityType.JOB,
            entity_id=job.id,
            action="job.updated",
            actor_user_id=actor_user_id,
            payload=diff,
        )
    # Captura updated_at do server (onupdate=func.now) antes do commit,
    # senão acesso depois do commit dispara lazy load em contexto async/sync.
    await session.refresh(job, ["updated_at"])
    await session.commit()
    return JobRead.model_validate(job)


@router.delete(
    "/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"description": "Job não existe"}},
)
async def delete_job(
    job_id: UUID,
    tenant_id: UUID = Depends(require_tenant),
    actor_user_id: UUID = Depends(get_actor_user_id),
    session: AsyncSession = Depends(get_db),
) -> None:
    job = await session.scalar(
        select(Job).where(Job.id == job_id, Job.deleted_at.is_(None))
    )
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job_not_found")

    job.deleted_at = datetime.now(UTC)
    await session.flush()

    await ActivityService.log(
        session,
        tenant_id=tenant_id,
        entity_type=ActivityEntityType.JOB,
        entity_id=job.id,
        action="job.deleted",
        actor_user_id=actor_user_id,
    )
    await session.commit()


@router.get(
    "/{job_id}/pipeline",
    response_model=PipelineRead,
    summary="Board view por stage (kanban da Fase 1)",
    responses={404: {"description": "Job não existe"}},
)
async def get_job_pipeline(
    job_id: UUID,
    tenant_id: UUID = Depends(require_tenant),
    session: AsyncSession = Depends(get_db),
) -> PipelineRead:
    # Garante que o job existe (e pertence ao tenant via RLS) — sem isso
    # caímos no fluxo "sem stages active" e retornaríamos um corpo vazio
    # em vez de 404.
    job_exists = await session.scalar(
        select(Job.id).where(Job.id == job_id, Job.deleted_at.is_(None))
    )
    if job_exists is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job_not_found")

    active_stages = (
        await session.execute(
            select(Stage)
            .where(Stage.job_id == job_id, Stage.kind == StageKind.ACTIVE)
            .order_by(Stage.position)
        )
    ).scalars().all()

    # Single round-trip: count agregado por stage + top-20 apps (subquery).
    # Aqui fazemos 2 queries enxutas (count, depois apps) ao invés de N+1.
    counts_rows = (
        await session.execute(
            select(Application.current_stage_id, func.count(Application.id))
            .where(Application.job_id == job_id)
            .group_by(Application.current_stage_id)
        )
    ).all()
    counts = dict(counts_rows)

    # Top-20 por stage via window function (single query).
    if active_stages:
        from sqlalchemy import literal_column

        rn = func.row_number().over(
            partition_by=Application.current_stage_id,
            order_by=Application.created_at.desc(),
        ).label("rn")
        ranked = (
            select(Application, rn)
            .where(
                Application.job_id == job_id,
                Application.current_stage_id.in_([s.id for s in active_stages]),
            )
            .subquery()
        )
        app_alias = (
            select(Application)
            .join(ranked, ranked.c.id == Application.id)
            .where(literal_column("rn") <= 20)
            .order_by(Application.current_stage_id, Application.created_at.desc())
        )
        apps = (await session.execute(app_alias)).scalars().all()
    else:
        apps = []

    by_stage: dict[UUID, list[ApplicationListItem]] = {s.id: [] for s in active_stages}
    for a in apps:
        by_stage[a.current_stage_id].append(ApplicationListItem.model_validate(a))

    stages = [
        PipelineStage(
            stage_id=s.id,
            name=s.name,
            position=s.position,
            applications=by_stage[s.id],
            total_count=counts.get(s.id, 0),
        )
        for s in active_stages
    ]
    return PipelineRead(job_id=job_id, stages=stages)


# Activity import necessário no runtime mesmo sem uso direto — o ORM precisa
# do mapping registrado quando os endpoints rodam consultas relacionadas.
_ = Activity
