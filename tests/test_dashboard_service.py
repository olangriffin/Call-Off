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
from app.backend.models.programme.programme import Programme
from app.backend.models.programme.programme_activity import ProgrammeActivity
from app.backend.models.programme.programme_revision import ProgrammeRevision
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
            Programme.__table__,
            ProgrammeRevision.__table__,
            ProgrammeActivity.__table__,
        ):
            table.create(self.engine)

    def tearDown(self) -> None:
        self.engine.dispose()

    def _add_healthy_project(
        self,
        database: Session,
        *,
        organization_id: str,
        code: str,
        today: date,
        status: str = "active",
    ) -> Project:
        project = Project(
            organization_id=organization_id,
            code=code,
            name=f"{code} project",
            status=status,
            planned_start=today - timedelta(days=30),
            planned_finish=today + timedelta(days=90),
        )
        database.add(project)
        database.flush()

        package = WorkPackage(
            project_id=project.id,
            code=f"{code}-WP",
            name="Facade",
            status="active",
            planned_start=today - timedelta(days=10),
            planned_finish=today + timedelta(days=30),
            required_on_site_date=today + timedelta(days=45),
        )
        database.add(package)
        database.flush()
        database.add(
            Deliverable(
                work_package_id=package.id,
                reference=f"{code}-D01",
                name="Coordination drawing",
                deliverable_type="drawing",
                status="in_progress",
                planned_issue_date=today + timedelta(days=21),
                required_approval_date=today + timedelta(days=35),
            )
        )

        programme = Programme(project_id=project.id)
        database.add(programme)
        database.flush()
        revision = ProgrammeRevision(
            programme_id=programme.id,
            revision_code="P01",
            is_current=True,
        )
        database.add(revision)
        database.flush()
        database.add(
            ProgrammeActivity(
                programme_revision_id=revision.id,
                activity_code="A-001",
                name="Coordinate facade",
                activity_type="task",
                status="in_progress",
                planned_start=datetime.combine(
                    today + timedelta(days=7),
                    datetime.min.time(),
                ),
                planned_finish=datetime.combine(
                    today + timedelta(days=28),
                    datetime.min.time(),
                ),
            )
        )
        database.flush()
        return project

    def test_portfolio_rows_are_uncapped_and_tenant_scoped(self) -> None:
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

            database.commit()

            overview = get_dashboard_overview(
                database,
                "org-a",
                today=today,
            )

        self.assertEqual(overview.project_count, 101)
        self.assertEqual(overview.active_project_count, 1)
        self.assertEqual(overview.health_counts.incomplete, 1)
        self.assertEqual(overview.health_counts.inactive, 100)
        self.assertEqual(len(overview.project_health_rows), 101)
        self.assertTrue(
            all(
                row.project.organization_id == "org-a"
                for row in overview.project_health_rows
            )
        )

    def test_healthy_project_is_on_track_with_complete_assessable_data(
        self,
    ) -> None:
        today = date(2026, 8, 11)
        with Session(self.engine) as database:
            organisation = Organisation(
                id="org-health",
                name="Health Organisation",
                slug="health-organisation",
                created_at=datetime.now(timezone.utc),
            )
            database.add(organisation)
            self._add_healthy_project(
                database,
                organization_id=organisation.id,
                code="HEALTH",
                today=today,
            )
            database.commit()

            overview = get_dashboard_overview(
                database,
                organisation.id,
                today=today,
            )

        row = overview.project_health_rows[0]
        self.assertEqual(row.overall_health.key, "on_track")
        self.assertEqual(row.design_health.key, "on_track")
        self.assertEqual(row.programme_health.key, "on_track")
        self.assertEqual(row.procurement_health.key, "incomplete")
        self.assertEqual(row.data_completeness, 100)
        self.assertEqual(overview.health_counts.on_track, 1)

    def test_missing_operational_setup_is_incomplete_not_on_track(self) -> None:
        today = date(2026, 8, 11)
        with Session(self.engine) as database:
            organisation = Organisation(
                id="org-incomplete",
                name="Incomplete Organisation",
                slug="incomplete-organisation",
                created_at=datetime.now(timezone.utc),
            )
            database.add(organisation)
            database.add(
                Project(
                    organization_id=organisation.id,
                    code="GAP",
                    name="Incomplete project",
                    status="active",
                )
            )
            database.commit()

            overview = get_dashboard_overview(
                database,
                organisation.id,
                today=today,
            )

        row = overview.project_health_rows[0]
        self.assertEqual(row.overall_health.key, "incomplete")
        self.assertEqual(row.design_health.key, "incomplete")
        self.assertEqual(row.programme_health.key, "incomplete")
        self.assertGreaterEqual(row.data_completeness, 0)
        self.assertLessEqual(row.data_completeness, 100)

    def test_critical_and_at_risk_conditions_take_precedence_over_incomplete(
        self,
    ) -> None:
        today = date(2026, 8, 11)
        with Session(self.engine) as database:
            organisation = Organisation(
                id="org-risk",
                name="Risk Organisation",
                slug="risk-organisation",
                created_at=datetime.now(timezone.utc),
            )
            database.add(organisation)
            critical_project = self._add_healthy_project(
                database,
                organization_id=organisation.id,
                code="CRITICAL",
                today=today,
            )
            risk_project = self._add_healthy_project(
                database,
                organization_id=organisation.id,
                code="RISK",
                today=today,
            )
            critical_project.work_packages[0].deliverables[0].planned_issue_date = (
                today - timedelta(days=1)
            )
            risk_project.programmes[0].revisions[0].activities[0].planned_finish = (
                datetime.combine(
                    today + timedelta(days=5),
                    datetime.min.time(),
                )
            )
            risk_project.planned_finish = None
            database.commit()

            overview = get_dashboard_overview(
                database,
                organisation.id,
                today=today,
            )

        rows = {row.project.code: row for row in overview.project_health_rows}
        self.assertEqual(rows["CRITICAL"].overall_health.key, "critical")
        self.assertEqual(rows["RISK"].overall_health.key, "at_risk")
        self.assertEqual(overview.health_counts.critical, 1)
        self.assertEqual(overview.health_counts.at_risk, 1)

    def test_inactive_projects_are_excluded_from_active_health_counts(self) -> None:
        today = date(2026, 8, 11)
        with Session(self.engine) as database:
            organisation = Organisation(
                id="org-inactive",
                name="Inactive Organisation",
                slug="inactive-organisation",
                created_at=datetime.now(timezone.utc),
            )
            database.add(organisation)
            self._add_healthy_project(
                database,
                organization_id=organisation.id,
                code="CLOSED",
                today=today,
                status="completed",
            )
            database.commit()

            overview = get_dashboard_overview(
                database,
                organisation.id,
                today=today,
            )

        self.assertEqual(overview.active_project_count, 0)
        self.assertEqual(overview.health_counts.inactive, 1)
        self.assertEqual(
            overview.project_health_rows[0].overall_health.key,
            "inactive",
        )

    def test_no_project_organisation_has_an_empty_portfolio(self) -> None:
        with Session(self.engine) as database:
            organisation = Organisation(
                id="org-empty",
                name="Empty Organisation",
                slug="empty-organisation",
                created_at=datetime.now(timezone.utc),
            )
            database.add(organisation)
            database.commit()

            overview = get_dashboard_overview(database, organisation.id)

        self.assertEqual(overview.project_count, 0)
        self.assertEqual(overview.active_project_count, 0)
        self.assertEqual(overview.project_health_rows, ())

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
        self.assertEqual(overview.health_counts.critical, 1)
        self.assertEqual(
            overview.project_health_rows[0].design_health.key,
            "critical",
        )

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
