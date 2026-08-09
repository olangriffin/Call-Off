import re
from typing import Annotated

import httpx
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.backend.database.session import get_db
from app.backend.core.config import get_settings
from app.backend.models.auth import AuthUser
from app.backend.models.membership import Membership
from app.backend.models.organisation import Organisation
from app.backend.schemas.auth import (
    AuthenticatedUser,
    OrganisationAccessContext,
)

CALL_OFF_SESSION_COOKIE = "calloff_session"
CALL_OFF_SESSION_NAME_COOKIE = "calloff_session_name"

_COOKIE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")

DatabaseSession = Annotated[
    Session,
    Depends(get_db),
]


def get_neon_auth_base_url() -> str:
    base_url = (get_settings().neon_auth_base_url or "").rstrip("/")

    if not base_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Neon Auth is not configured.",
        )

    return base_url


def get_app_base_url() -> str:
    return get_settings().app_base_url.rstrip("/")


def get_calloff_session(
    request: Request,
) -> tuple[str, str]:
    cookie_name = request.cookies.get(CALL_OFF_SESSION_NAME_COOKIE)

    cookie_value = request.cookies.get(CALL_OFF_SESSION_COOKIE)

    if not cookie_name or not cookie_value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )

    if not _COOKIE_NAME_PATTERN.fullmatch(cookie_name):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session cookie.",
        )

    if any(character in cookie_value for character in "\r\n;"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session cookie.",
        )

    return cookie_name, cookie_value


async def get_neon_session(
    cookie_name: str,
    cookie_value: str,
) -> dict:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{get_neon_auth_base_url()}/get-session",
                headers={
                    "Origin": get_app_base_url(),
                    "Cookie": f"{cookie_name}={cookie_value}",
                },
            )

    except httpx.RequestError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is unavailable.",
        ) from error

    if response.status_code >= 500:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is unavailable.",
        )

    if response.status_code != status.HTTP_200_OK:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session.",
        )

    try:
        payload = response.json()
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Authentication service returned invalid data.",
        ) from error

    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session.",
        )

    user_values = payload.get("user")
    session_values = payload.get("session")

    if not isinstance(user_values, dict):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session.",
        )

    if not isinstance(session_values, dict):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session.",
        )

    return payload


async def require_organisation_access(
    request: Request,
    database: DatabaseSession,
) -> OrganisationAccessContext:
    cookie_name, cookie_value = get_calloff_session(request)

    neon_session = await get_neon_session(
        cookie_name,
        cookie_value,
    )

    user_values = neon_session["user"]
    session_values = neon_session["session"]

    user_id = user_values.get("id")

    if not isinstance(user_id, str) or not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user ID is missing.",
        )

    auth_user = database.get(
        AuthUser,
        user_id,
    )

    if auth_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(f"Authenticated user does not exist. Session user ID: {user_id}"),
        )

    memberships = list(
        database.scalars(
            select(Membership).where(
                Membership.user_id == user_id,
                Membership.status == "active",
                Membership.revoked_at.is_(None),
            )
        )
    )

    if not memberships:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user has no organisation membership.",
        )

    if len(memberships) > 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=("Call-Off permits one organisation membership per user."),
        )

    membership = memberships[0]

    organisation = database.get(
        Organisation,
        membership.organization_id,
    )

    if organisation is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The organisation does not exist.",
        )

    return OrganisationAccessContext(
        user=AuthenticatedUser(
            id=auth_user.id,
            name=auth_user.name,
            email=auth_user.email,
            email_verified=auth_user.email_verified,
        ),
        membership_id=str(membership.id),
        role=membership.role.lower(),
        organization_id=organisation.id,
        organization_name=organisation.name,
        organization_slug=organisation.slug,
    )


CurrentOrganisationAccess = Annotated[
    OrganisationAccessContext,
    Depends(require_organisation_access),
]

PROJECT_CREATOR_ROLES = frozenset({"owner", "project_manager"})


def can_create_projects(access: OrganisationAccessContext) -> bool:
    """Return whether the authenticated membership may create projects."""

    return access.role in PROJECT_CREATOR_ROLES


def enforce_project_creation_access(
    access: OrganisationAccessContext,
) -> OrganisationAccessContext:
    """Enforce the shared project-creation capability rule."""

    if not can_create_projects(access):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners and project managers can create projects.",
        )

    return access


def require_project_creation_access(
    access: CurrentOrganisationAccess,
) -> OrganisationAccessContext:
    return enforce_project_creation_access(access)


ProjectCreationAccess = Annotated[
    OrganisationAccessContext,
    Depends(require_project_creation_access),
]


class FrontendAuthenticationRequired(Exception):
    """Raised when a protected HTML page requires login."""


async def require_frontend_organisation_access(
    request: Request,
    database: DatabaseSession,
) -> OrganisationAccessContext:
    try:
        return await require_organisation_access(
            request,
            database,
        )
    except HTTPException as error:
        if error.status_code == status.HTTP_401_UNAUTHORIZED:
            raise FrontendAuthenticationRequired from error

        raise


FrontendOrganisationAccess = Annotated[
    OrganisationAccessContext,
    Depends(require_frontend_organisation_access),
]


def require_frontend_project_creation_access(
    access: FrontendOrganisationAccess,
) -> OrganisationAccessContext:
    return enforce_project_creation_access(access)


FrontendProjectCreationAccess = Annotated[
    OrganisationAccessContext,
    Depends(require_frontend_project_creation_access),
]
