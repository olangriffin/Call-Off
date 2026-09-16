from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.backend.models.organisation import Organisation
from app.backend.models.package.package import WorkPackage
from app.backend.models.programme.programme import Programme
from app.backend.models.programme.programme_activity import ProgrammeActivity
from app.backend.models.programme.programme_activity_identity import (
    ProgrammeActivityIdentity,
)
from app.backend.models.programme.programme_revision import ProgrammeRevision
from app.backend.models.project import Project
from app.backend.schemas.programme_activity import (
    ProgrammeActivityCreate,
    ProgrammeActivityUpdate,
)
from app.backend.services.programme_activity import (
    ProgrammeActivityParentCycleError,
    ProgrammeActivityWorkPackageNotFoundError,
    create_activity,
    delete_activity,
    update_activity,
)


PROJECT_A_ID = uuid.UUID("a0000000-0000-0000-0000-000000000001")
PROJECT_B_ID = uuid.UUID("b0000000-0000-0000-0000-000000000001")
PACKAGE_A_ID = uuid.UUID("a0000000-0000-0000-0000-000000000002")
PACKAGE_B_ID = uuid.UUID("b0000000-0000-0000-0000-000000000002")
PROGRAMME_A_ID = uuid.UUID("a0000000-0000-0000-0000-000000000003")
REVISION_A_ID = uuid.UUID("a0000000-0000-0000-0000-000000000004")

TABLES = (
    Organisation.__table__,
    Project.__table__,
    WorkPackage.__table__,
    Programme.__table__,
    ProgrammeRevision.__table__,
    ProgrammeActivityIdentity.__table__,
    ProgrammeActivity.__table__,
)


