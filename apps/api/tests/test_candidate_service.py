"""CandidateService.create — CPF/email dedup tenant-scoped."""
from __future__ import annotations

import pytest

from src.schemas.candidate import CandidateCreate, CandidateUpdate
from src.services.candidate import (
    CandidateService,
    DuplicateCandidateError,
    InvalidCPFError,
)


@pytest.mark.asyncio
async def test_create_with_valid_cpf(db_session, two_tenants):
    a, _, _, _ = two_tenants
    c = await CandidateService.create(
        db_session,
        CandidateCreate(full_name="Ana Silva", email="ana@example.com", cpf="11144477735"),
        tenant_id=a.id,
    )
    await db_session.commit()
    assert c.cpf == "11144477735"
    assert c.tenant_id == a.id


@pytest.mark.asyncio
async def test_create_normalizes_formatted_cpf(db_session, two_tenants):
    a, _, _, _ = two_tenants
    c = await CandidateService.create(
        db_session,
        CandidateCreate(
            full_name="Bia", email="bia@example.com", cpf="111.444.777-35"
        ),
        tenant_id=a.id,
    )
    await db_session.commit()
    assert c.cpf == "11144477735"


@pytest.mark.asyncio
async def test_create_invalid_cpf_raises(db_session, two_tenants):
    a, _, _, _ = two_tenants
    with pytest.raises(InvalidCPFError):
        await CandidateService.create(
            db_session,
            CandidateCreate(
                full_name="Bad", email="bad@example.com", cpf="12345678900"
            ),
            tenant_id=a.id,
        )


@pytest.mark.asyncio
async def test_duplicate_cpf_same_tenant(db_session, two_tenants):
    a, _, _, _ = two_tenants
    first = await CandidateService.create(
        db_session,
        CandidateCreate(full_name="Ana", email="ana@x.com", cpf="11144477735"),
        tenant_id=a.id,
    )
    await db_session.commit()

    with pytest.raises(DuplicateCandidateError) as exc:
        await CandidateService.create(
            db_session,
            CandidateCreate(full_name="Outro", email="outro@x.com", cpf="11144477735"),
            tenant_id=a.id,
        )
    assert exc.value.field == "cpf"
    assert exc.value.existing_id == first.id


@pytest.mark.asyncio
async def test_duplicate_cpf_different_tenant_allowed(db_session, two_tenants):
    a, _, b, _ = two_tenants
    await CandidateService.create(
        db_session,
        CandidateCreate(full_name="Ana", email="ana@x.com", cpf="11144477735"),
        tenant_id=a.id,
    )
    await db_session.commit()

    # Mesmo CPF, outro tenant — OK.
    c2 = await CandidateService.create(
        db_session,
        CandidateCreate(full_name="Ana 2", email="ana2@x.com", cpf="11144477735"),
        tenant_id=b.id,
    )
    await db_session.commit()
    assert c2.tenant_id == b.id


@pytest.mark.asyncio
async def test_duplicate_email_same_tenant(db_session, two_tenants):
    a, _, _, _ = two_tenants
    first = await CandidateService.create(
        db_session,
        CandidateCreate(full_name="Ana", email="dup@x.com"),
        tenant_id=a.id,
    )
    await db_session.commit()

    with pytest.raises(DuplicateCandidateError) as exc:
        await CandidateService.create(
            db_session,
            CandidateCreate(full_name="Outro", email="DUP@X.COM"),  # case-insensitive
            tenant_id=a.id,
        )
    assert exc.value.field == "email"
    assert exc.value.existing_id == first.id


@pytest.mark.asyncio
async def test_update_keeps_dedup_excludes_self(db_session, two_tenants):
    a, _, _, _ = two_tenants
    c = await CandidateService.create(
        db_session,
        CandidateCreate(full_name="Ana", email="ana@x.com", cpf="11144477735"),
        tenant_id=a.id,
    )
    await db_session.commit()

    # Editar o próprio candidato com o mesmo email não pode disparar duplicate.
    updated = await CandidateService.update(
        db_session, c, CandidateUpdate(full_name="Ana Atualizada", email="ana@x.com")
    )
    await db_session.commit()
    assert updated.full_name == "Ana Atualizada"
