"""Schemas do board view de Job (GET /jobs/{id}/pipeline)."""
from uuid import UUID

from pydantic import BaseModel

from src.schemas.application import ApplicationListItem


class PipelineStage(BaseModel):
    stage_id: UUID
    name: str
    position: int
    applications: list[ApplicationListItem]
    total_count: int


class PipelineRead(BaseModel):
    job_id: UUID
    stages: list[PipelineStage]
