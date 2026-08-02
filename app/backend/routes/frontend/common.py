from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.backend.core.auth import FrontendOrganisationAccess
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
    }
