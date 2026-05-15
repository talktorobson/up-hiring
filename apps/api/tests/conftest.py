"""Fixtures globais.

Pipeline de setup:
  1. Antes de qualquer import de `src.*`: setamos `DATABASE_URL` apontando
     para `uphiring_test`. Pydantic Settings lê do env, então tudo que
     instancia `settings` em seguida vê o DB de teste.
  2. `pytest_configure`: cria o DB `uphiring_test`, roda `alembic upgrade
     head` via subprocess (env limpo). Subprocess porque a Settings cache
     é módulo-level — mais simples re-rodar tudo do zero.
  3. `pytest_unconfigure`: dropa o DB.

Fixtures fornecidas:
  - `db_engine` (session): engine async ligada ao test DB.
  - `db_session` (function): sessão admin (`ats` superuser, BYPASS RLS),
    commit explícito; cleanup TRUNCATE entre testes.
  - `app_role_session` (function): conexão com `SET LOCAL ROLE
    uphiring_app` — RLS ativo, sem bypass.
  - `two_tenants` (function): cria 2 tenants + 1 user em cada + memberships.
  - `rsa_keypair` (session) + `jwks_mock` (autouse): par de chaves RS256
    para forjar tokens; substitui o JWKSClient global.
  - `clerk_token_for(user_id, org_id, ...)` helper que devolve JWT assinado.
"""
from __future__ import annotations

import base64
import os
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable

# 1) Set test DB URL ANTES de qualquer import de src.*. A ordem importa porque
# `src.config.Settings` é instanciado uma vez e cacheado via lru_cache.
TEST_DB_NAME = "uphiring_test"
ADMIN_DB_URL = os.environ.get(
    "TEST_ADMIN_DB_URL", "postgresql://ats:ats@localhost:5432/postgres"
)
TEST_DB_URL_ASYNC = f"postgresql+asyncpg://ats:ats@localhost:5432/{TEST_DB_NAME}"
TEST_DB_URL_SYNC = f"postgresql://ats:ats@localhost:5432/{TEST_DB_NAME}"

os.environ["DATABASE_URL"] = TEST_DB_URL_ASYNC
os.environ["DATABASE_URL_SYNC"] = TEST_DB_URL_SYNC
os.environ.setdefault(
    "CLERK_WEBHOOK_SECRET", "whsec_test_dGVzdC13ZWJob29rLXNlY3JldC1mb3ItcHl0ZXN0cw=="
)
os.environ.setdefault("CLERK_AUDIENCE", "")  # validation off
os.environ.setdefault("APP_ENV", "test")

from datetime import UTC  # noqa: E402

import psycopg2  # noqa: E402
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import rsa  # noqa: E402
from jose import jwt  # noqa: E402
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.middleware import jwks as jwks_module  # noqa: E402
from src.models.tenant import AppUser, Role, Tenant  # noqa: E402
from src.services import tenant as tenant_service  # noqa: E402
from tests.factories import make_membership, make_tenant, make_user  # noqa: E402

API_DIR = Path(__file__).resolve().parent.parent
TEST_KID = "test-rsa-kid"


# ---------------------------------------------------------------------------
# DB lifecycle (sync, sessionscoped via pytest hooks)
# ---------------------------------------------------------------------------


def _run_admin_sql(*statements: str) -> None:
    """psycopg2's `with conn` opens a txn — DROP/CREATE DATABASE forbid that.
    Use connection without context manager + autocommit + manual close.
    """
    conn = psycopg2.connect(ADMIN_DB_URL)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    try:
        cur = conn.cursor()
        for stmt in statements:
            cur.execute(stmt)
        cur.close()
    finally:
        conn.close()


def _create_test_db() -> None:
    # `WITH (FORCE)` (PG 13+) encerra conexões + dropa atomicamente — sem isso
    # ficamos numa corrida onde pg_terminate_backend retorna antes do backend
    # de fato fechar e o DROP segue erranndo "ObjectInUse".
    _run_admin_sql(
        f"DROP DATABASE IF EXISTS {TEST_DB_NAME} WITH (FORCE)",
        f"CREATE DATABASE {TEST_DB_NAME}",
    )


