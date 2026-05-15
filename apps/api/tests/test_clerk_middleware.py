"""Issue #24: ClerkAuthMiddleware must return JSON 401, not surface as 500.

Strict RS256 signature tests live in #40 — the cases here exercise the
non-cryptographic branches (missing/malformed token, missing claims) and
use the `clerk_skip_verify` debug flag so HS256 forged tokens reach the
claims-handling code without going through JWKS.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt

from src.config import settings
from src.middleware.clerk import ClerkAuthMiddleware


@pytest.fixture
def skip_verify(monkeypatch):
    monkeypatch.setattr(settings, "clerk_skip_verify", True)


def _client() -> TestClient:
    app = FastAPI()
    app.add_middleware(ClerkAuthMiddleware)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/v1/jobs")
    def jobs() -> dict[str, str]:
        return {"jobs": "would-be-listed"}

    return TestClient(app)


def test_public_path_no_auth_required() -> None:
    r = _client().get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_missing_bearer_returns_401_not_500() -> None:
    r = _client().get("/api/v1/jobs")
    assert r.status_code == 401
    assert r.json() == {"detail": "Missing Bearer token"}


def test_malformed_token_returns_401() -> None:
    r = _client().get("/api/v1/jobs", headers={"Authorization": "Bearer not-a-jwt"})
    assert r.status_code == 401
    assert r.json() == {"detail": "Invalid token"}


def test_token_without_sub_returns_401(skip_verify) -> None:
    token = jwt.encode({"foo": "bar"}, "irrelevant-secret", algorithm="HS256")
    r = _client().get("/api/v1/jobs", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401
    assert r.json() == {"detail": "Missing user"}


def test_valid_token_without_org_passes_through(skip_verify) -> None:
    # Sem org_id o middleware não tenta resolver tenant; apenas passa adiante.
    # O endpoint individual decide se exige org via request.state.tenant_id.
    token = jwt.encode({"sub": "user_abc"}, "secret", algorithm="HS256")
    r = _client().get("/api/v1/jobs", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json() == {"jobs": "would-be-listed"}
