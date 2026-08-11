from __future__ import annotations

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
from app.backend.schemas.approval import ApprovalCreate, ApprovalUpdate
from app.backend.schemas.deliverable import DeliverableCreate
from app.backend.schemas.deliverable_revision import DeliverableRevisionCreate
from app.backend.services.approval import (
    InvalidApprovalUpdateError,
    create_approval,
    get_approval,
    update_approval,
    validate_approval_response,
)
from app.backend.services.deliverable import (
    DeliverableReferenceConflictError,
    create_deliverable,
    get_deliverable,
    get_deliverable_with_review_history,
)
from app.backend.services.deliverable_revision import (
    RevisionCodeConflictError,
    create_deliverable_revision,
    get_deliverable_revision,
)
from app.backend.services.package_readiness import (
    latest_approval,
    latest_revision,
)
from app.backend.services.project import get_project
from app.backend.services.work_package import get_work_package

router = APIRouter(include_in_schema=False)


def _form_string(form: object, key: str, default: str = "") -> str:
    value = form.get(key, default)  # type: ignore[attr-defined]
    return str(value or "").strip()


def _not_found_context(
    access: FrontendOrganisationAccess,
    *,
    page_title: str,
    project=None,
    work_package=None,
    deliverable=None,
    revision=None,
    approval=None,
) -> dict[str, object]:
    return {
        **authenticated_template_context(access),
        "page_title": page_title,
        "project": project,
        "work_package": work_package,
        "deliverable": deliverable,
        "revision": revision,
        "approval": approval,
        "form_values": {},
    }


def _resolve_project_and_package(
    database: DatabaseSession,
    access: FrontendOrganisationAccess,
    project_id: uuid.UUID,
    work_package_id: uuid.UUID,
):
    project = get_project(database, project_id, access.organization_id)
    if project is None:
        return None, None

    work_package = get_work_package(database, work_package_id, project_id)
    if work_package is None:
        return project, None

    return project, work_package


@router.get(
    "/app/projects/{project_id}/work-packages/{work_package_id}/deliverables/new",
    response_class=HTMLResponse,
)
def new_deliverable_page(
    request: Request,
    project_id: uuid.UUID,
    work_package_id: uuid.UUID,
    database: DatabaseSession,
    access: FrontendOrganisationAccess,
) -> HTMLResponse:
    project, work_package = _resolve_project_and_package(
        database,
        access,
        project_id,
        work_package_id,
    )

    if project is None or work_package is None:
        return templates.TemplateResponse(
            request=request,
            name="deliverable/deliverable_new.html",
            context=_not_found_context(
                access,
                page_title="Work package not found",
                project=project,
                work_package=work_package,
            ),
            status_code=404,
        )

    return templates.TemplateResponse(
        request=request,
        name="deliverable/deliverable_new.html",
        context={
            **authenticated_template_context(access),
            "page_title": "New deliverable",
            "project": project,
            "work_package": work_package,
            "form_values": {},
        },
    )


