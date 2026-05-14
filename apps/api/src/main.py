"""Entrypoint do FastAPI."""
import logging

import logfire
import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.v1 import api_v1_router
from src.config import settings
from src.middleware.clerk import ClerkAuthMiddleware

logging.basicConfig(level=settings.log_level)

if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.app_env,
        traces_sample_rate=0.1,
    )

if settings.logfire_token:
    logfire.configure(token=settings.logfire_token, environment=settings.app_env)


app = FastAPI(
    title="UpHiring API",
    version="0.0.1",
    docs_url="/docs" if settings.app_env != "prod" else None,
    redoc_url=None,
)

if settings.logfire_token:
    logfire.instrument_fastapi(app)

# CORS (em prod, restringir origins)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"] if settings.app_env == "local" else ["https://app.seu-dominio.com.br"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth middleware (valida JWT Clerk + injeta tenant no contexto)
app.add_middleware(ClerkAuthMiddleware)

app.include_router(api_v1_router, prefix="/api/v1")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
