from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Response,
    status,
)
from sqlalchemy.orm import Session

from app.backend.database.session import get_db
from app.backend.models.package.deliverable import Deliverable
from app.backend.models.package.package import WorkPackage
from app.backend.models.package.revision import DeliverableRevision
from app.backend.models.project import Project
from app.backend.schemas.approval import (
    ApprovalCreate,
    ApprovalRead,
    ApprovalUpdate,
)
from app.backend.services.approval import (
    InvalidApprovalUpdateError,
    create_approval,
    delete_approval,
    get_approval,
    list_approvals,
    update_approval,
)
from app.backend.services.deliverable import get_deliverable
from app.backend.services.deliverable_revision import (
    get_deliverable_revision,
)
from app.backend.services.project import get_project
from app.backend.services.work_package import get_work_package

router = APIRouter(
    prefix=(
        "/projects/{project_id}"
        "/work-packages/{work_package_id}"
        "/deliverables/{deliverable_id}"
        "/revisions/{revision_id}"
        "/approvals"
    ),
    tags=["Approvals"],
)

DatabaseSession = Annotated[Session, Depends(get_db)]


def require_project(
    database: Session,
    project_id: uuid.UUID,
    organization_id: str,
) -> Project:
    project = get_project(
        database,
        project_id,
        organization_id,
    )

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project was not found.",
        )

    return project


def require_work_package(
    database: Session,
    project_id: uuid.UUID,
    work_package_id: uuid.UUID,
    organization_id: str,
) -> WorkPackage:
    require_project(
        database,
        project_id,
        organization_id,
    )

    work_package = get_work_package(
        database,
        work_package_id,
        project_id,
    )

    if work_package is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Work package was not found.",
        )

    return work_package


def require_deliverable(
    database: Session,
    project_id: uuid.UUID,
    work_package_id: uuid.UUID,
    deliverable_id: uuid.UUID,
    organization_id: str,
) -> Deliverable:
    require_work_package(
        database,
        project_id,
        work_package_id,
        organization_id,
    )

    deliverable = get_deliverable(
        database,
        deliverable_id,
        work_package_id,
    )

    if deliverable is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Deliverable was not found.",
        )

    return deliverable


def require_revision(
    database: Session,
    project_id: uuid.UUID,
    work_package_id: uuid.UUID,
    deliverable_id: uuid.UUID,
    revision_id: uuid.UUID,
    organization_id: str,
) -> DeliverableRevision:
    require_deliverable(
        database,
        project_id,
        work_package_id,
        deliverable_id,
        organization_id,
    )

    revision = get_deliverable_revision(
        database,
        revision_id,
        deliverable_id,
    )

    if revision is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Deliverable revision was not found.",
        )

    return revision


@router.post(
    "",
    response_model=ApprovalRead,
    status_code=status.HTTP_201_CREATED,
)
def create_approval_route(
    project_id: uuid.UUID,
    work_package_id: uuid.UUID,
    deliverable_id: uuid.UUID,
    revision_id: uuid.UUID,
    approval_data: ApprovalCreate,
    database: DatabaseSession,
    organization_id: Annotated[str, Query(min_length=1)],
) -> ApprovalRead:
    revision = require_revision(
        database,
        project_id,
        work_package_id,
        deliverable_id,
        revision_id,
        organization_id,
    )

    return create_approval(
        database,
        revision,
        approval_data,
    )


@router.get(
    "",
    response_model=list[ApprovalRead],
)
def list_approvals_route(
    project_id: uuid.UUID,
    work_package_id: uuid.UUID,
    deliverable_id: uuid.UUID,
    revision_id: uuid.UUID,
    database: DatabaseSession,
    organization_id: Annotated[str, Query(min_length=1)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[ApprovalRead]:
    require_revision(
        database,
        project_id,
        work_package_id,
        deliverable_id,
        revision_id,
        organization_id,
    )

    return list_approvals(
        database,
        revision_id,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/{approval_id}",
    response_model=ApprovalRead,
)
def get_approval_route(
    project_id: uuid.UUID,
    work_package_id: uuid.UUID,
    deliverable_id: uuid.UUID,
    revision_id: uuid.UUID,
    approval_id: uuid.UUID,
    database: DatabaseSession,
    organization_id: Annotated[str, Query(min_length=1)],
) -> ApprovalRead:
    require_revision(
        database,
        project_id,
        work_package_id,
        deliverable_id,
        revision_id,
        organization_id,
    )

    approval = get_approval(
        database,
        approval_id,
        revision_id,
    )

    if approval is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Approval was not found.",
        )

    return approval


@router.patch(
    "/{approval_id}",
    response_model=ApprovalRead,
)
def update_approval_route(
    project_id: uuid.UUID,
    work_package_id: uuid.UUID,
    deliverable_id: uuid.UUID,
    revision_id: uuid.UUID,
    approval_id: uuid.UUID,
    approval_data: ApprovalUpdate,
    database: DatabaseSession,
    organization_id: Annotated[str, Query(min_length=1)],
) -> ApprovalRead:
    require_revision(
        database,
        project_id,
        work_package_id,
        deliverable_id,
        revision_id,
        organization_id,
    )

    approval = get_approval(
        database,
        approval_id,
        revision_id,
    )

    if approval is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Approval was not found.",
        )

    try:
        return update_approval(
            database,
            approval,
            approval_data,
        )
    except InvalidApprovalUpdateError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error


@router.delete(
    "/{approval_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_approval_route(
    project_id: uuid.UUID,
    work_package_id: uuid.UUID,
    deliverable_id: uuid.UUID,
    revision_id: uuid.UUID,
    approval_id: uuid.UUID,
    database: DatabaseSession,
    organization_id: Annotated[str, Query(min_length=1)],
) -> Response:
    require_revision(
        database,
        project_id,
        work_package_id,
        deliverable_id,
        revision_id,
        organization_id,
    )

    approval = get_approval(
        database,
        approval_id,
        revision_id,
    )

    if approval is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Approval was not found.",
        )

    delete_approval(
        database,
        approval,
    )

    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
    )
