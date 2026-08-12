from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException, status
from starlette.requests import Request

from app.backend.core.auth import (
    can_create_projects,
    enforce_project_creation_access,
    require_frontend_project_creation_access,
    require_organisation_access,
    require_project_creation_access,
)
from app.backend.routes.frontend.dashboard import dashboard
from app.backend.routes.frontend.projects import router as frontend_projects_router
from app.backend.routes.projects import router as projects_router
from app.backend.schemas.auth import AuthenticatedUser, OrganisationAccessContext
from app.main import create_app


USER_ID = "11111111-1111-1111-1111-111111111111"


def request_with_session() -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/auth/context",
            "headers": [
                (
                    b"cookie",
                    (
                        b"calloff_session_name=neon_session_token; "
                        b"calloff_session=session-value"
                    ),
                )
            ],
        }
    )


def authenticated_database(memberships: list[object]) -> MagicMock:
    database = MagicMock()
    auth_user = SimpleNamespace(
        id=USER_ID,
        name="Tenant User",
        email="tenant@example.com",
        email_verified=True,
    )
    organisation = SimpleNamespace(
        id="org-a",
        name="Organisation A",
        slug="organisation-a",
    )
    database.get.side_effect = [auth_user, organisation]
    database.scalars.return_value = memberships
    return database


def active_membership() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
        user_id=USER_ID,
        organization_id="org-a",
        role="PROJECT_MANAGER",
        status="active",
        revoked_at=None,
    )


def organisation_access(role: str) -> OrganisationAccessContext:
    return OrganisationAccessContext(
        user=AuthenticatedUser(
            id=USER_ID,
            name="Tenant User",
            email="tenant@example.com",
            email_verified=True,
        ),
        membership_id="22222222-2222-2222-2222-222222222222",
        role=role,
        organization_id="org-a",
        organization_name="Organisation A",
        organization_slug="organisation-a",
    )


class RequireOrganisationAccessTestCase(IsolatedAsyncioTestCase):
    async def call_dependency(self, database: MagicMock):
        neon_session = {
            "user": {"id": USER_ID},
            "session": {"id": "session-id"},
        }
        with patch(
            "app.backend.core.auth.get_neon_session",
            new=AsyncMock(return_value=neon_session),
        ):
            return await require_organisation_access(
                request_with_session(),
                database,
            )

    async def test_active_non_revoked_membership_returns_access_context(self) -> None:
        database = authenticated_database([active_membership()])

        access = await self.call_dependency(database)

        self.assertEqual(access.user.id, USER_ID)
        self.assertEqual(access.organization_id, "org-a")
        self.assertEqual(access.role, "project_manager")

        membership_statement = database.scalars.call_args.args[0]
        statement_text = str(membership_statement)
        self.assertIn("memberships.status =", statement_text)
        self.assertIn("memberships.revoked_at IS NULL", statement_text)

    async def test_missing_session_returns_401(self) -> None:
        request = Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/auth/context",
                "headers": [],
            }
        )

        with self.assertRaises(HTTPException) as raised:
            await require_organisation_access(request, MagicMock())

        self.assertEqual(raised.exception.status_code, status.HTTP_401_UNAUTHORIZED)

    async def test_no_qualifying_active_non_revoked_membership_returns_403(self) -> None:
        database = authenticated_database([])

        with self.assertRaises(HTTPException) as raised:
            await self.call_dependency(database)

        self.assertEqual(raised.exception.status_code, status.HTTP_403_FORBIDDEN)

    async def test_multiple_active_memberships_preserve_one_organisation_rule(self) -> None:
        first = active_membership()
        second = active_membership()
        second.id = uuid.UUID("33333333-3333-3333-3333-333333333333")
        second.organization_id = "org-b"
        database = authenticated_database([first, second])

        with self.assertRaises(HTTPException) as raised:
            await self.call_dependency(database)

        self.assertEqual(raised.exception.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("one organisation", raised.exception.detail)


class ProjectCreationCapabilityTestCase(TestCase):
    def test_owner_can_create_projects(self) -> None:
        access = organisation_access("owner")

        self.assertTrue(can_create_projects(access))
        self.assertIs(enforce_project_creation_access(access), access)

    def test_project_manager_can_create_projects(self) -> None:
        access = organisation_access("project_manager")

        self.assertTrue(can_create_projects(access))
        self.assertIs(enforce_project_creation_access(access), access)

    def test_member_cannot_create_projects(self) -> None:
        access = organisation_access("member")

        self.assertFalse(can_create_projects(access))
        with self.assertRaises(HTTPException) as raised:
            enforce_project_creation_access(access)

        self.assertEqual(raised.exception.status_code, status.HTTP_403_FORBIDDEN)

    def test_html_and_json_creation_routes_use_capability_dependencies(self) -> None:
        json_route = next(
            route
            for route in projects_router.routes
            if getattr(route, "path", None) == "/projects"
            and "POST" in getattr(route, "methods", set())
        )
        json_dependencies = {
            dependency.call for dependency in json_route.dependant.dependencies
        }
        self.assertIn(require_project_creation_access, json_dependencies)

        for method in ("GET", "POST"):
            html_route = next(
                route
                for route in frontend_projects_router.routes
                if getattr(route, "path", None) == "/app/projects/new"
                and method in getattr(route, "methods", set())
            )
            html_dependencies = {
                dependency.call for dependency in html_route.dependant.dependencies
            }
            self.assertIn(
                require_frontend_project_creation_access,
                html_dependencies,
            )

    def test_dashboard_creation_actions_match_capability_rule(self) -> None:
        application = create_app()
        overview = SimpleNamespace(
            project_count=0,
            active_project_count=0,
            health_counts=SimpleNamespace(
                on_track=0,
                at_risk=0,
                critical=0,
                incomplete=0,
                inactive=0,
            ),
            project_health_rows=[],
            active_project_health_rows=[],
        )

        for role, should_show_action in (
            ("owner", True),
            ("project_manager", True),
            ("member", False),
        ):
            with self.subTest(role=role):
                request = Request(
                    {
                        "type": "http",
                        "method": "GET",
                        "path": "/app",
                        "headers": [],
                        "router": application.router,
                    }
                )
                with patch(
                    "app.backend.routes.frontend.dashboard.get_dashboard_overview",
                    return_value=overview,
                ):
                    response = dashboard(
                        request,
                        MagicMock(),
                        organisation_access(role),
                    )

                body = response.body.decode("utf-8")
                self.assertEqual(
                    '/app/projects/new' in body,
                    should_show_action,
                )
