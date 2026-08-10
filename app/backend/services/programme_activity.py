from __future__ import annotations

import re
import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.backend.models.programme.programme_activity import ProgrammeActivity
from app.backend.models.programme.programme_revision import ProgrammeRevision
from app.backend.models.package.package import WorkPackage
from app.backend.schemas.programme_activity import (
    ProgrammeActivityCreate,
    ProgrammeActivityUpdate,
)


class ProgrammeActivityServiceError(Exception):
    """Base exception for programme activity service errors."""


class ProgrammeActivityCodeConflictError(ProgrammeActivityServiceError):
    """Raised when an activity code already exists in the current revision."""


class InvalidProgrammeActivityUpdateError(ProgrammeActivityServiceError):
    """Raised when a programme activity update is invalid."""


class ProgrammeActivityParentNotFoundError(ProgrammeActivityServiceError):
    """Raised when a parent activity reference is invalid."""


class ProgrammeActivityParentCycleError(ProgrammeActivityServiceError):
    """Raised when a parent assignment would create a hierarchy cycle."""


class ProgrammeActivityHasChildrenError(ProgrammeActivityServiceError):
    """Raised when attempting to delete an activity that still has children."""


class ProgrammeActivityWorkPackageNotFoundError(ProgrammeActivityServiceError):
    """Raised when a work package is unavailable to the programme project."""


def _validate_work_package_in_project(
    database: Session,
    work_package_id: uuid.UUID,
    project_id: uuid.UUID,
) -> None:
    work_package = database.scalar(
        select(WorkPackage.id).where(
            WorkPackage.id == work_package_id,
            WorkPackage.project_id == project_id,
        )
    )

    if work_package is None:
        raise ProgrammeActivityWorkPackageNotFoundError(
            "Work package was not found in this project."
        )


def _get_parent_in_revision(
    database: Session,
    parent_activity_id: uuid.UUID,
    revision_id: uuid.UUID,
) -> ProgrammeActivity:
    parent = database.scalar(
        select(ProgrammeActivity).where(
            ProgrammeActivity.id == parent_activity_id,
            ProgrammeActivity.programme_revision_id == revision_id,
        )
    )

    if parent is None:
        raise ProgrammeActivityParentNotFoundError(
            "Parent activity was not found in this programme."
        )

    return parent


def _would_create_cycle(
    database: Session,
    activity_id: uuid.UUID,
    candidate_parent_id: uuid.UUID,
) -> bool:
    """Walk up from the candidate parent; if we reach activity_id, it's a cycle."""

    current_id: uuid.UUID | None = candidate_parent_id

    while current_id is not None:
        if current_id == activity_id:
            return True

        current_id = database.scalar(
            select(ProgrammeActivity.parent_activity_id).where(
                ProgrammeActivity.id == current_id
            )
        )

    return False


def _recalculate_is_summary(
    database: Session,
    activity_id: uuid.UUID | None,
) -> None:
    if activity_id is None:
        return

    activity = database.get(ProgrammeActivity, activity_id)

    if activity is None:
        return

    has_children = (
        database.scalar(
            select(func.count())
            .select_from(ProgrammeActivity)
            .where(ProgrammeActivity.parent_activity_id == activity_id)
        )
        > 0
    )

    if activity.is_summary != has_children:
        activity.is_summary = has_children


_AUTO_ACTIVITY_CODE_PATTERN = re.compile(r"^A-(\d{5})$")
_AUTO_ACTIVITY_CODE_STEP = 10
_AUTO_ACTIVITY_CODE_MAX_ATTEMPTS = 5


def _generate_next_activity_code(database: Session, revision_id: uuid.UUID) -> str:
    """Produce the next zero-padded auto code (A-00010, A-00020, ...).

    Zero-padded so codes stay in the right order under the plain string sort
    `list_activities` uses — "A-00020" sorts before "A-00100" the way you'd
    expect, unlike "A-20" vs "A-100". Continues on from the highest
    auto-generated code already in the revision; hand-entered codes that
    don't match the A-NNNNN shape are left alone and just don't collide.
    """

    existing_codes = database.scalars(
        select(ProgrammeActivity.activity_code).where(
            ProgrammeActivity.programme_revision_id == revision_id
        )
    ).all()

    highest = 0

    for code in existing_codes:
        match = _AUTO_ACTIVITY_CODE_PATTERN.match(code)

        if match:
            highest = max(highest, int(match.group(1)))

    return f"A-{highest + _AUTO_ACTIVITY_CODE_STEP:05d}"


def create_activity(
    database: Session,
    revision: ProgrammeRevision,
    activity_data: ProgrammeActivityCreate,
) -> ProgrammeActivity:
    if activity_data.work_package_id is not None:
        _validate_work_package_in_project(
            database,
            activity_data.work_package_id,
            revision.programme.project_id,
        )

    if activity_data.parent_activity_id is not None:
        _get_parent_in_revision(
            database,
            activity_data.parent_activity_id,
            revision.id,
        )

    activity_values = activity_data.model_dump()
    activity_values["is_milestone"] = activity_data.activity_type == "milestone"

    auto_generate_code = activity_values["activity_code"] is None
    max_attempts = _AUTO_ACTIVITY_CODE_MAX_ATTEMPTS if auto_generate_code else 1
    activity: ProgrammeActivity | None = None

    for attempt in range(1, max_attempts + 1):
        if auto_generate_code:
            activity_values["activity_code"] = _generate_next_activity_code(
                database,
                revision.id,
            )

        activity = ProgrammeActivity(
            programme_revision_id=revision.id,
            **activity_values,
        )

        database.add(activity)

        try:
            database.commit()
            break
        except IntegrityError as error:
            database.rollback()

            if not auto_generate_code or attempt == max_attempts:
                raise ProgrammeActivityCodeConflictError(
                    f"Activity code '{activity_values['activity_code']}' "
                    "already exists for this programme."
                ) from error

    _recalculate_is_summary(database, activity_data.parent_activity_id)
    database.commit()

    database.refresh(activity)

    return activity


