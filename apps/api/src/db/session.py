"""Sessão SQLAlchemy async com hook de RLS."""
from collections.abc import AsyncGenerator
from contextvars import ContextVar
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config import settings
from src.db.url import ensure_async_driver

current_tenant_id: ContextVar[UUID | None] = ContextVar("current_tenant_id", default=None)

engine = create_async_engine(
    ensure_async_driver(settings.database_url),
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
