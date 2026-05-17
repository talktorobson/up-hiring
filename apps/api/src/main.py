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

# Auth middleware (valida JWT Clerk + injeta tenant no contexto).
# Adicionado ANTES do CORS de propósito: no Starlette o último
# `add_middleware` fica mais externo, então o CORS abaixo envolve o auth e
# responde o preflight OPTIONS (sem Authorization) antes do Clerk 401ar.
app.add_middleware(ClerkAuthMiddleware)

# CORS — outermost. Origens via settings (CSV) + regex pros previews Vercel.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_origin_regex=settings.cors_allow_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_v1_router, prefix="/api/v1")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
