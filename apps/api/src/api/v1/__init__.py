"""Router v1."""
from fastapi import APIRouter

from src.api.v1 import health, jobs

api_v1_router = APIRouter()
api_v1_router.include_router(health.router, tags=["health"])
api_v1_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
