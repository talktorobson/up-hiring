"""Candidate."""
from uuid import UUID

from sqlalchemy import Index, String, Text, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base, SoftDeleteMixin, TenantScopedMixin, TimestampMixin, new_uuid


class Candidate(Base, TenantScopedMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "candidate"
    __table_args__ = (
        Index(
            "uq_candidate_tenant_cpf_alive",
            "tenant_id",
            "cpf",
            unique=True,
            postgresql_where=text("cpf IS NOT NULL AND deleted_at IS NULL"),
        ),
        Index(
            "uq_candidate_tenant_email_alive",
            "tenant_id",
            text("lower(email)"),
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=new_uuid)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32))
    cpf: Mapped[str | None] = mapped_column(String(11))
    linkedin_url: Mapped[str | None] = mapped_column(String(512))
    source: Mapped[str | None] = mapped_column(String(64))
    notes: Mapped[str | None] = mapped_column(Text)
