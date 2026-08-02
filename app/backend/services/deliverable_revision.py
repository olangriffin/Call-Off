from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.backend.models.package.deliverable import Deliverable
from app.backend.models.package.revision import DeliverableRevision
from app.backend.schemas.deliverable_revision import (
    DeliverableRevisionCreate,
    DeliverableRevisionUpdate,
)


class DeliverableRevisionServiceError(Exception):
    """Base exception for deliverable revision service errors."""


class RevisionCodeConflictError(DeliverableRevisionServiceError):
    """Raised when a revision code already exists for a deliverable."""


class InvalidDeliverableRevisionUpdateError(DeliverableRevisionServiceError):
    """Raised when a deliverable revision update is invalid."""


def create_deliverable_revision(
    database: Session,
    deliverable: Deliverable,
    revision_data: DeliverableRevisionCreate,
) -> DeliverableRevision:
    revision = DeliverableRevision(
        deliverable_id=deliverable.id,
        **revision_data.model_dump(),
    )

    database.add(revision)

    if revision_data.status == "issued":
        deliverable.status = "submitted"

    try:
        database.commit()
    except IntegrityError as error:
        database.rollback()

        raise RevisionCodeConflictError(
            f"Revision code '{revision_data.revision_code}' "
            "already exists for this deliverable."
        ) from error

    database.refresh(revision)
    database.refresh(deliverable)

    return revision


def list_deliverable_revisions(
    database: Session,
    deliverable_id: uuid.UUID,
    *,
    offset: int = 0,
    limit: int = 100,
) -> list[DeliverableRevision]:
    statement = (
        select(DeliverableRevision)
        .where(
            DeliverableRevision.deliverable_id == deliverable_id,
        )
        .order_by(DeliverableRevision.revision_code)
        .offset(offset)
        .limit(limit)
    )

    return list(database.scalars(statement).all())


def get_deliverable_revision(
    database: Session,
    revision_id: uuid.UUID,
    deliverable_id: uuid.UUID,
) -> DeliverableRevision | None:
    statement = select(DeliverableRevision).where(
        DeliverableRevision.id == revision_id,
        DeliverableRevision.deliverable_id == deliverable_id,
    )

    return database.scalar(statement)


def update_deliverable_revision(
    database: Session,
    revision: DeliverableRevision,
    revision_data: DeliverableRevisionUpdate,
) -> DeliverableRevision:
    update_values = revision_data.model_dump(
        exclude_unset=True,
    )

    required_fields = {
        "revision_code",
        "status",
    }

    for field_name in required_fields:
        if field_name in update_values and update_values[field_name] is None:
            raise InvalidDeliverableRevisionUpdateError(f"{field_name} cannot be null.")

    for field_name, value in update_values.items():
        setattr(revision, field_name, value)

    try:
        database.commit()
    except IntegrityError as error:
        database.rollback()

        raise RevisionCodeConflictError(
            f"Revision code '{revision.revision_code}' "
            "already exists for this deliverable."
        ) from error

    database.refresh(revision)

    return revision


def delete_deliverable_revision(
    database: Session,
    revision: DeliverableRevision,
) -> None:
    database.delete(revision)
    database.commit()
