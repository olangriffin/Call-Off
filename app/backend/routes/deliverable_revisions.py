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
from app.backend.models.project import Project
from app.backend.schemas.deliverable_revision import (
    DeliverableRevisionCreate,
    DeliverableRevisionRead,
    DeliverableRevisionUpdate,
)
from app.backend.services.deliverable import get_deliverable
from app.backend.services.deliverable_revision import (
    InvalidDeliverableRevisionUpdateError,
    RevisionCodeConflictError,
    create_deliverable_revision,
    delete_deliverable_revision,
    get_deliverable_revision,
    list_deliverable_revisions,
    update_deliverable_revision,
)
from app.backend.services.project import get_project
from app.backend.services.work_package import get_work_package

router = APIRouter(
    prefix=(
        "/projects/{project_id}"
        "/work-packages/{work_package_id}"
        "/deliverables/{deliverable_id}"
        "/revisions"
    ),
    tags=["Deliverable Revisions"],
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


@router.post(
    "",
    response_model=DeliverableRevisionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_deliverable_revision_route(
    project_id: uuid.UUID,
    work_package_id: uuid.UUID,
    deliverable_id: uuid.UUID,
    revision_data: DeliverableRevisionCreate,
    database: DatabaseSession,
    organization_id: Annotated[str, Query(min_length=1)],
) -> DeliverableRevisionRead:
    deliverable = require_deliverable(
        database,
        project_id,
        work_package_id,
        deliverable_id,
        organization_id,
    )

    try:
        return create_deliverable_revision(
            database,
            deliverable,
            revision_data,
        )
    except RevisionCodeConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error


@router.get(
    "",
    response_model=list[DeliverableRevisionRead],
)
def list_deliverable_revisions_route(
    project_id: uuid.UUID,
    work_package_id: uuid.UUID,
    deliverable_id: uuid.UUID,
    database: DatabaseSession,
    organization_id: Annotated[str, Query(min_length=1)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[DeliverableRevisionRead]:
    require_deliverable(
        database,
        project_id,
        work_package_id,
        deliverable_id,
        organization_id,
    )

    return list_deliverable_revisions(
        database,
        deliverable_id,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/{revision_id}",
    response_model=DeliverableRevisionRead,
)
def get_deliverable_revision_route(
    project_id: uuid.UUID,
    work_package_id: uuid.UUID,
    deliverable_id: uuid.UUID,
    revision_id: uuid.UUID,
    database: DatabaseSession,
    organization_id: Annotated[str, Query(min_length=1)],
) -> DeliverableRevisionRead:
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


@router.patch(
    "/{revision_id}",
    response_model=DeliverableRevisionRead,
)
def update_deliverable_revision_route(
    project_id: uuid.UUID,
    work_package_id: uuid.UUID,
    deliverable_id: uuid.UUID,
    revision_id: uuid.UUID,
    revision_data: DeliverableRevisionUpdate,
    database: DatabaseSession,
    organization_id: Annotated[str, Query(min_length=1)],
) -> DeliverableRevisionRead:
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

    try:
        return update_deliverable_revision(
            database,
            revision,
            revision_data,
        )
    except InvalidDeliverableRevisionUpdateError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
    except RevisionCodeConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error


@router.delete(
    "/{revision_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_deliverable_revision_route(
    project_id: uuid.UUID,
    work_package_id: uuid.UUID,
    deliverable_id: uuid.UUID,
    revision_id: uuid.UUID,
    database: DatabaseSession,
    organization_id: Annotated[str, Query(min_length=1)],
) -> Response:
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

    delete_deliverable_revision(
        database,
        revision,
    )

    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
    )
