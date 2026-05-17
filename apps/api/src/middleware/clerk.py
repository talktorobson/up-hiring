"""Middleware de autenticação Clerk.

Valida JWT do Clerk presente no header Authorization, extrai user_id e org_id,
resolve `tenant_id` no banco (cacheado em Redis) e injeta no contexto da
request — incluindo o ContextVar de tenant que `get_db` usa pra `SET LOCAL
app.current_tenant_id` (RLS).

Endpoints públicos passam livremente. Demais exigem token válido. Endpoints
tenant-scoped que precisem de tenant devem checar `request.state.tenant_id`
e devolver 400 `org_required` se for None.
"""
import logging

import sentry_sdk
from fastapi import Request, status
from jose import ExpiredSignatureError, JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from src.config import settings
from src.db.session import AsyncSessionLocal, current_tenant_id
from src.middleware.jwks import get_jwks_client
from src.services.tenant import resolve_tenant_id_cached

logger = logging.getLogger(__name__)

PUBLIC_PATHS = {"/health", "/docs", "/openapi.json", "/api/v1/webhooks/clerk"}


def _unauthorized(detail: str) -> JSONResponse:
    # Returning a Response — not raising HTTPException — because BaseHTTPMiddleware
    # does not route exceptions through FastAPI's exception handlers, so a raise
    # would leak as a generic 500. See issue #24.
    return JSONResponse({"detail": detail}, status_code=status.HTTP_401_UNAUTHORIZED)


def _forbidden(detail: str) -> JSONResponse:
    return JSONResponse({"detail": detail}, status_code=status.HTTP_403_FORBIDDEN)


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
        # Clerk v2 default session token carrega a org ativa em `o.id`
        # (objeto compacto). Tokens com template customizado usam o `org_id`
        # achatado. Aceita ambos pra não depender de config de dashboard.
        org_claim = claims.get("o")
        org_id = claims.get("org_id") or (
            org_claim.get("id") if isinstance(org_claim, dict) else None
        )
        if not user_id:
            return _unauthorized("Missing user")

        request.state.user_id = user_id
        request.state.org_id = org_id
        request.state.tenant_id = None

        if org_id:
            try:
                tenant_id = await resolve_tenant_id_cached(AsyncSessionLocal, org_id)
            except Exception as exc:
                # Falhas de Redis caem dentro do helper; aqui pegamos só DB
                # down/permission. Sem este except o BaseHTTPMiddleware vaza 500.
                logger.exception("tenant resolve failed for org_id=%s", org_id)
                _breadcrumb("tenant resolve failed", error=exc.__class__.__name__)
                return _forbidden("tenant_resolve_failed")

            if tenant_id is None:
                _breadcrumb("tenant_not_provisioned", org_id=org_id)
                return _forbidden("tenant_not_provisioned")

            request.state.tenant_id = tenant_id
            current_tenant_id.set(tenant_id)

        return await call_next(request)
