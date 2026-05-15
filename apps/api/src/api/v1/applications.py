"""Applications + movimentação de stage."""
from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID  # noqa: TC003 — runtime use by FastAPI DI

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select

from src.api.v1._deps import get_actor_user_id, require_tenant
from src.db.session import get_db
from src.models.activity import Activity
from src.models.application import Application
from src.models.enums import ActivityEntityType
from src.schemas.activity import ActivityRead
from src.schemas.application import (
    ApplicationCreate,
    ApplicationListItem,
    ApplicationRead,
    ApplicationStageMove,
)
from src.schemas.pagination import Page
from src.services.application import ApplicationDomainError, ApplicationService
from src.utils.pagination import InvalidCursorError, paginate

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


router = APIRouter()

_DOMAIN_ERROR_STATUS = {
    "job_not_found": status.HTTP_404_NOT_FOUND,
    "stage_not_in_job": status.HTTP_422_UNPROCESSABLE_ENTITY,
    "duplicate_application": status.HTTP_409_CONFLICT,
}


def _domain_http(exc: ApplicationDomainError) -> HTTPException:
    detail: dict | str = {"code": exc.code, **exc.extra} if exc.extra else exc.code
    return HTTPException(
        status_code=_DOMAIN_ERROR_STATUS.get(exc.code, status.HTTP_400_BAD_REQUEST),
        detail=detail,
    )


@router.get("", response_model=Page[ApplicationListItem])
async def list_applications(
    cursor: str | None = Query(default=None),
    limit: int | None = Query(default=None, ge=1, le=100),
    job_id: UUID | None = Query(default=None),
    stage_id: UUID | None = Query(default=None),
    candidate_id: UUID | None = Query(default=None),
    tenant_id: UUID = Depends(require_tenant),
    session: AsyncSession = Depends(get_db),
) -> Page[ApplicationListItem]:
    stmt = select(Application)
    if job_id is not None:
        stmt = stmt.where(Application.job_id == job_id)
    if stage_id is not None:
        stmt = stmt.where(Application.current_stage_id == stage_id)
    if candidate_id is not None:
        stmt = stmt.where(Application.candidate_id == candidate_id)
    try:
        rows, next_cursor, has_more = await paginate(
            session, stmt, Application, cursor=cursor, limit=limit
        )
    except InvalidCursorError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_cursor"
        ) from exc
    return Page[ApplicationListItem](
        items=[ApplicationListItem.model_validate(a) for a in rows],
        next_cursor=next_cursor,
        has_more=has_more,
    )


@router.get(
    "/{application_id}",
    response_model=ApplicationRead,
    responses={404: {"description": "Application não existe"}},
)
async def get_application(
    application_id: UUID,
    tenant_id: UUID = Depends(require_tenant),
    session: AsyncSession = Depends(get_db),
) -> ApplicationRead:
    application = await session.scalar(
        select(Application).where(Application.id == application_id)
    )
    if application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="application_not_found"
        )

    # Últimas 20 activities de stage_changed pra essa application.
    history = (
        await session.execute(
            select(Activity)
            .where(
                Activity.entity_type == ActivityEntityType.APPLICATION,
                Activity.entity_id == application.id,
                Activity.action == "application.stage_changed",
            )
            .order_by(Activity.created_at.desc())
            .limit(20)
        )
    ).scalars().all()

    return ApplicationRead(
        id=application.id,
        job_id=application.job_id,
        candidate_id=application.candidate_id,
        current_stage_id=application.current_stage_id,
        status=application.status,
        created_at=application.created_at,
        updated_at=application.updated_at,
        stage_history=[ActivityRead.model_validate(a) for a in history],
    )


@router.post(
    "",
    response_model=ApplicationRead,
    status_code=status.HTTP_201_CREATED,
    responses={
        404: {"description": "job_not_found"},
        409: {"description": "duplicate_application"},
    },
)
async def create_application(
    payload: ApplicationCreate,
    tenant_id: UUID = Depends(require_tenant),
    actor_user_id: UUID = Depends(get_actor_user_id),
    session: AsyncSession = Depends(get_db),
) -> ApplicationRead:
    try:
        application = await ApplicationService.create(
            session,
            tenant_id=tenant_id,
            job_id=payload.job_id,
            candidate_id=payload.candidate_id,
            actor_user_id=actor_user_id,
        )
    except ApplicationDomainError as exc:
        raise _domain_http(exc) from exc
    await session.commit()
    return ApplicationRead(
        id=application.id,
        job_id=application.job_id,
        candidate_id=application.candidate_id,
        current_stage_id=application.current_stage_id,
        status=application.status,
        created_at=application.created_at,
        updated_at=application.updated_at,
        stage_history=[],
    )


@router.patch(
    "/{application_id}/stage",
    response_model=ApplicationRead,
    responses={
        404: {"description": "application_not_found"},
        422: {"description": "stage_not_in_job"},
    },
)
async def move_application_stage(
    application_id: UUID,
    payload: ApplicationStageMove,
    tenant_id: UUID = Depends(require_tenant),
    actor_user_id: UUID = Depends(get_actor_user_id),
    session: AsyncSession = Depends(get_db),
) -> ApplicationRead:
    application = await session.scalar(
        select(Application).where(Application.id == application_id)
    )
    if application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="application_not_found"
        )
    try:
        await ApplicationService.move_stage(
            session,
            application,
            target_stage_id=payload.target_stage_id,
            actor_user_id=actor_user_id,
        )
    except ApplicationDomainError as exc:
        raise _domain_http(exc) from exc
    # Refresh ANTES de commit pra capturar server-side onupdate(func.now())
    # de updated_at. Acessar updated_at depois do commit dispara lazy load
    # → MissingGreenlet em contexto async/sync mix.
    await session.refresh(application, ["updated_at"])
    await session.commit()
    return ApplicationRead(
        id=application.id,
        job_id=application.job_id,
        candidate_id=application.candidate_id,
        current_stage_id=application.current_stage_id,
        status=application.status,
        created_at=application.created_at,
        updated_at=application.updated_at,
        stage_history=[],
    )
