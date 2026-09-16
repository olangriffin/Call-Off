from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.backend.models.organisation import Organisation
from app.backend.models.programme.programme import Programme
from app.backend.models.programme.programme_activity import ProgrammeActivity
from app.backend.models.programme.programme_activity_identity import (
    ProgrammeActivityIdentity,
)
from app.backend.models.programme.programme_import import ProgrammeImport
from app.backend.models.programme.programme_revision import ProgrammeRevision
from app.backend.models.project import Project
from app.backend.services.programme_import import create_import_preview
from app.backend.services.programme_import_commit import confirm_import


ORGANISATION_ID = "org-import"
PROJECT_ID = uuid.UUID("c0000000-0000-0000-0000-000000000001")
PROGRAMME_ID = uuid.UUID("c0000000-0000-0000-0000-000000000002")


@compiles(JSONB, "sqlite")
def compile_jsonb_for_sqlite(_type, _compiler, **_kwargs) -> str:
    return "JSON"


TABLES = (
    Organisation.__table__,
    Project.__table__,
    Programme.__table__,
    ProgrammeRevision.__table__,
    ProgrammeActivityIdentity.__table__,
    ProgrammeActivity.__table__,
    ProgrammeImport.__table__,
)


def programme_xml(*, project_name: str, activity_code: str, activity_name: str) -> bytes:
    return f"""<Project>
  <Name>{project_name}</Name>
  <Tasks>
    <Task>
      <UID>1</UID>
      <ID>1</ID>
      <WBS>{activity_code}</WBS>
      <Name>{activity_name}</Name>
      <OutlineLevel>1</OutlineLevel>
      <Start>2026-09-14T08:00:00</Start>
      <Finish>2026-09-18T17:00:00</Finish>
      <PercentComplete>0</PercentComplete>
    </Task>
  </Tasks>
</Project>""".encode()


class ProgrammeImportCommitTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = create_engine(
            "sqlite+pysqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        cls.session_factory = sessionmaker(
            bind=cls.engine,
            expire_on_commit=False,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.engine.dispose()

    def setUp(self) -> None:
        for table in reversed(TABLES):
            table.drop(self.engine, checkfirst=True)
        for table in TABLES:
            table.create(self.engine, checkfirst=True)

        # ProgrammeRevision defines its one-current-revision constraint with a
        # PostgreSQL partial index. SQLite otherwise compiles that as an
        # unconditional unique index, so mirror the production semantics here.
        with self.engine.begin() as connection:
            connection.exec_driver_sql(
                "DROP INDEX IF EXISTS uq_programme_revisions_current"
            )
            connection.exec_driver_sql(
                "CREATE UNIQUE INDEX uq_programme_revisions_current "
                "ON programme_revisions (programme_id) WHERE is_current = 1"
            )

        now = datetime.now(timezone.utc)
        with self.session_factory() as database:
            database.add(
                Organisation(
                    id=ORGANISATION_ID,
                    name="Import Organisation",
                    slug="import-organisation",
                    created_at=now,
                )
            )
            database.add(
                Project(
                    id=PROJECT_ID,
                    organization_id=ORGANISATION_ID,
                    code="IMPORT",
                    name="Import Project",
                )
            )
            database.add(
                Programme(
                    id=PROGRAMME_ID,
                    project_id=PROJECT_ID,
                )
            )
            database.commit()

    def test_successive_confirmed_imports_preserve_history_and_activity_identity(
        self,
    ) -> None:
        with self.session_factory() as database:
            project = database.get(Project, PROJECT_ID)
            first_import, first_preview = create_import_preview(
                database,
                project,
                filename="programme-r1.xml",
                content=programme_xml(
                    project_name="Programme R1",
                    activity_code="1",
                    activity_name="Design package",
                ),
            )
            self.assertTrue(first_preview.can_confirm)

            first_revision = confirm_import(database, project, first_import)
            first_revision_id = first_revision.id

            database.expire_all()
            persisted_first_revision = database.get(
                ProgrammeRevision,
                first_revision_id,
            )
            first_activity = database.scalar(
                select(ProgrammeActivity).where(
                    ProgrammeActivity.programme_revision_id == first_revision_id,
                    ProgrammeActivity.external_id == "1",
                )
            )

            self.assertIsNotNone(persisted_first_revision)
            self.assertTrue(persisted_first_revision.is_current)
            self.assertEqual(persisted_first_revision.revision_code, "R1")
            self.assertIsNotNone(first_activity)
            self.assertEqual(first_activity.name, "Design package")
            first_identity_id = first_activity.activity_identity_id
            self.assertIsNotNone(
                database.get(ProgrammeActivityIdentity, first_identity_id)
            )

            second_import, second_preview = create_import_preview(
                database,
                project,
                filename="programme-r2.xml",
                content=programme_xml(
                    project_name="Programme R2",
                    activity_code="1A",
                    activity_name="Design package revised",
                ),
            )
            self.assertTrue(second_preview.can_confirm)

            second_revision = confirm_import(database, project, second_import)
            second_revision_id = second_revision.id

            database.expire_all()
            revisions = list(
                database.scalars(
                    select(ProgrammeRevision)
                    .where(ProgrammeRevision.programme_id == PROGRAMME_ID)
                    .order_by(ProgrammeRevision.revision_code)
                ).all()
            )
            persisted_first_revision = database.get(
                ProgrammeRevision,
                first_revision_id,
            )
            persisted_second_revision = database.get(
                ProgrammeRevision,
                second_revision_id,
            )
            historical_activity = database.scalar(
                select(ProgrammeActivity).where(
                    ProgrammeActivity.programme_revision_id == first_revision_id,
                    ProgrammeActivity.external_id == "1",
                )
            )
            current_activity = database.scalar(
                select(ProgrammeActivity).where(
                    ProgrammeActivity.programme_revision_id == second_revision_id,
                    ProgrammeActivity.external_id == "1",
                )
            )
            identities = list(
                database.scalars(
                    select(ProgrammeActivityIdentity).where(
                        ProgrammeActivityIdentity.programme_id == PROGRAMME_ID
                    )
                ).all()
            )

            self.assertEqual(len(revisions), 2)
            self.assertEqual(
                [revision.revision_code for revision in revisions],
                ["R1", "R2"],
            )
            self.assertFalse(persisted_first_revision.is_current)
            self.assertTrue(persisted_second_revision.is_current)
            self.assertEqual(historical_activity.name, "Design package")
            self.assertEqual(historical_activity.activity_code, "1")
            self.assertEqual(current_activity.name, "Design package revised")
            self.assertEqual(current_activity.activity_code, "1A")
            self.assertEqual(
                current_activity.activity_identity_id,
                first_identity_id,
            )
            self.assertEqual(len(identities), 1)

            persisted_first_import = database.get(ProgrammeImport, first_import.id)
            persisted_second_import = database.get(ProgrammeImport, second_import.id)
            self.assertEqual(persisted_first_import.status, "completed")
            self.assertEqual(persisted_second_import.status, "completed")
            self.assertEqual(
                persisted_first_import.programme_revision_id,
                first_revision_id,
            )
            self.assertEqual(
                persisted_second_import.programme_revision_id,
                second_revision_id,
            )


if __name__ == "__main__":
    unittest.main()
