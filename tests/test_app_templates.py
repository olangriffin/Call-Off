from __future__ import annotations

import unittest
from datetime import datetime, timezone
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
            'class="sidebar-user"',
        ):
            self.assertIn(expected, body)

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
            context={"page_title": "Project", "company_name": "Call-Off"},
        )
        self.assertNotIn('aria-current="page"', nested_response.body.decode("utf-8"))

    def test_authenticated_pages_use_shared_shell_and_page_title(self) -> None:
        for template_name in AUTHENTICATED_TEMPLATES:
            source = (self.template_root / template_name).read_text()
            with self.subTest(template=template_name):
                self.assertIn('{% extends "base.html" %}', source)
                self.assertIn('class="page-title"', source)

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

    def test_operational_styles_are_scoped_to_authenticated_pages(self) -> None:
        source = Path("app/frontend/static/css/app.css").read_text()

        for expected in (
            "body.app-interface",
            ".app-shell-operational",
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
        source = (self.template_root / "programme/programme.html").read_text()

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

        javascript = Path(
            "app/frontend/static/js/programme-workspace.js"
        ).read_text()
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
        self.assertIn("programme-workspace.js", body)


if __name__ == "__main__":
    unittest.main()
