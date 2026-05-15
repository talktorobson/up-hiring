"""Resolução de tenant a partir do `clerk_org_id`, com cache Redis.

Cache TTL 10 min, key `clerk_org:{org_id}:tenant_id`. Falhas de Redis caem
silenciosamente pro DB — cache é otimização, não fonte da verdade.

Pré-requisito de RLS: o `SELECT FROM tenant` precisa de conexão com
`BYPASSRLS` (em dev: `ats` superuser). Sem isso o middleware sempre devolve
403 tenant_not_provisioned mesmo com tenant existente.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from uuid import UUID

import redis.asyncio as redis_async
from sqlalchemy import select

from src.config import settings
from src.models.tenant import Tenant

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 600
_CACHE_KEY_TMPL = "clerk_org:{org_id}:tenant_id"

_redis: redis_async.Redis | None = None


def _get_redis() -> redis_async.Redis:
    global _redis
    if _redis is None:
        _redis = redis_async.from_url(settings.redis_url, decode_responses=True)
    return _redis


def reset_redis() -> None:
    """Para uso em testes — força nova conexão na próxima call."""
    global _redis
    _redis = None


async def resolve_tenant_id(session: AsyncSession, clerk_org_id: str) -> UUID | None:
    """DB lookup direto, sem cache."""
    return await session.scalar(
        select(Tenant.id).where(Tenant.clerk_org_id == clerk_org_id)
    )


async def resolve_tenant_id_cached(
    session_factory: Callable[[], Awaitable[AsyncSession] | AsyncSession],
    clerk_org_id: str,
) -> UUID | None:
    """Cache-first: Redis → DB. Atualiza cache em hit no DB."""
    cached = await _get_cached(clerk_org_id)
    if cached is not None:
        logger.debug("tenant.cache hit clerk_org_id=%s", clerk_org_id)
        return cached

    logger.debug("tenant.cache miss clerk_org_id=%s", clerk_org_id)
    async with session_factory() as session:
        tenant_id = await resolve_tenant_id(session, clerk_org_id)

    if tenant_id is not None:
        await _set_cached(clerk_org_id, tenant_id)
    return tenant_id


async def _get_cached(clerk_org_id: str) -> UUID | None:
    try:
        val = await _get_redis().get(_CACHE_KEY_TMPL.format(org_id=clerk_org_id))
    except Exception as exc:
        logger.warning("tenant.cache get failed: %s", exc)
        return None
    if not val:
        return None
    try:
        return UUID(val)
    except ValueError:
        return None


async def _set_cached(clerk_org_id: str, tenant_id: UUID) -> None:
    try:
        await _get_redis().setex(
            _CACHE_KEY_TMPL.format(org_id=clerk_org_id),
            CACHE_TTL_SECONDS,
            str(tenant_id),
        )
    except Exception as exc:
        logger.warning("tenant.cache set failed: %s", exc)


async def invalidate_cached_tenant(clerk_org_id: str) -> None:
    try:
        await _get_redis().delete(_CACHE_KEY_TMPL.format(org_id=clerk_org_id))
    except Exception as exc:
        logger.warning("tenant.cache delete failed: %s", exc)
