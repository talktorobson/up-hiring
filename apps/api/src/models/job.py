"""Job."""
from uuid import UUID

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base, SoftDeleteMixin, TenantScopedMixin, TimestampMixin, new_uuid
from src.models.enums import (
    EMPLOYMENT_TYPE_ENUM_NAME,
    JOB_STATUS_ENUM_NAME,
    EmploymentType,
    JobStatus,
)


class Job(Base, TenantScopedMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "job"
    __table_args__ = (
        Index(
            "ix_job_tenant_status_created_at",
            "tenant_id",
            "status",
            "created_at",
            postgresql_using="btree",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=new_uuid)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(String(255))
    employment_type: Mapped[EmploymentType] = mapped_column(
        SAEnum(EmploymentType, name=EMPLOYMENT_TYPE_ENUM_NAME, native_enum=True),
        nullable=False,
        default=EmploymentType.CLT,
    )
    salary_min: Mapped[int | None] = mapped_column(Integer)
    salary_max: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[JobStatus] = mapped_column(
        SAEnum(JobStatus, name=JOB_STATUS_ENUM_NAME, native_enum=True),
        nullable=False,
        default=JobStatus.DRAFT,
    )
    created_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("app_user.id"), nullable=True
    )
