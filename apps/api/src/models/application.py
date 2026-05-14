"""Application: liga Candidate a Job em um Stage."""
from enum import StrEnum
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base, TenantScopedMixin, TimestampMixin, new_uuid


class ApplicationStatus(StrEnum):
    ACTIVE = "active"
    HIRED = "hired"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class Application(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "application"
    __table_args__ = (
        UniqueConstraint("tenant_id", "job_id", "candidate_id", name="uq_app_tenant_job_candidate"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=new_uuid)
    job_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("job.id"), nullable=False, index=True
    )
    candidate_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("candidate.id"), nullable=False, index=True
    )
    current_stage_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("stage.id"), nullable=False
    )
    status: Mapped[ApplicationStatus] = mapped_column(
        String(32), nullable=False, default=ApplicationStatus.ACTIVE
    )
    rating: Mapped[int | None] = mapped_column(Integer)  # 1 a 5
