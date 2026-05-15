"""Handlers que materializam eventos do Clerk no banco.

Cada handler é idempotente. Sessão SQLAlchemy abre via `AsyncSessionLocal()`
direto (sem `SET app.current_tenant_id`) — eventos do Clerk são admin-level,
e a conexão precisa de `BYPASSRLS` (em dev: `ats` superuser; em prod: role
do webhook configurado com o atributo). Veja `src.services.provisioning`.

Em qualquer erro o handler propaga: o endpoint devolve 500 e o Clerk
retenta com backoff.
"""
import logging
from collections.abc import Awaitable, Callable
from uuid import UUID

from sqlalchemy import delete, select

from src.db.session import AsyncSessionLocal
from src.models.tenant import AppUser, Membership, Role, Tenant
from src.services.provisioning import (
    upsert_membership,
    upsert_tenant_from_clerk,
    upsert_user_from_clerk,
)

logger = logging.getLogger(__name__)


CLERK_ROLE_TO_ROLE: dict[str, Role] = {
    "org:admin": Role.ADMIN,
    "org:member": Role.RECRUITER,
}


async def handle_organization_created(payload: dict) -> None:
    data = payload.get("data") or {}
    async with AsyncSessionLocal() as session:
        tenant = await upsert_tenant_from_clerk(session, data)
        await session.commit()
        logger.info("tenant upserted: clerk_org_id=%s id=%s", tenant.clerk_org_id, tenant.id)


async def handle_organization_updated(payload: dict) -> None:
    # upsert_tenant_from_clerk já trata update por clerk_org_id.
    await handle_organization_created(payload)


async def handle_organization_deleted(payload: dict) -> None:
    # Sem coluna `deleted_at` no schema atual. Apenas log para auditoria;
    # cleanup do registro pode rolar em sprint futura quando a UX exigir.
    data = payload.get("data") or {}
    logger.warning("organization.deleted received: clerk_org_id=%s", data.get("id"))


async def handle_user_created(payload: dict) -> None:
    data = payload.get("data") or {}
    async with AsyncSessionLocal() as session:
        user = await upsert_user_from_clerk(session, data)
        await session.commit()
        logger.info("app_user upserted: clerk_user_id=%s id=%s", user.clerk_user_id, user.id)


async def handle_organization_membership_created(payload: dict) -> None:
    data = payload.get("data") or {}
    org = data.get("organization") or {}
    pud = data.get("public_user_data") or {}
    clerk_org_id = org.get("id")
    clerk_user_id = pud.get("user_id")
    clerk_role = data.get("role", "")

    if not clerk_org_id or not clerk_user_id:
        raise ValueError(
            f"organizationMembership payload missing ids: org={clerk_org_id} user={clerk_user_id}"
        )

    role = CLERK_ROLE_TO_ROLE.get(clerk_role, Role.RECRUITER)

    async with AsyncSessionLocal() as session:
        tenant_id = await _resolve_tenant_id(session, clerk_org_id)
        user_id = await _resolve_user_id(session, clerk_user_id)
        await upsert_membership(session, user_id=user_id, tenant_id=tenant_id, role=role)
        await session.commit()
        logger.info(
            "membership upserted: org=%s user=%s role=%s",
            clerk_org_id,
            clerk_user_id,
            role.value,
        )


async def handle_organization_membership_deleted(payload: dict) -> None:
    data = payload.get("data") or {}
    org = data.get("organization") or {}
    pud = data.get("public_user_data") or {}
    clerk_org_id = org.get("id")
    clerk_user_id = pud.get("user_id")

    if not clerk_org_id or not clerk_user_id:
        raise ValueError(
            f"organizationMembership delete payload missing ids: "
            f"org={clerk_org_id} user={clerk_user_id}"
        )

    async with AsyncSessionLocal() as session:
        tenant_id = await _resolve_tenant_id(session, clerk_org_id)
        user_id = await _resolve_user_id(session, clerk_user_id)
        await session.execute(
            delete(Membership).where(
                Membership.tenant_id == tenant_id,
                Membership.user_id == user_id,
            )
        )
        await session.commit()
        logger.info("membership deleted: org=%s user=%s", clerk_org_id, clerk_user_id)


async def _resolve_tenant_id(session, clerk_org_id: str) -> UUID:
    tenant_id = await session.scalar(
        select(Tenant.id).where(Tenant.clerk_org_id == clerk_org_id)
    )
    if tenant_id is None:
        raise LookupError(f"tenant not provisioned for clerk_org_id={clerk_org_id}")
    return tenant_id


async def _resolve_user_id(session, clerk_user_id: str) -> UUID:
    user_id = await session.scalar(
        select(AppUser.id).where(AppUser.clerk_user_id == clerk_user_id)
    )
    if user_id is None:
        raise LookupError(f"app_user not provisioned for clerk_user_id={clerk_user_id}")
    return user_id


HandlerFn = Callable[[dict], Awaitable[None]]

HANDLERS: dict[str, HandlerFn] = {
    "organization.created": handle_organization_created,
    "organization.updated": handle_organization_updated,
    "organization.deleted": handle_organization_deleted,
    "user.created": handle_user_created,
    "organizationMembership.created": handle_organization_membership_created,
    "organizationMembership.deleted": handle_organization_membership_deleted,
}
