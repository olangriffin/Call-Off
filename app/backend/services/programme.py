from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.backend.models.programme.programme import Programme
from app.backend.models.programme.programme_activity import ProgrammeActivity
from app.backend.models.programme.programme_revision import ProgrammeRevision
from app.backend.models.project import Project


def get_current_revision(
    database: Session,
    project_id: uuid.UUID,
) -> ProgrammeRevision | None:
    """Return the current Programme revision without changing database state."""

    return database.scalar(
        select(ProgrammeRevision)
        .join(Programme)
        .where(
            Programme.project_id == project_id,
            ProgrammeRevision.is_current.is_(True),
        )
    )


def is_programme_established(
    database: Session,
    project_id: uuid.UUID,
) -> bool:
    """Return whether the current Programme has at least one activity."""

    revision = get_current_revision(database, project_id)
    if revision is None:
        return False

    activity_id = database.scalar(
        select(ProgrammeActivity.id)
        .where(ProgrammeActivity.programme_revision_id == revision.id)
        .limit(1)
    )
    return activity_id is not None


def ensure_current_revision(
    database: Session,
    project: Project,
) -> ProgrammeRevision:
    """Return an editable Programme revision, creating it on an explicit write path."""

    programme = database.scalar(
        select(Programme).where(Programme.project_id == project.id)
    )

    if programme is None:
        programme = Programme(project_id=project.id)
        database.add(programme)
        database.flush()

    current_revision = database.scalar(
        select(ProgrammeRevision).where(
            ProgrammeRevision.programme_id == programme.id,
            ProgrammeRevision.is_current.is_(True),
        )
    )

    if current_revision is None:
        current_revision = ProgrammeRevision(
            programme_id=programme.id,
            revision_code="R1",
            source_type="manual",
            status="draft",
            is_current=True,
        )
        database.add(current_revision)

    database.flush()

    return current_revision