class ProgrammeActivitySecurityTestCase(unittest.TestCase):
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
        for table in TABLES:
            table.create(cls.engine, checkfirst=True)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.engine.dispose()

    def setUp(self) -> None:
        for table in reversed(TABLES):
            table.drop(self.engine, checkfirst=True)
        for table in TABLES:
            table.create(self.engine, checkfirst=True)

        now = datetime.now(timezone.utc)
        with self.session_factory() as database:
            database.add_all(
                [
                    Organisation(
                        id="org-a",
                        name="Organisation A",
                        slug="org-a",
                        created_at=now,
                    ),
                    Organisation(
                        id="org-b",
                        name="Organisation B",
                        slug="org-b",
                        created_at=now,
                    ),
                    Project(
                        id=PROJECT_A_ID,
                        organization_id="org-a",
                        code="A",
                        name="Project A",
                    ),
                    Project(
                        id=PROJECT_B_ID,
                        organization_id="org-b",
                        code="B",
                        name="Project B",
                    ),
                    WorkPackage(
                        id=PACKAGE_A_ID,
                        project_id=PROJECT_A_ID,
                        code="A-WP",
                        name="Package A",
                    ),
                    WorkPackage(
                        id=PACKAGE_B_ID,
                        project_id=PROJECT_B_ID,
                        code="B-WP",
                        name="Package B",
                    ),
                    Programme(id=PROGRAMME_A_ID, project_id=PROJECT_A_ID),
                    ProgrammeRevision(
                        id=REVISION_A_ID,
                        programme_id=PROGRAMME_A_ID,
                        revision_code="R1",
                        is_current=True,
                    ),
                ]
            )
            database.commit()

    @staticmethod
    def _create_activity(database, **overrides) -> ProgrammeActivity:
        values = {"activity_code": "A100", "name": "Activity"}
        values.update(overrides)
        revision = database.get(ProgrammeRevision, REVISION_A_ID)
        return create_activity(
            database,
            revision,
            ProgrammeActivityCreate(**values),
        )

    def test_create_rejects_work_package_outside_programme_project(self) -> None:
        with self.session_factory() as database:
            revision = database.get(ProgrammeRevision, REVISION_A_ID)

            with self.assertRaises(ProgrammeActivityWorkPackageNotFoundError):
                create_activity(
                    database,
                    revision,
                    ProgrammeActivityCreate(
                        activity_code="A100",
                        name="Foreign package attempt",
                        work_package_id=PACKAGE_B_ID,
                    ),
                )

            self.assertIsNone(
                database.query(ProgrammeActivity)
                .filter_by(activity_code="A100")
                .one_or_none()
            )

    def test_update_rejects_work_package_outside_programme_project(self) -> None:
        with self.session_factory() as database:
            activity = self._create_activity(
                database,
                activity_code="A200",
                name="Valid activity",
                work_package_id=PACKAGE_A_ID,
            )

            with self.assertRaises(ProgrammeActivityWorkPackageNotFoundError):
                update_activity(
                    database,
                    activity,
                    ProgrammeActivityUpdate(work_package_id=PACKAGE_B_ID),
                )

            database.refresh(activity)
            self.assertEqual(activity.work_package_id, PACKAGE_A_ID)

    def test_activity_type_canonically_controls_milestone_flag(self) -> None:
        with self.session_factory() as database:
            activity = self._create_activity(
                database,
                activity_code="M100",
                name="Milestone",
                activity_type="milestone",
                is_milestone=False,
            )
            self.assertTrue(activity.is_milestone)

            updated = update_activity(
                database,
                activity,
                ProgrammeActivityUpdate(
                    activity_type="task",
                    is_milestone=True,
                ),
            )
            self.assertEqual(updated.activity_type, "task")
            self.assertFalse(updated.is_milestone)

    def test_creating_child_persists_parent_summary_state(self) -> None:
        with self.session_factory() as database:
            parent = self._create_activity(
                database,
                activity_code="P100",
                name="Parent",
            )
            parent_id = parent.id
            self._create_activity(
                database,
                activity_code="C100",
                name="Child",
                parent_activity_id=parent_id,
            )

        with self.session_factory() as database:
            persisted_parent = database.get(ProgrammeActivity, parent_id)
            self.assertIsNotNone(persisted_parent)
            self.assertTrue(persisted_parent.is_summary)

    def test_moving_child_persists_old_and_new_parent_summary_state(self) -> None:
        with self.session_factory() as database:
            parent_a = self._create_activity(
                database,
                activity_code="P200",
                name="Parent A",
            )
            parent_b = self._create_activity(
                database,
                activity_code="P300",
                name="Parent B",
            )
            child = self._create_activity(
                database,
                activity_code="C200",
                name="Child",
                parent_activity_id=parent_a.id,
            )
            parent_a_id, parent_b_id, child_id = parent_a.id, parent_b.id, child.id

            update_activity(
                database,
                child,
                ProgrammeActivityUpdate(parent_activity_id=parent_b_id),
            )

        with self.session_factory() as database:
            parent_a = database.get(ProgrammeActivity, parent_a_id)
            parent_b = database.get(ProgrammeActivity, parent_b_id)
            child = database.get(ProgrammeActivity, child_id)
            self.assertFalse(parent_a.is_summary)
            self.assertTrue(parent_b.is_summary)
            self.assertEqual(child.parent_activity_id, parent_b_id)

    def test_deleting_final_child_persists_parent_not_summary(self) -> None:
        with self.session_factory() as database:
            parent = self._create_activity(
                database,
                activity_code="P400",
                name="Parent",
            )
            child = self._create_activity(
                database,
                activity_code="C400",
                name="Child",
                parent_activity_id=parent.id,
            )
            parent_id, child_id = parent.id, child.id
            delete_activity(database, child)

        with self.session_factory() as database:
            self.assertFalse(database.get(ProgrammeActivity, parent_id).is_summary)
            self.assertIsNone(database.get(ProgrammeActivity, child_id))

    def test_cycle_rejection_leaves_persisted_hierarchy_unchanged(self) -> None:
        with self.session_factory() as database:
            parent = self._create_activity(
                database,
                activity_code="P500",
                name="Parent",
            )
            child = self._create_activity(
                database,
                activity_code="C500",
                name="Child",
                parent_activity_id=parent.id,
            )
            parent_id, child_id = parent.id, child.id

            with self.assertRaises(ProgrammeActivityParentCycleError):
                update_activity(
                    database,
                    parent,
                    ProgrammeActivityUpdate(parent_activity_id=child_id),
                )

        with self.session_factory() as database:
            parent = database.get(ProgrammeActivity, parent_id)
            child = database.get(ProgrammeActivity, child_id)
            self.assertIsNone(parent.parent_activity_id)
            self.assertEqual(child.parent_activity_id, parent_id)

    def test_auto_generated_activity_codes_are_sequential_and_persisted(self) -> None:
        with self.session_factory() as database:
            first = self._create_activity(
                database,
                activity_code=None,
                name="First generated activity",
            )
            second = self._create_activity(
                database,
                activity_code=None,
                name="Second generated activity",
            )
            first_id, second_id = first.id, second.id

        with self.session_factory() as database:
            self.assertEqual(
                database.get(ProgrammeActivity, first_id).activity_code,
                "A-00010",
            )
            self.assertEqual(
                database.get(ProgrammeActivity, second_id).activity_code,
                "A-00020",
            )


if __name__ == "__main__":
    unittest.main()
