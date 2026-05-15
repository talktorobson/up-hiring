"""Helpers for database URLs."""


def ensure_async_driver(url: str) -> str:
    """Rewrite ``postgres://`` or ``postgresql://`` to ``postgresql+asyncpg://``.

    SQLAlchemy resolves the bare scheme to psycopg2 (sync), which the asyncio
    extension refuses. Supabase and most managed Postgres providers hand out
    the bare form, so callers shouldn't have to remember the prefix.

    Explicit driver URLs (``postgresql+asyncpg``, ``postgresql+psycopg``) and
    non-postgres schemes pass through untouched.
    """
    if url.startswith("postgresql+"):
        return url
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url[len("postgresql://"):]
    if url.startswith("postgres://"):
        return "postgresql+asyncpg://" + url[len("postgres://"):]
    return url
