import uuid

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.backend.core.auth import FrontendOrganisationAccess
from app.backend.routes.frontend.common import (
    DatabaseSession,
    authenticated_template_context,
    templates,
)
from app.backend.services.programme import get_or_create_current_revision
from app.backend.services.programme_activity import (
    build_activity_tree,
    list_activities,
)
from app.backend.services.programme_workspace import build_programme_workspace
from app.backend.services.project import get_project
from app.backend.services.work_package import list_work_packages

router = APIRouter(
    include_in_schema=False,
)


@router.get(
    "/app/projects/{project_id}/programme",
    response_class=HTMLResponse,
)
def programme_page(
    request: Request,
    project_id: uuid.UUID,
    database: DatabaseSession,
    access: FrontendOrganisationAccess,
) -> HTMLResponse:
    project = get_project(
        database,
        project_id,
        access.organization_id,
    )

    if project is None:
        return templates.TemplateResponse(
            request=request,
            name="programme/programme.html",
            context={
                **authenticated_template_context(access),
                "page_title": "Programme not found",
                "project": None,
                "activities": [],
            },
            status_code=404,
        )

    revision = get_or_create_current_revision(database, project)

    activities = list_activities(
        database,
        revision.id,
        offset=0,
        limit=None,
    )

    activity_rows = build_activity_tree(activities)
    workspace = build_programme_workspace(activity_rows)

    work_packages = list_work_packages(
        database,
        project_id,
        offset=0,
        limit=None,
    )

    return templates.TemplateResponse(
        request=request,
        name="programme/programme.html",
        context={
            **authenticated_template_context(access),
            "page_title": "Programme",
            "project": project,
            "revision": revision,
            "activity_rows": activity_rows,
            "workspace": workspace,
            "work_packages": work_packages,
        },
    )
