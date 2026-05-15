"""Provas de RLS via SQL direto.

Estes testes não passam pelo middleware nem pelo SQLAlchemy ORM. Eles abrem
sessão como `uphiring_app` (sem BYPASSRLS) e exercem as policies definidas
na migration `5580eabe8ece` — se algum vazamento aparecer aqui, o problema
é de Postgres-level, antes de qualquer camada da app.

Cada `_with_tenant_ctx` abre uma transação explícita pra que o `SET LOCAL`
e o SELECT subsequente fiquem na mesma tx (SET LOCAL é tx-scoped). Isso
evita corner cases onde SQLAlchemy isola statements em txs separadas.
"""
from contextlib import asynccontextmanager
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from src.models.tenant import Role
from tests.factories import make_membership, make_tenant, make_user

pytestmark = pytest.mark.rls


@asynccontextmanager
async def _with_tenant_ctx(session, tenant_id: UUID | None):
    """Abre tx explícita; opcionalmente seta app.current_tenant_id."""
    async with session.begin():
        if tenant_id is not None:
            # SET LOCAL não suporta parameter binding em asyncpg. UUID validado
            # upstream — interpolação é segura.
            await session.execute(
                text(f"SET LOCAL app.current_tenant_id = '{tenant_id}'")
            )
        yield


async def test_tenant_isolation_select(app_role_session, two_tenants) -> None:
    a, _, b, _ = two_tenants

    async with _with_tenant_ctx(app_role_session, a.id):
        rows = (await app_role_session.execute(text("SELECT id FROM tenant"))).scalars().all()
        assert list(rows) == [a.id]

    async with _with_tenant_ctx(app_role_session, b.id):
        rows = (await app_role_session.execute(text("SELECT id FROM tenant"))).scalars().all()
        assert list(rows) == [b.id]


async def test_membership_isolation(app_role_session, two_tenants) -> None:
    a, ua, b, ub = two_tenants

    async with _with_tenant_ctx(app_role_session, a.id):
        rows = (
            await app_role_session.execute(text("SELECT user_id, tenant_id FROM membership"))
        ).all()
        assert len(rows) == 1
        assert rows[0] == (ua.id, a.id)

    async with _with_tenant_ctx(app_role_session, b.id):
        rows = (
            await app_role_session.execute(text("SELECT user_id, tenant_id FROM membership"))
        ).all()
        assert len(rows) == 1
        assert rows[0] == (ub.id, b.id)


async def test_insert_blocked_wrong_tenant(app_role_session, two_tenants) -> None:
    a, ua, b, _ = two_tenants

    with pytest.raises(ProgrammingError) as exc_info:
        async with _with_tenant_ctx(app_role_session, a.id):
            await app_role_session.execute(
                text(
                    "INSERT INTO membership (id, user_id, tenant_id, role) "
                    f"VALUES ('{uuid4()}', '{ua.id}', '{b.id}', '{Role.RECRUITER.value}')"
                )
            )
    assert "row-level security policy" in str(exc_info.value).lower()


async def test_no_tenant_returns_empty(app_role_session, two_tenants) -> None:
    # Sem SET LOCAL: current_setting('app.current_tenant_id', true) é NULL,
    # comparação NULL = id é NULL → linha excluída pela policy.
    async with _with_tenant_ctx(app_role_session, None):
        rows = (await app_role_session.execute(text("SELECT id FROM tenant"))).all()
        assert rows == []
        rows = (await app_role_session.execute(text("SELECT id FROM membership"))).all()
        assert rows == []


async def test_app_role_cannot_bypass(app_role_session, db_session) -> None:
    # Cria tenant via admin (BYPASS RLS) e tenta SELECT como uphiring_app
    # sem SET LOCAL — policies devem bloquear mesmo com FORCE RLS.
    tenant = await make_tenant(db_session, clerk_org_id="org_isolated", slug="isolated")
    user = await make_user(db_session, clerk_user_id="user_isolated")
    await make_membership(db_session, user_id=user.id, tenant_id=tenant.id, role=Role.OWNER)
    await db_session.commit()

    async with _with_tenant_ctx(app_role_session, None):
        rows = (
            await app_role_session.execute(
                text("SELECT id FROM tenant WHERE clerk_org_id = 'org_isolated'")
            )
        ).all()
        assert rows == [], "uphiring_app sem SET LOCAL conseguiu ler tenant — RLS BYPASS!"

    async with _with_tenant_ctx(app_role_session, tenant.id):
        rows = (
            await app_role_session.execute(
                text("SELECT id FROM tenant WHERE clerk_org_id = 'org_isolated'")
            )
        ).all()
        assert rows == [(tenant.id,)]
