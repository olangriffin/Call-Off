from __future__ import annotations

import hashlib
import hmac
import logging
from datetime import datetime, timedelta, timezone
from typing import Annotated, Mapping

from email_validator import EmailNotValidError, validate_email
from fastapi import APIRouter, BackgroundTasks, Depends, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.backend.core.config import get_settings
from app.backend.core.csrf import verified_form
from app.backend.database.session import get_db
from app.backend.models.early_access import EarlyAccessApplication
from app.backend.routes.frontend.common import templates
from app.backend.services.email_notifications import send_early_access_emails
from app.backend.services.turnstile import verify_turnstile

logger = logging.getLogger(__name__)

router = APIRouter(include_in_schema=False)
DatabaseSession = Annotated[Session, Depends(get_db)]

COMPANY_SIZES = ("1-10", "11-50", "51-150", "151-500", "500+")
ACTIVE_PROJECT_COUNTS = ("1-3", "4-10", "11-25", "26-50", "50+")
INTEREST_LEVELS = ("early_access", "pilot_customer", "design_partner")

FIELD_LIMITS: dict[str, int] = {
    "full_name": 200,
    "work_email": 320,
    "company_name": 200,
    "job_title": 160,
    "subcontractor_type": 160,
    "company_size": 80,
    "active_projects": 80,
    "current_tools": 2000,
    "biggest_delivery_challenge": 4000,
    "interest_level": 40,
    "additional_information": 4000,
}

REQUIRED_FIELDS = {
    "full_name": "Full name is required.",
    "work_email": "Work email is required.",
    "company_name": "Company name is required.",
    "job_title": "Job title is required.",
    "subcontractor_type": "Subcontractor type or trade is required.",
    "company_size": "Company size is required.",
    "active_projects": "Number of active projects is required.",
    "current_tools": "Current tools used is required.",
    "biggest_delivery_challenge": "Biggest delivery challenge is required.",
    "interest_level": "Interest level is required.",
}


def public_context(**extra: object) -> dict[str, object]:
    settings = get_settings()
    return {
        "current_year": datetime.now(timezone.utc).year,
        "contact_email": settings.public_contact_email,
        "legal_entity_name": settings.legal_entity_name,
        "privacy_retention_days": settings.privacy_retention_days,
        **extra,
    }


def early_access_context(
    *,
    form_values: Mapping[str, str] | None = None,
    errors: Mapping[str, str] | None = None,
    success: bool = False,
) -> dict[str, object]:
    settings = get_settings()
    return public_context(
        form_values=dict(form_values or {}),
        errors=dict(errors or {}),
        success=success,
        company_sizes=COMPANY_SIZES,
        active_project_counts=ACTIVE_PROJECT_COUNTS,
        turnstile_site_key=settings.turnstile_site_key,
    )


def client_ip_hash(request: Request) -> str:
    settings = get_settings()
    client_ip = request.client.host if request.client else "unknown"
    return hmac.new(
        settings.ip_hash_secret.encode("utf-8"),
        client_ip.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def normalise_form_value(form: Mapping[str, object], field: str) -> str:
    return str(form.get(field, "") or "").strip()


def extract_form_values(form: Mapping[str, object]) -> dict[str, str]:
    return {field: normalise_form_value(form, field) for field in FIELD_LIMITS}


def validate_early_access_form(
    form_values: dict[str, str],
) -> dict[str, str]:
    errors: dict[str, str] = {}

    for field, message in REQUIRED_FIELDS.items():
        if not form_values.get(field):
            errors[field] = message

    for field, limit in FIELD_LIMITS.items():
        if len(form_values.get(field, "")) > limit:
            errors[field] = f"Use {limit} characters or fewer."

    email = form_values.get("work_email", "")
    if email and "work_email" not in errors:
        try:
            normalized = validate_email(email, check_deliverability=False).normalized
            form_values["work_email"] = normalized.lower()
        except EmailNotValidError:
            errors["work_email"] = "Enter a valid work email address."

    company_size = form_values.get("company_size", "")
    if company_size and company_size not in COMPANY_SIZES:
        errors["company_size"] = "Choose a valid company size."

    active_projects = form_values.get("active_projects", "")
    if active_projects and active_projects not in ACTIVE_PROJECT_COUNTS:
        errors["active_projects"] = "Choose a valid number of active projects."

    interest_level = form_values.get("interest_level", "")
    if interest_level and interest_level not in INTEREST_LEVELS:
        errors["interest_level"] = "Choose a valid interest level."

    return errors


def render_early_access(
    request: Request,
    *,
    form_values: Mapping[str, str] | None = None,
    errors: Mapping[str, str] | None = None,
    success: bool = False,
    status_code: int = status.HTTP_200_OK,
) -> HTMLResponse:
    response = templates.TemplateResponse(
        request=request,
        name="marketing/early_access.html",
        context=early_access_context(
            form_values=form_values,
            errors=errors,
            success=success,
        ),
        status_code=status_code,
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@router.get("/", response_class=HTMLResponse)
def landing_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="marketing/landing.html",
        context=public_context(),
    )


@router.get("/pricing", response_class=HTMLResponse)
def pricing_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="marketing/pricing.html",
        context=public_context(),
    )


