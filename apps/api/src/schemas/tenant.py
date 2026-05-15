"""Schemas Pydantic para tenant, app_user, membership e o GET /me."""
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr

from src.models.tenant import Role


class TenantCreate(BaseModel):
    clerk_org_id: str
    name: str
    slug: str


class TenantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    clerk_org_id: str
    name: str
    slug: str


class AppUserCreate(BaseModel):
    clerk_user_id: str
    email: EmailStr
    full_name: str | None = None


class AppUserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    clerk_user_id: str
    email: EmailStr
    full_name: str | None = None


class MembershipRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    user_id: UUID
    tenant_id: UUID
    role: Role


class MeResponse(BaseModel):
    user: AppUserRead
    tenant: TenantRead
    role: Role
