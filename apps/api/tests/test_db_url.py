from src.db.url import ensure_async_driver as _ensure_async_driver


def test_bare_postgresql_gets_asyncpg() -> None:
    assert _ensure_async_driver(
        "postgresql://user:pwd@aws-1-sa-east-1.pooler.supabase.com:6543/postgres"
    ) == "postgresql+asyncpg://user:pwd@aws-1-sa-east-1.pooler.supabase.com:6543/postgres"


def test_postgres_short_form_gets_asyncpg() -> None:
    assert _ensure_async_driver(
        "postgres://user:pwd@host:5432/db"
    ) == "postgresql+asyncpg://user:pwd@host:5432/db"


def test_explicit_asyncpg_unchanged() -> None:
    url = "postgresql+asyncpg://user:pwd@host:5432/db"
    assert _ensure_async_driver(url) == url


def test_explicit_psycopg_unchanged() -> None:
    url = "postgresql+psycopg://user:pwd@host:5432/db"
    assert _ensure_async_driver(url) == url


def test_non_postgres_unchanged() -> None:
    url = "mysql://x"
    assert _ensure_async_driver(url) == url
