"""Testes do `ClerkAuthMiddleware`.

Cobre os caminhos críticos de auth + tenant lookup:
- token ausente / inválido / expirado / kid desconhecido
- assinatura RS256 verificada via JWKSClient stub
- claims populados em `request.state`
- org_id resolvido via DB → tenant_id no state
- org desconhecido → 403 tenant_not_provisioned

Endpoints públicos / 24-style retornam JSON 401 (não vazam 500) — coberto
por casos negativos abaixo.

Usamos `httpx.AsyncClient + ASGITransport` em vez de `TestClient` porque
TestClient roda o app num thread/loop separado via anyio portal, e o
engine do SQLAlchemy fica preso ao loop em que foi criado — isso quebra
qualquer teste que faça o middleware tocar o DB.
"""
import time

import httpx
import pytest_asyncio
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI, Request
from jose import jwt

from src.middleware.clerk import ClerkAuthMiddleware
from tests.factories import make_tenant


def _build_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(ClerkAuthMiddleware)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/v1/echo")
    def echo(request: Request) -> dict[str, object]:
        return {
            "user_id": getattr(request.state, "user_id", None),
            "org_id": getattr(request.state, "org_id", None),
            "tenant_id": (
                str(getattr(request.state, "tenant_id", None))
                if getattr(request.state, "tenant_id", None)
                else None
            ),
        }

    return app


@pytest_asyncio.fixture
async def client():
    app = _build_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_public_path_no_auth_required(client) -> None:
    r = await client.get("/health")
    assert r.status_code == 200


async def test_missing_token_401(client) -> None:
    r = await client.get("/api/v1/echo")
    assert r.status_code == 401
    assert r.json() == {"detail": "Missing Bearer token"}


async def test_invalid_signature_401(client, rsa_keypair) -> None:
    # Token assinado por chave que NÃO está no JWKS stub.
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    other_pem = other.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    forged = jwt.encode(
        {"sub": "user_x", "exp": int(time.time()) + 600},
        other_pem.decode(),
        algorithm="RS256",
        headers={"kid": rsa_keypair["kid"]},
    )
    r = await client.get("/api/v1/echo", headers={"Authorization": f"Bearer {forged}"})
    assert r.status_code == 401
    assert r.json() == {"detail": "Invalid token"}


async def test_expired_token_401(client, clerk_token_for) -> None:
    token = clerk_token_for("user_x", org_id=None, ttl_seconds=-60)
    r = await client.get("/api/v1/echo", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401
    assert r.json() == {"detail": "Token expired"}


async def test_unknown_kid_401(client, clerk_token_for) -> None:
    token = clerk_token_for("user_x", org_id=None, kid="other-kid")
    r = await client.get("/api/v1/echo", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401
    assert r.json() == {"detail": "Unknown signing key"}


async def test_valid_token_populates_state(client, clerk_token_for) -> None:
    token = clerk_token_for("user_abc", org_id=None)
    r = await client.get("/api/v1/echo", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.json()
    assert body["user_id"] == "user_abc"
    assert body["org_id"] is None
    assert body["tenant_id"] is None


async def test_org_id_resolves_tenant(client, db_session, clerk_token_for) -> None:
    tenant = await make_tenant(db_session, clerk_org_id="org_known")
    await db_session.commit()

    token = clerk_token_for("user_in_org", org_id="org_known")
    r = await client.get("/api/v1/echo", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.json()
    assert body["org_id"] == "org_known"
    assert body["tenant_id"] == str(tenant.id)


async def test_unknown_org_returns_403_tenant_not_provisioned(
    client, clerk_token_for
) -> None:
    token = clerk_token_for("user_x", org_id="org_does_not_exist")
    r = await client.get("/api/v1/echo", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403
    assert r.json() == {"detail": "tenant_not_provisioned"}
