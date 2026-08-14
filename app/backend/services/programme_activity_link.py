from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.backend.models.programme.programme_activity import ProgrammeActivity
from app.backend.models.programme.programme_activity_link import (
    ProgrammeActivityLink,
)


class ProgrammeActivityLinkServiceError(Exception):
    """Base exception for programme activity link errors."""


class ProgrammeActivityLinkConflictError(ProgrammeActivityLinkServiceError):
    """Raised when the same client-to-internal link already exists."""


class ProgrammeActivityLinkProjectMismatchError(ProgrammeActivityLinkServiceError):
    """Raised when linked activities belong to different projects."""


class InvalidProgrammeActivityLinkTypeError(ProgrammeActivityLinkServiceError):
    """Raised when a link is not directed from client to internal."""


def _validate_link(
    source_activity: ProgrammeActivity,
    target_activity: ProgrammeActivity,
) -> None:
    source_programme = source_activity.programme_revision.programme
    target_programme = target_activity.programme_revision.programme

    if source_programme.project_id != target_programme.project_id:
        raise ProgrammeActivityLinkProjectMismatchError(
            "Programme activities must belong to the same project."
        )

    if (
        source_programme.programme_type != "client"
        or target_programme.programme_type != "internal"
    ):
        raise InvalidProgrammeActivityLinkTypeError(
            "Programme activity links must run from client to internal."
        )


def link_activities(
    database: Session,
    source_activity: ProgrammeActivity,
    target_activity: ProgrammeActivity,
) -> ProgrammeActivityLink:
    """Link a client programme activity to an internal programme activity."""
    _validate_link(source_activity, target_activity)

    existing_link = database.scalar(
        select(ProgrammeActivityLink).where(
            ProgrammeActivityLink.source_activity_id == source_activity.id,
            ProgrammeActivityLink.target_activity_id == target_activity.id,
        )
    )
    if existing_link is not None:
        raise ProgrammeActivityLinkConflictError(
            "These programme activities are already linked."
        )

    activity_link = ProgrammeActivityLink(
        source_activity_id=source_activity.id,
        target_activity_id=target_activity.id,
    )
    database.add(activity_link)

    try:
        database.commit()
    except IntegrityError as error:
        database.rollback()
        raise ProgrammeActivityLinkConflictError(
            "These programme activities are already linked."
        ) from error

    database.refresh(activity_link)
    return activity_link


def unlink_activities(
    database: Session,
    source_activity: ProgrammeActivity,
    target_activity: ProgrammeActivity,
) -> bool:
    """Remove a client-to-internal activity link if it exists."""
    _validate_link(source_activity, target_activity)

    activity_link = database.scalar(
        select(ProgrammeActivityLink).where(
            ProgrammeActivityLink.source_activity_id == source_activity.id,
            ProgrammeActivityLink.target_activity_id == target_activity.id,
        )
    )
    if activity_link is None:
        return False

    database.delete(activity_link)
    database.commit()
    return True


def list_linked_client_activities(
    database: Session,
    internal_activity: ProgrammeActivity,
) -> list[ProgrammeActivity]:
    """Return client activities linked to an internal programme activity."""
    if internal_activity.programme_revision.programme.programme_type != "internal":
        raise InvalidProgrammeActivityLinkTypeError(
            "Linked client activities can only be listed for an internal activity."
        )

    statement = (
        select(ProgrammeActivity)
        .join(
            ProgrammeActivityLink,
            ProgrammeActivityLink.source_activity_id == ProgrammeActivity.id,
        )
        .where(ProgrammeActivityLink.target_activity_id == internal_activity.id)
        .order_by(ProgrammeActivity.activity_code, ProgrammeActivity.id)
    )
    return list(database.scalars(statement).all())