@router.get("/privacy", response_class=HTMLResponse)
def privacy_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="marketing/privacy.html",
        context=public_context(),
    )


@router.get("/early-access", response_class=HTMLResponse)
def early_access_page(request: Request) -> HTMLResponse:
    return render_early_access(
        request,
        success=request.query_params.get("submitted") == "1",
    )


@router.post("/early-access", response_class=HTMLResponse)
async def submit_early_access(
    request: Request,
    background_tasks: BackgroundTasks,
    database: DatabaseSession,
) -> HTMLResponse:
    settings = get_settings()
    form = await verified_form(request)
    form_values = extract_form_values(form)
    errors = validate_early_access_form(form_values)

    if normalise_form_value(form, "website"):
        errors["form"] = "We could not submit this application."

    if not errors:
        turnstile_token = normalise_form_value(form, "cf-turnstile-response")
        if not await verify_turnstile(turnstile_token):
            errors["form"] = (
                "We could not verify this submission. Please try again."
            )

    if errors:
        return render_early_access(
            request,
            form_values=form_values,
            errors=errors,
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )

    ip_hash = client_ip_hash(request)
    recent_cutoff = datetime.now(timezone.utc) - timedelta(
        minutes=settings.early_access_rate_window_minutes
    )

    try:
        recent_submission_count = database.scalar(
            select(func.count())
            .select_from(EarlyAccessApplication)
            .where(
                EarlyAccessApplication.ip_address_hash == ip_hash,
                EarlyAccessApplication.created_at >= recent_cutoff,
            )
        )

        if (
            recent_submission_count
            and recent_submission_count >= settings.early_access_rate_limit
        ):
            response = render_early_access(
                request,
                form_values=form_values,
                errors={
                    "form": "Too many recent applications. Please try again later."
                },
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            )
            response.headers["Retry-After"] = str(
                settings.early_access_rate_window_minutes * 60
            )
            return response

        duplicate_application = database.scalar(
            select(EarlyAccessApplication.id).where(
                EarlyAccessApplication.work_email == form_values["work_email"]
            )
        )
    except SQLAlchemyError:
        database.rollback()
        logger.error("The early-access database check failed.")
        return render_early_access(
            request,
            form_values=form_values,
            errors={
                "form": "The application could not be submitted. Please try again."
            },
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    if duplicate_application:
        return render_early_access(
            request,
            form_values=form_values,
            errors={
                "work_email": (
                    "We already have an early-access application for this email."
                )
            },
            status_code=status.HTTP_409_CONFLICT,
        )

    application = EarlyAccessApplication(
        full_name=form_values["full_name"],
        work_email=form_values["work_email"],
        company_name=form_values["company_name"],
        job_title=form_values["job_title"],
        subcontractor_type=form_values["subcontractor_type"],
        company_size=form_values["company_size"],
        active_projects=form_values["active_projects"],
        current_tools=form_values["current_tools"],
        biggest_delivery_challenge=form_values["biggest_delivery_challenge"],
        interest_level=form_values["interest_level"],
        additional_information=form_values["additional_information"] or None,
        ip_address_hash=ip_hash,
        user_agent=request.headers.get("user-agent", "")[:500] or None,
    )
    database.add(application)

    try:
        database.commit()
    except IntegrityError:
        database.rollback()
        return render_early_access(
            request,
            form_values=form_values,
            errors={
                "work_email": (
                    "We already have an early-access application for this email."
                )
            },
            status_code=status.HTTP_409_CONFLICT,
        )
    except SQLAlchemyError:
        database.rollback()
        logger.error("The early-access application could not be stored.")
        return render_early_access(
            request,
            form_values=form_values,
            errors={
                "form": "The application could not be submitted. Please try again."
            },
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    background_tasks.add_task(send_early_access_emails, form_values.copy())
    return RedirectResponse(
        url="/early-access?submitted=1",
        status_code=status.HTTP_303_SEE_OTHER,
    )
