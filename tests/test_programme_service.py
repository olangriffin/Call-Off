from __future__ import annotations

from datetime import datetime, timezone
from unittest import TestCase

from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.backend.models.organisation import Organisation
from app.backend.models.programme.programme import Programme
from app.backend.models.programme.programme_revision import ProgrammeRevision
from app.backend.models.project import Project
from app.backend.services.programme import get_or_create_current_revision


class ProgrammeServiceTestCase(TestCase):
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

    def _create_project(self, database: Session, *, code: str = "PRG") -> Project:
        organisation = Organisation(
            id=f"org-{code.lower()}",
            name=f"{code} Organisation",
            slug=f"{code.lower()}-organisation",
            created_at=datetime.now(timezone.utc),
        )
        project = Project(
            organization_id=organisation.id,
            code=code,
            name=f"{code} Project",
        )
        database.add_all([organisation, project])
        database.flush()
        return project

    def test_project_can_have_one_client_and_one_internal_programme(self) -> None:
        with Session(self.engine) as database:
            project = self._create_project(database)
            database.add_all(
                [
                    Programme(project_id=project.id, programme_type="client"),
                    Programme(project_id=project.id, programme_type="internal"),
                ]
            )
            database.commit()

            programme_types = set(
                database.scalars(
                    select(Programme.programme_type).where(
                        Programme.project_id == project.id
                    )
                ).all()
            )

        self.assertEqual(programme_types, {"client", "internal"})

    def test_duplicate_client_and_internal_programmes_are_rejected(self) -> None:
        for programme_type in ("client", "internal"):
            with self.subTest(programme_type=programme_type):
                with Session(self.engine) as database:
                    project = self._create_project(
                        database,
                        code=f"DUP-{programme_type}",
                    )
                    database.add_all(
                        [
                            Programme(
                                project_id=project.id,
                                programme_type=programme_type,
                            ),
                            Programme(
                                project_id=project.id,
                                programme_type=programme_type,
                            ),
                        ]
                    )

                    with self.assertRaises(IntegrityError):
                        database.commit()

    def test_programme_type_must_be_client_or_internal(self) -> None:
        with Session(self.engine) as database:
            project = self._create_project(database, code="TYPE")
            database.add(
                Programme(project_id=project.id, programme_type="external")
            )

            with self.assertRaises(IntegrityError):
                database.commit()

    def test_editable_workspace_uses_the_internal_programme(self) -> None:
        with Session(self.engine) as database:
            project = self._create_project(database, code="WORKSPACE")
            client_programme = Programme(
                project_id=project.id,
                programme_type="client",
            )
            database.add(client_programme)
            database.flush()
            client_revision = ProgrammeRevision(
                programme_id=client_programme.id,
                revision_code="C1",
                is_current=True,
            )
            database.add(client_revision)
            database.commit()

            workspace_revision = get_or_create_current_revision(database, project)

            self.assertEqual(
                workspace_revision.programme.programme_type,
                "internal",
            )
            self.assertNotEqual(workspace_revision.programme_id, client_programme.id)
            self.assertEqual(
                set(
                    database.scalars(
                        select(Programme.programme_type).where(
                            Programme.project_id == project.id
                        )
                    ).all()
                ),
                {"client", "internal"},
            )
