"""Application: liga Candidate a Job em um Stage."""
from uuid import UUID

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base, TenantScopedMixin, TimestampMixin, new_uuid
from src.models.enums import APPLICATION_STATUS_ENUM_NAME, ApplicationStatus, enum_values


class Application(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "application"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "job_id", "candidate_id", name="uq_app_tenant_job_candidate"
        ),
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
        SAEnum(
            ApplicationStatus,
            name=APPLICATION_STATUS_ENUM_NAME,
            native_enum=True,
            values_callable=enum_values,
        ),
        nullable=False,
        default=ApplicationStatus.ACTIVE,
    )
