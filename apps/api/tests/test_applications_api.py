"""Cobertura formal /api/v1/applications — stage move, terminal, duplicação."""
from __future__ import annotations

import httpx
import pytest_asyncio

from src.main import app


@pytest_asyncio.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _create_job_and_candidate(client, token):
    r = await client.post(
        "/api/v1/jobs",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Pedreiro"},
    )
    assert r.status_code == 201, r.text
    job = r.json()
    r = await client.post(
        "/api/v1/candidates",
        headers={"Authorization": f"Bearer {token}"},
        json={"full_name": "Ana", "email": "ana@x.com"},
    )
    assert r.status_code == 201, r.text
    candidate = r.json()
    return job, candidate


async def test_create_application_lands_on_sourced(
    client, two_tenants, clerk_token_for, db_session
):
    token = clerk_token_for("user_a", org_id="org_a")
    job, candidate = await _create_job_and_candidate(client, token)

    r = await client.post(
        "/api/v1/applications",
        headers={"Authorization": f"Bearer {token}"},
        json={"job_id": job["id"], "candidate_id": candidate["id"]},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    # Primeiro stage active é "Sourced".
    sourced_id = next(s["id"] for s in job["stages"] if s["name"] == "Sourced")
    assert body["current_stage_id"] == sourced_id
    assert body["status"] == "active"


async def test_move_to_terminal_hired_sets_status(
    client, two_tenants, clerk_token_for
):
    token = clerk_token_for("user_a", org_id="org_a")
    job, candidate = await _create_job_and_candidate(client, token)

    r = await client.post(
        "/api/v1/applications",
        headers={"Authorization": f"Bearer {token}"},
        json={"job_id": job["id"], "candidate_id": candidate["id"]},
    )
    application_id = r.json()["id"]
    hired_id = next(s["id"] for s in job["stages"] if s["name"] == "Hired")

    r = await client.patch(
        f"/api/v1/applications/{application_id}/stage",
        headers={"Authorization": f"Bearer {token}"},
        json={"target_stage_id": hired_id},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["current_stage_id"] == hired_id
    assert body["status"] == "hired"


async def test_move_stage_logs_activity(
    client, two_tenants, clerk_token_for, db_session
):
    """PATCH stage grava activity application.stage_changed na mesma tx."""
    from sqlalchemy import select

    from src.models.activity import Activity

    token = clerk_token_for("user_a", org_id="org_a")
    job, candidate = await _create_job_and_candidate(client, token)

    r = await client.post(
        "/api/v1/applications",
        headers={"Authorization": f"Bearer {token}"},
        json={"job_id": job["id"], "candidate_id": candidate["id"]},
    )
    application_id = r.json()["id"]
    applied_id = next(s["id"] for s in job["stages"] if s["name"] == "Applied")

    r = await client.patch(
        f"/api/v1/applications/{application_id}/stage",
        headers={"Authorization": f"Bearer {token}"},
        json={"target_stage_id": applied_id},
    )
    assert r.status_code == 200, r.text

    activities = (
        await db_session.execute(
            select(Activity).where(
                Activity.entity_id == r.json()["id"],
                Activity.action == "application.stage_changed",
            )
        )
    ).scalars().all()
    assert len(activities) == 1
    payload = activities[0].payload
    assert payload["from_stage_name"] == "Sourced"
    assert payload["to_stage_name"] == "Applied"


async def test_move_to_stage_of_other_job_422(client, two_tenants, clerk_token_for):
    token = clerk_token_for("user_a", org_id="org_a")
    job, candidate = await _create_job_and_candidate(client, token)
    # Outro job no MESMO tenant.
    r = await client.post(
        "/api/v1/jobs",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Outro Job"},
    )
    other_job = r.json()

    r = await client.post(
        "/api/v1/applications",
        headers={"Authorization": f"Bearer {token}"},
        json={"job_id": job["id"], "candidate_id": candidate["id"]},
    )
    app_id = r.json()["id"]
    foreign_stage_id = other_job["stages"][0]["id"]

    r = await client.patch(
        f"/api/v1/applications/{app_id}/stage",
        headers={"Authorization": f"Bearer {token}"},
        json={"target_stage_id": foreign_stage_id},
    )
    assert r.status_code == 422
    detail = r.json()["detail"]
    code = detail["code"] if isinstance(detail, dict) else detail
    assert code == "stage_not_in_job"


async def test_list_applications_filter_by_job(client, two_tenants, clerk_token_for):
    token = clerk_token_for("user_a", org_id="org_a")
    job1, cand1 = await _create_job_and_candidate(client, token)
    r = await client.post(
        "/api/v1/jobs",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Outro Job"},
    )
    job2 = r.json()
    r = await client.post(
        "/api/v1/candidates",
        headers={"Authorization": f"Bearer {token}"},
        json={"full_name": "Outro", "email": "outro@x.com"},
    )
    cand2 = r.json()
    await client.post(
        "/api/v1/applications",
        headers={"Authorization": f"Bearer {token}"},
        json={"job_id": job1["id"], "candidate_id": cand1["id"]},
    )
    await client.post(
        "/api/v1/applications",
        headers={"Authorization": f"Bearer {token}"},
        json={"job_id": job2["id"], "candidate_id": cand2["id"]},
    )

    r = await client.get(
        f"/api/v1/applications?job_id={job1['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["job_id"] == job1["id"]


async def test_get_application_returns_stage_history(
    client, two_tenants, clerk_token_for
):
    token = clerk_token_for("user_a", org_id="org_a")
    job, candidate = await _create_job_and_candidate(client, token)
    r = await client.post(
        "/api/v1/applications",
        headers={"Authorization": f"Bearer {token}"},
        json={"job_id": job["id"], "candidate_id": candidate["id"]},
    )
    app_id = r.json()["id"]
    applied_id = next(s["id"] for s in job["stages"] if s["name"] == "Applied")
    await client.patch(
        f"/api/v1/applications/{app_id}/stage",
        headers={"Authorization": f"Bearer {token}"},
        json={"target_stage_id": applied_id},
    )

    r = await client.get(
        f"/api/v1/applications/{app_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    history = r.json()["stage_history"]
    assert len(history) == 1
    assert history[0]["action"] == "application.stage_changed"


async def test_duplicate_application_409(client, two_tenants, clerk_token_for):
    token = clerk_token_for("user_a", org_id="org_a")
    job, candidate = await _create_job_and_candidate(client, token)

    r1 = await client.post(
        "/api/v1/applications",
        headers={"Authorization": f"Bearer {token}"},
        json={"job_id": job["id"], "candidate_id": candidate["id"]},
    )
    assert r1.status_code == 201
    r2 = await client.post(
        "/api/v1/applications",
        headers={"Authorization": f"Bearer {token}"},
        json={"job_id": job["id"], "candidate_id": candidate["id"]},
    )
    assert r2.status_code == 409
    detail = r2.json()["detail"]
    assert detail["code"] == "duplicate_application"
    assert detail["existing_id"] == r1.json()["id"]