def _drop_test_db() -> None:
    _run_admin_sql(f"DROP DATABASE IF EXISTS {TEST_DB_NAME} WITH (FORCE)")


def _migrate_test_db() -> None:
    env = os.environ.copy()
    env["DATABASE_URL"] = TEST_DB_URL_ASYNC
    env["DATABASE_URL_SYNC"] = TEST_DB_URL_SYNC
    subprocess.run(
        ["uv", "run", "alembic", "upgrade", "head"],
        cwd=API_DIR,
        env=env,
        check=True,
        capture_output=True,
    )


def pytest_configure(config) -> None:  # noqa: ARG001
    if os.environ.get("PYTEST_DISABLE_DB_SETUP") == "1":
        return
    _create_test_db()
    try:
        _migrate_test_db()
    except subprocess.CalledProcessError as exc:
        sys.stderr.write(exc.stdout.decode() if exc.stdout else "")
        sys.stderr.write(exc.stderr.decode() if exc.stderr else "")
        raise


def pytest_unconfigure(config) -> None:  # noqa: ARG001
    if os.environ.get("PYTEST_DISABLE_DB_SETUP") == "1":
        return
    _drop_test_db()


# ---------------------------------------------------------------------------
# Async engine + sessions
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db_engine():
    """Function-scoped: pytest-asyncio cria event loop por teste; engine
    cross-loop quebra. Custo é pequeno (engine async é leve)."""
    engine = create_async_engine(TEST_DB_URL_ASYNC, pool_pre_ping=True)
    try:
        yield engine
    finally:
        await engine.dispose()


async def _truncate_all(engine) -> None:
    # DELETE em vez de TRUNCATE: TRUNCATE precisa de ACCESS EXCLUSIVE lock e
    # qualquer conexão idle-in-transaction de fixtures anteriores trava o
    # cleanup. DELETE usa locks linha-a-linha — não há deadlock se as outras
    # conns estão idle.
    async with engine.begin() as conn:
        await conn.execute(text("SET LOCAL lock_timeout = '5s'"))
        await conn.execute(text("DELETE FROM membership"))
        await conn.execute(text("DELETE FROM app_user"))
        await conn.execute(text("DELETE FROM tenant"))


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Session admin (BYPASS RLS), commit visível pra outras conexões."""
    session_local = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_local() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
    await _truncate_all(db_engine)


@pytest_asyncio.fixture
async def app_role_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Sessão como `uphiring_app` — RLS efetivo, sem BYPASSRLS."""
    async with db_engine.connect() as conn:
        await conn.execute(text("SET ROLE uphiring_app"))
        session_local = async_sessionmaker(
            bind=conn, class_=AsyncSession, expire_on_commit=False
        )
        async with session_local() as session:
            try:
                yield session
            finally:
                await session.rollback()
        await conn.execute(text("RESET ROLE"))


# ---------------------------------------------------------------------------
# Two tenants (commits via db_session pra ficar visível em outras conexões)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def two_tenants(db_session) -> tuple[Tenant, AppUser, Tenant, AppUser]:
    a = await make_tenant(
        db_session, clerk_org_id="org_a", name="Tenant A", slug="tenant-a"
    )
    ua = await make_user(db_session, clerk_user_id="user_a", email="a@example.com")
    await make_membership(db_session, user_id=ua.id, tenant_id=a.id, role=Role.ADMIN)

    b = await make_tenant(
        db_session, clerk_org_id="org_b", name="Tenant B", slug="tenant-b"
    )
    ub = await make_user(db_session, clerk_user_id="user_b", email="b@example.com")
    await make_membership(db_session, user_id=ub.id, tenant_id=b.id, role=Role.ADMIN)

    await db_session.commit()
    return (a, ua, b, ub)


# ---------------------------------------------------------------------------
# RSA keypair + JWKSClient mock + token forge
# ---------------------------------------------------------------------------


def _b64url_uint(n: int) -> str:
    raw = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


@pytest.fixture(scope="session")
def rsa_keypair() -> dict[str, object]:
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = private.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_numbers = private.public_key().public_numbers()
    jwk = {
        "kty": "RSA",
        "kid": TEST_KID,
        "use": "sig",
        "alg": "RS256",
        "n": _b64url_uint(public_numbers.n),
        "e": _b64url_uint(public_numbers.e),
    }
    return {"private_pem": pem, "jwk": jwk, "kid": TEST_KID}


