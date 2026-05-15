"""GET /api/v1/me — contexto da sessão (user + tenant + role).

Frontend chama este endpoint após sign-in pra montar a UI: nome do tenant
ativo, role do user dentro dele, etc.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db
from src.models.tenant import AppUser, Membership, Tenant
from src.schemas import AppUserRead, MeResponse, TenantRead

router = APIRouter()


@router.get(
    "/me",
    response_model=MeResponse,
    summary="Contexto do usuário autenticado",
    responses={
        200: {
            "description": "User + tenant ativo + role no tenant",
            "content": {
                "application/json": {
                    "example": {
                        "user": {
                            "id": "11111111-1111-1111-1111-111111111111",
                            "clerk_user_id": "user_abc",
                            "email": "ana@example.com",
                            "full_name": "Ana Silva",
                        },
                        "tenant": {
                            "id": "22222222-2222-2222-2222-222222222222",
                            "clerk_org_id": "org_xyz",
                            "name": "Acabamentos LTDA",
                            "slug": "acabamentos-ltda",
                        },
                        "role": "admin",
                    }
                }
            },
        },
        400: {"description": "`org_required` — token sem `org_id`"},
        403: {"description": "`not_member` — user não pertence ao tenant ativo"},
        404: {"description": "`user_not_provisioned` — webhook user.created ainda não rodou"},
    },
)
async def get_me(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> MeResponse:
    clerk_user_id: str | None = getattr(request.state, "user_id", None)
    tenant_id = getattr(request.state, "tenant_id", None)

    if tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="org_required"
        )

    user = await session.scalar(
        select(AppUser).where(AppUser.clerk_user_id == clerk_user_id)
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="user_not_provisioned"
        )

    membership = await session.scalar(
        select(Membership).where(
            Membership.user_id == user.id,
            Membership.tenant_id == tenant_id,
        )
    )
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="not_member"
        )

    tenant = await session.scalar(select(Tenant).where(Tenant.id == tenant_id))
    if tenant is None:
        # Race condition: middleware resolveu, tenant deletado entre lookups.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="tenant_disappeared"
        )

    return MeResponse(
        user=AppUserRead.model_validate(user),
        tenant=TenantRead.model_validate(tenant),
        role=membership.role,
    )
