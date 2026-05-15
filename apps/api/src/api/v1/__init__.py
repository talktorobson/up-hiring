"""Router v1."""
from fastapi import APIRouter

from src.api.v1 import applications, candidates, health, jobs, me, webhooks_clerk

api_v1_router = APIRouter()
api_v1_router.include_router(health.router, tags=["health"])
api_v1_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
api_v1_router.include_router(candidates.router, prefix="/candidates", tags=["candidates"])
api_v1_router.include_router(
    applications.router, prefix="/applications", tags=["applications"]
)
api_v1_router.include_router(me.router, tags=["me"])
api_v1_router.include_router(webhooks_clerk.router, prefix="/webhooks", tags=["webhooks"])