class _StubJWKSClient:
    def __init__(self, jwk: dict) -> None:
        self.jwk = jwk
        self.call_count = 0

    async def get_key(self, kid: str) -> dict:
        self.call_count += 1
        if kid == self.jwk["kid"]:
            return self.jwk
        raise KeyError(f"unknown kid {kid}")


@pytest.fixture(autouse=True)
def jwks_mock(rsa_keypair):
    stub = _StubJWKSClient(rsa_keypair["jwk"])
    jwks_module.set_jwks_client(stub)
    yield stub
    jwks_module.set_jwks_client(None)


@pytest.fixture
def svix_signed_request() -> Callable[..., dict]:
    """Forja headers svix-* assinando o body com `CLERK_WEBHOOK_SECRET`."""
    import json
    from datetime import datetime
    from uuid import uuid4

    from svix.webhooks import Webhook

    secret = os.environ["CLERK_WEBHOOK_SECRET"]

    def _make(payload: dict, *, msg_id: str | None = None, override_sig: str | None = None):
        body_str = json.dumps(payload)
        body = body_str.encode()
        msg_id = msg_id or f"msg_{uuid4().hex[:16]}"
        # Floor pra int e reconverte pra datetime — sem isso `sign` arredonda
        # internamente e `verify` (que lê o int do header) não bate.
        ts_int = int(datetime.now(UTC).timestamp())
        ts = datetime.fromtimestamp(ts_int, tz=UTC)
        # svix.sign quer str; verify aceita bytes ou str.
        signature = override_sig or Webhook(secret).sign(msg_id, ts, body_str)
        return {
            "body": body,
            "headers": {
                "svix-id": msg_id,
                "svix-timestamp": str(ts_int),
                "svix-signature": signature,
                "Content-Type": "application/json",
            },
        }

    return _make


@pytest.fixture
def clerk_token_for(rsa_keypair) -> Callable[..., str]:
    """Forja JWT assinado pela chave de teste; aceita kwargs como overrides do payload."""
    pem = rsa_keypair["private_pem"]

    def _make(
        user_id: str = "user_a",
        org_id: str | None = "org_a",
        *,
        ttl_seconds: int = 600,
        extra_claims: dict | None = None,
        kid: str = TEST_KID,
        algorithm: str = "RS256",
    ) -> str:
        import time

        now = int(time.time())
        claims = {
            "sub": user_id,
            "iat": now,
            "exp": now + ttl_seconds,
        }
        if org_id is not None:
            claims["org_id"] = org_id
        if extra_claims:
            claims.update(extra_claims)
        return jwt.encode(claims, pem, algorithm=algorithm, headers={"kid": kid})

    return _make


# ---------------------------------------------------------------------------
# Misc reset entre testes
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(autouse=True)
async def reset_tenant_redis_singleton():
    """Limpa o cache de tenant entre testes (best-effort) e força nova
    conexão. Se o Redis não está disponível (CI sem o serviço), o cache
    do `src.services.tenant` cai pro DB silenciosamente — testes que
    dependem da camada de cache devem skipar via `redis_available`.
    """
    import redis.asyncio as redis_async

    try:
        client = redis_async.from_url(
            os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
            socket_connect_timeout=0.5,
        )
        await client.flushdb()
        await client.aclose()
    except Exception:
        pass
    yield
    tenant_service.reset_redis()


@pytest.fixture(autouse=True)
def patch_db_session_module(db_engine, monkeypatch):
    """O engine de prod em `src.db.session` é criado no import e atrela conns
    a um event loop. Pytest-asyncio cria loop por teste — sem patch o
    middleware/handlers falam com pool stale ("attached to a different loop").

    Patcha em TODOS os módulos que fizeram `from src.db.session import
    AsyncSessionLocal` — refs diretas não pegam o patch só na origem.
    """
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr("src.db.session.engine", db_engine)
    monkeypatch.setattr("src.db.session.AsyncSessionLocal", factory)
    monkeypatch.setattr("src.middleware.clerk.AsyncSessionLocal", factory)
    monkeypatch.setattr("src.services.webhook_handlers.AsyncSessionLocal", factory)
