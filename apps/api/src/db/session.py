"""Sessão SQLAlchemy async com hook de RLS."""
from collections.abc import AsyncGenerator
from contextvars import ContextVar
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config import settings

current_tenant_id: ContextVar[UUID | None] = ContextVar("current_tenant_id", default=None)


def _ensure_async_driver(url: str) -> str:
    """Force the asyncpg driver in the URL so create_async_engine works
    regardless of whether the secret was set as ``postgres://``,
    ``postgresql://`` or already ``postgresql+asyncpg://``. Supabase and most
    cloud providers hand out the bare form, which SQLAlchemy resolves to
    psycopg2 (sync) by default and then refuses to use with create_async_engine.
    """
    if url.startswith("postgresql+"):
        return url
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url[len("postgresql://"):]
    if url.startswith("postgres://"):
        return "postgresql+asyncpg://" + url[len("postgres://"):]
    return url


engine = create_async_engine(
    _ensure_async_driver(settings.database_url),
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield session com tenant_id setado via SET LOCAL para RLS funcionar."""
    async with AsyncSessionLocal() as session:
        tenant_id = current_tenant_id.get()
        if tenant_id is not None:
            await session.execute(
                text("SET LOCAL app.current_tenant_id = :tid"),
                {"tid": str(tenant_id)},
            )
        try:
            yield session
        finally:
            await session.close()


async def get_db_no_tenant() -> AsyncGenerator[AsyncSession, None]:
    """Para operações que não exigem tenant (ex: webhooks de admin). Use com cuidado."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
