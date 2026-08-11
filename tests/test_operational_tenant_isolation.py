from __future__ import annotations

import re
import unittest
import uuid
from datetime import date, datetime, timezone

import httpx
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.backend.core.auth import (
    require_frontend_organisation_access,
    require_organisation_access,
)
from app.backend.database.session import get_db
from app.backend.models.organisation import Organisation
from app.backend.models.package.approval import Approval
from app.backend.models.package.deliverable import Deliverable
from app.backend.models.package.package import WorkPackage
from app.backend.models.package.revision import DeliverableRevision
from app.backend.models.programme.programme import Programme
from app.backend.models.programme.programme_activity import ProgrammeActivity
from app.backend.models.programme.programme_revision import ProgrammeRevision
from app.backend.models.project import Project
from app.backend.schemas.auth import AuthenticatedUser, OrganisationAccessContext
from app.backend.services.deliverable import (
    list_deliverables_with_review_history,
)
from app.backend.services.programme_activity import list_activities
from app.backend.services.work_package import list_work_packages
from app.main import create_app


PROJECT_A_ID = uuid.UUID("10000000-0000-0000-0000-000000000001")
PROJECT_B_ID = uuid.UUID("20000000-0000-0000-0000-000000000001")
PACKAGE_A_ID = uuid.UUID("10000000-0000-0000-0000-000000000002")
PACKAGE_B_ID = uuid.UUID("20000000-0000-0000-0000-000000000002")
DELIVERABLE_A_ID = uuid.UUID("10000000-0000-0000-0000-000000000003")
DELIVERABLE_B_ID = uuid.UUID("20000000-0000-0000-0000-000000000003")
REVISION_A_ID = uuid.UUID("10000000-0000-0000-0000-000000000004")
REVISION_B_ID = uuid.UUID("20000000-0000-0000-0000-000000000004")
APPROVAL_A_ID = uuid.UUID("10000000-0000-0000-0000-000000000005")
APPROVAL_B_ID = uuid.UUID("20000000-0000-0000-0000-000000000005")
PROGRAMME_A_ID = uuid.UUID("10000000-0000-0000-0000-000000000006")
PROGRAMME_B_ID = uuid.UUID("20000000-0000-0000-0000-000000000006")
PROGRAMME_REVISION_A_ID = uuid.UUID("10000000-0000-0000-0000-000000000007")
PROGRAMME_REVISION_B_ID = uuid.UUID("20000000-0000-0000-0000-000000000007")
ACTIVITY_A_ID = uuid.UUID("10000000-0000-0000-0000-000000000008")
ACTIVITY_B_ID = uuid.UUID("20000000-0000-0000-0000-000000000008")


TABLES = [
    Organisation.__table__,
    Project.__table__,
    WorkPackage.__table__,
    Deliverable.__table__,
    DeliverableRevision.__table__,
    Approval.__table__,
    Programme.__table__,
    ProgrammeRevision.__table__,
    ProgrammeActivity.__table__,
]


def access_for(organization_id: str) -> OrganisationAccessContext:
    suffix = organization_id[-1]
    return OrganisationAccessContext(
        user=AuthenticatedUser(
            id=f"00000000-0000-0000-0000-00000000000{suffix}",
            name=f"User {suffix.upper()}",
            email=f"user-{suffix}@example.com",
            email_verified=True,
        ),
        membership_id=f"30000000-0000-0000-0000-00000000000{suffix}",
        role="project_manager",
        organization_id=organization_id,
        organization_name=f"Organisation {suffix.upper()}",
        organization_slug=f"organisation-{suffix}",
    )


