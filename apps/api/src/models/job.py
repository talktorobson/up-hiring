"""Job e Stage."""
from enum import StrEnum
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base, TenantScopedMixin, TimestampMixin, new_uuid


class JobStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    PAUSED = "paused"
    CLOSED = "closed"


class EmploymentType(StrEnum):
    CLT = "clt"
    PJ = "pj"
    INTERN = "intern"
    TEMP = "temp"
    FREELANCE = "freelance"


class StageType(StrEnum):
    SOURCED = "sourced"
    APPLIED = "applied"
    SCREENING = "screening"
    INTERVIEW = "interview"
    OFFER = "offer"
    HIRED = "hired"
    REJECTED = "rejected"


class Job(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "job"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=new_uuid)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[JobStatus] = mapped_column(String(32), nullable=False, default=JobStatus.DRAFT)
    location: Mapped[str | None] = mapped_column(String(255))
    remote: Mapped[bool] = mapped_column(default=False)
    employment_type: Mapped[EmploymentType] = mapped_column(
        String(32), nullable=False, default=EmploymentType.CLT
    )
    salary_min: Mapped[float | None] = mapped_column(Numeric(12, 2))
    salary_max: Mapped[float | None] = mapped_column(Numeric(12, 2))
    created_by: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("app_user.id"))


class Stage(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "stage"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=new_uuid)
    job_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("job.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    type: Mapped[StageType] = mapped_column(String(32), nullable=False)
