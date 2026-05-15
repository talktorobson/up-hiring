"""Smoke wire-check do /api/v1/candidates."""
from __future__ import annotations

import httpx
import pytest_asyncio

from src.main import app


@pytest_asyncio.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_create_candidate_valid_cpf(client, two_tenants, clerk_token_for):
    token = clerk_token_for("user_a", org_id="org_a")
    r = await client.post(
        "/api/v1/candidates",
        headers={"Authorization": f"Bearer {token}"},
        json={"full_name": "Ana Silva", "email": "ana@example.com", "cpf": "111.444.777-35"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["cpf"] == "11144477735"  # normalized


async def test_create_candidate_invalid_cpf(client, two_tenants, clerk_token_for):
    token = clerk_token_for("user_a", org_id="org_a")
    r = await client.post(
        "/api/v1/candidates",
        headers={"Authorization": f"Bearer {token}"},
        json={"full_name": "Ana", "email": "x@y.com", "cpf": "12345678900"},
    )
    assert r.status_code == 422
    assert r.json()["detail"] == "invalid_cpf"


async def test_duplicate_cpf_returns_409_with_existing_id(
    client, two_tenants, clerk_token_for
):
    token = clerk_token_for("user_a", org_id="org_a")
    r1 = await client.post(
        "/api/v1/candidates",
        headers={"Authorization": f"Bearer {token}"},
        json={"full_name": "Ana", "email": "ana@x.com", "cpf": "11144477735"},
    )
    existing_id = r1.json()["id"]

    r2 = await client.post(
        "/api/v1/candidates",
        headers={"Authorization": f"Bearer {token}"},
        json={"full_name": "Outro", "email": "outro@x.com", "cpf": "11144477735"},
    )
    assert r2.status_code == 409
    detail = r2.json()["detail"]
    assert detail["code"] == "duplicate_cpf"
    assert detail["existing_id"] == existing_id


async def test_search_by_name_ilike(client, two_tenants, clerk_token_for):
    token = clerk_token_for("user_a", org_id="org_a")
    for name in ("Ana Silva", "Beto Souza", "Carla Mendes"):
        r = await client.post(
            "/api/v1/candidates",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "full_name": name,
                "email": f"{name.replace(' ', '.').lower()}@x.com",
            },
        )
        assert r.status_code == 201

    r = await client.get(
        "/api/v1/candidates?q=souza", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["full_name"] == "Beto Souza"
