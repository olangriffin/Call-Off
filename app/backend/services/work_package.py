from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.backend.models.package.package import WorkPackage
from app.backend.models.project import Project
from app.backend.schemas.work_package import (
    WorkPackageCreate,
    WorkPackageUpdate,
)


class WorkPackageServiceError(Exception):
    """Base exception for work package service errors."""


class WorkPackageCodeConflictError(WorkPackageServiceError):
    """Raised when a work package code already exists in a project."""


class InvalidWorkPackageUpdateError(WorkPackageServiceError):
    """Raised when a work package update is invalid."""


def create_work_package(
    database: Session,
    project: Project,
    work_package_data: WorkPackageCreate,
) -> WorkPackage:
    work_package = WorkPackage(
        project_id=project.id,
        **work_package_data.model_dump(),
    )

    database.add(work_package)

    try:
        database.commit()
    except IntegrityError as error:
        database.rollback()

        raise WorkPackageCodeConflictError(
            f"Work package code '{work_package_data.code}' "
            "already exists for this project."
        ) from error

    database.refresh(work_package)

    return work_package


def list_work_packages(
    database: Session,
    project_id: uuid.UUID,
    *,
    offset: int = 0,
    limit: int | None = 100,
) -> list[WorkPackage]:
    statement = (
        select(WorkPackage)
        .where(WorkPackage.project_id == project_id)
        .order_by(WorkPackage.code)
        .offset(offset)
    )

    if limit is not None:
        statement = statement.limit(limit)

    return list(database.scalars(statement).all())


def get_work_package(
    database: Session,
    work_package_id: uuid.UUID,
    project_id: uuid.UUID,
) -> WorkPackage | None:
    statement = select(WorkPackage).where(
        WorkPackage.id == work_package_id,
        WorkPackage.project_id == project_id,
    )

    return database.scalar(statement)


def update_work_package(
    database: Session,
    work_package: WorkPackage,
    work_package_data: WorkPackageUpdate,
) -> WorkPackage:
    update_values = work_package_data.model_dump(exclude_unset=True)

    required_fields = {"code", "name", "status"}

    for field_name in required_fields:
        if field_name in update_values and update_values[field_name] is None:
            raise InvalidWorkPackageUpdateError(f"{field_name} cannot be null.")

    planned_start = update_values.get(
        "planned_start",
        work_package.planned_start,
    )
    planned_finish = update_values.get(
        "planned_finish",
        work_package.planned_finish,
    )

    if (
        planned_start is not None
        and planned_finish is not None
        and planned_finish < planned_start
    ):
        raise InvalidWorkPackageUpdateError(
            "planned_finish cannot be earlier than planned_start."
        )

    for field_name, value in update_values.items():
        setattr(work_package, field_name, value)

    try:
        database.commit()
    except IntegrityError as error:
        database.rollback()

        raise WorkPackageCodeConflictError(
            f"Work package code '{work_package.code}' already exists for this project."
        ) from error

    database.refresh(work_package)

    return work_package


def delete_work_package(
    database: Session,
    work_package: WorkPackage,
) -> None:
    database.delete(work_package)
    database.commit()
