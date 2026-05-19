"""Provisiona tenants/users reais do Clerk pro happy-path E2E (Sprint 4 #89).

Em CI o webhook do Clerk NÃO dispara (sem Clerk → runner efêmero), então a
árvore tenant/user/membership que normalmente é materializada por
`organization.created` não existe. Sem ela o primeiro request autenticado do
happy-path bate em 403 `tenant_not_provisioned` (middleware/clerk.py) ou 404
`user_not_provisioned` (_deps.get_actor_user_id) — o teste fica vermelho.

Este script espelha o que o webhook faria, mas a partir dos IDs reais dos
test users/orgs do Clerk passados por env (GitHub secrets). É idempotente e
**no-op** (exit 0) se os IDs não estiverem setados — assim é seguro rodar
incondicionalmente em CI e localmente.

NÃO altera comportamento de produção: prod continua provisionando via webhook.

Uso (rodar DEPOIS de `seed --reset`):
    uv run python -m src.scripts.seed_e2e
"""
from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass

from sqlalchemy import select, text

from src.db.session import AsyncSessionLocal
from src.models.tenant import AppUser, Membership, Role, Tenant


@dataclass(frozen=True)
class E2ESpec:
    org_id: str
    user_id: str
    email: str
    slug: str
    name: str


def _specs() -> list[E2ESpec] | None:
    """Lê os IDs reais do Clerk do env. None se algum obrigatório faltar."""
    raw = {
        "org_a": os.environ.get("E2E_CLERK_ORG_A_ID"),
        "user_a": os.environ.get("E2E_CLERK_USER_A_ID"),
        "org_b": os.environ.get("E2E_CLERK_ORG_B_ID"),
        "user_b": os.environ.get("E2E_CLERK_USER_B_ID"),
    }
    missing = [k for k, v in raw.items() if not v]
    if missing:
        print(
            "seed_e2e: IDs Clerk E2E ausentes "
            f"({', '.join(sorted(missing))}) — no-op (ver RUNBOOK §8)."
        )
        return None
    return [
        E2ESpec(
            org_id=raw["org_a"],
            user_id=raw["user_a"],
            email=os.environ.get("E2E_USER_A_EMAIL", "e2e-a@uphiring.test"),
            slug="e2e-a",
            name="E2E Org A",
        ),
        E2ESpec(
            org_id=raw["org_b"],
            user_id=raw["user_b"],
            email=os.environ.get("E2E_USER_B_EMAIL", "e2e-b@uphiring.test"),
            slug="e2e-b",
            name="E2E Org B",
        ),
    ]


async def provision(spec: E2ESpec) -> None:
    """Tenant + AppUser + Membership(OWNER) idempotentes, 1 txn por org."""
    async with AsyncSessionLocal() as s:
        tenant = await s.scalar(
            select(Tenant).where(Tenant.clerk_org_id == spec.org_id)
        )
        if tenant is None:
            tenant = Tenant(
                clerk_org_id=spec.org_id, name=spec.name, slug=spec.slug
            )
            s.add(tenant)
            await s.flush()
        await s.execute(
            text(f"SET LOCAL app.current_tenant_id = '{tenant.id}'")
        )

        user = await s.scalar(
            select(AppUser).where(AppUser.clerk_user_id == spec.user_id)
        )
        if user is None:
            user = AppUser(
                clerk_user_id=spec.user_id,
                email=spec.email,
                full_name=spec.name + " Owner",
            )
            s.add(user)
            await s.flush()

        membership = await s.scalar(
            select(Membership).where(
                Membership.user_id == user.id,
                Membership.tenant_id == tenant.id,
            )
        )
        if membership is None:
            s.add(
                Membership(
                    user_id=user.id, tenant_id=tenant.id, role=Role.OWNER
                )
            )

        await s.commit()
        print(
            f"  {spec.name}: org={spec.org_id} user={spec.user_id} "
            f"tenant={tenant.id} (provisionado/ok)"
        )


async def main() -> None:
    specs = _specs()
    if specs is None:
        return
    print("Provisionando tenants/users E2E…")
    for spec in specs:
        await provision(spec)
    print("seed_e2e concluído.")


if __name__ == "__main__":
    asyncio.run(main())
