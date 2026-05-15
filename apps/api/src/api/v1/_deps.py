"""Dependências compartilhadas entre endpoints v1."""
from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID  # noqa: TC003 — needed at runtime by FastAPI DI

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select

from src.db.session import get_db
from src.models.tenant import AppUser

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def require_tenant(request: Request) -> UUID:
    """Garante request.state.tenant_id setado pelo middleware."""
    tenant_id = getattr(request.state, "tenant_id", None)
    if tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="org_required"
        )
    return tenant_id


async def get_actor_user_id(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> UUID:
    """Resolve app_user.id a partir do clerk_user_id no JWT.

    Endpoints que registram `actor_user_id` (activity log, created_by, etc.)
    precisam do UUID interno do AppUser — o sub do JWT é o id Clerk.
    """
    clerk_user_id = getattr(request.state, "user_id", None)
    if not clerk_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthenticated"
        )
    actor_id = await session.scalar(
        select(AppUser.id).where(AppUser.clerk_user_id == clerk_user_id)
    )
    if actor_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="user_not_provisioned"
        )
    return actor_id