@router.post(
    "/app/projects/{project_id}/work-packages/{work_package_id}/deliverables/new",
    response_class=HTMLResponse,
)
async def create_deliverable_page(
    request: Request,
    project_id: uuid.UUID,
    work_package_id: uuid.UUID,
    database: DatabaseSession,
    access: FrontendOrganisationAccess,
):
    project, work_package = _resolve_project_and_package(
        database,
        access,
        project_id,
        work_package_id,
    )

    if project is None or work_package is None:
        return templates.TemplateResponse(
            request=request,
            name="deliverable/deliverable_new.html",
            context=_not_found_context(
                access,
                page_title="Work package not found",
                project=project,
                work_package=work_package,
            ),
            status_code=404,
        )

    form = await verified_form(request)
    form_values = {
        "reference": _form_string(form, "reference"),
        "name": _form_string(form, "name"),
        "deliverable_type": _form_string(form, "deliverable_type"),
        "description": _form_string(form, "description"),
        "status": _form_string(form, "status", "not_started"),
        "planned_issue_date": _form_string(form, "planned_issue_date"),
        "required_approval_date": _form_string(form, "required_approval_date"),
    }

    values = {
        **form_values,
        "description": form_values["description"] or None,
        "planned_issue_date": form_values["planned_issue_date"] or None,
        "required_approval_date": form_values["required_approval_date"] or None,
    }

    try:
        deliverable_data = DeliverableCreate.model_validate(values)
        deliverable = create_deliverable(
            database,
            work_package,
            deliverable_data,
        )
    except ValidationError as error:
        return templates.TemplateResponse(
            request=request,
            name="deliverable/deliverable_new.html",
            context={
                **authenticated_template_context(access),
                "page_title": "New deliverable",
                "project": project,
                "work_package": work_package,
                "form_values": form_values,
                "error_message": error.errors()[0]["msg"],
            },
            status_code=422,
        )
    except DeliverableReferenceConflictError as error:
        return templates.TemplateResponse(
            request=request,
            name="deliverable/deliverable_new.html",
            context={
                **authenticated_template_context(access),
                "page_title": "New deliverable",
                "project": project,
                "work_package": work_package,
                "form_values": form_values,
                "error_message": str(error),
            },
            status_code=409,
        )

    return RedirectResponse(
        url=(
            f"/app/projects/{project.id}/work-packages/{work_package.id}"
            f"/deliverables/{deliverable.id}"
        ),
        status_code=303,
    )


@router.get(
    "/app/projects/{project_id}/work-packages/{work_package_id}"
    "/deliverables/{deliverable_id}",
    response_class=HTMLResponse,
)
def deliverable_detail_page(
    request: Request,
    project_id: uuid.UUID,
    work_package_id: uuid.UUID,
    deliverable_id: uuid.UUID,
    database: DatabaseSession,
    access: FrontendOrganisationAccess,
) -> HTMLResponse:
    project, work_package = _resolve_project_and_package(
        database,
        access,
        project_id,
        work_package_id,
    )

    deliverable = None
    if work_package is not None:
        deliverable = get_deliverable_with_review_history(
            database,
            deliverable_id,
            work_package_id,
        )

    if project is None or work_package is None or deliverable is None:
        return templates.TemplateResponse(
            request=request,
            name="deliverable/deliverable_detail.html",
            context=_not_found_context(
                access,
                page_title="Deliverable not found",
                project=project,
                work_package=work_package,
                deliverable=deliverable,
            ),
            status_code=404,
        )

    revisions = sorted(
        deliverable.revisions,
        key=lambda item: (
            item.issue_date is not None,
            item.issue_date,
            item.revision_code,
        ),
        reverse=True,
    )
    current_revision = latest_revision(deliverable)
    current_approval = (
        latest_approval(current_revision)
        if current_revision is not None
        else None
    )

    return templates.TemplateResponse(
        request=request,
        name="deliverable/deliverable_detail.html",
        context={
            **authenticated_template_context(access),
            "page_title": deliverable.name,
            "project": project,
            "work_package": work_package,
            "deliverable": deliverable,
            "revisions": revisions,
            "current_revision": current_revision,
            "current_approval": current_approval,
            "historical_revisions": revisions[1:],
        },
    )


@router.get(
    "/app/projects/{project_id}/work-packages/{work_package_id}"
    "/deliverables/{deliverable_id}/revisions/new",
    response_class=HTMLResponse,
)
def new_revision_page(
    request: Request,
    project_id: uuid.UUID,
    work_package_id: uuid.UUID,
    deliverable_id: uuid.UUID,
    database: DatabaseSession,
    access: FrontendOrganisationAccess,
) -> HTMLResponse:
    project, work_package = _resolve_project_and_package(
        database,
        access,
        project_id,
        work_package_id,
    )
    deliverable = None
    if work_package is not None:
        deliverable = get_deliverable(
            database,
            deliverable_id,
            work_package_id,
        )

    if project is None or work_package is None or deliverable is None:
        return templates.TemplateResponse(
            request=request,
            name="deliverable/deliverable_revision_new.html",
            context=_not_found_context(
                access,
                page_title="Deliverable not found",
                project=project,
                work_package=work_package,
                deliverable=deliverable,
            ),
            status_code=404,
        )

    return templates.TemplateResponse(
        request=request,
        name="deliverable/deliverable_revision_new.html",
        context={
            **authenticated_template_context(access),
            "page_title": "New revision",
            "project": project,
            "work_package": work_package,
            "deliverable": deliverable,
            "form_values": {},
        },
    )


