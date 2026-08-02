from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.backend.core.auth import FrontendAuthenticationRequired
from app.backend.core.config import get_settings
from app.backend.core.csrf import CSRFCookieMiddleware
from app.backend.database.session import get_db
from app.backend.frontend_templates import build_frontend_templates
from app.backend.routes.approvals import router as approvals_router
from app.backend.routes.auth import router as auth_router
from app.backend.routes.deliverable_revisions import (
    router as deliverable_revisions_router,
)
from app.backend.routes.deliverables import router as deliverables_router
from app.backend.routes.frontend import router as frontend_router
from app.backend.routes.programme_activities import (
    router as programme_activities_router,
)
from app.backend.routes.projects import router as projects_router
from app.backend.routes.work_packages import router as work_packages_router

logger = logging.getLogger(__name__)
BASE_DIR = Path(__file__).resolve().parent
templates = build_frontend_templates()


def error_context(status_code: int, heading: str, message: str) -> dict[str, object]:
    settings = get_settings()
    return {
        "current_year": datetime.now(timezone.utc).year,
        "contact_email": settings.public_contact_email,
        "legal_entity_name": settings.legal_entity_name,
        "status_code": status_code,
        "error_heading": heading,
        "error_message": message,
    }


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="Call-Off API",
        version="0.1.0",
        debug=settings.debug,
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None if settings.is_production else "/redoc",
        openapi_url=None if settings.is_production else "/openapi.json",
    )

    application.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.trusted_host_list,
    )
    application.add_middleware(CSRFCookieMiddleware)

    @application.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), geolocation=(), microphone=()",
        )
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; "
            "base-uri 'self'; "
            "connect-src 'self' https://challenges.cloudflare.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "form-action 'self'; "
            "frame-ancestors 'none'; "
            "frame-src https://challenges.cloudflare.com; "
            "img-src 'self' data:; "
            "script-src 'self' https://challenges.cloudflare.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
        )
        if settings.is_production:
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000",
            )
        return response

    @application.exception_handler(FrontendAuthenticationRequired)
    async def frontend_authentication_handler(
        request: Request,
        error: FrontendAuthenticationRequired,
    ) -> RedirectResponse:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    @application.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request,
        error: StarletteHTTPException,
    ):
        accepts_html = "text/html" in request.headers.get("accept", "").lower()
        if accepts_html and error.status_code in {
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
        }:
            is_not_found = error.status_code == status.HTTP_404_NOT_FOUND
            return templates.TemplateResponse(
                request=request,
                name="marketing/error.html",
                context=error_context(
                    error.status_code,
                    "Page not found" if is_not_found else "Request not accepted",
                    (
                        "The page you requested does not exist or may have moved."
                        if is_not_found
                        else "The form expired or could not be verified. Please try again."
                    ),
                ),
                status_code=error.status_code,
            )
        return JSONResponse(
            {"detail": str(error.detail)},
            status_code=error.status_code,
            headers=error.headers,
        )

    @application.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, error: Exception):
        logger.error(
            "Unhandled application error type=%s path=%s",
            type(error).__name__,
            request.url.path,
        )
        return templates.TemplateResponse(
            request=request,
            name="marketing/error.html",
            context=error_context(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                "Something went wrong",
                "The request could not be completed. Please try again later.",
            ),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    @application.get("/health", include_in_schema=False)
    def health(database: Session = Depends(get_db)) -> JSONResponse:
        try:
            database.execute(text("SELECT 1"))
        except SQLAlchemyError:
            return JSONResponse(
                {"status": "unavailable"},
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return JSONResponse({"status": "ok"})

    application.include_router(frontend_router)
    application.include_router(projects_router)
    application.include_router(work_packages_router)
    application.include_router(programme_activities_router)
    application.include_router(deliverables_router)
    application.include_router(deliverable_revisions_router)
    application.include_router(approvals_router)
    application.include_router(auth_router)

    application.mount(
        "/static",
        StaticFiles(directory=BASE_DIR / "frontend" / "static"),
        name="static",
    )
    return application


app = create_app()
