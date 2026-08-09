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

from app.backend.core.auth import CurrentOrganisationAccess
from app.backend.database.session import get_db
from app.backend.models.project import Project
from app.backend.schemas.work_package import (
    WorkPackageCreate,
    WorkPackageRead,
    WorkPackageUpdate,
)
from app.backend.services.project import get_project
from app.backend.services.work_package import (
    InvalidWorkPackageUpdateError,
    WorkPackageCodeConflictError,
    create_work_package,
    delete_work_package,
    get_work_package,
    list_work_packages,
    update_work_package,
)

router = APIRouter(
    prefix="/projects/{project_id}/work-packages",
    tags=["Work Packages"],
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


@router.post(
    "",
    response_model=WorkPackageRead,
    status_code=status.HTTP_201_CREATED,
)
def create_work_package_route(
    project_id: uuid.UUID,
    work_package_data: WorkPackageCreate,
    database: DatabaseSession,
    access: CurrentOrganisationAccess,
) -> WorkPackageRead:
    project = require_project(
        database,
        project_id,
        access.organization_id,
    )

    try:
        return create_work_package(
            database,
            project,
            work_package_data,
        )
    except WorkPackageCodeConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error


@router.get(
    "",
    response_model=list[WorkPackageRead],
)
def list_work_packages_route(
    project_id: uuid.UUID,
    database: DatabaseSession,
    access: CurrentOrganisationAccess,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[WorkPackageRead]:
    require_project(
        database,
        project_id,
        access.organization_id,
    )

    return list_work_packages(
        database,
        project_id,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/{work_package_id}",
    response_model=WorkPackageRead,
)
def get_work_package_route(
    project_id: uuid.UUID,
    work_package_id: uuid.UUID,
    database: DatabaseSession,
    access: CurrentOrganisationAccess,
) -> WorkPackageRead:
    require_project(
        database,
        project_id,
        access.organization_id,
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


@router.patch(
    "/{work_package_id}",
    response_model=WorkPackageRead,
)
def update_work_package_route(
    project_id: uuid.UUID,
    work_package_id: uuid.UUID,
    work_package_data: WorkPackageUpdate,
    database: DatabaseSession,
    access: CurrentOrganisationAccess,
) -> WorkPackageRead:
    require_project(
        database,
        project_id,
        access.organization_id,
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

    try:
        return update_work_package(
            database,
            work_package,
            work_package_data,
        )
    except InvalidWorkPackageUpdateError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
    except WorkPackageCodeConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error


@router.delete(
    "/{work_package_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_work_package_route(
    project_id: uuid.UUID,
    work_package_id: uuid.UUID,
    database: DatabaseSession,
    access: CurrentOrganisationAccess,
) -> Response:
    require_project(
        database,
        project_id,
        access.organization_id,
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

    delete_work_package(
        database,
        work_package,
    )

    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
    )
