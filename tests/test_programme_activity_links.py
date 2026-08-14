from __future__ import annotations

from datetime import datetime, timezone
from unittest import TestCase

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.backend.models.organisation import Organisation
from app.backend.models.programme.programme import Programme
from app.backend.models.programme.programme_activity import ProgrammeActivity
from app.backend.models.programme.programme_activity_link import (
    ProgrammeActivityLink,
)
from app.backend.models.programme.programme_revision import ProgrammeRevision
from app.backend.models.project import Project
from app.backend.services.programme_activity_link import (
    InvalidProgrammeActivityLinkTypeError,
    ProgrammeActivityLinkConflictError,
    ProgrammeActivityLinkProjectMismatchError,
    link_activities,
    list_linked_client_activities,
    unlink_activities,
)


class ProgrammeActivityLinkTestCase(TestCase):
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
            ProgrammeActivity.__table__,
            ProgrammeActivityLink.__table__,
        ):
            table.create(self.engine)

    def tearDown(self) -> None:
        self.engine.dispose()

    def _add_project_activities(
        self,
        database: Session,
        *,
        project_code: str,
    ) -> tuple[list[ProgrammeActivity], list[ProgrammeActivity]]:
        organisation = Organisation(
            id=f"org-{project_code.lower()}",
            name=f"{project_code} Organisation",
            slug=f"{project_code.lower()}-organisation",
            created_at=datetime.now(timezone.utc),
        )
        project = Project(
            organization_id=organisation.id,
            code=project_code,
            name=f"{project_code} Project",
        )
        database.add_all([organisation, project])
        database.flush()

        client_programme = Programme(
            project_id=project.id,
            programme_type="client",
        )
        internal_programme = Programme(
            project_id=project.id,
            programme_type="internal",
        )
        database.add_all([client_programme, internal_programme])
        database.flush()

        client_revision = ProgrammeRevision(
            programme_id=client_programme.id,
            revision_code="C1",
            is_current=True,
        )
        internal_revision = ProgrammeRevision(
            programme_id=internal_programme.id,
            revision_code="I1",
            is_current=True,
        )
        database.add_all([client_revision, internal_revision])
        database.flush()

        client_activities = [
            ProgrammeActivity(
                programme_revision_id=client_revision.id,
                activity_code=f"C-{index}",
                name=f"Client activity {index}",
            )
            for index in (1, 2)
        ]
        internal_activities = [
            ProgrammeActivity(
                programme_revision_id=internal_revision.id,
                activity_code=f"I-{index}",
                name=f"Internal activity {index}",
            )
            for index in (1, 2)
        ]
        database.add_all([*client_activities, *internal_activities])
        database.commit()
        return client_activities, internal_activities

    def test_links_and_unlinks_client_activity_to_internal_activity(self) -> None:
        with Session(self.engine) as database:
            client_activities, internal_activities = self._add_project_activities(
                database,
                project_code="VALID",
            )
            client_activity = client_activities[0]
            internal_activity = internal_activities[0]

            activity_link = link_activities(
                database,
                client_activity,
                internal_activity,
            )

            self.assertEqual(activity_link.source_activity_id, client_activity.id)
            self.assertEqual(activity_link.target_activity_id, internal_activity.id)
            self.assertEqual(
                list_linked_client_activities(database, internal_activity),
                [client_activity],
            )
            self.assertEqual(
                client_activity.linked_internal_activities,
                [internal_activity],
            )
            self.assertEqual(
                internal_activity.linked_client_activities,
                [client_activity],
            )

            self.assertTrue(
                unlink_activities(database, client_activity, internal_activity)
            )
            self.assertEqual(
                list_linked_client_activities(database, internal_activity),
                [],
            )
            self.assertFalse(
                unlink_activities(database, client_activity, internal_activity)
            )

    def test_supports_multiple_links_in_both_directions(self) -> None:
        with Session(self.engine) as database:
            client_activities, internal_activities = self._add_project_activities(
                database,
                project_code="MULTI",
            )

            link_activities(database, client_activities[0], internal_activities[0])
            link_activities(database, client_activities[1], internal_activities[0])
            link_activities(database, client_activities[0], internal_activities[1])

            self.assertEqual(
                list_linked_client_activities(database, internal_activities[0]),
                client_activities,
            )
            self.assertEqual(
                set(client_activities[0].linked_internal_activities),
                set(internal_activities),
            )

    def test_rejects_duplicate_links(self) -> None:
        with Session(self.engine) as database:
            client_activities, internal_activities = self._add_project_activities(
                database,
                project_code="DUPLICATE",
            )
            link_activities(database, client_activities[0], internal_activities[0])

            with self.assertRaises(ProgrammeActivityLinkConflictError):
                link_activities(
                    database,
                    client_activities[0],
                    internal_activities[0],
                )

    def test_rejects_cross_project_links(self) -> None:
        with Session(self.engine) as database:
            client_activities, _ = self._add_project_activities(
                database,
                project_code="PROJECT-A",
            )
            _, internal_activities = self._add_project_activities(
                database,
                project_code="PROJECT-B",
            )

            with self.assertRaises(ProgrammeActivityLinkProjectMismatchError):
                link_activities(
                    database,
                    client_activities[0],
                    internal_activities[0],
                )

    def test_rejects_internal_to_internal_and_client_to_client_links(self) -> None:
        with Session(self.engine) as database:
            client_activities, internal_activities = self._add_project_activities(
                database,
                project_code="TYPE",
            )

            invalid_pairs = (
                (internal_activities[0], internal_activities[1]),
                (client_activities[0], client_activities[1]),
            )
            for source_activity, target_activity in invalid_pairs:
                with self.subTest(
                    source=source_activity.activity_code,
                    target=target_activity.activity_code,
                ):
                    with self.assertRaises(InvalidProgrammeActivityLinkTypeError):
                        link_activities(database, source_activity, target_activity)
