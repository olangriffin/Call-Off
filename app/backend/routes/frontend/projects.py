import uuid

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError

from app.backend.core.auth import (
    FrontendOrganisationAccess,
    FrontendProjectCreationAccess,
)
from app.backend.core.csrf import verified_form
from app.backend.routes.frontend.common import (
    DatabaseSession,
    authenticated_template_context,
    templates,
)
from app.backend.schemas.project import ProjectCreate
from app.backend.services.project import (
    OrganisationNotFoundError,
    ProjectCodeConflictError,
    create_project,
    get_project,
)
from app.backend.services.work_package import list_work_packages

router = APIRouter(
    include_in_schema=False,
)


@router.get(
    "/app/projects/new",
    response_class=HTMLResponse,
)
def new_project_page(
    request: Request,
    access: FrontendProjectCreationAccess,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="project/project_new.html",
        context={
            **authenticated_template_context(access),
            "page_title": "New project",
            "form_values": {},
        },
    )


@router.post(
    "/app/projects/new",
    response_class=HTMLResponse,
)
async def create_project_page(
    request: Request,
    database: DatabaseSession,
    access: FrontendProjectCreationAccess,
):
    form = await verified_form(request)

    form_values = {
        "code": str(form.get("code", "")).strip(),
        "name": str(form.get("name", "")).strip(),
        "client_name": str(form.get("client_name", "")).strip(),
        "status": str(form.get("status", "planning")).strip(),
        "planned_start": str(form.get("planned_start", "")).strip(),
        "planned_finish": str(form.get("planned_finish", "")).strip(),
    }

    project_values = {
        **form_values,
        "client_name": form_values["client_name"] or None,
        "planned_start": form_values["planned_start"] or None,
        "planned_finish": form_values["planned_finish"] or None,
    }

    try:
        project_data = ProjectCreate.model_validate(
            project_values,
        )

        project = create_project(
            database,
            access.organization_id,
            project_data,
        )

    except ValidationError as error:
        return templates.TemplateResponse(
            request=request,
            name="project/project_new.html",
            context={
                **authenticated_template_context(access),
                "page_title": "New project",
                "form_values": form_values,
                "error_message": error.errors()[0]["msg"],
            },
            status_code=422,
        )

    except ProjectCodeConflictError as error:
        return templates.TemplateResponse(
            request=request,
            name="project/project_new.html",
            context={
                **authenticated_template_context(access),
                "page_title": "New project",
                "form_values": form_values,
                "error_message": str(error),
            },
            status_code=409,
        )

    except OrganisationNotFoundError as error:
        return templates.TemplateResponse(
            request=request,
            name="project/project_new.html",
            context={
                **authenticated_template_context(access),
                "page_title": "New project",
                "form_values": form_values,
                "error_message": str(error),
            },
            status_code=404,
        )

    return RedirectResponse(
        url=f"/app/projects/{project.id}",
        status_code=303,
    )


@router.get(
    "/app/projects/{project_id}",
    response_class=HTMLResponse,
)
def project_detail_page(
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
            name="project/project_detail.html",
            context={
                **authenticated_template_context(access),
                "page_title": "Project not found",
                "project": None,
                "work_packages": [],
            },
            status_code=404,
        )

    work_packages = list_work_packages(
        database,
        project_id,
        offset=0,
        limit=None,
    )

    return templates.TemplateResponse(
        request=request,
        name="project/project_detail.html",
        context={
            **authenticated_template_context(access),
            "page_title": project.name,
            "project": project,
            "work_packages": work_packages,
        },
    )
