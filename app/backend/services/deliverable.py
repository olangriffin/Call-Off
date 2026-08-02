from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.backend.models.package.deliverable import Deliverable
from app.backend.models.package.package import WorkPackage
from app.backend.models.package.revision import DeliverableRevision
from app.backend.schemas.deliverable import (
    DeliverableCreate,
    DeliverableUpdate,
)


class DeliverableServiceError(Exception):
    """Base exception for deliverable service errors."""


class DeliverableReferenceConflictError(DeliverableServiceError):
    """Raised when a reference already exists in a work package."""


class InvalidDeliverableUpdateError(DeliverableServiceError):
    """Raised when a deliverable update is invalid."""


def create_deliverable(
    database: Session,
    work_package: WorkPackage,
    deliverable_data: DeliverableCreate,
) -> Deliverable:
    deliverable = Deliverable(
        work_package_id=work_package.id,
        **deliverable_data.model_dump(),
    )

    database.add(deliverable)

    try:
        database.commit()
    except IntegrityError as error:
        database.rollback()

        raise DeliverableReferenceConflictError(
            f"Deliverable reference '{deliverable_data.reference}' "
            "already exists for this work package."
        ) from error

    database.refresh(deliverable)

    return deliverable


def list_deliverables(
    database: Session,
    work_package_id: uuid.UUID,
    *,
    offset: int = 0,
    limit: int = 100,
) -> list[Deliverable]:
    statement = (
        select(Deliverable)
        .where(
            Deliverable.work_package_id == work_package_id,
        )
        .order_by(Deliverable.reference)
        .offset(offset)
        .limit(limit)
    )

    return list(database.scalars(statement).all())


def list_deliverables_with_review_history(
    database: Session,
    work_package_id: uuid.UUID,
    *,
    offset: int = 0,
    limit: int = 100,
) -> list[Deliverable]:
    statement = (
        select(Deliverable)
        .options(
            selectinload(Deliverable.revisions).selectinload(
                DeliverableRevision.approvals
            )
        )
        .where(Deliverable.work_package_id == work_package_id)
        .order_by(Deliverable.reference)
        .offset(offset)
        .limit(limit)
    )

    return list(database.scalars(statement).all())


def get_deliverable(
    database: Session,
    deliverable_id: uuid.UUID,
    work_package_id: uuid.UUID,
) -> Deliverable | None:
    statement = select(Deliverable).where(
        Deliverable.id == deliverable_id,
        Deliverable.work_package_id == work_package_id,
    )

    return database.scalar(statement)


def get_deliverable_with_review_history(
    database: Session,
    deliverable_id: uuid.UUID,
    work_package_id: uuid.UUID,
) -> Deliverable | None:
    statement = (
        select(Deliverable)
        .options(
            selectinload(Deliverable.revisions).selectinload(
                DeliverableRevision.approvals
            )
        )
        .where(
            Deliverable.id == deliverable_id,
            Deliverable.work_package_id == work_package_id,
        )
    )

    return database.scalar(statement)


def update_deliverable(
    database: Session,
    deliverable: Deliverable,
    deliverable_data: DeliverableUpdate,
) -> Deliverable:
    update_values = deliverable_data.model_dump(
        exclude_unset=True,
    )

    required_fields = {
        "reference",
        "name",
        "deliverable_type",
        "status",
    }

    for field_name in required_fields:
        if (
            field_name in update_values
            and update_values[field_name] is None
        ):
            raise InvalidDeliverableUpdateError(
                f"{field_name} cannot be null."
            )

    planned_issue_date = update_values.get(
        "planned_issue_date",
        deliverable.planned_issue_date,
    )
    required_approval_date = update_values.get(
        "required_approval_date",
        deliverable.required_approval_date,
    )

    if (
        planned_issue_date is not None
        and required_approval_date is not None
        and required_approval_date < planned_issue_date
    ):
        raise InvalidDeliverableUpdateError(
            "required_approval_date cannot be earlier "
            "than planned_issue_date."
        )

    for field_name, value in update_values.items():
        setattr(deliverable, field_name, value)

    try:
        database.commit()
    except IntegrityError as error:
        database.rollback()

        raise DeliverableReferenceConflictError(
            f"Deliverable reference '{deliverable.reference}' "
            "already exists for this work package."
        ) from error

    database.refresh(deliverable)

    return deliverable


def delete_deliverable(
    database: Session,
    deliverable: Deliverable,
) -> None:
    database.delete(deliverable)
    database.commit()
