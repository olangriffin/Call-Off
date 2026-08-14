from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.backend.models.programme.programme import Programme
from app.backend.models.programme.programme_revision import ProgrammeRevision
from app.backend.models.project import Project


def get_or_create_current_revision(
    database: Session,
    project: Project,
) -> ProgrammeRevision:
    """Return the project's current, freely-editable internal programme revision,
    creating the internal programme and its first revision if neither exists yet."""

    programme = database.scalar(
        select(Programme).where(
            Programme.project_id == project.id,
            Programme.programme_type == "internal",
        )
    )

    if programme is None:
        programme = Programme(
            project_id=project.id,
            programme_type="internal",
        )
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

    database.commit()
    database.refresh(current_revision)

    return current_revision
