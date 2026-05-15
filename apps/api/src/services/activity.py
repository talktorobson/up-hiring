"""ActivityService — log síncrono na mesma transação da ação."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.models.activity import Activity
from src.models.enums import ActivityEntityType  # noqa: TC001 — runtime annotation

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession


class ActivityService:
    @staticmethod
    async def log(
        session: AsyncSession,
        *,
        tenant_id: UUID,
        entity_type: ActivityEntityType,
        entity_id: UUID,
        action: str,
        actor_user_id: UUID | None,
        payload: dict[str, Any] | None = None,
    ) -> Activity:
        activity = Activity(
            tenant_id=tenant_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            actor_user_id=actor_user_id,
            payload=payload,
        )
        session.add(activity)
        await session.flush()
        return activity
