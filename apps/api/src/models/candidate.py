"""Candidate."""
from uuid import UUID

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base, TenantScopedMixin, TimestampMixin, new_uuid


class Candidate(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "candidate"
    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_candidate_tenant_email"),
        UniqueConstraint("tenant_id", "cpf", name="uq_candidate_tenant_cpf"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=new_uuid)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(String(32))
    cpf: Mapped[str | None] = mapped_column(String(14), index=True)
    linkedin_url: Mapped[str | None] = mapped_column(String(512))
    resume_s3_key: Mapped[str | None] = mapped_column(String(512))
    source: Mapped[str | None] = mapped_column(String(64))
