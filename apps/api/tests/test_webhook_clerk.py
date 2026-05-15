"""Webhook do Clerk: signature verify + dispatcher → handlers materializam DB."""
import httpx
import pytest_asyncio
from sqlalchemy import select

from src.main import app
from src.models.tenant import AppUser, Membership, Tenant


@pytest_asyncio.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _org_payload(*, org_id: str = "org_a", name: str = "Acabamentos LTDA") -> dict:
    return {
        "type": "organization.created",
        "data": {"id": org_id, "name": name, "slug": "acabamentos-ltda"},
    }


def _user_payload(*, user_id: str = "user_a") -> dict:
    return {
        "type": "user.created",
        "data": {
            "id": user_id,
            "email_addresses": [
                {"id": "ema_1", "email_address": "ana@example.com"}
            ],
            "primary_email_address_id": "ema_1",
            "first_name": "Ana",
            "last_name": "Silva",
        },
    }


def _membership_payload(
    *, org_id: str = "org_a", user_id: str = "user_a", role: str = "org:admin"
) -> dict:
    return {
        "type": "organizationMembership.created",
        "data": {
            "id": "orgmem_1",
            "organization": {"id": org_id, "name": "Acabamentos LTDA"},
            "public_user_data": {"user_id": user_id},
            "role": role,
        },
    }


async def test_bad_signature_401(client, svix_signed_request) -> None:
    import base64

    # Base64 válido mas valor errado — sem isso o middleware quebra dentro
    # do svix.verify (binascii.Error em vez de WebhookVerificationError).
    fake = "v1," + base64.b64encode(b"x" * 32).decode()
    req = svix_signed_request(_org_payload(), override_sig=fake)
    r = await client.post("/api/v1/webhooks/clerk", content=req["body"], headers=req["headers"])
    assert r.status_code == 401
    assert r.json() == {"detail": "invalid_signature"}


async def test_organization_created_inserts_tenant(
    client, svix_signed_request, db_session
) -> None:
    req = svix_signed_request(_org_payload(org_id="org_create_test"))
    r = await client.post("/api/v1/webhooks/clerk", content=req["body"], headers=req["headers"])
    assert r.status_code == 200
    assert r.json()["dispatched"] is True

    tenant = await db_session.scalar(
        select(Tenant).where(Tenant.clerk_org_id == "org_create_test")
    )
    assert tenant is not None
    assert tenant.name == "Acabamentos LTDA"


async def test_user_created_inserts_app_user(
    client, svix_signed_request, db_session
) -> None:
    req = svix_signed_request(_user_payload(user_id="user_create_test"))
    r = await client.post("/api/v1/webhooks/clerk", content=req["body"], headers=req["headers"])
    assert r.status_code == 200

    user = await db_session.scalar(
        select(AppUser).where(AppUser.clerk_user_id == "user_create_test")
    )
    assert user is not None
    assert user.email == "ana@example.com"
    assert user.full_name == "Ana Silva"


async def test_membership_created_inserts_membership(
    client, svix_signed_request, db_session
) -> None:
    # Pré-condição: tenant + user já existem (eventos prévios).
    org_req = svix_signed_request(_org_payload(org_id="org_for_member"))
    await client.post(
        "/api/v1/webhooks/clerk", content=org_req["body"], headers=org_req["headers"]
    )
    user_req = svix_signed_request(_user_payload(user_id="user_for_member"))
    await client.post(
        "/api/v1/webhooks/clerk", content=user_req["body"], headers=user_req["headers"]
    )

    mem_req = svix_signed_request(
        _membership_payload(org_id="org_for_member", user_id="user_for_member")
    )
    r = await client.post(
        "/api/v1/webhooks/clerk", content=mem_req["body"], headers=mem_req["headers"]
    )
    assert r.status_code == 200

    tenant = await db_session.scalar(
        select(Tenant).where(Tenant.clerk_org_id == "org_for_member")
    )
    user = await db_session.scalar(
        select(AppUser).where(AppUser.clerk_user_id == "user_for_member")
    )
    membership = await db_session.scalar(
        select(Membership).where(
            Membership.user_id == user.id, Membership.tenant_id == tenant.id
        )
    )
    assert membership is not None
    # role é coluna String — SQLAlchemy retorna str, não Role enum.
    assert membership.role == "admin"


async def test_idempotent_replay(client, svix_signed_request, db_session) -> None:
    # Mesmo payload 2x não duplica.
    req = svix_signed_request(_org_payload(org_id="org_idempotent"))
    for _ in range(2):
        r = await client.post(
            "/api/v1/webhooks/clerk", content=req["body"], headers=req["headers"]
        )
        # Svix rejeita timestamps repetidos como anti-replay; o que queremos
        # provar aqui é que o handler em si é idempotente. Re-assina cada vez.
        if r.status_code != 200:
            req = svix_signed_request(_org_payload(org_id="org_idempotent"))
            r = await client.post(
                "/api/v1/webhooks/clerk", content=req["body"], headers=req["headers"]
            )
        assert r.status_code == 200

    rows = (
        await db_session.execute(
            select(Tenant).where(Tenant.clerk_org_id == "org_idempotent")
        )
    ).all()
    assert len(rows) == 1
