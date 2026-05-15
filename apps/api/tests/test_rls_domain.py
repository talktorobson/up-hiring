"""Provas de RLS para job/stage/candidate/application/activity.

Mesmo padrão do `test_rls.py` (Sprint 2): conexão como `uphiring_app`,
tx explícita com `SET LOCAL app.current_tenant_id`, SELECT direto via SQL.

Cobre os 4 modelos novos + cross-INSERT bloqueado + role sem BYPASS.
"""
from contextlib import asynccontextmanager
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from src.models.enums import StageKind

pytestmark = pytest.mark.rls


@asynccontextmanager
async def _with_tenant_ctx(session, tenant_id: UUID | None):
    async with session.begin():
        if tenant_id is not None:
            await session.execute(
                text(f"SET LOCAL app.current_tenant_id = '{tenant_id}'")
            )
        yield


async def _seed_domain(db_session, tenant_id) -> dict[str, UUID]:
    """Cria 1 job + 1 stage + 1 candidate + 1 application + 1 activity como admin."""
    job_id = uuid4()
    stage_id = uuid4()
    candidate_id = uuid4()
    app_id = uuid4()
    activity_id = uuid4()

    await db_session.execute(
        text(
            """
            INSERT INTO job (id, tenant_id, title, employment_type, status, created_at, updated_at)
            VALUES (:id, :tid, 'Job', 'clt', 'open', now(), now())
            """
        ),
        {"id": job_id, "tid": tenant_id},
    )
    await db_session.execute(
        text(
            """
            INSERT INTO stage (id, tenant_id, job_id, name, position, kind, created_at)
            VALUES (:id, :tid, :jid, 'Sourced', 0, :kind, now())
            """
        ),
        {"id": stage_id, "tid": tenant_id, "jid": job_id, "kind": StageKind.ACTIVE.value},
    )
    await db_session.execute(
        text(
            """
            INSERT INTO candidate (id, tenant_id, full_name, email, created_at, updated_at)
            VALUES (:id, :tid, 'Cand', :email, now(), now())
            """
        ),
        {"id": candidate_id, "tid": tenant_id, "email": f"c{candidate_id}@x.com"},
    )
    await db_session.execute(
        text(
            """
            INSERT INTO application
                (id, tenant_id, job_id, candidate_id, current_stage_id, status, created_at, updated_at)
            VALUES (:id, :tid, :jid, :cid, :sid, 'active', now(), now())
            """
        ),
        {
            "id": app_id,
            "tid": tenant_id,
            "jid": job_id,
            "cid": candidate_id,
            "sid": stage_id,
        },
    )
    await db_session.execute(
        text(
            """
            INSERT INTO activity (id, tenant_id, entity_type, entity_id, action, created_at)
            VALUES (:id, :tid, 'application', :eid, 'application.created', now())
            """
        ),
        {"id": activity_id, "tid": tenant_id, "eid": app_id},
    )
    await db_session.commit()
    return {
        "job": job_id,
        "stage": stage_id,
        "candidate": candidate_id,
        "application": app_id,
        "activity": activity_id,
    }


async def test_job_isolation(app_role_session, db_session, two_tenants):
    a, _, b, _ = two_tenants
    ids_a = await _seed_domain(db_session, a.id)
    ids_b = await _seed_domain(db_session, b.id)

    async with _with_tenant_ctx(app_role_session, a.id):
        rows = (await app_role_session.execute(text("SELECT id FROM job"))).scalars().all()
        assert list(rows) == [ids_a["job"]]

    async with _with_tenant_ctx(app_role_session, b.id):
        rows = (await app_role_session.execute(text("SELECT id FROM job"))).scalars().all()
        assert list(rows) == [ids_b["job"]]


