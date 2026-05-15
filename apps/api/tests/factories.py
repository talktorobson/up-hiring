"""Factories pra criar Tenant/AppUser/Membership em testes.

Tudo idempotente por chamada (UUID novo a cada vez); para reuse explícito,
passe os kwargs.
"""
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.tenant import AppUser, Membership, Role, Tenant


async def make_tenant(
    session: AsyncSession,
    *,
    clerk_org_id: str | None = None,
    name: str | None = None,
    slug: str | None = None,
) -> Tenant:
    suffix = uuid4().hex[:8]
    tenant = Tenant(
        clerk_org_id=clerk_org_id or f"org_{suffix}",
        name=name or f"Tenant {suffix}",
        slug=slug or f"tenant-{suffix}",
    )
    session.add(tenant)
    await session.flush()
    return tenant


async def make_user(
    session: AsyncSession,
    *,
    clerk_user_id: str | None = None,
    email: str | None = None,
    full_name: str | None = None,
) -> AppUser:
    suffix = uuid4().hex[:8]
    user = AppUser(
        clerk_user_id=clerk_user_id or f"user_{suffix}",
        email=email or f"u{suffix}@example.com",
        full_name=full_name,
    )
    session.add(user)
    await session.flush()
    return user


async def make_membership(
    session: AsyncSession,
    *,
    user_id,
    tenant_id,
    role: Role = Role.ADMIN,
) -> Membership:
    membership = Membership(user_id=user_id, tenant_id=tenant_id, role=role)
    session.add(membership)
    await session.flush()
    return membership
