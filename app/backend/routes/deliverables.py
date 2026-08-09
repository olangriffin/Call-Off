from __future__ import annotations

import uuid
from typing import Annotated

from app.backend.schemas.deliverable import (
    DeliverableCreate,
    DeliverableRead,
    DeliverableUpdate,
)
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Response,
    status,
)
from sqlalchemy.orm import Session

from app.backend.core.auth import CurrentOrganisationAccess
from app.backend.database.session import get_db
from app.backend.models.package.package import WorkPackage
from app.backend.models.project import Project
from app.backend.services.deliverable import (
    DeliverableReferenceConflictError,
    InvalidDeliverableUpdateError,
    create_deliverable,
    delete_deliverable,
    get_deliverable,
    list_deliverables,
    update_deliverable,
)
from app.backend.services.project import get_project
from app.backend.services.work_package import get_work_package

router = APIRouter(
    prefix=("/projects/{project_id}/work-packages/{work_package_id}/deliverables"),
    tags=["Deliverables"],
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


@router.post(
    "",
    response_model=DeliverableRead,
    status_code=status.HTTP_201_CREATED,
)
def create_deliverable_route(
    project_id: uuid.UUID,
    work_package_id: uuid.UUID,
    deliverable_data: DeliverableCreate,
    database: DatabaseSession,
    access: CurrentOrganisationAccess,
) -> DeliverableRead:
    work_package = require_work_package(
        database,
        project_id,
        work_package_id,
        access.organization_id,
    )

    try:
        return create_deliverable(
            database,
            work_package,
            deliverable_data,
        )
    except DeliverableReferenceConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error


@router.get(
    "",
    response_model=list[DeliverableRead],
)
def list_deliverables_route(
    project_id: uuid.UUID,
    work_package_id: uuid.UUID,
    database: DatabaseSession,
    access: CurrentOrganisationAccess,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[DeliverableRead]:
    require_work_package(
        database,
        project_id,
        work_package_id,
        access.organization_id,
    )

    return list_deliverables(
        database,
        work_package_id,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/{deliverable_id}",
    response_model=DeliverableRead,
)
def get_deliverable_route(
    project_id: uuid.UUID,
    work_package_id: uuid.UUID,
    deliverable_id: uuid.UUID,
    database: DatabaseSession,
    access: CurrentOrganisationAccess,
) -> DeliverableRead:
    require_work_package(
        database,
        project_id,
        work_package_id,
        access.organization_id,
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


@router.patch(
    "/{deliverable_id}",
    response_model=DeliverableRead,
)
def update_deliverable_route(
    project_id: uuid.UUID,
    work_package_id: uuid.UUID,
    deliverable_id: uuid.UUID,
    deliverable_data: DeliverableUpdate,
    database: DatabaseSession,
    access: CurrentOrganisationAccess,
) -> DeliverableRead:
    require_work_package(
        database,
        project_id,
        work_package_id,
        access.organization_id,
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

    try:
        return update_deliverable(
            database,
            deliverable,
            deliverable_data,
        )
    except InvalidDeliverableUpdateError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
    except DeliverableReferenceConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error


@router.delete(
    "/{deliverable_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_deliverable_route(
    project_id: uuid.UUID,
    work_package_id: uuid.UUID,
    deliverable_id: uuid.UUID,
    database: DatabaseSession,
    access: CurrentOrganisationAccess,
) -> Response:
    require_work_package(
        database,
        project_id,
        work_package_id,
        access.organization_id,
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

    delete_deliverable(
        database,
        deliverable,
    )

    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
    )
