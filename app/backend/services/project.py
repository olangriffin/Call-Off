from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.backend.models.organisation import Organisation
from app.backend.models.project import Project
from app.backend.schemas.project import ProjectCreate, ProjectUpdate


class ProjectServiceError(Exception):
    """Base exception for project service errors."""


class OrganisationNotFoundError(ProjectServiceError):
    """Raised when an organisation does not exist."""


class ProjectCodeConflictError(ProjectServiceError):
    """Raised when a project code already exists in an organisation."""


class InvalidProjectUpdateError(ProjectServiceError):
    """Raised when a project update is invalid."""


def create_project(
    database: Session,
    project_data: ProjectCreate,
) -> Project:
    organisation_exists = database.scalar(
        select(Organisation.id).where(
            Organisation.id == project_data.organization_id
        )
    )

    if organisation_exists is None:
        raise OrganisationNotFoundError(
            f"Organisation '{project_data.organization_id}' was not found."
        )

    project = Project(**project_data.model_dump())

    database.add(project)

    try:
        database.commit()
    except IntegrityError as error:
        database.rollback()

        raise ProjectCodeConflictError(
            f"Project code '{project_data.code}' already exists "
            "for this organisation."
        ) from error

    database.refresh(project)

    return project


def list_projects(
    database: Session,
    organization_id: str,
    *,
    offset: int = 0,
    limit: int = 100,
) -> list[Project]:
    statement = (
        select(Project)
        .where(Project.organization_id == organization_id)
        .order_by(Project.code)
        .offset(offset)
        .limit(limit)
    )

    return list(database.scalars(statement).all())


def get_project(
    database: Session,
    project_id: uuid.UUID,
    organization_id: str,
) -> Project | None:
    statement = select(Project).where(
        Project.id == project_id,
        Project.organization_id == organization_id,
    )

    return database.scalar(statement)


def update_project(
    database: Session,
    project: Project,
    project_data: ProjectUpdate,
) -> Project:
    update_values = project_data.model_dump(exclude_unset=True)

    required_fields = {"code", "name", "status"}

    for field_name in required_fields:
        if field_name in update_values and update_values[field_name] is None:
            raise InvalidProjectUpdateError(
                f"{field_name} cannot be null."
            )

    planned_start = update_values.get(
        "planned_start",
        project.planned_start,
    )
    planned_finish = update_values.get(
        "planned_finish",
        project.planned_finish,
    )

    if (
        planned_start is not None
        and planned_finish is not None
        and planned_finish < planned_start
    ):
        raise InvalidProjectUpdateError(
            "planned_finish cannot be earlier than planned_start."
        )

    for field_name, value in update_values.items():
        setattr(project, field_name, value)

    try:
        database.commit()
    except IntegrityError as error:
        database.rollback()

        raise ProjectCodeConflictError(
            f"Project code '{project.code}' already exists "
            "for this organisation."
        ) from error

    database.refresh(project)

    return project


def delete_project(
    database: Session,
    project: Project,
) -> None:
    database.delete(project)
    database.commit()
