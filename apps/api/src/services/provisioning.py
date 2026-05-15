"""Materializa Tenant/AppUser/Membership a partir de payloads do Clerk.

Pré-requisito de RLS: o tenant e a membership ficam atrás de FORCE ROW LEVEL
SECURITY. Estes upserts presumem que a conexão tem `BYPASSRLS` (em dev usamos o
superuser `ats`; em prod, o role da connection do webhook precisa do atributo).
Sem isso o SELECT/INSERT em `tenant` falha porque NULL = id é falso e FORCE RLS
ignora ownership.
"""
import re
import unicodedata
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.tenant import AppUser, Membership, Role, Tenant


def slugify(text: str, fallback: str = "tenant") -> str:
    """Lowercase ASCII com hífens. Vazio → fallback."""
    normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", normalized.lower()).strip("-")
    return slug or fallback


async def _unique_slug(session: AsyncSession, base: str) -> str:
    """Devolve `base`, ou `base-2`, `base-3`... se já existir."""
    candidate = base
    suffix = 2
    while await session.scalar(select(Tenant.id).where(Tenant.slug == candidate)):
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


async def upsert_tenant_from_clerk(session: AsyncSession, payload: dict) -> Tenant:
    """Idempotente por `clerk_org_id`. Atualiza name/slug em re-recebimento."""
    clerk_org_id = payload["id"]
    name = payload.get("name") or "Tenant"

    existing = await session.scalar(
        select(Tenant).where(Tenant.clerk_org_id == clerk_org_id)
    )
    if existing:
        existing.name = name
        return existing

    desired_slug = payload.get("slug") or slugify(name)
    slug = await _unique_slug(session, desired_slug)
    tenant = Tenant(clerk_org_id=clerk_org_id, name=name, slug=slug)
    session.add(tenant)
    await session.flush()
    return tenant


def _primary_email(payload: dict) -> str:
    addrs = payload.get("email_addresses") or []
    primary_id = payload.get("primary_email_address_id")
    for addr in addrs:
        if addr.get("id") == primary_id:
            return addr["email_address"]
    if addrs:
        return addrs[0]["email_address"]
    return payload.get("email_address", "")


def _full_name(payload: dict) -> str | None:
    parts = [payload.get("first_name"), payload.get("last_name")]
    name = " ".join(p for p in parts if p)
    return name or None


async def upsert_user_from_clerk(session: AsyncSession, payload: dict) -> AppUser:
    """Idempotente por `clerk_user_id`. Atualiza email/full_name em re-recebimento."""
    clerk_user_id = payload["id"]
    email = _primary_email(payload)
    full_name = _full_name(payload)

    existing = await session.scalar(
        select(AppUser).where(AppUser.clerk_user_id == clerk_user_id)
    )
    if existing:
        existing.email = email
        existing.full_name = full_name
        return existing

    user = AppUser(clerk_user_id=clerk_user_id, email=email, full_name=full_name)
    session.add(user)
    await session.flush()
    return user


async def upsert_membership(
    session: AsyncSession,
    *,
    user_id: UUID,
    tenant_id: UUID,
    role: Role,
) -> Membership:
    """Idempotente por `(user_id, tenant_id)`. Atualiza role."""
    existing = await session.scalar(
        select(Membership).where(
            Membership.user_id == user_id,
            Membership.tenant_id == tenant_id,
        )
    )
    if existing:
        existing.role = role
        return existing

    membership = Membership(user_id=user_id, tenant_id=tenant_id, role=role)
    session.add(membership)
    await session.flush()
    return membership
