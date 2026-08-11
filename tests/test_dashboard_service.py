from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest import TestCase

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.backend.models.organisation import Organisation
from app.backend.models.package.approval import Approval
from app.backend.models.package.deliverable import Deliverable
from app.backend.models.package.package import WorkPackage
from app.backend.models.package.revision import DeliverableRevision
from app.backend.models.project import Project
from app.backend.services.approval import (
    InvalidApprovalUpdateError,
    validate_approval_response,
)
from app.backend.services.dashboard import get_dashboard_overview
from app.backend.services.package_readiness import (
    calculate_package_readiness,
    latest_approval,
    latest_revision,
)
from app.backend.services.status import (
    is_complete_status,
    normalize_status,
)


class DashboardServiceTestCase(TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        for table in (
            Organisation.__table__,
            Project.__table__,
            WorkPackage.__table__,
            Deliverable.__table__,
            DeliverableRevision.__table__,
            Approval.__table__,
        ):
            table.create(self.engine)

    def tearDown(self) -> None:
        self.engine.dispose()

    def test_counts_are_uncapped_and_attention_is_sorted_and_tenant_scoped(
        self,
    ) -> None:
        today = date(2026, 8, 11)
        now = datetime.now(timezone.utc)
        with Session(self.engine) as database:
            database.add_all(
                [
                    Organisation(
                        id="org-a",
                        name="Organisation A",
                        slug="organisation-a",
                        created_at=now,
                    ),
                    Organisation(
                        id="org-b",
                        name="Organisation B",
                        slug="organisation-b",
                        created_at=now,
                    ),
                ]
            )
            projects = [
                Project(
                    organization_id="org-a",
                    code=f"A-{index:03}",
                    name=f"Project {index}",
                    status="active" if index == 0 else "completed",
                )
                for index in range(101)
            ]
            project_b = Project(
                organization_id="org-b",
                code="B-001",
                name="Other tenant",
            )
            database.add_all([*projects, project_b])
            database.flush()

            package_a = WorkPackage(
                project_id=projects[0].id,
                code="WP-A",
                name="Facade",
                status="active",
                required_on_site_date=today + timedelta(days=10),
            )
            package_b = WorkPackage(
                project_id=project_b.id,
                code="WP-B",
                name="Other package",
                required_on_site_date=today - timedelta(days=30),
            )
            database.add_all([package_a, package_b])
            database.flush()

            deliverable_a = Deliverable(
                work_package_id=package_a.id,
                reference="D-A",
                name="Elevation drawing",
                deliverable_type="drawing",
                status="in_progress",
                planned_issue_date=today - timedelta(days=2),
                required_approval_date=today + timedelta(days=3),
            )
            deliverable_b = Deliverable(
                work_package_id=package_b.id,
                reference="D-B",
                name="Other tenant drawing",
                deliverable_type="drawing",
                planned_issue_date=today - timedelta(days=20),
            )
            database.add_all([deliverable_a, deliverable_b])
            database.flush()

            revision_a = DeliverableRevision(
                deliverable_id=deliverable_a.id,
                revision_code="P01",
            )
            revision_b = DeliverableRevision(
                deliverable_id=deliverable_b.id,
                revision_code="P01",
            )
            database.add_all([revision_a, revision_b])
            database.flush()
            database.add_all(
                [
                    Approval(
                        revision_id=revision_a.id,
                        status="pending",
                        response_due_date=today - timedelta(days=1),
                    ),
                    Approval(
                        revision_id=revision_a.id,
                        status="status_a",
                        response_due_date=today - timedelta(days=3),
                    ),
                    Approval(
                        revision_id=revision_a.id,
                        status="pending",
                        response_due_date=today + timedelta(days=60),
                    ),
                    Approval(
                        revision_id=revision_b.id,
                        status="pending",
                        response_due_date=today - timedelta(days=10),
                    ),
                ]
            )
            database.commit()

            overview = get_dashboard_overview(
                database,
                "org-a",
                today=today,
            )

        self.assertEqual(overview.project_count, 101)
        self.assertEqual(overview.active_project_count, 1)
        self.assertEqual(overview.work_package_count, 1)
        self.assertEqual(overview.deliverable_count, 1)
        self.assertEqual(overview.overdue_deadline_count, 3)
        self.assertEqual(overview.overdue_count, 3)
        self.assertEqual(len(overview.attention_items), 5)
        self.assertEqual(
            {item.kind for item in overview.attention_items},
            {
                "approval_response",
                "deliverable_issue",
                "deliverable_approval",
                "package_on_site",
            },
        )
        self.assertEqual(
            [item.due_date for item in overview.attention_items],
            sorted(item.due_date for item in overview.attention_items),
        )
        self.assertTrue(
            all(
                item.due_date <= today + timedelta(days=14)
                for item in overview.attention_items
            )
        )
        self.assertTrue(
            all("Other tenant" not in item.label for item in overview.attention_items)
        )
        self.assertTrue(
            all("org-b" not in item.url for item in overview.attention_items)
        )
        self.assertEqual(
            sum(
                item.kind == "approval_response"
                for item in overview.attention_items
            ),
            2,
        )

    def test_contractor_codes_do_not_imply_completion(self) -> None:
        for contractor_status in ("status_a", "status_b"):
            with self.subTest(status=contractor_status):
                approval = SimpleNamespace(
                    status=contractor_status,
                    response_received_date=date(2026, 8, 10),
                    submitted_date=date(2026, 8, 1),
                    id=uuid.uuid4(),
                )
                revision = SimpleNamespace(
                    issue_date=date(2026, 8, 1),
                    revision_code="P01",
                    approvals=[approval],
                )
                deliverable = SimpleNamespace(
                    status="in_progress",
                    planned_issue_date=None,
                    required_approval_date=None,
                    revisions=[revision],
                )

                summary = calculate_package_readiness(
                    [deliverable],
                    date(2026, 9, 1),
                    today=date(2026, 8, 11),
                )

                self.assertEqual(summary.complete_deliverables, 0)
                self.assertEqual(summary.pending_approval_count, 1)

    def test_completion_status_variants_are_consistent_across_services(
        self,
    ) -> None:
        today = date(2026, 8, 11)
        now = datetime.now(timezone.utc)
        complete_statuses = (
            "accepted_with_comments",
            "accepted with comments",
            "accepted-with-comments",
            "  ACCEPTED  WITH-COMMENTS  ",
        )

        self.assertEqual(
            {normalize_status(status) for status in complete_statuses},
            {"accepted_with_comments"},
        )
        self.assertTrue(
            all(is_complete_status(status) for status in complete_statuses)
        )
        self.assertFalse(is_complete_status("status_a"))
        self.assertFalse(is_complete_status("status_b"))

        for status in complete_statuses:
            deliverable = SimpleNamespace(
                status=status,
                planned_issue_date=today - timedelta(days=5),
                required_approval_date=today - timedelta(days=4),
                revisions=[],
            )
            summary = calculate_package_readiness(
                [deliverable],
                today + timedelta(days=20),
                today=today,
            )
            self.assertEqual(summary.complete_deliverables, 1)
            self.assertEqual(summary.overdue_issue_count, 0)
            self.assertEqual(summary.overdue_approval_count, 0)

        with Session(self.engine) as database:
            organisation = Organisation(
                id="org-status",
                name="Status Organisation",
                slug="status-organisation",
                created_at=now,
            )
            project = Project(
                organization_id=organisation.id,
                code="STATUS",
                name="Status project",
                status="  ACTIVE  ",
            )
            database.add_all([organisation, project])
            database.flush()

            for index, status in enumerate(complete_statuses):
                package = WorkPackage(
                    project_id=project.id,
                    code=f"WP-{index}",
                    name=f"Complete package {index}",
                    status=status,
                    required_on_site_date=today - timedelta(days=3),
                )
                database.add(package)
                database.flush()
                database.add(
                    Deliverable(
                        work_package_id=package.id,
                        reference=f"D-{index}",
                        name=f"Complete deliverable {index}",
                        deliverable_type="drawing",
                        status=status,
                        planned_issue_date=today - timedelta(days=2),
                        required_approval_date=today - timedelta(days=1),
                    )
                )

            contractor_package = WorkPackage(
                project_id=project.id,
                code="WP-CONTRACTOR",
                name="Contractor-coded package",
                status="status_a",
                required_on_site_date=today - timedelta(days=3),
            )
            database.add(contractor_package)
            database.flush()
            database.add(
                Deliverable(
                    work_package_id=contractor_package.id,
                    reference="D-CONTRACTOR",
                    name="Contractor-coded deliverable",
                    deliverable_type="drawing",
                    status="status_b",
                    planned_issue_date=today - timedelta(days=2),
                    required_approval_date=today - timedelta(days=1),
                )
            )
            database.commit()

            overview = get_dashboard_overview(
                database,
                organisation.id,
                today=today,
            )

        self.assertEqual(overview.active_project_count, 1)
        self.assertEqual(overview.overdue_deadline_count, 3)
        self.assertEqual(len(overview.attention_items), 3)

    def test_latest_approval_uses_request_chronology_not_response_date(
        self,
    ) -> None:
        older_approval = SimpleNamespace(
            response_received_date=date(2026, 8, 10),
            submitted_date=date(2026, 8, 1),
            created_at=datetime(2026, 8, 1, 8, tzinfo=timezone.utc),
            id=uuid.UUID("10000000-0000-0000-0000-000000000001"),
        )
        newer_approval = SimpleNamespace(
            response_received_date=None,
            submitted_date=date(2026, 8, 5),
            created_at=datetime(2026, 8, 5, 8, tzinfo=timezone.utc),
            id=uuid.UUID("10000000-0000-0000-0000-000000000002"),
        )
        older_revision = SimpleNamespace(
            issue_date=date(2026, 8, 1),
            revision_code="P02",
            approvals=[],
        )
        newer_revision = SimpleNamespace(
            issue_date=date(2026, 8, 5),
            revision_code="P01",
            approvals=[older_approval, newer_approval],
        )
        deliverable = SimpleNamespace(
            revisions=[older_revision, newer_revision],
        )

        selected_revision = latest_revision(deliverable)

        self.assertIs(selected_revision, newer_revision)
        self.assertIs(latest_approval(selected_revision), newer_approval)

    def test_latest_approval_uses_id_only_for_an_exact_chronology_tie(
        self,
    ) -> None:
        earlier_creation = Approval(
            id=uuid.UUID("f0000000-0000-0000-0000-000000000001"),
            revision_id=uuid.uuid4(),
            submitted_date=None,
            created_at=datetime(2026, 8, 2, 9, tzinfo=timezone.utc),
        )
        later_creation = Approval(
            id=uuid.UUID("10000000-0000-0000-0000-000000000001"),
            revision_id=uuid.uuid4(),
            submitted_date=None,
            created_at=datetime(2026, 8, 3, 9, tzinfo=timezone.utc),
        )
        revision = SimpleNamespace(
            approvals=[earlier_creation, later_creation],
        )

        self.assertIs(latest_approval(revision), later_creation)

        first_tie = SimpleNamespace(
            submitted_date=date(2026, 8, 4),
            id=uuid.UUID("10000000-0000-0000-0000-000000000001"),
        )
        deterministic_tie_winner = SimpleNamespace(
            submitted_date=date(2026, 8, 4),
            id=uuid.UUID("f0000000-0000-0000-0000-000000000001"),
        )
        tied_revision = SimpleNamespace(
            approvals=[deterministic_tie_winner, first_tie],
        )

        self.assertIs(
            latest_approval(tied_revision),
            deterministic_tie_winner,
        )

    def test_package_and_deliverable_views_share_latest_approval_helper(
        self,
    ) -> None:
        from app.backend.routes.frontend import deliverables, work_packages

        self.assertIs(deliverables.latest_approval, latest_approval)
        self.assertIs(work_packages.latest_approval, latest_approval)

    def test_approval_response_requires_a_consistent_status_date_pair(
        self,
    ) -> None:
        with self.assertRaisesRegex(
            InvalidApprovalUpdateError,
            "pending approval cannot have",
        ):
            validate_approval_response("pending", date(2026, 8, 9))

        with self.assertRaisesRegex(
            InvalidApprovalUpdateError,
            "response received date is required",
        ):
            validate_approval_response("status_a", None)

        validate_approval_response("pending", None)
        validate_approval_response("status_a", date(2026, 8, 9))
