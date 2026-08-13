from __future__ import annotations

import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from starlette.requests import Request

from app.backend.frontend_templates import build_frontend_templates
from app.backend.services.programme_workspace import build_programme_workspace
from app.main import create_app


AUTHENTICATED_TEMPLATES = (
    "dashboard.html",
    "project/project_detail.html",
    "project/project_new.html",
    "package/work_package_detail.html",
    "package/work_package_new.html",
    "programme/programme.html",
    "programme/programme_activity_new.html",
    "programme/programme_activity_edit.html",
    "deliverable/deliverable_detail.html",
    "deliverable/deliverable_new.html",
    "deliverable/deliverable_revision_new.html",
    "deliverable/approval_new.html",
    "deliverable/approval_response.html",
)

NORMALIZED_FORM_TEMPLATES = (
    "project/project_new.html",
    "package/work_package_new.html",
    "programme/programme_activity_new.html",
    "programme/programme_activity_edit.html",
)


class AppTemplateTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = create_app()
        cls.templates = build_frontend_templates()
        cls.template_root = Path("app/frontend/templates")

    def test_authenticated_shell_uses_operational_visual_hooks(self) -> None:
        request = Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/app",
                "headers": [],
                "router": self.application.router,
            }
        )
        response = self.templates.TemplateResponse(
            request=request,
            name="base.html",
            context={
                "page_title": "Projects",
                "company_name": "Call-Off",
                "current_role": "owner",
                "current_user": SimpleNamespace(
                    name="Alex Builder",
                    email="alex@example.com",
                ),
            },
        )
        body = response.body.decode("utf-8")

        for expected in (
            'class="app-interface"',
            "app-shell-operational",
            'class="skip-link" href="#main-content"',
            'id="main-content"',
            'aria-label="Application"',
            'aria-current="page"',
            "site-nav-menu-account",
            'class="site-nav-account-name"',
        ):
            self.assertIn(expected, body)

        # No sidebar left to remove: the nav is a single shared component,
        # and it must not fall back to the marketing nav on an authenticated
        # page just because the URL is nested under /app.
        self.assertNotIn('class="site-nav-links" aria-label="Primary"', body)

        nested_request = Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/app/projects/project-1",
                "headers": [],
                "router": self.application.router,
            }
        )
        nested_response = self.templates.TemplateResponse(
            request=nested_request,
            name="base.html",
            context={
                "page_title": "Project",
                "company_name": "Call-Off",
                "current_role": "owner",
                "current_user": SimpleNamespace(
                    name="Alex Builder",
                    email="alex@example.com",
                ),
            },
        )
        nested_body = nested_response.body.decode("utf-8")
        self.assertIn("site-nav-menu-account", nested_body)
        self.assertIn('aria-current="page">Dashboard</a>', nested_body)
        self.assertNotIn(">Settings</a>", nested_body)

    def test_authenticated_pages_use_shared_shell_and_page_title(self) -> None:
        for template_name in AUTHENTICATED_TEMPLATES:
            source = (self.template_root / template_name).read_text()
            with self.subTest(template=template_name):
                self.assertIn('{% extends "base.html" %}', source)
                self.assertTrue(
                    'class="page-title"' in source or "section_header(" in source
                )

    def test_dashboard_renders_portfolio_health_and_not_attention_queue(self) -> None:
        source = (self.template_root / "dashboard.html").read_text()

        for expected in (
            "Project health distribution",
            "Delivery health by project",
            "Project portfolio health",
            "overview.health_counts.on_track",
            "row.data_completeness",
            "Procurement",
        ):
            self.assertIn(expected, source)

        self.assertNotIn("Requires attention", source)
        self.assertNotIn("attention_items", source)
        self.assertNotIn("overdue_deadline_count", source)

        request = Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/app",
                "headers": [],
                "router": self.application.router,
            }
        )
        project = SimpleNamespace(
            id="project-1",
            code="LON15",
            name="London facade",
        )

        def state(key: str, label: str, css_class: str) -> SimpleNamespace:
            return SimpleNamespace(
                key=key,
                label=label,
                css_class=css_class,
            )

        row = SimpleNamespace(
            project=project,
            overall_health=state("critical", "Critical", "badge-critical"),
            design_health=state("at_risk", "At Risk", "badge-warning"),
            programme_health=state("critical", "Critical", "badge-critical"),
            procurement_health=state("incomplete", "Incomplete", "badge-muted"),
            data_completeness=98,
            delivery_health=[
                SimpleNamespace(
                    package=SimpleNamespace(code="WP-01"),
                    health=state("critical", "Critical", "badge-critical"),
                )
            ],
        )
        overview = SimpleNamespace(
            project_count=1,
            active_project_count=1,
            health_counts=SimpleNamespace(
                on_track=0,
                at_risk=0,
                critical=1,
                incomplete=0,
            ),
            project_health_rows=[row],
            active_project_health_rows=[row],
        )
        response = self.templates.TemplateResponse(
            request=request,
            name="dashboard.html",
            context={
                "page_title": "Dashboard",
                "company_name": "Call-Off",
                "can_create_projects": True,
                "overview": overview,
            },
        )
        body = response.body.decode("utf-8")
        self.assertIn("LON15", body)
        self.assertIn("98%", body)
        self.assertIn("Procurement", body)
        self.assertIn("Incomplete", body)

    def test_missing_project_state_keeps_primary_heading(self) -> None:
        request = Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/app/projects/missing",
                "headers": [],
                "router": self.application.router,
            }
        )
        response = self.templates.TemplateResponse(
            request=request,
            name="project/project_detail.html",
            context={
                "project": None,
                "page_title": "Project not found",
                "company_name": "Call-Off",
            },
        )
        body = response.body.decode("utf-8")

        self.assertIn('<h1 class="page-title">Project not found</h1>', body)
        self.assertNotIn('aria-current="page"', body)

    def test_outlier_forms_use_shared_form_components(self) -> None:
        for template_name in NORMALIZED_FORM_TEMPLATES:
            source = (self.template_root / template_name).read_text()
            with self.subTest(template=template_name):
                self.assertIn('class="form-grid"', source)
                self.assertIn('class="form-field', source)
                self.assertIn('class="form-actions form-field-full"', source)

    def test_package_deliverables_render_from_prepared_rows(self) -> None:
        request = Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/app/projects/project-1/work-packages/package-1",
                "headers": [],
                "router": self.application.router,
            }
        )
        deliverable = SimpleNamespace(
            id="deliverable-1",
            reference="D-001",
            name="Coordination drawings",
            deliverable_type="drawing",
            status="in_progress",
            planned_issue_date=date(2026, 8, 12),
            required_approval_date=date(2026, 8, 20),
        )
        latest_revision = SimpleNamespace(revision_code="P02")
        latest_approval = SimpleNamespace(
            status="pending",
            response_due_date=date(2026, 8, 18),
        )
        readiness = SimpleNamespace(
            key="attention",
            css_class="badge-warning",
            label="Attention needed",
            completion_percentage=25,
            description="Approval work remains outstanding.",
            complete_deliverables=0,
            total_deliverables=1,
            overdue_issue_count=0,
            overdue_approval_count=0,
            pending_approval_count=1,
        )

        response = self.templates.TemplateResponse(
            request=request,
            name="package/work_package_detail.html",
            context={
                "project": SimpleNamespace(id="project-1", code="P100"),
                "work_package": SimpleNamespace(
                    id="package-1",
                    code="WP01",
                    name="External envelope",
                    package_type="subcontract",
                    status="active",
                    required_on_site_date=date(2026, 9, 1),
                ),
                "deliverable_rows": [
                    {
                        "deliverable": deliverable,
                        "latest_revision": latest_revision,
                        "latest_approval": latest_approval,
                    }
                ],
                "readiness": readiness,
                "page_title": "External envelope",
                "company_name": "Call-Off",
            },
        )
        body = response.body.decode("utf-8")

        self.assertIn("Coordination drawings", body)
        self.assertIn("Revision P02", body)
        self.assertIn("Due 18 Aug 2026", body)
        source = (self.template_root / "package/work_package_detail.html").read_text()
        self.assertNotIn("sort(attribute='created_at'", source)

    def test_approval_response_preserves_unrecognised_current_status(self) -> None:
        request = Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/app/projects/project-1/work-packages/package-1/deliverables/deliverable-1/revisions/revision-1/approvals/approval-1/respond",
                "headers": [],
                "router": self.application.router,
            }
        )
        response = self.templates.TemplateResponse(
            request=request,
            name="deliverable/approval_response.html",
            context={
                "project": SimpleNamespace(id="project-1", code="P100"),
                "work_package": SimpleNamespace(id="package-1", code="WP01"),
                "deliverable": SimpleNamespace(
                    id="deliverable-1", reference="D-001"
                ),
                "revision": SimpleNamespace(id="revision-1", revision_code="P02"),
                "approval": SimpleNamespace(
                    id="approval-1",
                    approval_stage="client_approval",
                    reviewer_name="Design team",
                    submitted_date=date(2026, 8, 1),
                    response_due_date=date(2026, 8, 10),
                    response_received_date=date(2026, 8, 9),
                    status="status_b",
                    comments="Accepted subject to notes",
                ),
                "form_values": {
                    "status": "status_b",
                    "response_received_date": "2026-08-09",
                    "comments": "Accepted subject to notes",
                },
                "page_title": "Record approval response",
                "company_name": "Call-Off",
            },
        )
        body = response.body.decode("utf-8")

        self.assertIn(
            '<option value="status_b" selected>Status B (current recorded status)</option>',
            body,
        )
        self.assertIn('aria-describedby="response-received-date-help"', body)
        self.assertIn("Required for any outcome other than Pending", body)

    def test_non_pending_approval_without_response_date_is_explicit(self) -> None:
        request = Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/app/projects/project-1/work-packages/package-1/deliverables/deliverable-1",
                "headers": [],
                "router": self.application.router,
            }
        )
        approval = SimpleNamespace(
            id="approval-1",
            approval_stage="client_approval",
            reviewer_name="Design team",
            submitted_date=date(2026, 8, 1),
            response_due_date=date(2026, 8, 10),
            response_received_date=None,
            status="approved",
            created_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        )
        revision = SimpleNamespace(
            id="revision-1",
            revision_code="P02",
            status="issued",
            issue_purpose="For construction",
            issue_date=date(2026, 8, 1),
            notes=None,
            approvals=[approval],
        )
        response = self.templates.TemplateResponse(
            request=request,
            name="deliverable/deliverable_detail.html",
            context={
                "project": SimpleNamespace(id="project-1", code="P100"),
                "work_package": SimpleNamespace(id="package-1", code="WP01"),
                "deliverable": SimpleNamespace(
                    id="deliverable-1",
                    reference="D-001",
                    name="Coordination drawings",
                    deliverable_type="drawing",
                    status="in_progress",
                    planned_issue_date=date(2026, 8, 1),
                    required_approval_date=date(2026, 8, 10),
                    description=None,
                    created_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
                    updated_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
                ),
                "current_revision": revision,
                "current_approval": approval,
                "historical_revisions": [],
                "page_title": "Coordination drawings",
                "company_name": "Call-Off",
            },
        )
        body = response.body.decode("utf-8")

        self.assertIn("Response date missing", body)
        self.assertIn("Complete response record", body)
        self.assertNotIn("Response due 10 Aug 2026", body)

    def test_operational_styles_are_scoped_to_authenticated_pages(self) -> None:
        # main.css is just the @import manifest; the actual rules live in
        # the split files it pulls in under css/.
        css_dir = Path("app/frontend/static/css")
        source = (css_dir / "main.css").read_text() + "".join(
            path.read_text() for path in sorted(css_dir.rglob("*.css")) if path.name != "main.css"
        )

        for expected in (
            "body.app-interface",
            ".site-nav-menu-account",
            "--radius-panel",
            "body.app-interface .panel",
            "body.app-interface .form-field input",
            "body.app-interface .table-container",
        ):
            self.assertIn(expected, source)

    def test_auth_pages_keep_their_marketing_shell_overrides(self) -> None:
        for template_name in ("auth/login.html", "auth/register.html"):
            source = (self.template_root / template_name).read_text()
            with self.subTest(template=template_name):
                self.assertIn("auth-marketing", source)
                self.assertIn("app-shell-auth", source)

    def test_programme_uses_operational_register_and_timeline(self) -> None:
        # programme.html pulls its thead/add-row/edit-row markup in from
        # partials/programme/, so check the page's whole template graph
        # rather than just the one file.
        partials_dir = self.template_root / "partials/programme"
        source = (self.template_root / "programme/programme.html").read_text() + "".join(
            path.read_text() for path in sorted(partials_dir.glob("*.html"))
        )

        for expected in (
            "data-programme-workspace",
            "programme-table",
            "programme-timeline-column",
            "data-programme-search",
            "data-programme-status",
            "data-programme-package",
            "data-programme-today",
            '<span class="visually-hidden">Timeline</span>',
            "Add first activity",
        ):
            self.assertIn(expected, source)

        self.assertEqual(source.count("data-today-marker"), 1)

        javascript = Path("app/frontend/static/js/programme/workspace.js").read_text()
        for expected in (
            'matchMedia("(prefers-reduced-motion: reduce)")',
            "todayButton.disabled = matchCount === 0",
            "visibleActivityIds.add(parentId)",
            "with their parent activities",
        ):
            self.assertIn(expected, javascript)

    def test_programme_activity_type_controls_milestone_flag(self) -> None:
        source = Path(
            "app/backend/routes/frontend/programme_activities.py"
        ).read_text()

        self.assertEqual(source.count('== "milestone"'), 2)
        self.assertNotIn('form.get("is_milestone") == "on"', source)

    def test_programme_workspace_renders_scheduled_and_unscheduled_rows(self) -> None:
        request = Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/app/projects/project-1/programme",
                "headers": [],
                "router": self.application.router,
            }
        )
        base_values = {
            "activity_type": "task",
            "duration_minutes": None,
            "percent_complete": 25,
            "is_milestone": False,
            "is_summary": False,
            "status": "in_progress",
            "work_package": None,
        }
        scheduled = SimpleNamespace(
            **base_values,
            id="activity-1",
            activity_code="A100",
            name="Coordinate design",
            planned_start=datetime(2026, 8, 10, tzinfo=timezone.utc),
            planned_finish=datetime(2026, 8, 14, tzinfo=timezone.utc),
        )
        unscheduled = SimpleNamespace(
            **base_values,
            id="activity-2",
            activity_code="A200",
            name="Release package",
            planned_start=None,
            planned_finish=None,
        )
        activity_rows = [
            {"activity": scheduled, "depth": 0},
            {"activity": unscheduled, "depth": 1},
        ]
        workspace = build_programme_workspace(activity_rows)

        response = self.templates.TemplateResponse(
            request=request,
            name="programme/programme.html",
            context={
                "project": SimpleNamespace(id="project-1", code="P100"),
                "revision": SimpleNamespace(revision_code="CURRENT"),
                "activity_rows": activity_rows,
                "workspace": workspace,
                "page_title": "Programme",
                "company_name": "Call-Off",
            },
        )
        body = response.body.decode("utf-8")

        self.assertIn("Coordinate design", body)
        self.assertIn("programme-bar", body)
        self.assertIn("Release package", body)
        self.assertIn("Dates not set", body)
        self.assertIn("programme/workspace.js", body)


if __name__ == "__main__":
    unittest.main()
