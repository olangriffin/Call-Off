import uuid

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError

from app.backend.core.auth import FrontendOrganisationAccess
from app.backend.core.csrf import verified_form
from app.backend.routes.frontend.common import (
    DatabaseSession,
    authenticated_template_context,
    templates,
)
from app.backend.schemas.work_package import WorkPackageCreate
from app.backend.services.deliverable import (
    list_deliverables_with_review_history,
)
from app.backend.services.package_readiness import (
    calculate_package_readiness,
    latest_approval,
    latest_revision,
)
from app.backend.services.project import get_project
from app.backend.services.work_package import (
    WorkPackageCodeConflictError,
    create_work_package,
    get_work_package,
)

router = APIRouter(
    include_in_schema=False,
)


@router.get(
    "/app/projects/{project_id}/work-packages/new",
    response_class=HTMLResponse,
)
def new_work_package_page(
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
            name="package/work_package_new.html",
            context={
                **authenticated_template_context(access),
                "page_title": "Project not found",
                "project": None,
                "form_values": {},
            },
            status_code=404,
        )

    return templates.TemplateResponse(
        request=request,
        name="package/work_package_new.html",
        context={
            **authenticated_template_context(access),
            "page_title": "New work package",
            "project": project,
            "form_values": {},
        },
    )


@router.post(
    "/app/projects/{project_id}/work-packages/new",
    response_class=HTMLResponse,
)
async def create_work_package_page(
    request: Request,
    project_id: uuid.UUID,
    database: DatabaseSession,
    access: FrontendOrganisationAccess,
):
    project = get_project(
        database,
        project_id,
        access.organization_id,
    )

    if project is None:
        return templates.TemplateResponse(
            request=request,
            name="package/work_package_new.html",
            context={
                **authenticated_template_context(access),
                "page_title": "Project not found",
                "project": None,
                "form_values": {},
            },
            status_code=404,
        )

    form = await verified_form(request)

    form_values = {
        "code": str(form.get("code", "")).strip(),
        "name": str(form.get("name", "")).strip(),
        "package_type": str(form.get("package_type", "")).strip(),
        "description": str(form.get("description", "")).strip(),
        "status": str(form.get("status", "active")).strip(),
        "planned_start": str(form.get("planned_start", "")).strip(),
        "planned_finish": str(form.get("planned_finish", "")).strip(),
        "required_on_site_date": str(
            form.get(
                "required_on_site_date",
                "",
            )
        ).strip(),
    }

    work_package_values = {
        **form_values,
        "package_type": form_values["package_type"] or None,
        "description": form_values["description"] or None,
        "planned_start": form_values["planned_start"] or None,
        "planned_finish": form_values["planned_finish"] or None,
        "required_on_site_date": (form_values["required_on_site_date"] or None),
    }

    try:
        work_package_data = WorkPackageCreate.model_validate(
            work_package_values,
        )

        create_work_package(
            database,
            project,
            work_package_data,
        )

    except ValidationError as error:
        return templates.TemplateResponse(
            request=request,
            name="package/work_package_new.html",
            context={
                **authenticated_template_context(access),
                "page_title": "New work package",
                "project": project,
                "form_values": form_values,
                "error_message": error.errors()[0]["msg"],
            },
            status_code=422,
        )

    except WorkPackageCodeConflictError as error:
        return templates.TemplateResponse(
            request=request,
            name="package/work_package_new.html",
            context={
                **authenticated_template_context(access),
                "page_title": "New work package",
                "project": project,
                "form_values": form_values,
                "error_message": str(error),
            },
            status_code=409,
        )

    return RedirectResponse(
        url=f"/app/projects/{project.id}",
        status_code=303,
    )


@router.get(
    "/app/projects/{project_id}/work-packages/{work_package_id}",
    response_class=HTMLResponse,
)
def work_package_detail_page(
    request: Request,
    project_id: uuid.UUID,
    work_package_id: uuid.UUID,
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
            name="package/work_package_detail.html",
            context={
                **authenticated_template_context(access),
                "page_title": "Work package not found",
                "project": None,
                "work_package": None,
                "deliverables": [],
                "deliverable_rows": [],
            },
            status_code=404,
        )

    work_package = get_work_package(
        database,
        work_package_id,
        project_id,
    )

    if work_package is None:
        return templates.TemplateResponse(
            request=request,
            name="package/work_package_detail.html",
            context={
                **authenticated_template_context(access),
                "page_title": "Work package not found",
                "project": project,
                "work_package": None,
                "deliverables": [],
                "deliverable_rows": [],
            },
            status_code=404,
        )

    deliverables = list_deliverables_with_review_history(
        database,
        work_package_id,
        offset=0,
        limit=None,
    )

    deliverable_rows = []
    for deliverable in deliverables:
        revision = latest_revision(deliverable)
        deliverable_rows.append(
            {
                "deliverable": deliverable,
                "latest_revision": revision,
                "latest_approval": (
                    latest_approval(revision) if revision is not None else None
                ),
            }
        )

    readiness = calculate_package_readiness(
        deliverables,
        work_package.required_on_site_date,
    )

    return templates.TemplateResponse(
        request=request,
        name="package/work_package_detail.html",
        context={
            **authenticated_template_context(access),
            "page_title": work_package.name,
            "project": project,
            "work_package": work_package,
            "deliverables": deliverables,
            "deliverable_rows": deliverable_rows,
            "readiness": readiness,
        },
    )
