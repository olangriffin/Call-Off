from __future__ import annotations

from datetime import datetime, timezone
from unittest import TestCase

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.backend.models.organisation import Organisation
from app.backend.models.programme.programme import Programme
from app.backend.models.programme.programme_revision import ProgrammeRevision
from app.backend.models.project import Project
from app.backend.schemas.project import ProjectCreate
from app.backend.services.programme import get_current_revision
from app.backend.services.project import create_project


class ProjectProgrammeAlignmentTestCase(TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        for table in (
            Organisation.__table__,
            Project.__table__,
            Programme.__table__,
            ProgrammeRevision.__table__,
        ):
            table.create(self.engine)

    def tearDown(self) -> None:
        self.engine.dispose()

    def _add_organisation(self, database: Session) -> Organisation:
        organisation = Organisation(
            id="org-alignment",
            name="Alignment Organisation",
            slug="alignment-organisation",
            created_at=datetime.now(timezone.utc),
        )
        database.add(organisation)
        database.commit()
        return organisation

    def test_project_creation_bootstraps_programme_without_choosing_source(self) -> None:
        with Session(self.engine) as database:
            organisation = self._add_organisation(database)

            project = create_project(
                database,
                organisation.id,
                ProjectCreate(code="P-001", name="Programme-led project"),
            )

            programme = database.scalar(
                select(Programme).where(Programme.project_id == project.id)
            )
            self.assertIsNotNone(programme)
            self.assertIsNone(get_current_revision(database, project.id))

    def test_current_revision_lookup_does_not_create_legacy_programme_state(self) -> None:
        with Session(self.engine) as database:
            organisation = self._add_organisation(database)
            legacy_project = Project(
                organization_id=organisation.id,
                code="LEGACY",
                name="Legacy project",
            )
            database.add(legacy_project)
            database.commit()

            self.assertIsNone(get_current_revision(database, legacy_project.id))
            self.assertEqual(
                database.scalar(select(func.count()).select_from(Programme)),
                0,
            )
            self.assertEqual(
                database.scalar(select(func.count()).select_from(ProgrammeRevision)),
                0,
            )
