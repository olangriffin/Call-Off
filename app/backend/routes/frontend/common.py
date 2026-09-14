from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.backend.core.auth import (
    FrontendOrganisationAccess,
    can_destructive_operations,
    can_respond_to_approvals,
    can_create_projects,
    can_operational_write,
)
from app.backend.database.session import get_db
from app.backend.frontend_templates import build_frontend_templates

templates = build_frontend_templates()

DatabaseSession = Annotated[
    Session,
    Depends(get_db),
]


def authenticated_template_context(
    access: FrontendOrganisationAccess,
) -> dict:
    """Return shared context for protected application templates."""

    return {
        "company_name": access.organization_name,
        "current_user": access.user,
        "current_role": access.role,
        "can_create_projects": can_create_projects(access),
        "can_operational_write": can_operational_write(access),
        "can_destructive_operation": can_destructive_operations(access),
        "can_approval_response": can_respond_to_approvals(access),
    }
