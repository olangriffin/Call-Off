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
from app.backend.schemas.programme_activity import (
    ProgrammeActivityCreate,
    ProgrammeActivityUpdate,
)
from app.backend.services.programme import get_or_create_current_revision
from app.backend.services.programme_activity import (
    InvalidProgrammeActivityUpdateError,
    ProgrammeActivityCodeConflictError,
    ProgrammeActivityHasChildrenError,
    ProgrammeActivityParentCycleError,
    ProgrammeActivityParentNotFoundError,
    ProgrammeActivityWorkPackageNotFoundError,
    build_activity_tree,
    create_activity,
    delete_activity,
    get_activity,
    get_descendant_ids,
    list_activities,
    update_activity,
)
from app.backend.services.programme_workspace import build_programme_workspace
from app.backend.services.project import get_project
from app.backend.services.work_package import list_work_packages

router = APIRouter(
    include_in_schema=False,
)


def _build_parent_options(
    activities: list,
    exclude_ids: set[uuid.UUID],
) -> list[dict]:
    return [
        {
            "id": row["activity"].id,
            "label": ("— " * row["depth"]) + row["activity"].name,
        }
        for row in build_activity_tree(activities)
        if row["activity"].id not in exclude_ids
    ]


def _activity_form_values(activity) -> dict:
    return {
        "activity_code": activity.activity_code,
        "name": activity.name,
        "activity_type": activity.activity_type,
        "work_package_id": (
            str(activity.work_package_id) if activity.work_package_id else ""
        ),
        "parent_activity_id": (
            str(activity.parent_activity_id) if activity.parent_activity_id else ""
        ),
        "planned_start": (
            activity.planned_start.strftime("%Y-%m-%d")
            if activity.planned_start
            else ""
        ),
        "planned_finish": (
            activity.planned_finish.strftime("%Y-%m-%d")
            if activity.planned_finish
            else ""
        ),
        "is_milestone": activity.is_milestone,
        "status": activity.status,
        "notes": activity.notes or "",
    }


@router.get(
    "/app/projects/{project_id}/programme/new",
    response_class=HTMLResponse,
)
def new_programme_activity_page(
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
            name="programme/programme_activity_new.html",
            context={
                **authenticated_template_context(access),
                "page_title": "Project not found",
                "project": None,
                "work_packages": [],
                "form_values": {},
            },
            status_code=404,
        )

    work_packages = list_work_packages(
        database,
        project_id,
        offset=0,
        limit=None,
    )

    revision = get_or_create_current_revision(database, project)

    activities = list_activities(
        database,
        revision.id,
        offset=0,
        limit=None,
    )

    parent_options = [
        {
            "id": row["activity"].id,
            "label": ("— " * row["depth"]) + row["activity"].name,
        }
        for row in build_activity_tree(activities)
    ]

    return templates.TemplateResponse(
        request=request,
        name="programme/programme_activity_new.html",
        context={
            **authenticated_template_context(access),
            "page_title": "New activity",
            "project": project,
            "work_packages": work_packages,
            "parent_options": parent_options,
            "form_values": {},
        },
    )


