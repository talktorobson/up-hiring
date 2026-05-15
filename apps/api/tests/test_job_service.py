"""JobService.create — Job + 7 default stages na mesma transação."""
from __future__ import annotations

import pytest

from src.models.enums import StageKind
from src.schemas.job import JobCreate
from src.services.job import JobService


@pytest.mark.asyncio
async def test_create_job_seeds_7_default_stages(db_session, two_tenants):
    a, ua, _, _ = two_tenants
    payload = JobCreate(title="Engenheiro de Acabamentos")

    job = await JobService.create(
        db_session, payload, tenant_id=a.id, actor_user_id=ua.id
    )
    await db_session.commit()

    assert job.tenant_id == a.id
    assert job.title == "Engenheiro de Acabamentos"
    assert len(job.stages) == 7
    names = [s.name for s in job.stages]
    assert names == ["Sourced", "Applied", "Screening", "Interview", "Offer", "Hired", "Rejected"]
    positions = [s.position for s in job.stages]
    assert positions == [0, 1, 2, 3, 4, 5, 6]
    kinds = [s.kind for s in job.stages]
    assert kinds[:5] == [StageKind.ACTIVE] * 5
    assert kinds[5] == StageKind.TERMINAL_HIRED
    assert kinds[6] == StageKind.TERMINAL_REJECTED


@pytest.mark.asyncio
async def test_create_job_uses_payload_defaults(db_session, two_tenants):
    a, ua, _, _ = two_tenants

    job = await JobService.create(
        db_session,
        JobCreate(
            title="Pedreiro",
            description="Acabamento fino",
            location="São Paulo",
            salary_min=2500,
            salary_max=4000,
        ),
        tenant_id=a.id,
        actor_user_id=ua.id,
    )
    await db_session.commit()

    assert job.description == "Acabamento fino"
    assert job.location == "São Paulo"
    assert job.salary_min == 2500
    assert job.salary_max == 4000
    assert job.created_by == ua.id
