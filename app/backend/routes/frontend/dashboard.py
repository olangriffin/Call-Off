from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.backend.core.auth import FrontendOrganisationAccess
from app.backend.routes.frontend.common import (
    DatabaseSession,
    authenticated_template_context,
    templates,
)
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

    active_project_count = sum(
        1 for project in projects if project.status.lower() == "active"
    )

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            **authenticated_template_context(access),
            "page_title": "Projects",
            "projects": projects,
            "project_count": len(projects),
            "active_project_count": active_project_count,
        },
    )
