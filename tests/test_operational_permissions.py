from __future__ import annotations

import unittest
import uuid
from unittest.mock import MagicMock

import httpx
from fastapi import HTTPException, status
from starlette.routing import Match

from app.backend.core.auth import (
    enforce_approval_response_access,
    enforce_destructive_operation_access,
    enforce_operational_write_access,
    require_approval_response_access,
    require_destructive_operation_access,
    require_frontend_approval_response_access,
    require_frontend_destructive_operation_access,
    require_frontend_operational_write_access,
    require_frontend_organisation_access,
    require_frontend_project_creation_access,
    require_operational_write_access,
    require_organisation_access,
    require_project_creation_access,
)
from app.backend.database.session import get_db
from app.backend.routes.approvals import router as approvals_router
from app.backend.routes.deliverable_revisions import router as revisions_router
from app.backend.routes.deliverables import router as deliverables_router
from app.backend.routes.frontend.deliverables import router as frontend_deliverables_router
from app.backend.routes.frontend.programme_activities import (
    router as frontend_programme_router,
)
from app.backend.routes.frontend.projects import router as frontend_projects_router
from app.backend.routes.frontend.work_packages import router as frontend_packages_router
from app.backend.routes.programme_activities import router as programme_router
from app.backend.routes.projects import router as projects_router
from app.backend.routes.work_packages import router as packages_router
from app.backend.schemas.auth import AuthenticatedUser, OrganisationAccessContext
from app.main import create_app


RESOURCE_IDS = [
    str(uuid.UUID(int=index))
    for index in range(1, 7)
]
PROJECT_ID, PACKAGE_ID, DELIVERABLE_ID, REVISION_ID, APPROVAL_ID, ACTIVITY_ID = (
    RESOURCE_IDS
)


def access_for(role: str) -> OrganisationAccessContext:
    return OrganisationAccessContext(
        user=AuthenticatedUser(
            id="11111111-1111-1111-1111-111111111111",
            name="Permission Test User",
            email="permissions@example.com",
            email_verified=True,
        ),
        membership_id="22222222-2222-2222-2222-222222222222",
        role=role,
        organization_id="org-a",
        organization_name="Organisation A",
        organization_slug="organisation-a",
    )


JSON_MUTATIONS = (
    ("POST", "/projects", require_project_creation_access),
    ("PATCH", f"/projects/{PROJECT_ID}", require_operational_write_access),
    ("DELETE", f"/projects/{PROJECT_ID}", require_destructive_operation_access),
    (
        "POST",
        f"/projects/{PROJECT_ID}/work-packages",
        require_operational_write_access,
    ),
    (
        "PATCH",
        f"/projects/{PROJECT_ID}/work-packages/{PACKAGE_ID}",
        require_operational_write_access,
    ),
    (
        "DELETE",
        f"/projects/{PROJECT_ID}/work-packages/{PACKAGE_ID}",
        require_destructive_operation_access,
    ),
    (
        "POST",
        f"/projects/{PROJECT_ID}/work-packages/{PACKAGE_ID}/deliverables",
        require_operational_write_access,
    ),
    (
        "PATCH",
        f"/projects/{PROJECT_ID}/work-packages/{PACKAGE_ID}/deliverables/{DELIVERABLE_ID}",
        require_operational_write_access,
    ),
    (
        "DELETE",
        f"/projects/{PROJECT_ID}/work-packages/{PACKAGE_ID}/deliverables/{DELIVERABLE_ID}",
        require_destructive_operation_access,
    ),
    (
        "POST",
        f"/projects/{PROJECT_ID}/work-packages/{PACKAGE_ID}/deliverables/{DELIVERABLE_ID}/revisions",
        require_operational_write_access,
    ),
    (
        "PATCH",
        f"/projects/{PROJECT_ID}/work-packages/{PACKAGE_ID}/deliverables/{DELIVERABLE_ID}/revisions/{REVISION_ID}",
        require_operational_write_access,
    ),
    (
        "DELETE",
        f"/projects/{PROJECT_ID}/work-packages/{PACKAGE_ID}/deliverables/{DELIVERABLE_ID}/revisions/{REVISION_ID}",
        require_destructive_operation_access,
    ),
    (
        "POST",
        f"/projects/{PROJECT_ID}/work-packages/{PACKAGE_ID}/deliverables/{DELIVERABLE_ID}/revisions/{REVISION_ID}/approvals",
        require_operational_write_access,
    ),
    (
        "PATCH",
        f"/projects/{PROJECT_ID}/work-packages/{PACKAGE_ID}/deliverables/{DELIVERABLE_ID}/revisions/{REVISION_ID}/approvals/{APPROVAL_ID}",
        require_approval_response_access,
    ),
    (
        "DELETE",
        f"/projects/{PROJECT_ID}/work-packages/{PACKAGE_ID}/deliverables/{DELIVERABLE_ID}/revisions/{REVISION_ID}/approvals/{APPROVAL_ID}",
        require_destructive_operation_access,
    ),
    (
        "POST",
        f"/projects/{PROJECT_ID}/programme/activities",
        require_operational_write_access,
    ),
    (
        "PATCH",
        f"/projects/{PROJECT_ID}/programme/activities/{ACTIVITY_ID}",
        require_operational_write_access,
    ),
    (
        "DELETE",
        f"/projects/{PROJECT_ID}/programme/activities/{ACTIVITY_ID}",
        require_destructive_operation_access,
    ),
)


