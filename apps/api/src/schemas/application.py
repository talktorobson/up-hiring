"""Schemas de Application."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from src.models.enums import ApplicationStatus


class ApplicationCreate(BaseModel):
    job_id: UUID
    candidate_id: UUID


class ApplicationStageMove(BaseModel):
    target_stage_id: UUID


class ApplicationListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_id: UUID
    candidate_id: UUID
    current_stage_id: UUID
    status: ApplicationStatus
    created_at: datetime
    updated_at: datetime


class ApplicationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_id: UUID
    candidate_id: UUID
    current_stage_id: UUID
    status: ApplicationStatus
    created_at: datetime
    updated_at: datetime
    stage_history: list["ActivityRead"] = []


# Necessário em runtime — Pydantic precisa resolver o forward ref de
# `stage_history`. `model_rebuild()` substitui o str pelo tipo real.
from src.schemas.activity import ActivityRead  # noqa: E402, TC001

ApplicationRead.model_rebuild()
