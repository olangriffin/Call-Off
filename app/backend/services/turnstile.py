from __future__ import annotations

import logging

import httpx

from app.backend.core.config import get_settings

logger = logging.getLogger(__name__)


async def verify_turnstile(token: str) -> bool:
    settings = get_settings()

    if not settings.turnstile_enabled:
        return not settings.is_production

    if not token:
        return False

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.post(
                settings.turnstile_verify_url,
                data={
                    "secret": settings.turnstile_secret_key.get_secret_value(),
                    "response": token,
                },
            )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError):
        logger.warning("Turnstile verification was unavailable.")
        return False

    return bool(isinstance(payload, dict) and payload.get("success") is True)