@router.post(
    "/app/projects/{project_id}/work-packages/{work_package_id}"
    "/deliverables/{deliverable_id}/revisions/new",
    response_class=HTMLResponse,
)
async def create_revision_page(
    request: Request,
    project_id: uuid.UUID,
    work_package_id: uuid.UUID,
    deliverable_id: uuid.UUID,
    database: DatabaseSession,
    access: FrontendOrganisationAccess,
):
    project, work_package = _resolve_project_and_package(
        database,
        access,
        project_id,
        work_package_id,
    )
    deliverable = None
    if work_package is not None:
        deliverable = get_deliverable(
            database,
            deliverable_id,
            work_package_id,
        )

    if project is None or work_package is None or deliverable is None:
        return templates.TemplateResponse(
            request=request,
            name="deliverable/deliverable_revision_new.html",
            context=_not_found_context(
                access,
                page_title="Deliverable not found",
                project=project,
                work_package=work_package,
                deliverable=deliverable,
            ),
            status_code=404,
        )

    form = await verified_form(request)
    form_values = {
        "revision_code": _form_string(form, "revision_code"),
        "status": "issued",
        "issue_purpose": _form_string(form, "issue_purpose"),
        "issue_date": _form_string(form, "issue_date"),
        "notes": _form_string(form, "notes"),
    }

    values = {
        **form_values,
        "issue_purpose": form_values["issue_purpose"] or None,
        "issue_date": form_values["issue_date"] or None,
        "notes": form_values["notes"] or None,
    }

    try:
        revision_data = DeliverableRevisionCreate.model_validate(values)
        create_deliverable_revision(database, deliverable, revision_data)
    except ValidationError as error:
        return templates.TemplateResponse(
            request=request,
            name="deliverable/deliverable_revision_new.html",
            context={
                **authenticated_template_context(access),
                "page_title": "New revision",
                "project": project,
                "work_package": work_package,
                "deliverable": deliverable,
                "form_values": form_values,
                "error_message": error.errors()[0]["msg"],
            },
            status_code=422,
        )
    except RevisionCodeConflictError as error:
        return templates.TemplateResponse(
            request=request,
            name="deliverable/deliverable_revision_new.html",
            context={
                **authenticated_template_context(access),
                "page_title": "New revision",
                "project": project,
                "work_package": work_package,
                "deliverable": deliverable,
                "form_values": form_values,
                "error_message": str(error),
            },
            status_code=409,
        )

    return RedirectResponse(
        url=(
            f"/app/projects/{project.id}/work-packages/{work_package.id}"
            f"/deliverables/{deliverable.id}"
        ),
        status_code=303,
    )


def _approval_response_context(
    access: FrontendOrganisationAccess,
    *,
    project,
    work_package,
    deliverable,
    revision,
    approval,
    form_values: dict[str, object],
    error_message: str | None = None,
) -> dict[str, object]:
    context = {
        **authenticated_template_context(access),
        "page_title": "Record approval response",
        "project": project,
        "work_package": work_package,
        "deliverable": deliverable,
        "revision": revision,
        "approval": approval,
        "form_values": form_values,
    }
    if error_message is not None:
        context["error_message"] = error_message
    return context


def _resolve_approval_hierarchy(
    database: DatabaseSession,
    access: FrontendOrganisationAccess,
    project_id: uuid.UUID,
    work_package_id: uuid.UUID,
    deliverable_id: uuid.UUID,
    revision_id: uuid.UUID,
    approval_id: uuid.UUID,
):
    project, work_package = _resolve_project_and_package(
        database,
        access,
        project_id,
        work_package_id,
    )
    deliverable = None
    revision = None
    approval = None
    if work_package is not None:
        deliverable = get_deliverable(database, deliverable_id, work_package_id)
    if deliverable is not None:
        revision = get_deliverable_revision(database, revision_id, deliverable_id)
    if revision is not None:
        approval = get_approval(database, approval_id, revision_id)
    return project, work_package, deliverable, revision, approval


