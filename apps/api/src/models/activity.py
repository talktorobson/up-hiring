"""Activity log genérico (entity_type, entity_id, action, payload)."""
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base, TenantScopedMixin, new_uuid
from src.models.enums import ACTIVITY_ENTITY_TYPE_ENUM_NAME, ActivityEntityType


class Activity(Base, TenantScopedMixin):
    __tablename__ = "activity"
    __table_args__ = (
        Index(
            "ix_activity_tenant_entity_created",
            "tenant_id",
            "entity_type",
            "entity_id",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=new_uuid)
    entity_type: Mapped[ActivityEntityType] = mapped_column(
        SAEnum(
            ActivityEntityType,
            name=ACTIVITY_ENTITY_TYPE_ENUM_NAME,
            native_enum=True,
        ),
        nullable=False,
    )
    entity_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("app_user.id"), nullable=True
    )
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
