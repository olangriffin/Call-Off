from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.backend.core.auth import (
    CurrentOrganisationAccess,
    ProjectCreationAccess,
)
from app.backend.database.session import get_db
from app.backend.schemas.project import (
    ProjectCreate,
    ProjectRead,
    ProjectUpdate,
)
from app.backend.services.project import (
    InvalidProjectUpdateError,
    OrganisationNotFoundError,
    ProjectCodeConflictError,
    create_project,
    delete_project,
    get_project,
    list_projects,
    update_project,
)

router = APIRouter(
    prefix="/projects",
    tags=["Projects"],
)

DatabaseSession = Annotated[Session, Depends(get_db)]


@router.post(
    "",
    response_model=ProjectRead,
    status_code=status.HTTP_201_CREATED,
)
def create_project_route(
    project_data: ProjectCreate,
    database: DatabaseSession,
    access: ProjectCreationAccess,
) -> ProjectRead:
    try:
        return create_project(
            database,
            access.organization_id,
            project_data,
        )
    except OrganisationNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except ProjectCodeConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error


@router.get(
    "",
    response_model=list[ProjectRead],
)
def list_projects_route(
    database: DatabaseSession,
    access: CurrentOrganisationAccess,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[ProjectRead]:
    return list_projects(
        database,
        access.organization_id,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/{project_id}",
    response_model=ProjectRead,
)
def get_project_route(
    project_id: uuid.UUID,
    database: DatabaseSession,
    access: CurrentOrganisationAccess,
) -> ProjectRead:
    project = get_project(
        database,
        project_id,
        access.organization_id,
    )

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project was not found.",
        )

    return project


@router.patch(
    "/{project_id}",
    response_model=ProjectRead,
)
def update_project_route(
    project_id: uuid.UUID,
    project_data: ProjectUpdate,
    database: DatabaseSession,
    access: CurrentOrganisationAccess,
) -> ProjectRead:
    project = get_project(
        database,
        project_id,
        access.organization_id,
    )

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project was not found.",
        )

    try:
        return update_project(
            database,
            project,
            project_data,
        )
    except InvalidProjectUpdateError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
    except ProjectCodeConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_project_route(
    project_id: uuid.UUID,
    database: DatabaseSession,
    access: CurrentOrganisationAccess,
) -> Response:
    project = get_project(
        database,
        project_id,
        access.organization_id,
    )

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project was not found.",
        )

    delete_project(database, project)

    return Response(status_code=status.HTTP_204_NO_CONTENT)