class OperationalTenantIsolationTestCase(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = create_engine(
            "sqlite+pysqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        cls.session_factory = sessionmaker(
            bind=cls.engine,
            autoflush=False,
            expire_on_commit=False,
        )
        cls.application = create_app()
        cls.current_access = access_for("org-a")

        def override_database():
            database = cls.session_factory()
            try:
                yield database
            finally:
                database.close()

        def override_access() -> OrganisationAccessContext:
            return cls.current_access

        cls.application.dependency_overrides[get_db] = override_database
        cls.application.dependency_overrides[require_organisation_access] = (
            override_access
        )
        cls.application.dependency_overrides[require_frontend_organisation_access] = (
            override_access
        )
    @classmethod
    def tearDownClass(cls) -> None:
        cls.application.dependency_overrides.clear()
        cls.engine.dispose()

    async def asyncSetUp(self) -> None:
        for table in reversed(TABLES):
            table.drop(self.engine, checkfirst=True)
        for table in TABLES:
            table.create(self.engine, checkfirst=True)
        self.seed_hierarchies()
        self.current_access = access_for("org-a")
        type(self).current_access = self.current_access
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.application),
            base_url="http://testserver",
        )

    async def asyncTearDown(self) -> None:
        await self.client.aclose()

    def seed_hierarchies(self) -> None:
        now = datetime.now(timezone.utc)
        with self.session_factory() as database:
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
                    Deliverable(
                        id=DELIVERABLE_A_ID,
                        work_package_id=PACKAGE_A_ID,
                        reference="A-D",
                        name="Deliverable A",
                        deliverable_type="drawing",
                    ),
                    Deliverable(
                        id=DELIVERABLE_B_ID,
                        work_package_id=PACKAGE_B_ID,
                        reference="B-D",
                        name="Deliverable B",
                        deliverable_type="drawing",
                    ),
                    DeliverableRevision(
                        id=REVISION_A_ID,
                        deliverable_id=DELIVERABLE_A_ID,
                        revision_code="A1",
                    ),
                    DeliverableRevision(
                        id=REVISION_B_ID,
                        deliverable_id=DELIVERABLE_B_ID,
                        revision_code="B1",
                    ),
                    Approval(
                        id=APPROVAL_A_ID,
                        revision_id=REVISION_A_ID,
                    ),
                    Approval(
                        id=APPROVAL_B_ID,
                        revision_id=REVISION_B_ID,
                    ),
                    Programme(
                        id=PROGRAMME_A_ID,
                        project_id=PROJECT_A_ID,
                    ),
                    Programme(
                        id=PROGRAMME_B_ID,
                        project_id=PROJECT_B_ID,
                    ),
                    ProgrammeRevision(
                        id=PROGRAMME_REVISION_A_ID,
                        programme_id=PROGRAMME_A_ID,
                        revision_code="R1",
                        is_current=True,
                    ),
                    ProgrammeRevision(
                        id=PROGRAMME_REVISION_B_ID,
                        programme_id=PROGRAMME_B_ID,
                        revision_code="R1",
                        is_current=True,
                    ),
                    ProgrammeActivity(
                        id=ACTIVITY_A_ID,
                        programme_revision_id=PROGRAMME_REVISION_A_ID,
                        activity_code="A-ACT",
                        name="Activity A",
                    ),
                    ProgrammeActivity(
                        id=ACTIVITY_B_ID,
                        programme_revision_id=PROGRAMME_REVISION_B_ID,
                        activity_code="B-ACT",
                        name="Activity B",
                    ),
                ]
            )
            database.commit()

    @staticmethod
    def request_body(method: str, path: str) -> dict[str, object] | None:
        if method == "POST" and path == "/projects":
            return {"code": "NEW", "name": "New project"}
        if method == "PATCH" and path.startswith("/projects/"):
            return {"name": "Updated"}
        if method == "POST" and path.endswith("/work-packages"):
            return {"code": "NEW-WP", "name": "New package"}
        if method == "POST" and path.endswith("/programme/activities"):
            return {"activity_code": "NEW-ACT", "name": "New activity"}
        if method == "POST" and path.endswith("/deliverables"):
            return {
                "reference": "NEW-D",
                "name": "New deliverable",
                "deliverable_type": "drawing",
            }
        if method == "POST" and path.endswith("/revisions"):
            return {"revision_code": "NEW-R"}
        if method == "POST" and path.endswith("/approvals"):
            return {}
        return None

    async def request(
        self,
        method: str,
        path: str,
        body: dict[str, object] | None = None,
    ):
        return await self.client.request(method, path, json=body)

    def operational_operations(self) -> list[tuple[str, str]]:
        replacements = {
            "project_id": str(PROJECT_A_ID),
            "work_package_id": str(PACKAGE_A_ID),
            "deliverable_id": str(DELIVERABLE_A_ID),
            "revision_id": str(REVISION_A_ID),
            "approval_id": str(APPROVAL_A_ID),
            "activity_id": str(ACTIVITY_A_ID),
        }
        operations: list[tuple[str, str]] = []
        for path, path_item in self.application.openapi()["paths"].items():
            concrete_path = path
            for name, value in replacements.items():
                concrete_path = concrete_path.replace(f"{{{name}}}", value)
            for method in path_item:
                if method in {"get", "post", "patch", "put", "delete"}:
                    operations.append((method.upper(), concrete_path))
        return operations

    async def test_all_enumerated_operational_operations_require_authentication(
        self,
    ) -> None:
        operations = self.operational_operations()
        self.assertEqual(len(operations), 30)
        override = self.application.dependency_overrides.pop(
            require_organisation_access
        )
        try:
            for method, path in operations:
                with self.subTest(method=method, path=path):
                    response = await self.request(
                        method,
                        path,
                        self.request_body(method, path),
                    )
                    self.assertEqual(response.status_code, 401, response.text)
        finally:
            self.application.dependency_overrides[require_organisation_access] = (
                override
            )

    async def test_json_project_creation_uses_trusted_tenant_and_forbids_input(
        self,
    ) -> None:
        rejected = await self.client.post(
            "/projects",
            json={
                "organization_id": "org-b",
                "code": "OVERRIDE",
                "name": "Tenant override",
            },
        )
        self.assertEqual(rejected.status_code, 422, rejected.text)

        created = await self.client.post(
            "/projects",
            json={"code": "TRUSTED", "name": "Trusted tenant project"},
        )
        self.assertEqual(created.status_code, 201, created.text)
        self.assertEqual(created.json()["organization_id"], "org-a")

    async def test_frontend_project_creation_uses_trusted_tenant(self) -> None:
        page = await self.client.get("/app/projects/new")
        self.assertEqual(page.status_code, 200, page.text)
        token_match = re.search(
            r'name="csrf_token" value="([A-Za-z0-9_-]+)"',
            page.text,
        )
        self.assertIsNotNone(token_match)

        created = await self.client.post(
            "/app/projects/new",
            data={
                "csrf_token": token_match.group(1),
                "code": "FRONTEND",
                "name": "Frontend project",
                "client_name": "",
                "status": "planning",
                "planned_start": "",
                "planned_finish": "",
            },
            follow_redirects=False,
        )
        self.assertEqual(created.status_code, 303, created.text)

        with self.session_factory() as database:
            project = database.scalar(
                select(Project).where(Project.code == "FRONTEND")
            )
            self.assertIsNotNone(project)
            self.assertEqual(project.organization_id, "org-a")

    async def test_client_query_cannot_override_project_list_tenant(self) -> None:
        response = await self.client.get("/projects?organization_id=org-b")
        self.assertEqual(response.status_code, 200, response.text)
        projects = response.json()
        self.assertTrue(projects)
        self.assertTrue(
            all(project["organization_id"] == "org-a" for project in projects)
        )

    async def test_cross_tenant_operations_return_404(self) -> None:
        project_b = f"/projects/{PROJECT_B_ID}"
        package_b = f"{project_b}/work-packages"
        activity_b = f"{project_b}/programme/activities"
        deliverable_b = f"{package_b}/{PACKAGE_B_ID}/deliverables"
        revision_b = f"{deliverable_b}/{DELIVERABLE_B_ID}/revisions"
        approval_b = f"{revision_b}/{REVISION_B_ID}/approvals"
        operations = [
            ("GET", project_b, None),
            ("PATCH", project_b, {"name": "Blocked"}),
            ("DELETE", project_b, None),
            ("POST", package_b, {"code": "X", "name": "Blocked"}),
            ("GET", package_b, None),
            ("GET", f"{package_b}/{PACKAGE_B_ID}", None),
            ("PATCH", f"{package_b}/{PACKAGE_B_ID}", {"name": "Blocked"}),
            ("DELETE", f"{package_b}/{PACKAGE_B_ID}", None),
            ("POST", activity_b, {"activity_code": "X", "name": "Blocked"}),
            ("GET", activity_b, None),
            ("GET", f"{activity_b}/{ACTIVITY_B_ID}", None),
            ("PATCH", f"{activity_b}/{ACTIVITY_B_ID}", {"name": "Blocked"}),
            ("DELETE", f"{activity_b}/{ACTIVITY_B_ID}", None),
            (
                "POST",
                deliverable_b,
                {
                    "reference": "X",
                    "name": "Blocked",
                    "deliverable_type": "drawing",
                },
            ),
            ("GET", deliverable_b, None),
            ("GET", f"{deliverable_b}/{DELIVERABLE_B_ID}", None),
            (
                "PATCH",
                f"{deliverable_b}/{DELIVERABLE_B_ID}",
                {"name": "Blocked"},
            ),
            ("DELETE", f"{deliverable_b}/{DELIVERABLE_B_ID}", None),
            ("POST", revision_b, {"revision_code": "X"}),
            ("GET", revision_b, None),
            ("GET", f"{revision_b}/{REVISION_B_ID}", None),
            (
                "PATCH",
                f"{revision_b}/{REVISION_B_ID}",
                {"revision_code": "X"},
            ),
            ("DELETE", f"{revision_b}/{REVISION_B_ID}", None),
            ("POST", approval_b, {}),
            ("GET", approval_b, None),
            ("GET", f"{approval_b}/{APPROVAL_B_ID}", None),
            (
                "PATCH",
                f"{approval_b}/{APPROVAL_B_ID}",
                {"status": "approved"},
            ),
            ("DELETE", f"{approval_b}/{APPROVAL_B_ID}", None),
        ]

        for method, path, body in operations:
            with self.subTest(method=method, path=path):
                response = await self.request(method, path, body)
                self.assertEqual(response.status_code, 404, response.text)

    async def test_wrong_parent_resources_return_404(self) -> None:
        package_a = f"/projects/{PROJECT_A_ID}/work-packages"
        deliverable_a = f"{package_a}/{PACKAGE_A_ID}/deliverables"
        revision_a = f"{deliverable_a}/{DELIVERABLE_A_ID}/revisions"
        approval_a = f"{revision_a}/{REVISION_A_ID}/approvals"
        paths = [
            f"{package_a}/{PACKAGE_B_ID}",
            f"{deliverable_a}/{DELIVERABLE_B_ID}",
            f"{revision_a}/{REVISION_B_ID}",
            f"{approval_a}/{APPROVAL_B_ID}",
            f"/projects/{PROJECT_A_ID}/programme/activities/{ACTIVITY_B_ID}",
        ]

        for path in paths:
            with self.subTest(path=path):
                response = await self.client.get(path)
                self.assertEqual(response.status_code, 404, response.text)

    async def test_same_tenant_hierarchy_remains_accessible(self) -> None:
        paths = [
            f"/projects/{PROJECT_A_ID}",
            f"/projects/{PROJECT_A_ID}/work-packages/{PACKAGE_A_ID}",
            (
                f"/projects/{PROJECT_A_ID}/work-packages/{PACKAGE_A_ID}"
                f"/deliverables/{DELIVERABLE_A_ID}"
            ),
            (
                f"/projects/{PROJECT_A_ID}/work-packages/{PACKAGE_A_ID}"
                f"/deliverables/{DELIVERABLE_A_ID}/revisions/{REVISION_A_ID}"
            ),
            (
                f"/projects/{PROJECT_A_ID}/work-packages/{PACKAGE_A_ID}"
                f"/deliverables/{DELIVERABLE_A_ID}/revisions/{REVISION_A_ID}"
                f"/approvals/{APPROVAL_A_ID}"
            ),
            f"/projects/{PROJECT_A_ID}/programme/activities/{ACTIVITY_A_ID}",
        ]

        for path in paths:
            with self.subTest(path=path):
                response = await self.client.get(path)
                self.assertEqual(response.status_code, 200, response.text)

    async def test_frontend_approval_response_updates_only_nested_record(
        self,
    ) -> None:
        with self.session_factory() as database:
            approval = database.get(Approval, APPROVAL_A_ID)
            approval.approval_stage = "client_approval"
            approval.reviewer_name = "Design team"
            approval.submitted_date = date(2026, 8, 1)
            approval.response_due_date = date(2026, 8, 10)
            database.commit()

        response_path = (
            f"/app/projects/{PROJECT_A_ID}/work-packages/{PACKAGE_A_ID}"
            f"/deliverables/{DELIVERABLE_A_ID}/revisions/{REVISION_A_ID}"
            f"/approvals/{APPROVAL_A_ID}/respond"
        )
        page = await self.client.get(response_path)
        self.assertEqual(page.status_code, 200, page.text)
        token_match = re.search(
            r'name="csrf_token" value="([A-Za-z0-9_-]+)"',
            page.text,
        )
        self.assertIsNotNone(token_match)

        response = await self.client.post(
            response_path,
            data={
                "csrf_token": token_match.group(1),
                "status": "approved",
                "response_received_date": "2026-08-09",
                "comments": "Accepted for construction",
            },
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 303, response.text)

        with self.session_factory() as database:
            approval = database.get(Approval, APPROVAL_A_ID)
            self.assertEqual(approval.status, "approved")
            self.assertEqual(approval.response_received_date, date(2026, 8, 9))
            self.assertEqual(approval.comments, "Accepted for construction")
            self.assertEqual(approval.approval_stage, "client_approval")
            self.assertEqual(approval.reviewer_name, "Design team")
            self.assertEqual(approval.submitted_date, date(2026, 8, 1))
            self.assertEqual(approval.response_due_date, date(2026, 8, 10))

    async def test_frontend_approval_response_rejects_cross_tenant_hierarchy(
        self,
    ) -> None:
        cross_tenant_path = (
            f"/app/projects/{PROJECT_B_ID}/work-packages/{PACKAGE_B_ID}"
            f"/deliverables/{DELIVERABLE_B_ID}/revisions/{REVISION_B_ID}"
            f"/approvals/{APPROVAL_B_ID}/respond"
        )
        wrong_parent_path = (
            f"/app/projects/{PROJECT_A_ID}/work-packages/{PACKAGE_A_ID}"
            f"/deliverables/{DELIVERABLE_A_ID}/revisions/{REVISION_A_ID}"
            f"/approvals/{APPROVAL_B_ID}/respond"
        )

        for path in (cross_tenant_path, wrong_parent_path):
            with self.subTest(path=path):
                for method in ("GET", "POST"):
                    response = await self.client.request(method, path)
                    self.assertEqual(response.status_code, 404, response.text)

    async def test_frontend_approval_response_enforces_date_status_pair(
        self,
    ) -> None:
        response_path = (
            f"/app/projects/{PROJECT_A_ID}/work-packages/{PACKAGE_A_ID}"
            f"/deliverables/{DELIVERABLE_A_ID}/revisions/{REVISION_A_ID}"
            f"/approvals/{APPROVAL_A_ID}/respond"
        )
        page = await self.client.get(response_path)
        token_match = re.search(
            r'name="csrf_token" value="([A-Za-z0-9_-]+)"',
            page.text,
        )
        self.assertIsNotNone(token_match)
        csrf_token = token_match.group(1)

        invalid_cases = (
            (
                {
                    "csrf_token": csrf_token,
                    "status": "pending",
                    "response_received_date": "2026-08-09",
                    "comments": "Should not persist",
                },
                "pending approval cannot have",
            ),
            (
                {
                    "csrf_token": csrf_token,
                    "status": "status_a",
                    "response_received_date": "",
                    "comments": "Should not persist",
                },
                "response received date is required",
            ),
        )
        for data, expected_message in invalid_cases:
            with self.subTest(status=data["status"]):
                response = await self.client.post(response_path, data=data)
                self.assertEqual(response.status_code, 422, response.text)
                self.assertIn(expected_message, response.text.lower())
                with self.session_factory() as database:
                    approval = database.get(Approval, APPROVAL_A_ID)
                    self.assertEqual(approval.status, "pending")
                    self.assertIsNone(approval.response_received_date)
                    self.assertIsNone(approval.comments)

        accepted = await self.client.post(
            response_path,
            data={
                "csrf_token": csrf_token,
                "status": "status_a",
                "response_received_date": "2026-08-09",
                "comments": "Contractor-specific outcome",
            },
            follow_redirects=False,
        )
        self.assertEqual(accepted.status_code, 303, accepted.text)
        with self.session_factory() as database:
            approval = database.get(Approval, APPROVAL_A_ID)
            self.assertEqual(approval.status, "status_a")
            self.assertEqual(approval.response_received_date, date(2026, 8, 9))

    async def test_frontend_operational_lists_can_be_uncapped(self) -> None:
        with self.session_factory() as database:
            database.add_all(
                [
                    WorkPackage(
                        project_id=PROJECT_A_ID,
                        code=f"A-WP-{index:03}",
                        name=f"Package {index}",
                    )
                    for index in range(100)
                ]
            )
            database.add_all(
                [
                    Deliverable(
                        work_package_id=PACKAGE_A_ID,
                        reference=f"A-D-{index:03}",
                        name=f"Deliverable {index}",
                        deliverable_type="drawing",
                    )
                    for index in range(100)
                ]
            )
            database.add_all(
                [
                    ProgrammeActivity(
                        programme_revision_id=PROGRAMME_REVISION_A_ID,
                        activity_code=f"A-ACT-{index:03}",
                        name=f"Activity {index}",
                    )
                    for index in range(200)
                ]
            )
            database.commit()

            self.assertEqual(
                len(list_work_packages(database, PROJECT_A_ID, limit=100)),
                100,
            )
            self.assertEqual(
                len(list_work_packages(database, PROJECT_A_ID, limit=None)),
                101,
            )
            self.assertEqual(
                len(
                    list_deliverables_with_review_history(
                        database,
                        PACKAGE_A_ID,
                        limit=100,
                    )
                ),
                100,
            )
            self.assertEqual(
                len(
                    list_deliverables_with_review_history(
                        database,
                        PACKAGE_A_ID,
                        limit=None,
                    )
                ),
                101,
            )
            self.assertEqual(
                len(
                    list_activities(
                        database,
                        PROGRAMME_REVISION_A_ID,
                        limit=200,
                    )
                ),
                200,
            )
            self.assertEqual(
                len(
                    list_activities(
                        database,
                        PROGRAMME_REVISION_A_ID,
                        limit=None,
                    )
                ),
                201,
            )

    async def test_openapi_has_no_client_controlled_tenant_identifier(self) -> None:
        schema = self.application.openapi()
        for path, path_item in schema["paths"].items():
            for method, operation in path_item.items():
                if method not in {"get", "post", "patch", "put", "delete"}:
                    continue
                parameter_names = {
                    parameter["name"] for parameter in operation.get("parameters", [])
                }
                self.assertNotIn(
                    "organization_id",
                    parameter_names,
                    f"{method.upper()} {path}",
                )

        project_create = schema["components"]["schemas"]["ProjectCreate"]
        self.assertNotIn("organization_id", project_create.get("properties", {}))
        self.assertFalse(project_create["additionalProperties"])
