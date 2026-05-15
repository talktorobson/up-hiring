"""Smoke wire-check do /api/v1/jobs/{id}/pipeline."""
from __future__ import annotations

import httpx
import pytest_asyncio

from src.main import app


@pytest_asyncio.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_pipeline_returns_active_stages_only(client, two_tenants, clerk_token_for):
    token = clerk_token_for("user_a", org_id="org_a")
    r = await client.post(
        "/api/v1/jobs",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Pedreiro"},
    )
    job = r.json()

    r = await client.get(
        f"/api/v1/jobs/{job['id']}/pipeline",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["job_id"] == job["id"]
    # 5 stages active (Sourced, Applied, Screening, Interview, Offer);
    # Hired e Rejected ficam de fora.
    assert len(body["stages"]) == 5
    names = [s["name"] for s in body["stages"]]
    assert names == ["Sourced", "Applied", "Screening", "Interview", "Offer"]
    for stage in body["stages"]:
        assert stage["applications"] == []
        assert stage["total_count"] == 0


async def test_pipeline_404_for_other_tenant_job(
    client, two_tenants, clerk_token_for
):
    token_a = clerk_token_for("user_a", org_id="org_a")
    token_b = clerk_token_for("user_b", org_id="org_b")

    r = await client.post(
        "/api/v1/jobs",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"title": "Job A"},
    )
    job_a_id = r.json()["id"]

    # Tenant B tenta acessar pipeline do Job A
    r = await client.get(
        f"/api/v1/jobs/{job_a_id}/pipeline",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert r.status_code == 404


async def test_pipeline_populates_applications_and_counts(
    client, two_tenants, clerk_token_for
):
    token = clerk_token_for("user_a", org_id="org_a")
    r = await client.post(
        "/api/v1/jobs",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Eletricista"},
    )
    job = r.json()
    sourced_id = next(s["id"] for s in job["stages"] if s["name"] == "Sourced")

    # 3 candidatos + 3 applications no stage Sourced.
    candidate_ids = []
    for i in range(3):
        r = await client.post(
            "/api/v1/candidates",
            headers={"Authorization": f"Bearer {token}"},
            json={"full_name": f"Cand {i}", "email": f"c{i}@x.com"},
        )
        candidate_ids.append(r.json()["id"])

    for cid in candidate_ids:
        r = await client.post(
            "/api/v1/applications",
            headers={"Authorization": f"Bearer {token}"},
            json={"job_id": job["id"], "candidate_id": cid},
        )
        assert r.status_code == 201

    r = await client.get(
        f"/api/v1/jobs/{job['id']}/pipeline",
        headers={"Authorization": f"Bearer {token}"},
    )
    body = r.json()
    sourced = next(s for s in body["stages"] if s["stage_id"] == sourced_id)
    assert sourced["total_count"] == 3
    assert len(sourced["applications"]) == 3
