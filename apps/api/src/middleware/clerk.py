"""Middleware de autenticação Clerk.

Valida JWT do Clerk presente no header Authorization, extrai user_id e org_id,
injeta no contexto da request (e no ContextVar de tenant para a sessão DB usar
RLS).

Endpoints públicos passam livremente. Demais exigem token válido.
"""
import logging
from uuid import UUID

import sentry_sdk
from fastapi import Request, status
from jose import ExpiredSignatureError, JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from src.config import settings
from src.db.session import current_tenant_id
from src.middleware.jwks import get_jwks_client

logger = logging.getLogger(__name__)

PUBLIC_PATHS = {"/health", "/docs", "/openapi.json", "/api/v1/webhooks/clerk"}


def _unauthorized(detail: str) -> JSONResponse:
    # Returning a Response — not raising HTTPException — because BaseHTTPMiddleware
    # does not route exceptions through FastAPI's exception handlers, so a raise
    # would leak as a generic 500. See issue #24.
    return JSONResponse({"detail": detail}, status_code=status.HTTP_401_UNAUTHORIZED)


def _breadcrumb(message: str, **data: object) -> None:
    sentry_sdk.add_breadcrumb(
        category="auth.clerk", level="warning", message=message, data=data
    )


async def _decode_token(token: str) -> dict:
    """Decode + verifica RS256 contra JWKS. Levanta JWTError em qualquer falha."""
    if settings.clerk_skip_verify:
        # Fallback DEBUG. Garantir nunca em prod via assert defensivo.
        if settings.app_env == "prod":
            raise RuntimeError("clerk_skip_verify=True em produção é proibido")
        return jwt.get_unverified_claims(token)

    header = jwt.get_unverified_header(token)
    kid = header.get("kid")
    if not kid:
        raise JWTError("token header missing kid")

    key = await get_jwks_client().get_key(kid)
    decode_kwargs: dict[str, object] = {"algorithms": ["RS256"]}
    if settings.clerk_audience:
        decode_kwargs["audience"] = settings.clerk_audience
    if settings.clerk_issuer:
        decode_kwargs["issuer"] = settings.clerk_issuer
    return jwt.decode(token, key, **decode_kwargs)


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
            claims = await _decode_token(token)
        except ExpiredSignatureError:
            _breadcrumb("token expired")
            return _unauthorized("Token expired")
        except KeyError as exc:
            _breadcrumb("kid not in JWKS", error=str(exc))
            return _unauthorized("Unknown signing key")
        except JWTError as exc:
            _breadcrumb("jwt decode failed", error=exc.__class__.__name__)
            return _unauthorized("Invalid token")

        user_id = claims.get("sub")
        org_id = claims.get("org_id")
        if not user_id:
            return _unauthorized("Missing user")

        request.state.user_id = user_id
        request.state.org_id = org_id

        # TODO(#33): substituir pelo lookup real em src/services/tenant.py.
        if org_id:
            try:
                token_tenant = UUID(org_id) if len(org_id) == 36 else None
                if token_tenant:
                    current_tenant_id.set(token_tenant)
            except ValueError:
                pass

        return await call_next(request)