@router.get(
    "/app/projects/{project_id}/work-packages/{work_package_id}"
    "/deliverables/{deliverable_id}/revisions/{revision_id}"
    "/approvals/{approval_id}/respond",
    response_class=HTMLResponse,
)
def approval_response_page(
    request: Request,
    project_id: uuid.UUID,
    work_package_id: uuid.UUID,
    deliverable_id: uuid.UUID,
    revision_id: uuid.UUID,
    approval_id: uuid.UUID,
    database: DatabaseSession,
    access: FrontendOrganisationAccess,
) -> HTMLResponse:
    project, work_package, deliverable, revision, approval = (
        _resolve_approval_hierarchy(
            database,
            access,
            project_id,
            work_package_id,
            deliverable_id,
            revision_id,
            approval_id,
        )
    )
    if approval is None:
        return templates.TemplateResponse(
            request=request,
            name="deliverable/approval_response.html",
            context=_approval_response_context(
                access,
                project=project,
                work_package=work_package,
                deliverable=deliverable,
                revision=revision,
                approval=approval,
                form_values={},
            ),
            status_code=404,
        )

    return templates.TemplateResponse(
        request=request,
        name="deliverable/approval_response.html",
        context=_approval_response_context(
            access,
            project=project,
            work_package=work_package,
            deliverable=deliverable,
            revision=revision,
            approval=approval,
            form_values={
                "status": approval.status,
                "response_received_date": approval.response_received_date or "",
                "comments": approval.comments or "",
            },
        ),
    )


@router.post(
    "/app/projects/{project_id}/work-packages/{work_package_id}"
    "/deliverables/{deliverable_id}/revisions/{revision_id}"
    "/approvals/{approval_id}/respond",
    response_class=HTMLResponse,
)
async def update_approval_response_page(
    request: Request,
    project_id: uuid.UUID,
    work_package_id: uuid.UUID,
    deliverable_id: uuid.UUID,
    revision_id: uuid.UUID,
    approval_id: uuid.UUID,
    database: DatabaseSession,
    access: FrontendOrganisationAccess,
):
    project, work_package, deliverable, revision, approval = (
        _resolve_approval_hierarchy(
            database,
            access,
            project_id,
            work_package_id,
            deliverable_id,
            revision_id,
            approval_id,
        )
    )
    if approval is None:
        return templates.TemplateResponse(
            request=request,
            name="deliverable/approval_response.html",
            context=_approval_response_context(
                access,
                project=project,
                work_package=work_package,
                deliverable=deliverable,
                revision=revision,
                approval=approval,
                form_values={},
            ),
            status_code=404,
        )

    form = await verified_form(request)
    form_values = {
        "status": _form_string(form, "status"),
        "response_received_date": _form_string(
            form, "response_received_date"
        ),
        "comments": _form_string(form, "comments"),
    }
    values = {
        "status": form_values["status"],
        "response_received_date": form_values["response_received_date"] or None,
        "comments": form_values["comments"] or None,
    }

    try:
        approval_data = ApprovalUpdate.model_validate(values)
        validate_approval_response(
            approval_data.status or "",
            approval_data.response_received_date,
        )
        update_approval(database, approval, approval_data)
    except (ValidationError, InvalidApprovalUpdateError) as error:
        if isinstance(error, ValidationError):
            error_message = error.errors()[0]["msg"]
        else:
            error_message = str(error)
        return templates.TemplateResponse(
            request=request,
            name="deliverable/approval_response.html",
            context=_approval_response_context(
                access,
                project=project,
                work_package=work_package,
                deliverable=deliverable,
                revision=revision,
                approval=approval,
                form_values=form_values,
                error_message=error_message,
            ),
            status_code=422,
        )

    return RedirectResponse(
        url=(
            f"/app/projects/{project.id}/work-packages/{work_package.id}"
            f"/deliverables/{deliverable.id}"
        ),
        status_code=303,
    )


