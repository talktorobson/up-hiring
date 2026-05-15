"""Smoke wire-check do /api/v1/jobs.

Cobertura formal de CRUD/paginação/activity vem na #64.
"""
from __future__ import annotations

import httpx
import pytest_asyncio

from src.main import app
from src.models.tenant import Role
from tests.factories import make_membership


@pytest_asyncio.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_create_job_seeds_stages_and_logs_activity(
    client, db_session, two_tenants, clerk_token_for
):
    a, ua, _, _ = two_tenants
    # Sprint 2 fixture só cria membership ADMIN; ok pro endpoint.
    token = clerk_token_for("user_a", org_id="org_a")

    r = await client.post(
        "/api/v1/jobs",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Engenheiro Civil", "location": "São Paulo"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["title"] == "Engenheiro Civil"
    assert len(body["stages"]) == 7

    # Activity log inserida na mesma transação.
    from sqlalchemy import select

    from src.models.activity import Activity

    activities = (
        await db_session.execute(
            select(Activity).where(Activity.tenant_id == a.id, Activity.action == "job.created")
        )
    ).scalars().all()
    assert len(activities) == 1
    assert activities[0].payload["title"] == "Engenheiro Civil"


async def test_list_jobs_isolates_tenants(
    client, db_session, two_tenants, clerk_token_for
):
    a, _, b, ub = two_tenants
    # Acumular um membership no tenant B usa o fixture pra recuperar ua/ub.
    token_a = clerk_token_for("user_a", org_id="org_a")
    token_b = clerk_token_for("user_b", org_id="org_b")

    # Cria 1 job em cada tenant.
    r = await client.post(
        "/api/v1/jobs",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"title": "Job A"},
    )
    assert r.status_code == 201
    r = await client.post(
        "/api/v1/jobs",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"title": "Job B"},
    )
    assert r.status_code == 201

    # Tenant A só vê Job A.
    r = await client.get("/api/v1/jobs", headers={"Authorization": f"Bearer {token_a}"})
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["title"] == "Job A"


async def test_delete_job_soft(client, two_tenants, clerk_token_for):
    token = clerk_token_for("user_a", org_id="org_a")
    r = await client.post(
        "/api/v1/jobs",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Para deletar"},
    )
    job_id = r.json()["id"]

    r = await client.delete(
        f"/api/v1/jobs/{job_id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 204

    r = await client.get(
        f"/api/v1/jobs/{job_id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 404


# Suprime warning "unused" pra factories importada — usada em uma das fixtures derivadas.
_ = make_membership, Role
