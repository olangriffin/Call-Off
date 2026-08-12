from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.backend.core.auth import FrontendOrganisationAccess
from app.backend.routes.frontend.common import (
    DatabaseSession,
    authenticated_template_context,
    templates,
)
from app.backend.services.dashboard import get_dashboard_overview

router = APIRouter(
    include_in_schema=False,
)


@router.get(
    "/app",
    response_class=HTMLResponse,
)
def dashboard(
    request: Request,
    database: DatabaseSession,
    access: FrontendOrganisationAccess,
) -> HTMLResponse:
    overview = get_dashboard_overview(database, access.organization_id)

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            **authenticated_template_context(access),
            "page_title": "Dashboard",
            "overview": overview,
        },
    )