def list_activities(
    database: Session,
    revision_id: uuid.UUID,
    *,
    offset: int = 0,
    limit: int = 200,
) -> list[ProgrammeActivity]:
    statement = (
        select(ProgrammeActivity)
        .where(ProgrammeActivity.programme_revision_id == revision_id)
        .order_by(ProgrammeActivity.activity_code)
        .offset(offset)
        .limit(limit)
    )

    return list(database.scalars(statement).all())


def get_activity(
    database: Session,
    activity_id: uuid.UUID,
    revision_id: uuid.UUID,
) -> ProgrammeActivity | None:
    statement = select(ProgrammeActivity).where(
        ProgrammeActivity.id == activity_id,
        ProgrammeActivity.programme_revision_id == revision_id,
    )

    return database.scalar(statement)


def update_activity(
    database: Session,
    activity: ProgrammeActivity,
    activity_data: ProgrammeActivityUpdate,
) -> ProgrammeActivity:
    update_values = activity_data.model_dump(exclude_unset=True)

    required_fields = {"activity_code", "name", "status"}

    for field_name in required_fields:
        if field_name in update_values and update_values[field_name] is None:
            raise InvalidProgrammeActivityUpdateError(f"{field_name} cannot be null.")

    planned_start = update_values.get("planned_start", activity.planned_start)
    planned_finish = update_values.get("planned_finish", activity.planned_finish)

    if (
        planned_start is not None
        and planned_finish is not None
        and planned_finish < planned_start
    ):
        raise InvalidProgrammeActivityUpdateError(
            "planned_finish cannot be earlier than planned_start."
        )

    if (
        "work_package_id" in update_values
        and update_values["work_package_id"] is not None
    ):
        _validate_work_package_in_project(
            database,
            update_values["work_package_id"],
            activity.programme_revision.programme.project_id,
        )

    resulting_activity_type = update_values.get(
        "activity_type",
        activity.activity_type,
    )
    update_values["is_milestone"] = resulting_activity_type == "milestone"

    old_parent_id = activity.parent_activity_id
    new_parent_id_set = "parent_activity_id" in update_values
    new_parent_id = update_values.get("parent_activity_id")

    if new_parent_id_set and new_parent_id is not None:
        if new_parent_id == activity.id:
            raise InvalidProgrammeActivityUpdateError(
                "An activity cannot be its own parent."
            )

        _get_parent_in_revision(
            database,
            new_parent_id,
            activity.programme_revision_id,
        )

        if _would_create_cycle(database, activity.id, new_parent_id):
            raise ProgrammeActivityParentCycleError(
                "This parent assignment would create a hierarchy cycle."
            )

    for field_name, value in update_values.items():
        setattr(activity, field_name, value)

    try:
        database.commit()
    except IntegrityError as error:
        database.rollback()

        raise ProgrammeActivityCodeConflictError(
            f"Activity code '{activity.activity_code}' "
            "already exists for this programme."
        ) from error

    if new_parent_id_set and old_parent_id != new_parent_id:
        _recalculate_is_summary(database, old_parent_id)
        _recalculate_is_summary(database, new_parent_id)
        database.commit()

    database.refresh(activity)

    return activity


def delete_activity(
    database: Session,
    activity: ProgrammeActivity,
) -> None:
    child_count = database.scalar(
        select(func.count())
        .select_from(ProgrammeActivity)
        .where(ProgrammeActivity.parent_activity_id == activity.id)
    )

    if child_count:
        raise ProgrammeActivityHasChildrenError(
            f"Activity '{activity.activity_code}' has {child_count} child "
            "activities and cannot be deleted directly."
        )

    parent_id = activity.parent_activity_id

    database.delete(activity)
    database.commit()

    _recalculate_is_summary(database, parent_id)
    database.commit()


def get_descendant_ids(
    activities: list[ProgrammeActivity],
    root_id: uuid.UUID,
) -> set[uuid.UUID]:
    """Return the IDs of every descendant of root_id within the given flat list."""

    children_by_parent: dict[uuid.UUID, list[ProgrammeActivity]] = {}

    for activity in activities:
        if activity.parent_activity_id is not None:
            children_by_parent.setdefault(activity.parent_activity_id, []).append(
                activity
            )

    descendants: set[uuid.UUID] = set()

    def visit(parent_id: uuid.UUID) -> None:
        for child in children_by_parent.get(parent_id, []):
            descendants.add(child.id)
            visit(child.id)

    visit(root_id)

    return descendants


def build_activity_tree(
    activities: list[ProgrammeActivity],
) -> list[dict]:
    """Order a flat list of activities into depth-first hierarchy order,
    returning [{"activity": ..., "depth": ...}, ...] for indented display."""

    children_by_parent: dict[uuid.UUID | None, list[ProgrammeActivity]] = {}

    for activity in activities:
        children_by_parent.setdefault(activity.parent_activity_id, []).append(activity)

    ordered: list[dict] = []

    def visit(parent_id: uuid.UUID | None, depth: int) -> None:
        for activity in children_by_parent.get(parent_id, []):
            ordered.append({"activity": activity, "depth": depth})
            visit(activity.id, depth + 1)

    visit(None, 0)

    return ordered
