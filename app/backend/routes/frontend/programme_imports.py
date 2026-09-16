from __future__ import annotations

import uuid

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.datastructures import UploadFile

from app.backend.core.auth import FrontendOperationalWriteAccess
from app.backend.core.csrf import verified_form
from app.backend.routes.frontend.common import (
    DatabaseSession,
    authenticated_template_context,
    templates,
)
from app.backend.services.programme_import import (
    InvalidProgrammeImportError,
    ProgrammeImportError,
    confirm_import,
    create_import_preview,
    get_import_for_programme,
)
from app.backend.services.project import get_project

router = APIRouter(include_in_schema=False)

_MAX_XML_BYTES = 10 * 1024 * 1024


def _render_import_page(
    request: Request,
    access: FrontendOperationalWriteAccess,
    *,
    project,
    preview=None,
    import_record=None,
    error_message: str | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="programme/programme_import.html",
        context={
            **authenticated_template_context(access),
            "page_title": "Import Programme",
            "project": project,
            "preview": preview,
            "import_record": import_record,
            "error_message": error_message,
        },
        status_code=status_code,
    )


@router.get(
    "/app/projects/{project_id}/programme/import",
    response_class=HTMLResponse,
)
def programme_import_page(
    request: Request,
    project_id: uuid.UUID,
    database: DatabaseSession,
    access: FrontendOperationalWriteAccess,
) -> HTMLResponse:
    project = get_project(database, project_id, access.organization_id)
    if project is None:
        return _render_import_page(
            request,
            access,
            project=None,
            error_message="Project not found.",
            status_code=404,
        )
    return _render_import_page(request, access, project=project)


@router.post(
    "/app/projects/{project_id}/programme/import",
    response_class=HTMLResponse,
)
async def programme_import_preview(
    request: Request,
    project_id: uuid.UUID,
    database: DatabaseSession,
    access: FrontendOperationalWriteAccess,
) -> HTMLResponse:
    project = get_project(database, project_id, access.organization_id)
    if project is None:
        return _render_import_page(
            request,
            access,
            project=None,
            error_message="Project not found.",
            status_code=404,
        )

    form = await verified_form(request)
    uploaded = form.get("programme_file")
    if not isinstance(uploaded, UploadFile) or not uploaded.filename:
        return _render_import_page(
            request,
            access,
            project=project,
            error_message="Choose a Microsoft Project XML file to import.",
            status_code=422,
        )

    if not uploaded.filename.lower().endswith(".xml"):
        await uploaded.close()
        return _render_import_page(
            request,
            access,
            project=project,
            error_message="The first Programme importer accepts Microsoft Project .xml files only.",
            status_code=422,
        )

    content = await uploaded.read(_MAX_XML_BYTES + 1)
    filename = uploaded.filename
    await uploaded.close()

    if len(content) > _MAX_XML_BYTES:
        return _render_import_page(
            request,
            access,
            project=project,
            error_message="The XML file is larger than the 10 MB import limit.",
            status_code=413,
        )

    try:
        import_record, preview = create_import_preview(
            database,
            project,
            filename=filename,
            content=content,
        )
    except ProgrammeImportError as error:
        return _render_import_page(
            request,
            access,
            project=project,
            error_message=str(error),
            status_code=422,
        )

    return _render_import_page(
        request,
        access,
        project=project,
        preview=preview,
        import_record=import_record,
        status_code=200 if preview.can_confirm else 422,
    )


@router.post(
    "/app/projects/{project_id}/programme/import/{import_id}/confirm",
)
async def programme_import_confirm(
    request: Request,
    project_id: uuid.UUID,
    import_id: uuid.UUID,
    database: DatabaseSession,
    access: FrontendOperationalWriteAccess,
):
    project = get_project(database, project_id, access.organization_id)
    if project is None:
        return _render_import_page(
            request,
            access,
            project=None,
            error_message="Project not found.",
            status_code=404,
        )

    await verified_form(request)

    if project.programme is None:
        return _render_import_page(
            request,
            access,
            project=project,
            error_message="This project does not have a Programme container.",
            status_code=409,
        )

    import_record = get_import_for_programme(
        database,
        project.programme.id,
        import_id,
    )
    if import_record is None:
        return _render_import_page(
            request,
            access,
            project=project,
            error_message="Programme import not found.",
            status_code=404,
        )

    try:
        confirm_import(database, project, import_record)
    except InvalidProgrammeImportError as error:
        return _render_import_page(
            request,
            access,
            project=project,
            error_message=str(error),
            status_code=409,
        )
    except Exception:
        return _render_import_page(
            request,
            access,
            project=project,
            error_message=(
                "The Programme import could not be committed. The previous current "
                "revision remains unchanged."
            ),
            status_code=500,
        )

    return RedirectResponse(
        url=f"/app/projects/{project.id}/programme",
        status_code=303,
    )
