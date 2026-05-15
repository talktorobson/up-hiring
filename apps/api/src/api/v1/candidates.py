"""CRUD de Candidate com validação de CPF e dedup tenant-scoped."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID  # noqa: TC003 — runtime use by FastAPI DI

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select

from src.api.v1._deps import get_actor_user_id, require_tenant
from src.db.session import get_db
from src.models.candidate import Candidate
from src.models.enums import ActivityEntityType
from src.schemas.candidate import CandidateCreate, CandidateRead, CandidateUpdate
from src.schemas.pagination import Page
from src.services.activity import ActivityService
from src.services.candidate import (
    CandidateService,
    DuplicateCandidateError,
    InvalidCPFError,
)
from src.utils.pagination import InvalidCursorError, paginate

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


def _duplicate_response(exc: DuplicateCandidateError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"code": f"duplicate_{exc.field}", "existing_id": str(exc.existing_id)},
    )


@router.get(
    "",
    response_model=Page[CandidateRead],
    summary="Listar candidatos com busca por nome/email",
)
async def list_candidates(
    cursor: str | None = Query(default=None),
    limit: int | None = Query(default=None, ge=1, le=100),
    q: str | None = Query(default=None, description="ilike em full_name e email"),
    tenant_id: UUID = Depends(require_tenant),
    session: AsyncSession = Depends(get_db),
) -> Page[CandidateRead]:
    stmt = select(Candidate).where(Candidate.deleted_at.is_(None))
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Candidate.full_name.ilike(like), Candidate.email.ilike(like)))
    try:
        rows, next_cursor, has_more = await paginate(
            session, stmt, Candidate, cursor=cursor, limit=limit
        )
    except InvalidCursorError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_cursor"
        ) from exc
    return Page[CandidateRead](
        items=[CandidateRead.model_validate(c) for c in rows],
        next_cursor=next_cursor,
        has_more=has_more,
    )


@router.get(
    "/{candidate_id}",
    response_model=CandidateRead,
    responses={404: {"description": "Candidate não existe ou RLS escondeu"}},
)
async def get_candidate(
    candidate_id: UUID,
    tenant_id: UUID = Depends(require_tenant),
    session: AsyncSession = Depends(get_db),
) -> CandidateRead:
    candidate = await session.scalar(
        select(Candidate).where(
            Candidate.id == candidate_id, Candidate.deleted_at.is_(None)
        )
    )
    if candidate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="candidate_not_found"
        )
    return CandidateRead.model_validate(candidate)


@router.post(
    "",
    response_model=CandidateRead,
    status_code=status.HTTP_201_CREATED,
    responses={
        409: {"description": "duplicate_cpf ou duplicate_email"},
        422: {"description": "invalid_cpf"},
    },
)
async def create_candidate(
    payload: CandidateCreate,
    tenant_id: UUID = Depends(require_tenant),
    actor_user_id: UUID = Depends(get_actor_user_id),
    session: AsyncSession = Depends(get_db),
) -> CandidateRead:
    try:
        candidate = await CandidateService.create(
            session, payload, tenant_id=tenant_id
        )
    except InvalidCPFError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid_cpf"
        ) from exc
    except DuplicateCandidateError as exc:
        raise _duplicate_response(exc) from exc

    await ActivityService.log(
        session,
        tenant_id=tenant_id,
        entity_type=ActivityEntityType.CANDIDATE,
        entity_id=candidate.id,
        action="candidate.created",
        actor_user_id=actor_user_id,
        payload={"email": candidate.email},
    )
    await session.commit()
    return CandidateRead.model_validate(candidate)


@router.patch(
    "/{candidate_id}",
    response_model=CandidateRead,
    responses={
        404: {"description": "Candidate não existe"},
        409: {"description": "duplicate_cpf ou duplicate_email"},
        422: {"description": "invalid_cpf"},
    },
)
async def update_candidate(
    candidate_id: UUID,
    payload: CandidateUpdate,
    tenant_id: UUID = Depends(require_tenant),
    actor_user_id: UUID = Depends(get_actor_user_id),
    session: AsyncSession = Depends(get_db),
) -> CandidateRead:
    candidate = await session.scalar(
        select(Candidate).where(
            Candidate.id == candidate_id, Candidate.deleted_at.is_(None)
        )
    )
    if candidate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="candidate_not_found"
        )

    try:
        await CandidateService.update(session, candidate, payload)
    except InvalidCPFError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid_cpf"
        ) from exc
    except DuplicateCandidateError as exc:
        raise _duplicate_response(exc) from exc

    await ActivityService.log(
        session,
        tenant_id=tenant_id,
        entity_type=ActivityEntityType.CANDIDATE,
        entity_id=candidate.id,
        action="candidate.updated",
        actor_user_id=actor_user_id,
    )
    await session.commit()
    return CandidateRead.model_validate(candidate)


@router.delete(
    "/{candidate_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"description": "Candidate não existe"}},
)
async def delete_candidate(
    candidate_id: UUID,
    tenant_id: UUID = Depends(require_tenant),
    actor_user_id: UUID = Depends(get_actor_user_id),
    session: AsyncSession = Depends(get_db),
) -> None:
    candidate = await session.scalar(
        select(Candidate).where(
            Candidate.id == candidate_id, Candidate.deleted_at.is_(None)
        )
    )
    if candidate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="candidate_not_found"
        )

    candidate.deleted_at = datetime.now(UTC)
    await session.flush()

    await ActivityService.log(
        session,
        tenant_id=tenant_id,
        entity_type=ActivityEntityType.CANDIDATE,
        entity_id=candidate.id,
        action="candidate.deleted",
        actor_user_id=actor_user_id,
    )
    await session.commit()
