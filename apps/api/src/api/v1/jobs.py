"""Endpoints CRUD básico de Job (esqueleto para Sprint 3)."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db
from src.models.job import EmploymentType, Job, JobStatus

router = APIRouter()


class JobCreate(BaseModel):
    title: str = Field(min_length=2, max_length=255)
    description: str | None = None
    location: str | None = None
    remote: bool = False
    employment_type: EmploymentType = EmploymentType.CLT
    salary_min: float | None = None
    salary_max: float | None = None


class JobRead(BaseModel):
    id: UUID
    title: str
    status: JobStatus
    location: str | None
    employment_type: EmploymentType

    model_config = {"from_attributes": True}


@router.post("", response_model=JobRead, status_code=status.HTTP_201_CREATED)
async def create_job(
    payload: JobCreate, request: Request, db: AsyncSession = Depends(get_db)
) -> Job:
    # TODO: resolver tenant_id e created_by a partir do request.state (middleware Clerk)
    # Placeholder até o Sprint 2 amadurecer o middleware:
    if not getattr(request.state, "org_id", None):
        raise HTTPException(status_code=400, detail="Missing org context")

    job = Job(
        title=payload.title,
        description=payload.description,
        location=payload.location,
        remote=payload.remote,
        employment_type=payload.employment_type,
        salary_min=payload.salary_min,
        salary_max=payload.salary_max,
        tenant_id=UUID(request.state.org_id),  # ajustar quando lookup tenant_id estiver pronto
        created_by=UUID(request.state.user_id),
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


@router.get("", response_model=list[JobRead])
async def list_jobs(db: AsyncSession = Depends(get_db)) -> list[Job]:
    # RLS já filtra por tenant_id setado em SET LOCAL na sessão.
    result = await db.execute(select(Job).order_by(Job.created_at.desc()))
    return list(result.scalars().all())
