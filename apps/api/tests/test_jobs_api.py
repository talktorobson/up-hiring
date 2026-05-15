"""Cobertura formal /api/v1/jobs — CRUD, paginação, isolamento, activity."""
from __future__ import annotations

import httpx
import pytest_asyncio
from sqlalchemy import select

from src.main import app
from src.models.activity import Activity


@pytest_asyncio.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_create_job_seeds_default_stages(
    client, db_session, two_tenants, clerk_token_for
):
    a, _, _, _ = two_tenants
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
    names = [s["name"] for s in body["stages"]]
    assert names == [
        "Sourced",
        "Applied",
        "Screening",
        "Interview",
        "Offer",
        "Hired",
        "Rejected",
    ]

    activities = (
        await db_session.execute(
            select(Activity).where(
                Activity.tenant_id == a.id, Activity.action == "job.created"
            )
        )
    ).scalars().all()
    assert len(activities) == 1
    assert activities[0].payload["title"] == "Engenheiro Civil"


async def test_list_jobs_pagination(client, two_tenants, clerk_token_for):
    """30 jobs paginados em páginas de 10 → 3 páginas sem duplicata."""
    token = clerk_token_for("user_a", org_id="org_a")
    for i in range(30):
        r = await client.post(
            "/api/v1/jobs",
            headers={"Authorization": f"Bearer {token}"},
            json={"title": f"Job {i:02d}"},
        )
        assert r.status_code == 201

    seen: list[str] = []
    cursor = None
    pages = 0
    while True:
        params = {"limit": "10"}
        if cursor is not None:
            params["cursor"] = cursor
        r = await client.get(
            "/api/v1/jobs",
            headers={"Authorization": f"Bearer {token}"},
            params=params,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        seen.extend(item["id"] for item in body["items"])
        pages += 1
        if not body["has_more"]:
            assert body["next_cursor"] is None
            break
        cursor = body["next_cursor"]
        assert pages < 10, "loop infinito"

    assert pages == 3
    assert len(seen) == 30
    assert len(set(seen)) == 30  # sem duplicata


async def test_list_jobs_isolates_tenants(
    client, two_tenants, clerk_token_for
):
    token_a = clerk_token_for("user_a", org_id="org_a")
    token_b = clerk_token_for("user_b", org_id="org_b")

    await client.post(
        "/api/v1/jobs",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"title": "Job A"},
    )
    await client.post(
        "/api/v1/jobs",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"title": "Job B"},
    )

    r = await client.get("/api/v1/jobs", headers={"Authorization": f"Bearer {token_a}"})
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["title"] == "Job A"


async def test_get_job_other_tenant_404(client, two_tenants, clerk_token_for):
    token_a = clerk_token_for("user_a", org_id="org_a")
    token_b = clerk_token_for("user_b", org_id="org_b")

    r = await client.post(
        "/api/v1/jobs",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"title": "Apenas A"},
    )
    job_a_id = r.json()["id"]

    r = await client.get(
        f"/api/v1/jobs/{job_a_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert r.status_code == 404


async def test_patch_job_updates_fields_and_logs_diff(
    client, db_session, two_tenants, clerk_token_for
):
    a, _, _, _ = two_tenants
    token = clerk_token_for("user_a", org_id="org_a")
    r = await client.post(
        "/api/v1/jobs",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Original"},
    )
    job_id = r.json()["id"]

    r = await client.patch(
        f"/api/v1/jobs/{job_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Atualizado", "location": "BH"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["title"] == "Atualizado"
    assert body["location"] == "BH"

    activities = (
        await db_session.execute(
            select(Activity).where(
                Activity.tenant_id == a.id, Activity.action == "job.updated"
            )
        )
    ).scalars().all()
    assert len(activities) == 1
    diff = activities[0].payload
    assert diff["title"] == {"from": "Original", "to": "Atualizado"}
    assert diff["location"] == {"from": None, "to": "BH"}


async def test_patch_job_404_when_not_exists(client, two_tenants, clerk_token_for):
    token = clerk_token_for("user_a", org_id="org_a")
    fake = "00000000-0000-0000-0000-000000000000"
    r = await client.patch(
        f"/api/v1/jobs/{fake}",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Algum Job"},
    )
    assert r.status_code == 404


async def test_list_jobs_filter_by_status(client, two_tenants, clerk_token_for):
    token = clerk_token_for("user_a", org_id="org_a")
    await client.post(
        "/api/v1/jobs",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Draft", "status": "draft"},
    )
    await client.post(
        "/api/v1/jobs",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Open", "status": "open"},
    )

    r = await client.get(
        "/api/v1/jobs?status=open",
        headers={"Authorization": f"Bearer {token}"},
    )
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["title"] == "Open"


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
