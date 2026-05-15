"""CandidateService — CRUD com validação de CPF e dedup tenant-scoped.

Erros levantam exceções específicas que `src/api/v1/candidates.py` traduz
em HTTP 4xx adequado.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, select

from src.models.candidate import Candidate
from src.utils.cpf import is_valid as cpf_is_valid
from src.utils.cpf import normalize as normalize_cpf

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

    from src.schemas.candidate import CandidateCreate, CandidateUpdate


class InvalidCPFError(ValueError):
    pass


class DuplicateCandidateError(ValueError):
    def __init__(self, field: str, existing_id: UUID) -> None:
        super().__init__(f"duplicate_{field}: {existing_id}")
        self.field = field
        self.existing_id = existing_id


class CandidateService:
    @staticmethod
    async def _check_cpf(session: AsyncSession, tenant_id: UUID, cpf: str | None) -> str | None:
        """Normaliza, valida algoritmo, busca duplicado vivo. Retorna o CPF cru ou None."""
        if cpf is None:
            return None
        norm = normalize_cpf(cpf)
        if norm is None:
            return None
        if not cpf_is_valid(norm):
            raise InvalidCPFError("invalid_cpf")
        existing = await session.scalar(
            select(Candidate.id).where(
                Candidate.tenant_id == tenant_id,
                Candidate.cpf == norm,
                Candidate.deleted_at.is_(None),
            )
        )
        if existing is not None:
            raise DuplicateCandidateError("cpf", existing)
        return norm

    @staticmethod
    async def _check_email(
        session: AsyncSession, tenant_id: UUID, email: str, *, exclude_id: UUID | None = None
    ) -> None:
        stmt = select(Candidate.id).where(
            Candidate.tenant_id == tenant_id,
            func.lower(Candidate.email) == email.lower(),
            Candidate.deleted_at.is_(None),
        )
        if exclude_id is not None:
            stmt = stmt.where(Candidate.id != exclude_id)
        existing = await session.scalar(stmt)
        if existing is not None:
            raise DuplicateCandidateError("email", existing)

    @staticmethod
    async def create(
        session: AsyncSession,
        payload: CandidateCreate,
        *,
        tenant_id: UUID,
    ) -> Candidate:
        cpf = await CandidateService._check_cpf(session, tenant_id, payload.cpf)
        await CandidateService._check_email(session, tenant_id, payload.email)
        candidate = Candidate(
            tenant_id=tenant_id,
            full_name=payload.full_name,
            email=payload.email,
            phone=payload.phone,
            cpf=cpf,
            linkedin_url=payload.linkedin_url,
            source=payload.source,
            notes=payload.notes,
        )
        session.add(candidate)
        await session.flush()
        return candidate

    @staticmethod
    async def update(
        session: AsyncSession,
        candidate: Candidate,
        payload: CandidateUpdate,
    ) -> Candidate:
        data = payload.model_dump(exclude_unset=True)
        if "cpf" in data:
            candidate.cpf = await CandidateService._check_cpf(
                session, candidate.tenant_id, data["cpf"]
            )
            data.pop("cpf")
        if "email" in data and data["email"] is not None:
            await CandidateService._check_email(
                session, candidate.tenant_id, data["email"], exclude_id=candidate.id
            )
        for key, value in data.items():
            setattr(candidate, key, value)
        await session.flush()
        return candidate