@router.post(
    "/app/projects/{project_id}/programme/new",
    response_class=HTMLResponse,
)
async def create_programme_activity_page(
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
            name="programme/programme_activity_new.html",
            context={
                **authenticated_template_context(access),
                "page_title": "Project not found",
                "project": None,
                "work_packages": [],
                "form_values": {},
            },
            status_code=404,
        )

    form = await verified_form(request)

    form_values = {
        "activity_code": str(form.get("activity_code", "")).strip(),
        "name": str(form.get("name", "")).strip(),
        "activity_type": str(form.get("activity_type", "task")).strip(),
        "work_package_id": str(form.get("work_package_id", "")).strip(),
        "parent_activity_id": str(form.get("parent_activity_id", "")).strip(),
        "planned_start": str(form.get("planned_start", "")).strip(),
        "planned_finish": str(form.get("planned_finish", "")).strip(),
        "is_milestone": (
            str(form.get("activity_type", "task")).strip() == "milestone"
        ),
        "status": str(form.get("status", "not_started")).strip(),
        "notes": str(form.get("notes", "")).strip(),
    }

    activity_values = {
        **form_values,
        "work_package_id": form_values["work_package_id"] or None,
        "parent_activity_id": form_values["parent_activity_id"] or None,
        "planned_start": form_values["planned_start"] or None,
        "planned_finish": form_values["planned_finish"] or None,
        "notes": form_values["notes"] or None,
    }

    work_packages = list_work_packages(
        database,
        project_id,
        offset=0,
        limit=None,
    )

    revision_for_options = get_or_create_current_revision(database, project)

    existing_activities = list_activities(
        database,
        revision_for_options.id,
        offset=0,
        limit=None,
    )

    parent_options = [
        {
            "id": row["activity"].id,
            "label": ("— " * row["depth"]) + row["activity"].name,
        }
        for row in build_activity_tree(existing_activities)
    ]

    try:
        activity_data = ProgrammeActivityCreate.model_validate(
            activity_values,
        )

        revision = get_or_create_current_revision(database, project)

        create_activity(
            database,
            revision,
            activity_data,
        )

    except ValidationError as error:
        return templates.TemplateResponse(
            request=request,
            name="programme/programme_activity_new.html",
            context={
                **authenticated_template_context(access),
                "page_title": "New activity",
                "project": project,
                "work_packages": work_packages,
                "parent_options": parent_options,
                "form_values": form_values,
                "error_message": error.errors()[0]["msg"],
            },
            status_code=422,
        )

    except ProgrammeActivityCodeConflictError as error:
        return templates.TemplateResponse(
            request=request,
            name="programme/programme_activity_new.html",
            context={
                **authenticated_template_context(access),
                "page_title": "New activity",
                "project": project,
                "work_packages": work_packages,
                "parent_options": parent_options,
                "form_values": form_values,
                "error_message": str(error),
            },
            status_code=409,
        )

    except (
        ProgrammeActivityParentNotFoundError,
        ProgrammeActivityWorkPackageNotFoundError,
    ) as error:
        return templates.TemplateResponse(
            request=request,
            name="programme/programme_activity_new.html",
            context={
                **authenticated_template_context(access),
                "page_title": "New activity",
                "project": project,
                "work_packages": work_packages,
                "parent_options": parent_options,
                "form_values": form_values,
                "error_message": str(error),
            },
            status_code=422,
        )

    return RedirectResponse(
        url=f"/app/projects/{project.id}/programme",
        status_code=303,
    )


@router.get(
    "/app/projects/{project_id}/programme/{activity_id}/edit",
    response_class=HTMLResponse,
)
def edit_programme_activity_page(
    request: Request,
    project_id: uuid.UUID,
    activity_id: uuid.UUID,
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
            name="programme/programme_activity_edit.html",
            context={
                **authenticated_template_context(access),
                "page_title": "Project not found",
                "project": None,
                "activity": None,
                "work_packages": [],
                "parent_options": [],
                "form_values": {},
            },
            status_code=404,
        )

    revision = get_or_create_current_revision(database, project)

    activity = get_activity(database, activity_id, revision.id)

    if activity is None:
        return templates.TemplateResponse(
            request=request,
            name="programme/programme_activity_edit.html",
            context={
                **authenticated_template_context(access),
                "page_title": "Activity not found",
                "project": project,
                "activity": None,
                "work_packages": [],
                "parent_options": [],
                "form_values": {},
            },
            status_code=404,
        )

    work_packages = list_work_packages(
        database,
        project_id,
        offset=0,
        limit=None,
    )

    activities = list_activities(
        database,
        revision.id,
        offset=0,
        limit=None,
    )

    exclude_ids = get_descendant_ids(activities, activity.id)
    exclude_ids.add(activity.id)

    return templates.TemplateResponse(
        request=request,
        name="programme/programme_activity_edit.html",
        context={
            **authenticated_template_context(access),
            "page_title": "Edit activity",
            "project": project,
            "activity": activity,
            "work_packages": work_packages,
            "parent_options": _build_parent_options(activities, exclude_ids),
            "form_values": _activity_form_values(activity),
        },
    )


