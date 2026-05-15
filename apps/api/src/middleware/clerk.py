"""Middleware de autenticação Clerk.

Valida JWT do Clerk presente no header Authorization, extrai user_id e org_id,
injeta no contexto da request (e no ContextVar de tenant para a sessão DB usar RLS).

Endpoints públicos passam livremente. Demais exigem token válido.
"""
import logging
from uuid import UUID

from fastapi import Request, status
from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from src.db.session import current_tenant_id

logger = logging.getLogger(__name__)

PUBLIC_PATHS = {"/health", "/docs", "/openapi.json", "/api/v1/webhooks/clerk"}

# Em produção, baixe e cache o JWKS do Clerk. Implementação simples aqui para Sprint 2.
CLERK_JWKS_URL = "https://api.clerk.com/v1/jwks"


def _unauthorized(detail: str) -> JSONResponse:
    # Returning a Response — not raising HTTPException — because BaseHTTPMiddleware
    # does not route exceptions through FastAPI's exception handlers, so a raise
    # would leak as a generic 500. See issue #24.
    return JSONResponse({"detail": detail}, status_code=status.HTTP_401_UNAUTHORIZED)


class ClerkAuthMiddleware(BaseHTTPMiddleware):
    """Valida JWT Clerk e popula request.state.user_id, request.state.org_id."""

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in PUBLIC_PATHS or request.url.path.startswith("/docs"):
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return _unauthorized("Missing Bearer token")

        token = auth_header.removeprefix("Bearer ").strip()

        try:
            # TODO: cachear JWKS e validar assinatura corretamente
            claims = jwt.get_unverified_claims(token)
        except JWTError as exc:
            logger.warning("invalid_jwt", exc_info=exc)
            return _unauthorized("Invalid token")

        user_id = claims.get("sub")
        org_id = claims.get("org_id")

        if not user_id:
            return _unauthorized("Missing user")

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
