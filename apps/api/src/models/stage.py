"""Stage — pipeline column de um Job."""
from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base, TenantScopedMixin, new_uuid
from src.models.enums import STAGE_KIND_ENUM_NAME, StageKind


class Stage(Base, TenantScopedMixin):
    __tablename__ = "stage"
    __table_args__ = (UniqueConstraint("job_id", "position", name="uq_stage_job_position"),)

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=new_uuid)
    job_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("job.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[StageKind] = mapped_column(
        SAEnum(StageKind, name=STAGE_KIND_ENUM_NAME, native_enum=True),
        nullable=False,
        default=StageKind.ACTIVE,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