async def test_candidate_isolation(app_role_session, db_session, two_tenants):
    a, _, b, _ = two_tenants
    ids_a = await _seed_domain(db_session, a.id)
    ids_b = await _seed_domain(db_session, b.id)

    async with _with_tenant_ctx(app_role_session, a.id):
        rows = (await app_role_session.execute(text("SELECT id FROM candidate"))).scalars().all()
        assert list(rows) == [ids_a["candidate"]]

    async with _with_tenant_ctx(app_role_session, b.id):
        rows = (await app_role_session.execute(text("SELECT id FROM candidate"))).scalars().all()
        assert list(rows) == [ids_b["candidate"]]


async def test_application_isolation(app_role_session, db_session, two_tenants):
    a, _, b, _ = two_tenants
    ids_a = await _seed_domain(db_session, a.id)
    ids_b = await _seed_domain(db_session, b.id)

    async with _with_tenant_ctx(app_role_session, a.id):
        rows = (
            await app_role_session.execute(text("SELECT id FROM application"))
        ).scalars().all()
        assert list(rows) == [ids_a["application"]]

    async with _with_tenant_ctx(app_role_session, b.id):
        rows = (
            await app_role_session.execute(text("SELECT id FROM application"))
        ).scalars().all()
        assert list(rows) == [ids_b["application"]]


async def test_activity_isolation(app_role_session, db_session, two_tenants):
    a, _, b, _ = two_tenants
    ids_a = await _seed_domain(db_session, a.id)
    ids_b = await _seed_domain(db_session, b.id)

    async with _with_tenant_ctx(app_role_session, a.id):
        rows = (await app_role_session.execute(text("SELECT id FROM activity"))).scalars().all()
        assert list(rows) == [ids_a["activity"]]

    async with _with_tenant_ctx(app_role_session, b.id):
        rows = (await app_role_session.execute(text("SELECT id FROM activity"))).scalars().all()
        assert list(rows) == [ids_b["activity"]]


async def test_stage_isolation_via_tenant(app_role_session, db_session, two_tenants):
    """Stage carrega tenant_id direto (defesa em profundidade) — RLS aplica."""
    a, _, b, _ = two_tenants
    ids_a = await _seed_domain(db_session, a.id)
    ids_b = await _seed_domain(db_session, b.id)

    async with _with_tenant_ctx(app_role_session, a.id):
        rows = (await app_role_session.execute(text("SELECT id FROM stage"))).scalars().all()
        assert list(rows) == [ids_a["stage"]]

    async with _with_tenant_ctx(app_role_session, b.id):
        rows = (await app_role_session.execute(text("SELECT id FROM stage"))).scalars().all()
        assert list(rows) == [ids_b["stage"]]


async def test_insert_application_wrong_tenant_blocked(
    app_role_session, db_session, two_tenants
):
    """Tentar inserir app com tenant_id ≠ session tenant é bloqueado pela policy WITH CHECK."""
    a, _, b, _ = two_tenants
    ids_a = await _seed_domain(db_session, a.id)  # cria recursos no tenant A

    with pytest.raises(ProgrammingError) as exc_info:
        async with _with_tenant_ctx(app_role_session, a.id):
            await app_role_session.execute(
                text(
                    "INSERT INTO application "
                    "(id, tenant_id, job_id, candidate_id, current_stage_id, status, created_at, updated_at) "
                    "VALUES (:id, :tid, :jid, :cid, :sid, 'active', now(), now())"
                ),
                {
                    "id": uuid4(),
                    "tid": b.id,  # tenant errado
                    "jid": ids_a["job"],
                    "cid": ids_a["candidate"],
                    "sid": ids_a["stage"],
                },
            )
    assert "row-level security policy" in str(exc_info.value).lower()


async def test_uphiring_app_role_does_not_bypass_rls(
    app_role_session, db_session, two_tenants
):
    """Sem SET LOCAL, role uphiring_app vê 0 linhas — RLS impede mesmo o owner."""
    a, _, _, _ = two_tenants
    await _seed_domain(db_session, a.id)

    async with _with_tenant_ctx(app_role_session, None):
        for table in ("job", "stage", "candidate", "application", "activity"):
            rows = (await app_role_session.execute(text(f"SELECT id FROM {table}"))).all()
            assert rows == [], f"vazamento RLS em {table}"
