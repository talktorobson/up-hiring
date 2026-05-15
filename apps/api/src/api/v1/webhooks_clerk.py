"""Webhook do Clerk com verificação Svix e dispatcher por `type`.

Endpoint público (entra em `PUBLIC_PATHS` do `ClerkAuthMiddleware`); a
segurança vem do header `svix-signature` validado contra o `webhook_secret`
do Clerk Dashboard. Handlers reais ficam em `src.services.webhook_handlers`
(issue #36) — aqui o dispatcher só registra o evento e devolve 200.
"""
import logging
from collections.abc import Awaitable, Callable

import sentry_sdk
from fastapi import APIRouter, Header, HTTPException, Request, status
from svix.webhooks import Webhook, WebhookVerificationError

from src.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


# Tipos suportados pelo Clerk que vamos materializar. Tudo fora dessa lista é
# logado mas devolve 200 (Clerk não retenta se receber 2xx).
HandlerFn = Callable[[dict], Awaitable[None]]
_HANDLERS: dict[str, HandlerFn] = {}


def register_handler(event_type: str) -> Callable[[HandlerFn], HandlerFn]:
    def decorator(fn: HandlerFn) -> HandlerFn:
        _HANDLERS[event_type] = fn
        return fn

    return decorator


@router.post("/clerk")
async def clerk_webhook(
    request: Request,
    svix_id: str = Header(..., alias="svix-id"),
    svix_timestamp: str = Header(..., alias="svix-timestamp"),
    svix_signature: str = Header(..., alias="svix-signature"),
) -> dict[str, object]:
    body = await request.body()
    headers = {
        "svix-id": svix_id,
        "svix-timestamp": svix_timestamp,
        "svix-signature": svix_signature,
    }

    if not settings.clerk_webhook_secret:
        # Sem secret nada de conferir: rejeita pra evitar aceitar payloads
        # forjados em ambientes mal configurados.
        logger.error("CLERK_WEBHOOK_SECRET ausente — rejeitando webhook")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="webhook_secret_not_configured",
        )

    try:
        event = Webhook(settings.clerk_webhook_secret).verify(body, headers)
    except WebhookVerificationError as e:
        sentry_sdk.add_breadcrumb(
            category="webhook.clerk",
            message="signature verify failed",
            level="warning",
            data={"svix_id": svix_id},
        )
        logger.warning("svix verify failed: id=%s", svix_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_signature",
        ) from e

    if not isinstance(event, dict):
        logger.warning("svix payload not dict: id=%s", svix_id)
        return {"received": True, "dispatched": False}

    event_type = event.get("type", "")
    event_data = event.get("data") or {}
    object_id = event_data.get("id", "?")

    logger.info("clerk webhook: type=%s id=%s svix_id=%s", event_type, object_id, svix_id)

    handler = _HANDLERS.get(event_type)
    if handler is None:
        logger.info("no handler for clerk event type=%s", event_type)
        return {"received": True, "dispatched": False, "type": event_type}

    await handler(event)
    return {"received": True, "dispatched": True, "type": event_type}
