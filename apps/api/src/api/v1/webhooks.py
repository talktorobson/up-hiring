"""Clerk webhook placeholder.

Real handling (creating tenants, syncing users) lands in Sprint 2. For now
this endpoint exists so Clerk's test POST returns 200 and so the signing
secret pipeline is exercised end to end before we write real business logic.
"""
import logging

from fastapi import APIRouter, HTTPException, Request, status
from svix.webhooks import Webhook, WebhookVerificationError

from src.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/clerk")
async def clerk_webhook(request: Request) -> dict[str, object]:
    body = await request.body()
    headers = dict(request.headers)

    if settings.clerk_webhook_secret:
        try:
            event = Webhook(settings.clerk_webhook_secret).verify(body, headers)
        except WebhookVerificationError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"invalid svix signature: {e}",
            ) from e
        event_type = event.get("type", "?") if isinstance(event, dict) else "?"
        logger.info("Clerk webhook accepted: type=%s", event_type)
        return {"received": True, "type": event_type}

    logger.warning("CLERK_WEBHOOK_SECRET not set — accepting without verification")
    return {"received": True, "verified": False}