FRONTEND_MUTATIONS = (
    ("GET", "/app/projects/new", require_frontend_project_creation_access),
    ("POST", "/app/projects/new", require_frontend_project_creation_access),
    (
        "GET",
        f"/app/projects/{PROJECT_ID}/work-packages/new",
        require_frontend_operational_write_access,
    ),
    (
        "POST",
        f"/app/projects/{PROJECT_ID}/work-packages/new",
        require_frontend_operational_write_access,
    ),
    (
        "GET",
        f"/app/projects/{PROJECT_ID}/work-packages/{PACKAGE_ID}/deliverables/new",
        require_frontend_operational_write_access,
    ),
    (
        "POST",
        f"/app/projects/{PROJECT_ID}/work-packages/{PACKAGE_ID}/deliverables/new",
        require_frontend_operational_write_access,
    ),
    (
        "GET",
        f"/app/projects/{PROJECT_ID}/work-packages/{PACKAGE_ID}/deliverables/{DELIVERABLE_ID}/revisions/new",
        require_frontend_operational_write_access,
    ),
    (
        "POST",
        f"/app/projects/{PROJECT_ID}/work-packages/{PACKAGE_ID}/deliverables/{DELIVERABLE_ID}/revisions/new",
        require_frontend_operational_write_access,
    ),
    (
        "GET",
        f"/app/projects/{PROJECT_ID}/work-packages/{PACKAGE_ID}/deliverables/{DELIVERABLE_ID}/revisions/{REVISION_ID}/approvals/new",
        require_frontend_operational_write_access,
    ),
    (
        "POST",
        f"/app/projects/{PROJECT_ID}/work-packages/{PACKAGE_ID}/deliverables/{DELIVERABLE_ID}/revisions/{REVISION_ID}/approvals/new",
        require_frontend_operational_write_access,
    ),
    (
        "GET",
        f"/app/projects/{PROJECT_ID}/work-packages/{PACKAGE_ID}/deliverables/{DELIVERABLE_ID}/revisions/{REVISION_ID}/approvals/{APPROVAL_ID}/respond",
        require_frontend_approval_response_access,
    ),
    (
        "POST",
        f"/app/projects/{PROJECT_ID}/work-packages/{PACKAGE_ID}/deliverables/{DELIVERABLE_ID}/revisions/{REVISION_ID}/approvals/{APPROVAL_ID}/respond",
        require_frontend_approval_response_access,
    ),
    (
        "GET",
        f"/app/projects/{PROJECT_ID}/programme/new",
        require_frontend_operational_write_access,
    ),
    (
        "POST",
        f"/app/projects/{PROJECT_ID}/programme/new",
        require_frontend_operational_write_access,
    ),
    (
        "GET",
        f"/app/projects/{PROJECT_ID}/programme/{ACTIVITY_ID}/edit",
        require_frontend_operational_write_access,
    ),
    (
        "POST",
        f"/app/projects/{PROJECT_ID}/programme/{ACTIVITY_ID}/edit",
        require_frontend_operational_write_access,
    ),
    (
        "POST",
        f"/app/projects/{PROJECT_ID}/programme/{ACTIVITY_ID}/delete",
        require_frontend_destructive_operation_access,
    ),
)


