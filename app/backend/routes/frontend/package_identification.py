import uuid

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.backend.core.auth import FrontendOrganisationAccess
from app.backend.routes.frontend.common import (
    DatabaseSession,
    authenticated_template_context,
    templates,
)
from app.backend.services.package_identification import (
    build_package_identification_preview,
)
from app.backend.services.programme import get_current_revision
from app.backend.services.programme_activity import list_activities
from app.backend.services.project import get_project

router = APIRouter(
    include_in_schema=False,
)


@router.get(
    "/app/projects/{project_id}/programme/package-identification",
    response_class=HTMLResponse,
)
def package_identification_preview_page(
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
            name="programme/package_identification.html",
            context={
                **authenticated_template_context(access),
                "page_title": "Package identification",
                "project": None,
                "revision": None,
                "preview": build_package_identification_preview([]),
            },
            status_code=404,
        )

    revision = get_current_revision(database, project.id)
    activities = (
        list_activities(database, revision.id, offset=0, limit=None)
        if revision is not None
        else []
    )
    preview = build_package_identification_preview(activities)

    return templates.TemplateResponse(
        request=request,
        name="programme/package_identification.html",
        context={
            **authenticated_template_context(access),
            "page_title": "Package identification",
            "project": project,
            "revision": revision,
            "preview": preview,
        },
    )
