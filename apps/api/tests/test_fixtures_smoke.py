"""Smoke test pra garantir que as fixtures principais bootam.

Garante que `db_session`, `app_role_session`, `two_tenants` e o forge de JWT
funcionam end-to-end. Testes específicos vivem em `test_rls.py`,
`test_middleware_clerk.py`, `test_webhook_clerk.py` e `test_me_endpoint.py`.
"""
from sqlalchemy import text


async def test_db_session_can_query(db_session) -> None:
    result = await db_session.scalar(text("SELECT 1"))
    assert result == 1


async def test_app_role_session_uses_uphiring_app(app_role_session) -> None:
    current = await app_role_session.scalar(text("SELECT current_user"))
    assert current == "uphiring_app"


async def test_two_tenants_visible_to_admin(db_session, two_tenants) -> None:
    a, ua, b, ub = two_tenants
    count = await db_session.scalar(text("SELECT count(*) FROM tenant"))
    assert count == 2
    assert a.slug == "tenant-a"
    assert b.slug == "tenant-b"
    assert ua.clerk_user_id == "user_a"
    assert ub.clerk_user_id == "user_b"


def test_clerk_token_for_decodes_with_jwks_mock(clerk_token_for, jwks_mock) -> None:
    from jose import jwt

    token = clerk_token_for("user_x", org_id="org_x")
    header = jwt.get_unverified_header(token)
    assert header["kid"] == jwks_mock.jwk["kid"]
    claims = jwt.get_unverified_claims(token)
    assert claims["sub"] == "user_x"
    assert claims["org_id"] == "org_x"
    assert claims["exp"] > claims["iat"]
