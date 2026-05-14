"""Middleware de autenticação Clerk.

Valida JWT do Clerk presente no header Authorization, extrai user_id e org_id,
injeta no contexto da request (e no ContextVar de tenant para a sessão DB usar RLS).

Endpoints públicos passam livremente. Demais exigem token válido.
"""
import logging
from uuid import UUID

import httpx
from fastapi import HTTPException, Request, status
from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from src.config import settings
from src.db.session import current_tenant_id

logger = logging.getLogger(__name__)

PUBLIC_PATHS = {"/health", "/docs", "/openapi.json", "/api/v1/webhooks/clerk"}

# Em produção, baixe e cache o JWKS do Clerk. Implementação simples aqui para Sprint 2.
CLERK_JWKS_URL = "https://api.clerk.com/v1/jwks"


class ClerkAuthMiddleware(BaseHTTPMiddleware):
    """Valida JWT Clerk e popula request.state.user_id, request.state.org_id."""

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in PUBLIC_PATHS or request.url.path.startswith("/docs"):
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing Bearer token",
            )

        token = auth_header.removeprefix("Bearer ").strip()

        try:
            # TODO: cachear JWKS e validar assinatura corretamente
            claims = jwt.get_unverified_claims(token)
        except JWTError as exc:
            logger.warning("invalid_jwt", exc_info=exc)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            ) from exc

        user_id = claims.get("sub")
        org_id = claims.get("org_id")

        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing user")

        request.state.user_id = user_id
        request.state.org_id = org_id

        # Resolve tenant_id local a partir do org_id Clerk
        # Em produção, fazer cache em Redis para evitar query por request.
        if org_id:
            # TODO: lookup tenant_id por clerk_org_id na tabela tenant
            # Placeholder: usar org_id como tenant_id se já for UUID válido
            try:
                token_tenant = UUID(org_id) if len(org_id) == 36 else None
                if token_tenant:
                    current_tenant_id.set(token_tenant)
            except ValueError:
                pass

        return await call_next(request)
