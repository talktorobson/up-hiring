"""Schemas de Job."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.models.enums import EmploymentType, JobStatus
from src.schemas.stage import StageRead


class JobCreate(BaseModel):
    title: str = Field(min_length=2, max_length=255)
    description: str | None = None
    location: str | None = None
    employment_type: EmploymentType = EmploymentType.CLT
    salary_min: int | None = Field(default=None, ge=0)
    salary_max: int | None = Field(default=None, ge=0)
    status: JobStatus = JobStatus.DRAFT


class JobUpdate(BaseModel):
    """Patch parcial — qualquer campo opcional."""

    title: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = None
    location: str | None = None
    employment_type: EmploymentType | None = None
    salary_min: int | None = Field(default=None, ge=0)
    salary_max: int | None = Field(default=None, ge=0)
    status: JobStatus | None = None


class JobListItem(BaseModel):
    """Versão enxuta para listagem — sem stages embutidos."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    status: JobStatus
    employment_type: EmploymentType
    location: str | None
    created_at: datetime
    updated_at: datetime


class JobRead(BaseModel):
    """Detalhe completo — inclui stages."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    description: str | None
    location: str | None
    employment_type: EmploymentType
    salary_min: int | None
    salary_max: int | None
    status: JobStatus
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime
    stages: list[StageRead] = Field(default_factory=list)
