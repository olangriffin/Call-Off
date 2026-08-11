from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.backend.core.auth import FrontendOrganisationAccess
from app.backend.routes.frontend.common import (
    DatabaseSession,
    authenticated_template_context,
    templates,
)
from app.backend.services.dashboard import get_dashboard_overview
from app.backend.services.project import list_projects

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
    projects = list_projects(
        database,
        access.organization_id,
        offset=0,
        limit=100,
    )
    overview = get_dashboard_overview(database, access.organization_id)

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            **authenticated_template_context(access),
            "page_title": "Dashboard",
            "projects": projects,
            "overview": overview,
            # Preserve the existing flat names while the dashboard template
            # migrates to the focused overview contract.
            "project_count": overview.project_count,
            "active_project_count": overview.active_project_count,
        },
    )
