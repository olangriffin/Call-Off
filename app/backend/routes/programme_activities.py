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
from app.backend.schemas.programme_activity import (
    ProgrammeActivityCreate,
    ProgrammeActivityRead,
    ProgrammeActivityUpdate,
)
from app.backend.services.programme import get_or_create_current_revision
from app.backend.services.programme_activity import (
    InvalidProgrammeActivityUpdateError,
    ProgrammeActivityCodeConflictError,
    ProgrammeActivityHasChildrenError,
    ProgrammeActivityParentCycleError,
    ProgrammeActivityParentNotFoundError,
    create_activity,
    delete_activity,
    get_activity,
    list_activities,
    update_activity,
)
from app.backend.services.project import get_project

router = APIRouter(
    prefix="/projects/{project_id}/programme/activities",
    tags=["Programme Activities"],
)

DatabaseSession = Annotated[Session, Depends(get_db)]


def require_project_and_revision(
    database: Session,
    project_id: uuid.UUID,
    organization_id: str,
):
    project = get_project(database, project_id, organization_id)

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project was not found.",
        )

    return get_or_create_current_revision(database, project)


@router.post(
    "",
    response_model=ProgrammeActivityRead,
    status_code=status.HTTP_201_CREATED,
)
def create_activity_route(
    project_id: uuid.UUID,
    activity_data: ProgrammeActivityCreate,
    database: DatabaseSession,
    organization_id: Annotated[str, Query(min_length=1)],
) -> ProgrammeActivityRead:
    revision = require_project_and_revision(database, project_id, organization_id)

    try:
        return create_activity(database, revision, activity_data)
    except ProgrammeActivityCodeConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    except ProgrammeActivityParentNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error


@router.get(
    "",
    response_model=list[ProgrammeActivityRead],
)
def list_activities_route(
    project_id: uuid.UUID,
    database: DatabaseSession,
    organization_id: Annotated[str, Query(min_length=1)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> list[ProgrammeActivityRead]:
    revision = require_project_and_revision(database, project_id, organization_id)

    return list_activities(database, revision.id, offset=offset, limit=limit)


@router.get(
    "/{activity_id}",
    response_model=ProgrammeActivityRead,
)
def get_activity_route(
    project_id: uuid.UUID,
    activity_id: uuid.UUID,
    database: DatabaseSession,
    organization_id: Annotated[str, Query(min_length=1)],
) -> ProgrammeActivityRead:
    revision = require_project_and_revision(database, project_id, organization_id)

    activity = get_activity(database, activity_id, revision.id)

    if activity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Programme activity was not found.",
        )

    return activity


@router.patch(
    "/{activity_id}",
    response_model=ProgrammeActivityRead,
)
def update_activity_route(
    project_id: uuid.UUID,
    activity_id: uuid.UUID,
    activity_data: ProgrammeActivityUpdate,
    database: DatabaseSession,
    organization_id: Annotated[str, Query(min_length=1)],
) -> ProgrammeActivityRead:
    revision = require_project_and_revision(database, project_id, organization_id)

    activity = get_activity(database, activity_id, revision.id)

    if activity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Programme activity was not found.",
        )

    try:
        return update_activity(database, activity, activity_data)
    except (
        InvalidProgrammeActivityUpdateError,
        ProgrammeActivityParentNotFoundError,
        ProgrammeActivityParentCycleError,
    ) as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
    except ProgrammeActivityCodeConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error


@router.delete(
    "/{activity_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_activity_route(
    project_id: uuid.UUID,
    activity_id: uuid.UUID,
    database: DatabaseSession,
    organization_id: Annotated[str, Query(min_length=1)],
) -> Response:
    revision = require_project_and_revision(database, project_id, organization_id)

    activity = get_activity(database, activity_id, revision.id)

    if activity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Programme activity was not found.",
        )

    try:
        delete_activity(database, activity)
    except ProgrammeActivityHasChildrenError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error

    return Response(status_code=status.HTTP_204_NO_CONTENT)