@router.post(
    "/app/projects/{project_id}/programme/{activity_id}/edit",
    response_class=HTMLResponse,
)
async def update_programme_activity_page(
    request: Request,
    project_id: uuid.UUID,
    activity_id: uuid.UUID,
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
            name="programme/programme_activity_edit.html",
            context={
                **authenticated_template_context(access),
                "page_title": "Project not found",
                "project": None,
                "activity": None,
                "work_packages": [],
                "parent_options": [],
                "form_values": {},
            },
            status_code=404,
        )

    revision = get_or_create_current_revision(database, project)

    activity = get_activity(database, activity_id, revision.id)

    if activity is None:
        return templates.TemplateResponse(
            request=request,
            name="programme/programme_activity_edit.html",
            context={
                **authenticated_template_context(access),
                "page_title": "Activity not found",
                "project": project,
                "activity": None,
                "work_packages": [],
                "parent_options": [],
                "form_values": {},
            },
            status_code=404,
        )

    form = await verified_form(request)

    form_values = {
        "activity_code": str(form.get("activity_code", "")).strip(),
        "name": str(form.get("name", "")).strip(),
        "activity_type": str(form.get("activity_type", "task")).strip(),
        "work_package_id": str(form.get("work_package_id", "")).strip(),
        "parent_activity_id": str(form.get("parent_activity_id", "")).strip(),
        "planned_start": str(form.get("planned_start", "")).strip(),
        "planned_finish": str(form.get("planned_finish", "")).strip(),
        "is_milestone": (
            str(form.get("activity_type", "task")).strip() == "milestone"
        ),
        "status": str(form.get("status", "not_started")).strip(),
        "notes": str(form.get("notes", "")).strip(),
    }

    activity_values = {
        **form_values,
        "work_package_id": form_values["work_package_id"] or None,
        "parent_activity_id": form_values["parent_activity_id"] or None,
        "planned_start": form_values["planned_start"] or None,
        "planned_finish": form_values["planned_finish"] or None,
        "notes": form_values["notes"] or None,
    }

    work_packages = list_work_packages(
        database,
        project_id,
        offset=0,
        limit=None,
    )

    activities = list_activities(
        database,
        revision.id,
        offset=0,
        limit=None,
    )

    exclude_ids = get_descendant_ids(activities, activity.id)
    exclude_ids.add(activity.id)

    parent_options = _build_parent_options(activities, exclude_ids)

    try:
        activity_data = ProgrammeActivityUpdate.model_validate(
            activity_values,
        )

        update_activity(database, activity, activity_data)

    except ValidationError as error:
        return templates.TemplateResponse(
            request=request,
            name="programme/programme_activity_edit.html",
            context={
                **authenticated_template_context(access),
                "page_title": "Edit activity",
                "project": project,
                "activity": activity,
                "work_packages": work_packages,
                "parent_options": parent_options,
                "form_values": form_values,
                "error_message": error.errors()[0]["msg"],
            },
            status_code=422,
        )

    except (
        InvalidProgrammeActivityUpdateError,
        ProgrammeActivityParentNotFoundError,
        ProgrammeActivityParentCycleError,
        ProgrammeActivityWorkPackageNotFoundError,
    ) as error:
        return templates.TemplateResponse(
            request=request,
            name="programme/programme_activity_edit.html",
            context={
                **authenticated_template_context(access),
                "page_title": "Edit activity",
                "project": project,
                "activity": activity,
                "work_packages": work_packages,
                "parent_options": parent_options,
                "form_values": form_values,
                "error_message": str(error),
            },
            status_code=422,
        )

    except ProgrammeActivityCodeConflictError as error:
        return templates.TemplateResponse(
            request=request,
            name="programme/programme_activity_edit.html",
            context={
                **authenticated_template_context(access),
                "page_title": "Edit activity",
                "project": project,
                "activity": activity,
                "work_packages": work_packages,
                "parent_options": parent_options,
                "form_values": form_values,
                "error_message": str(error),
            },
            status_code=409,
        )

    return RedirectResponse(
        url=f"/app/projects/{project.id}/programme",
        status_code=303,
    )


@router.post(
    "/app/projects/{project_id}/programme/{activity_id}/delete",
    response_class=HTMLResponse,
)
async def delete_programme_activity_page(
    request: Request,
    project_id: uuid.UUID,
    activity_id: uuid.UUID,
    database: DatabaseSession,
    access: FrontendOrganisationAccess,
):
    await verified_form(request)
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
                "activity_rows": [],
            },
            status_code=404,
        )

    revision = get_or_create_current_revision(database, project)

    activity = get_activity(database, activity_id, revision.id)

    if activity is None:
        activities = list_activities(database, revision.id, offset=0, limit=None)
        activity_rows = build_activity_tree(activities)

        return templates.TemplateResponse(
            request=request,
            name="programme/programme.html",
            context={
                **authenticated_template_context(access),
                "page_title": "Programme",
                "project": project,
                "revision": revision,
                "activity_rows": activity_rows,
                "workspace": build_programme_workspace(activity_rows),
                "error_message": "Activity was not found.",
            },
            status_code=404,
        )

    try:
        delete_activity(database, activity)
    except ProgrammeActivityHasChildrenError as error:
        activities = list_activities(database, revision.id, offset=0, limit=None)

        activity_rows = build_activity_tree(activities)

        return templates.TemplateResponse(
            request=request,
            name="programme/programme.html",
            context={
                **authenticated_template_context(access),
                "page_title": "Programme",
                "project": project,
                "revision": revision,
                "activity_rows": activity_rows,
                "workspace": build_programme_workspace(activity_rows),
                "error_message": str(error),
            },
            status_code=409,
        )

    return RedirectResponse(
        url=f"/app/projects/{project.id}/programme",
        status_code=303,
    )