class CapabilityPolicyTestCase(unittest.TestCase):
    def test_role_capability_matrix(self) -> None:
        policy = {
            "owner": (True, True, True),
            "project_manager": (True, False, True),
            "member": (False, False, False),
            "unexpected": (False, False, False),
        }

        enforcers = (
            enforce_operational_write_access,
            enforce_destructive_operation_access,
            enforce_approval_response_access,
        )
        for role, expectations in policy.items():
            for enforcer, allowed in zip(enforcers, expectations, strict=True):
                with self.subTest(role=role, capability=enforcer.__name__):
                    access = access_for(role)
                    if allowed:
                        self.assertIs(enforcer(access), access)
                    else:
                        with self.assertRaises(HTTPException) as raised:
                            enforcer(access)
                        self.assertEqual(raised.exception.status_code, status.HTTP_403_FORBIDDEN)

    def test_every_mutation_route_has_its_central_capability(self) -> None:
        routers = (
            projects_router,
            packages_router,
            deliverables_router,
            revisions_router,
            approvals_router,
            programme_router,
            frontend_projects_router,
            frontend_packages_router,
            frontend_deliverables_router,
            frontend_programme_router,
        )
        routes = [route for router in routers for route in router.routes]

        for method, path, required_dependency in (*JSON_MUTATIONS, *FRONTEND_MUTATIONS):
            scope = {"type": "http", "method": method, "path": path}
            route = next(
                route
                for route in routes
                if route.matches(scope)[0] is Match.FULL
            )
            dependencies = {
                dependency.call for dependency in route.dependant.dependencies
            }
            with self.subTest(method=method, path=path):
                self.assertIn(required_dependency, dependencies)


class DeniedDirectRequestTestCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.application = create_app()
        self.database = MagicMock()
        self.current_access = access_for("member")

        def override_database():
            yield self.database

        def override_access() -> OrganisationAccessContext:
            return self.current_access

        self.application.dependency_overrides[get_db] = override_database
        self.application.dependency_overrides[require_organisation_access] = override_access
        self.application.dependency_overrides[
            require_frontend_organisation_access
        ] = override_access
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.application),
            base_url="http://testserver",
        )

    async def asyncTearDown(self) -> None:
        await self.client.aclose()

    async def test_member_json_mutations_are_denied_before_database_changes(self) -> None:
        for method, path, _dependency in JSON_MUTATIONS:
            with self.subTest(method=method, path=path):
                response = await self.client.request(method, path, json={})
                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.database.add.assert_not_called()
        self.database.delete.assert_not_called()
        self.database.commit.assert_not_called()

    async def test_project_manager_destructive_requests_are_denied(self) -> None:
        self.current_access = access_for("project_manager")

        for method, path, dependency in JSON_MUTATIONS:
            if dependency is not require_destructive_operation_access:
                continue
            with self.subTest(method=method, path=path):
                response = await self.client.request(method, path)
                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.database.delete.assert_not_called()
        self.database.commit.assert_not_called()

    async def test_member_frontend_mutation_pages_and_posts_are_denied(self) -> None:
        for method, path, _dependency in FRONTEND_MUTATIONS:
            with self.subTest(method=method, path=path):
                response = await self.client.request(
                    method,
                    path,
                    headers={"accept": "text/html"},
                )
                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
                if method == "GET":
                    self.assertIn("do not have permission", response.text)

        self.database.add.assert_not_called()
        self.database.delete.assert_not_called()
        self.database.commit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
