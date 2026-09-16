from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.backend.models.programme.programme import Programme
from app.backend.models.programme.programme_activity import ProgrammeActivity
from app.backend.models.programme.programme_dependency import ProgrammeDependency
from app.backend.models.programme.programme_import import ProgrammeImport
from app.backend.models.programme.programme_revision import ProgrammeRevision
from app.backend.models.project import Project
from app.backend.services.programme_import import (
    InvalidProgrammeImportError,
    preview_from_import,
)

logger = logging.getLogger(__name__)
_REVISION_PATTERN = re.compile(r"^R(\d+)$", re.IGNORECASE)


def _next_revision_code(database: Session, programme_id: uuid.UUID) -> str:
    codes = database.scalars(
        select(ProgrammeRevision.revision_code).where(
            ProgrammeRevision.programme_id == programme_id
        )
    ).all()
    highest = 0
    for code in codes:
        match = _REVISION_PATTERN.fullmatch(code or "")
        if match:
            highest = max(highest, int(match.group(1)))
    candidate = highest + 1
    existing = set(codes)
    while f"R{candidate}" in existing:
        candidate += 1
    return f"R{candidate}"


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def _mark_import_failed(
    database: Session,
    import_id: uuid.UUID,
    *,
    message: str,
) -> None:
    failed_import = database.get(ProgrammeImport, import_id)
    if failed_import is None:
        return

    failed_import.status = "failed"
    failed_import.error_count = max(failed_import.error_count, 1)
    issues = list(failed_import.validation_issues or [])
    issues.append({"severity": "error", "message": message})
    failed_import.validation_issues = issues
    failed_import.completed_at = datetime.now(timezone.utc)
    database.commit()


def confirm_import(
    database: Session,
    project: Project,
    import_record: ProgrammeImport,
) -> ProgrammeRevision:
    """Commit a validated Programme import without exposing a half-built revision.

    Imported hierarchy rows are flushed level-by-level so every parent exists
    before its children are inserted. The new revision is kept non-current until
    activities and dependencies have been persisted successfully; only then is
    the current-revision switch performed in the same transaction.
    """

    import_id = import_record.id

    if import_record.status == "completed" and import_record.programme_revision_id:
        existing_revision = database.get(
            ProgrammeRevision,
            import_record.programme_revision_id,
        )
        if existing_revision is not None:
            return existing_revision

    if import_record.status != "validated":
        raise InvalidProgrammeImportError(
            "Only a validated Programme import can be confirmed. Upload the XML again to create a fresh preview."
        )

    programme = database.scalar(
        select(Programme).where(
            Programme.id == import_record.programme_id,
            Programme.project_id == project.id,
        )
    )
    if programme is None:
        raise InvalidProgrammeImportError(
            "The Programme import is not available for this project."
        )

    preview = preview_from_import(import_record)
    if not preview.can_confirm:
        raise InvalidProgrammeImportError(
            "The Programme import contains validation errors."
        )

    try:
        revision = ProgrammeRevision(
            programme_id=programme.id,
            revision_code=_next_revision_code(database, programme.id),
            name=preview.project_name or import_record.source_filename,
            source_type="ms_project_xml",
            source_filename=import_record.source_filename,
            status="active",
            is_current=False,
        )
        database.add(revision)
        database.flush()

        activities_by_uid: dict[str, ProgrammeActivity] = {}
        tasks_by_level: dict[int, list] = {}
        for task in preview.tasks:
            tasks_by_level.setdefault(task.outline_level, []).append(task)

        for outline_level in sorted(tasks_by_level):
            for task in tasks_by_level[outline_level]:
                parent_activity = None
                if task.parent_uid is not None:
                    parent_activity = activities_by_uid.get(task.parent_uid)
                    if parent_activity is None:
                        raise InvalidProgrammeImportError(
                            f"Programme hierarchy could not resolve the parent of activity {task.activity_code}."
                        )

                status = (
                    "complete"
                    if task.percent_complete >= 100
                    else "in_progress"
                    if task.percent_complete > 0
                    else "not_started"
                )

                activity = ProgrammeActivity(
                    id=uuid.uuid4(),
                    programme_revision_id=revision.id,
                    activity_code=task.activity_code,
                    name=task.name,
                    activity_type="milestone" if task.is_milestone else "task",
                    external_id=task.source_uid,
                    planned_start=_parse_datetime(task.planned_start),
                    planned_finish=_parse_datetime(task.planned_finish),
                    duration_minutes=task.duration_minutes,
                    percent_complete=task.percent_complete,
                    is_milestone=task.is_milestone,
                    status=status,
                    parent_activity=parent_activity,
                    is_summary=task.is_summary,
                )
                database.add(activity)
                activities_by_uid[task.source_uid] = activity

            # Keep imported self-referential hierarchy deterministic on every
            # supported database/driver rather than relying on bulk insert order.
            database.flush()

        for dependency in preview.dependencies:
            predecessor = activities_by_uid.get(dependency.predecessor_uid)
            successor = activities_by_uid.get(dependency.successor_uid)
            if predecessor is None or successor is None:
                raise InvalidProgrammeImportError(
                    "A Programme dependency references an activity that was not imported."
                )
            if predecessor.id == successor.id:
                raise InvalidProgrammeImportError(
                    "A Programme activity cannot depend on itself."
                )

            database.add(
                ProgrammeDependency(
                    predecessor_id=predecessor.id,
                    successor_id=successor.id,
                    dependency_type=dependency.dependency_type,
                    lag_minutes=dependency.lag_minutes,
                )
            )

        database.flush()

        # The new revision only becomes authoritative after its full structure
        # has been persisted successfully.
        current_revisions = database.scalars(
            select(ProgrammeRevision).where(
                ProgrammeRevision.programme_id == programme.id,
                ProgrammeRevision.is_current.is_(True),
                ProgrammeRevision.id != revision.id,
            )
        ).all()
        for current in current_revisions:
            current.is_current = False
        database.flush()

        revision.is_current = True
        import_record.programme_revision_id = revision.id
        import_record.status = "completed"
        import_record.imported_records = len(preview.tasks)
        import_record.completed_at = datetime.now(timezone.utc)

        database.commit()
        database.refresh(revision)
        return revision

    except InvalidProgrammeImportError:
        database.rollback()
        _mark_import_failed(
            database,
            import_id,
            message=(
                "The import could not be committed because its Programme structure "
                "could not be resolved safely. No Programme revision was activated."
            ),
        )
        raise
    except SQLAlchemyError as error:
        database.rollback()
        logger.exception("Programme import database commit failed", exc_info=error)
        _mark_import_failed(
            database,
            import_id,
            message=(
                "The import could not be committed to the database. No Programme "
                "revision was activated."
            ),
        )
        raise InvalidProgrammeImportError(
            "The Programme structure was valid, but Call-Off could not save it. "
            "No Programme revision was activated. Please upload the XML again after the deployment updates."
        ) from error
    except Exception as error:
        database.rollback()
        logger.exception("Unexpected Programme import commit failure", exc_info=error)
        _mark_import_failed(
            database,
            import_id,
            message=(
                "The import could not be committed because of an unexpected server "
                "error. No Programme revision was activated."
            ),
        )
        raise
