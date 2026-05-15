"""Schemas de Activity."""
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from src.models.enums import ActivityEntityType


class ActivityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    entity_type: ActivityEntityType
    entity_id: UUID
    action: str
    actor_user_id: UUID | None
    payload: dict[str, Any] | None
    created_at: datetime
