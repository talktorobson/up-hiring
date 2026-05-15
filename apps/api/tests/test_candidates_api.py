"""Cobertura formal /api/v1/candidates — CPF, dedup, email, busca."""
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


async def test_duplicate_cpf_different_tenant_ok(
    client, two_tenants, clerk_token_for
):
    """Mesmo CPF em tenants diferentes deve ser permitido (RLS isola)."""
    token_a = clerk_token_for("user_a", org_id="org_a")
    token_b = clerk_token_for("user_b", org_id="org_b")

    r1 = await client.post(
        "/api/v1/candidates",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"full_name": "Ana A", "email": "ana@a.com", "cpf": "11144477735"},
    )
    assert r1.status_code == 201

    r2 = await client.post(
        "/api/v1/candidates",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"full_name": "Ana B", "email": "ana@b.com", "cpf": "11144477735"},
    )
    assert r2.status_code == 201, r2.text


async def test_duplicate_email_returns_409(client, two_tenants, clerk_token_for):
    token = clerk_token_for("user_a", org_id="org_a")
    r1 = await client.post(
        "/api/v1/candidates",
        headers={"Authorization": f"Bearer {token}"},
        json={"full_name": "Primeiro", "email": "dup@x.com"},
    )
    existing_id = r1.json()["id"]

    # case-insensitive: DUP@X.COM colide com dup@x.com
    r2 = await client.post(
        "/api/v1/candidates",
        headers={"Authorization": f"Bearer {token}"},
        json={"full_name": "Segundo", "email": "DUP@X.COM"},
    )
    assert r2.status_code == 409
    detail = r2.json()["detail"]
    assert detail["code"] == "duplicate_email"
    assert detail["existing_id"] == existing_id


async def test_get_candidate_other_tenant_404(client, two_tenants, clerk_token_for):
    token_a = clerk_token_for("user_a", org_id="org_a")
    token_b = clerk_token_for("user_b", org_id="org_b")
    r = await client.post(
        "/api/v1/candidates",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"full_name": "Ana", "email": "ana@a.com"},
    )
    cid = r.json()["id"]
    r = await client.get(
        f"/api/v1/candidates/{cid}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert r.status_code == 404


async def test_patch_candidate_updates_email(client, two_tenants, clerk_token_for):
    token = clerk_token_for("user_a", org_id="org_a")
    r = await client.post(
        "/api/v1/candidates",
        headers={"Authorization": f"Bearer {token}"},
        json={"full_name": "Ana", "email": "ana@x.com"},
    )
    cid = r.json()["id"]

    r = await client.patch(
        f"/api/v1/candidates/{cid}",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": "nova@x.com"},
    )
    assert r.status_code == 200
    assert r.json()["email"] == "nova@x.com"


async def test_delete_candidate_soft(client, two_tenants, clerk_token_for):
    token = clerk_token_for("user_a", org_id="org_a")
    r = await client.post(
        "/api/v1/candidates",
        headers={"Authorization": f"Bearer {token}"},
        json={"full_name": "Ana", "email": "ana@x.com"},
    )
    cid = r.json()["id"]

    r = await client.delete(
        f"/api/v1/candidates/{cid}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 204

    r = await client.get(
        f"/api/v1/candidates/{cid}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 404


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
