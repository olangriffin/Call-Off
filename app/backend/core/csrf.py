from __future__ import annotations

import hmac
import re
import secrets

from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.backend.core.config import get_settings

CSRF_COOKIE_NAME = "calloff_csrf"
CSRF_FORM_FIELD = "csrf_token"
_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{32,128}$")


def _valid_token(value: str | None) -> bool:
    return bool(value and _TOKEN_PATTERN.fullmatch(value))


def csrf_token(request: Request) -> str:
    token = getattr(request.state, "csrf_token", None)
    if not _valid_token(token):
        token = secrets.token_urlsafe(32)
        request.state.csrf_token = token
    return token


def validate_csrf_token(request: Request, submitted_token: object) -> bool:
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    submitted = str(submitted_token or "")
    return bool(
        _valid_token(cookie_token)
        and _valid_token(submitted)
        and hmac.compare_digest(cookie_token, submitted)
    )


async def verified_form(request: Request):
    """Parse a form once and verify its double-submit CSRF token."""

    form = await request.form()
    if not validate_csrf_token(request, form.get(CSRF_FORM_FIELD)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The form expired or could not be verified. Please try again.",
        )
    return form


class CSRFCookieMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
        request.state.csrf_token = (
            cookie_token if _valid_token(cookie_token) else secrets.token_urlsafe(32)
        )

        response = await call_next(request)

        if cookie_token != request.state.csrf_token:
            settings = get_settings()
            response.set_cookie(
                key=CSRF_COOKIE_NAME,
                value=request.state.csrf_token,
                httponly=True,
                secure=settings.auth_cookie_secure,
                samesite="lax",
                max_age=60 * 60 * 2,
                path="/",
            )

        return response
