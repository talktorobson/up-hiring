"""GET /api/v1/me — caminho feliz + erros mapeados."""
import httpx
import pytest_asyncio

from src.main import app
from src.models.tenant import Role
from tests.factories import make_membership, make_tenant, make_user


@pytest_asyncio.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_me_returns_user_tenant_role(client, db_session, clerk_token_for) -> None:
    tenant = await make_tenant(db_session, clerk_org_id="org_me", name="Empresa X")
    user = await make_user(
        db_session, clerk_user_id="user_me", email="me@example.com", full_name="Me Tester"
    )
    await make_membership(
        db_session, user_id=user.id, tenant_id=tenant.id, role=Role.ADMIN
    )
    await db_session.commit()

    token = clerk_token_for("user_me", org_id="org_me")
    r = await client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.json()
    assert body["user"]["clerk_user_id"] == "user_me"
    assert body["user"]["email"] == "me@example.com"
    assert body["tenant"]["clerk_org_id"] == "org_me"
    assert body["tenant"]["name"] == "Empresa X"
    assert body["role"] == "admin"


async def test_me_without_org_returns_400(client, clerk_token_for) -> None:
    token = clerk_token_for("user_me_no_org", org_id=None)
    r = await client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 400
    assert r.json() == {"detail": "org_required"}


async def test_me_without_membership_returns_403(
    client, db_session, clerk_token_for
) -> None:
    tenant = await make_tenant(db_session, clerk_org_id="org_no_member")
    # Criamos o user também — sem ele cairíamos no 404 user_not_provisioned.
    await make_user(db_session, clerk_user_id="user_loose", email="loose@example.com")
    await db_session.commit()

    token = clerk_token_for("user_loose", org_id="org_no_member")
    r = await client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403
    assert r.json() == {"detail": "not_member"}
    # tenant declarado pra evitar warning sobre var não usada (validação implícita
    # de que o tenant_id resolve corretamente)
    assert tenant.clerk_org_id == "org_no_member"