@router.get(
    "/app/projects/{project_id}/work-packages/{work_package_id}"
    "/deliverables/{deliverable_id}/revisions/{revision_id}/approvals/new",
    response_class=HTMLResponse,
)
def new_approval_page(
    request: Request,
    project_id: uuid.UUID,
    work_package_id: uuid.UUID,
    deliverable_id: uuid.UUID,
    revision_id: uuid.UUID,
    database: DatabaseSession,
    access: FrontendOrganisationAccess,
) -> HTMLResponse:
    project, work_package = _resolve_project_and_package(
        database,
        access,
        project_id,
        work_package_id,
    )
    deliverable = None
    revision = None
    if work_package is not None:
        deliverable = get_deliverable(database, deliverable_id, work_package_id)
    if deliverable is not None:
        revision = get_deliverable_revision(database, revision_id, deliverable_id)

    if (
        project is None
        or work_package is None
        or deliverable is None
        or revision is None
    ):
        return templates.TemplateResponse(
            request=request,
            name="deliverable/approval_new.html",
            context=_not_found_context(
                access,
                page_title="Revision not found",
                project=project,
                work_package=work_package,
                deliverable=deliverable,
                revision=revision,
            ),
            status_code=404,
        )

    return templates.TemplateResponse(
        request=request,
        name="deliverable/approval_new.html",
        context={
            **authenticated_template_context(access),
            "page_title": "Send for approval",
            "project": project,
            "work_package": work_package,
            "deliverable": deliverable,
            "revision": revision,
            "form_values": {},
        },
    )


@router.post(
    "/app/projects/{project_id}/work-packages/{work_package_id}"
    "/deliverables/{deliverable_id}/revisions/{revision_id}/approvals/new",
    response_class=HTMLResponse,
)
async def create_approval_page(
    request: Request,
    project_id: uuid.UUID,
    work_package_id: uuid.UUID,
    deliverable_id: uuid.UUID,
    revision_id: uuid.UUID,
    database: DatabaseSession,
    access: FrontendOrganisationAccess,
):
    project, work_package = _resolve_project_and_package(
        database,
        access,
        project_id,
        work_package_id,
    )
    deliverable = None
    revision = None
    if work_package is not None:
        deliverable = get_deliverable(database, deliverable_id, work_package_id)
    if deliverable is not None:
        revision = get_deliverable_revision(database, revision_id, deliverable_id)

    if (
        project is None
        or work_package is None
        or deliverable is None
        or revision is None
    ):
        return templates.TemplateResponse(
            request=request,
            name="deliverable/approval_new.html",
            context=_not_found_context(
                access,
                page_title="Revision not found",
                project=project,
                work_package=work_package,
                deliverable=deliverable,
                revision=revision,
            ),
            status_code=404,
        )

    form = await verified_form(request)
    form_values = {
        "approval_stage": _form_string(form, "approval_stage", "external_review"),
        "reviewer_name": _form_string(form, "reviewer_name"),
        "status": "pending",
        "submitted_date": _form_string(form, "submitted_date"),
        "response_due_date": _form_string(form, "response_due_date"),
        "response_received_date": "",
        "comments": "",
    }

    values = {
        **form_values,
        "reviewer_name": form_values["reviewer_name"] or None,
        "submitted_date": form_values["submitted_date"] or None,
        "response_due_date": form_values["response_due_date"] or None,
        "response_received_date": form_values["response_received_date"] or None,
        "comments": form_values["comments"] or None,
    }

    try:
        approval_data = ApprovalCreate.model_validate(values)
        create_approval(database, revision, approval_data)
    except ValidationError as error:
        return templates.TemplateResponse(
            request=request,
            name="deliverable/approval_new.html",
            context={
                **authenticated_template_context(access),
                "page_title": "Send for approval",
                "project": project,
                "work_package": work_package,
                "deliverable": deliverable,
                "revision": revision,
                "form_values": form_values,
                "error_message": error.errors()[0]["msg"],
            },
            status_code=422,
        )

    return RedirectResponse(
        url=(
            f"/app/projects/{project.id}/work-packages/{work_package.id}"
            f"/deliverables/{deliverable.id}"
        ),
        status_code=303,
    )
