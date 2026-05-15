"""Schemas de Stage — só leitura no Sprint 3 (CRUD vai pra backlog Fase 1)."""
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from src.models.enums import StageKind


class StageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_id: UUID
    name: str
    position: int
    kind: StageKind
