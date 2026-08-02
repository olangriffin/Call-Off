from __future__ import annotations

import http.client
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime, timezone
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlencode, urlsplit

from sqlalchemy import create_engine, delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.backend.database.base import Base
from app.backend.models.early_access import EarlyAccessApplication

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class AnchorParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag != "a":
            return
        href = dict(attrs).get("href")
        if href:
            self.links.append(href)


class TurnstileHandler(BaseHTTPRequestHandler):
    success = True

    def do_POST(self) -> None:
        content_length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(content_length)
        payload = json.dumps({"success": self.success}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: object) -> None:
        return


class PublicSiteTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary_directory = tempfile.TemporaryDirectory(prefix="calloff-tests-")
        cls.database_path = Path(cls.temporary_directory.name) / "test.sqlite3"
        cls.engine = create_engine(f"sqlite+pysqlite:///{cls.database_path}")
        Base.metadata.create_all(
            cls.engine,
            tables=[EarlyAccessApplication.__table__],
        )
        cls.session_factory = sessionmaker(
            bind=cls.engine,
            autoflush=False,
            expire_on_commit=False,
        )

        cls.turnstile_server = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            TurnstileHandler,
        )
        cls.turnstile_thread = threading.Thread(
            target=cls.turnstile_server.serve_forever,
            daemon=True,
        )
        cls.turnstile_thread.start()

        with socket.socket() as port_socket:
            port_socket.bind(("127.0.0.1", 0))
            cls.port = port_socket.getsockname()[1]

        environment = os.environ.copy()
        environment.update(
            {
                "ENVIRONMENT": "test",
                "DEBUG": "false",
                "DATABASE_URL": f"sqlite+pysqlite:///{cls.database_path}",
                "APP_BASE_URL": f"http://127.0.0.1:{cls.port}",
                "TRUSTED_HOSTS": "127.0.0.1,localhost,testserver",
                "CONTACT_EMAIL": "hello@calloff.ie",
                "AUTH_COOKIE_SECURE": "false",
                "ALLOW_PUBLIC_REGISTRATION": "false",
                "IP_HASH_SECRET": "test-ip-hash-secret-with-more-than-32-characters",
                "TURNSTILE_SITE_KEY": "test-site-key",
                "TURNSTILE_SECRET_KEY": "test-secret-key",
                "TURNSTILE_VERIFY_URL": (
                    f"http://127.0.0.1:{cls.turnstile_server.server_port}/verify"
                ),
                "NO_PROXY": "127.0.0.1,localhost",
                "no_proxy": "127.0.0.1,localhost",
            }
        )

        cls.application_process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(cls.port),
                "--no-access-log",
            ],
            cwd=PROJECT_ROOT,
            env=environment,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if cls.application_process.poll() is not None:
                raise RuntimeError("The test application exited during startup.")
            try:
                connection = http.client.HTTPConnection(
                    "127.0.0.1",
                    cls.port,
                    timeout=1,
                )
                connection.request("GET", "/health")
                response = connection.getresponse()
                response.read()
                connection.close()
                if response.status == 200:
                    break
            except OSError:
                time.sleep(0.1)
        else:
            raise RuntimeError("The test application did not become healthy.")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.application_process.terminate()
        try:
            cls.application_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            cls.application_process.kill()
            cls.application_process.wait(timeout=5)
        cls.turnstile_server.shutdown()
        cls.turnstile_server.server_close()
        cls.turnstile_thread.join(timeout=5)
        cls.engine.dispose()
        cls.temporary_directory.cleanup()

    def setUp(self) -> None:
        TurnstileHandler.success = True
        self.cookies: dict[str, str] = {}
        EarlyAccessApplication.__table__.create(self.engine, checkfirst=True)
        with self.session_factory() as database:
            database.execute(delete(EarlyAccessApplication))
            database.commit()

    def request(
        self,
        method: str,
        path: str,
        data: dict[str, str] | None = None,
        accept: str = "text/html",
    ) -> tuple[int, dict[str, str], str]:
        body = urlencode(data).encode("utf-8") if data is not None else None
        headers = {"Accept": accept}
        if body is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            headers["Content-Length"] = str(len(body))
        if self.cookies:
            headers["Cookie"] = "; ".join(
                f"{name}={value}" for name, value in self.cookies.items()
            )

        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        raw_body = response.read()
        response_headers = response.getheaders()
        connection.close()

        for name, value in response_headers:
            if name.lower() == "set-cookie":
                parsed_cookie = SimpleCookie()
                parsed_cookie.load(value)
                for cookie_name, morsel in parsed_cookie.items():
                    self.cookies[cookie_name] = morsel.value

        headers_by_name = {name.lower(): value for name, value in response_headers}
        return response.status, headers_by_name, raw_body.decode("utf-8")

    def csrf_token(self) -> str:
        status_code, _headers, body = self.request("GET", "/early-access")
        self.assertEqual(status_code, 200)
        match = re.search(
            r'name="csrf_token" value="([A-Za-z0-9_-]+)"',
            body,
        )
        self.assertIsNotNone(match)
        return match.group(1)

    def valid_form(self, **overrides: str) -> dict[str, str]:
        values = {
            "full_name": "Alex Builder",
            "work_email": "alex@example.com",
            "company_name": "Example Specialist Ltd",
            "job_title": "Delivery Manager",
            "subcontractor_type": "Facade",
            "company_size": "11-50",
            "active_projects": "4-10",
            "current_tools": "Spreadsheets and email",
            "biggest_delivery_challenge": "Keeping approvals tied to deadlines",
            "interest_level": "early_access",
            "additional_information": "",
            "website": "",
            "cf-turnstile-response": "test-token",
        }
        values.update(overrides)
        values["csrf_token"] = self.csrf_token()
        return values

    def test_landing_page_returns_200(self) -> None:
        status_code, _headers, body = self.request("GET", "/")
        self.assertEqual(status_code, 200)
        self.assertIn("subcontractor delivery platform", body)
        self.assertNotIn("calloff.app", body)

    def test_early_access_page_returns_200(self) -> None:
        status_code, _headers, body = self.request("GET", "/early-access")
        self.assertEqual(status_code, 200)
        self.assertIn("Apply for Early Access", body)
        self.assertIn('name="csrf_token"', body)

    def test_navigation_contains_responsive_early_access_cta(self) -> None:
        status_code, _headers, body = self.request("GET", "/")
        self.assertEqual(status_code, 200)
        self.assertIn('class="marketing-nav-menu-panel"', body)
        self.assertIn('href="/early-access" class="primary-button"', body)

    def test_login_uses_app_shell_without_marketing_nav(self) -> None:
        status_code, _headers, body = self.request("GET", "/login")
        self.assertEqual(status_code, 200)
        self.assertNotIn('class="marketing-nav"', body)
        self.assertNotIn('href="/register"', body)
        self.assertIn("Call-Off", body)

    def test_login_rejects_invalid_input_without_provider_request(self) -> None:
        page_status, _headers, page_body = self.request("GET", "/login")
        self.assertEqual(page_status, 200)
        token_match = re.search(
            r'name="csrf_token" value="([A-Za-z0-9_-]+)"',
            page_body,
        )
        self.assertIsNotNone(token_match)
        status_code, _headers, body = self.request(
            "POST",
            "/login",
            {
                "csrf_token": token_match.group(1),
                "email": "not-an-email",
                "password": "password",
            },
        )
        self.assertEqual(status_code, 422)
        self.assertIn("Enter a valid email address and password.", body)

    def test_valid_application_submission_uses_prg(self) -> None:
        status_code, headers, _body = self.request(
            "POST",
            "/early-access",
            self.valid_form(work_email="  Alex@Example.COM "),
        )
        self.assertEqual(status_code, 303)
        self.assertEqual(headers["location"], "/early-access?submitted=1")

        with self.session_factory() as database:
            application = database.scalar(select(EarlyAccessApplication))
            self.assertIsNotNone(application)
            self.assertEqual(application.work_email, "alex@example.com")
            self.assertEqual(len(application.ip_address_hash), 64)
            self.assertNotEqual(application.ip_address_hash, "127.0.0.1")

        success_status, _success_headers, success_body = self.request(
            "GET",
            headers["location"],
        )
        self.assertEqual(success_status, 200)
        self.assertIn("Application received", success_body)

    def test_required_field_validation_preserves_values(self) -> None:
        status_code, _headers, body = self.request(
            "POST",
            "/early-access",
            self.valid_form(full_name="", company_name="Preserved Company"),
        )
        self.assertEqual(status_code, 422)
        self.assertIn("Full name is required.", body)
        self.assertIn('value="Preserved Company"', body)

    def test_invalid_email(self) -> None:
        status_code, _headers, body = self.request(
            "POST",
            "/early-access",
            self.valid_form(work_email="not-an-email"),
        )
        self.assertEqual(status_code, 422)
        self.assertIn("Enter a valid work email address.", body)

    def test_invalid_select_values(self) -> None:
        status_code, _headers, body = self.request(
            "POST",
            "/early-access",
            self.valid_form(company_size="unlimited", active_projects="many"),
        )
        self.assertEqual(status_code, 422)
        self.assertIn("Choose a valid company size.", body)
        self.assertIn("Choose a valid number of active projects.", body)

    def test_excessive_field_length(self) -> None:
        status_code, _headers, body = self.request(
            "POST",
            "/early-access",
            self.valid_form(full_name="A" * 201),
        )
        self.assertEqual(status_code, 422)
        self.assertIn("Use 200 characters or fewer.", body)

    def test_duplicate_submission(self) -> None:
        first_status, _headers, _body = self.request(
            "POST",
            "/early-access",
            self.valid_form(),
        )
        self.assertEqual(first_status, 303)

        duplicate_status, _headers, duplicate_body = self.request(
            "POST",
            "/early-access",
            self.valid_form(),
        )
        self.assertEqual(duplicate_status, 409)
        self.assertIn("already have an early-access application", duplicate_body)

    def test_honeypot_rejection(self) -> None:
        status_code, _headers, body = self.request(
            "POST",
            "/early-access",
            self.valid_form(website="automated"),
        )
        self.assertEqual(status_code, 422)
        self.assertIn("We could not submit this application.", body)

    def test_turnstile_failure(self) -> None:
        TurnstileHandler.success = False
        status_code, _headers, body = self.request(
            "POST",
            "/early-access",
            self.valid_form(),
        )
        self.assertEqual(status_code, 422)
        self.assertIn("could not verify this submission", body)

    def test_rate_limiting(self) -> None:
        for index in range(5):
            status_code, _headers, _body = self.request(
                "POST",
                "/early-access",
                self.valid_form(work_email=f"applicant{index}@example.com"),
            )
            self.assertEqual(status_code, 303)

        status_code, headers, body = self.request(
            "POST",
            "/early-access",
            self.valid_form(work_email="next@example.com"),
        )
        self.assertEqual(status_code, 429)
        self.assertIn("retry-after", headers)
        self.assertIn("Too many recent applications", body)

    def test_database_failure_handling(self) -> None:
        EarlyAccessApplication.__table__.drop(self.engine)
        try:
            status_code, _headers, body = self.request(
                "POST",
                "/early-access",
                self.valid_form(),
            )
        finally:
            EarlyAccessApplication.__table__.create(self.engine)

        self.assertEqual(status_code, 503)
        self.assertIn("could not be submitted", body)
        self.assertNotIn("OperationalError", body)

    def test_csrf_rejection(self) -> None:
        values = self.valid_form()
        self.cookies.clear()
        values.pop("csrf_token")
        status_code, _headers, body = self.request(
            "POST",
            "/early-access",
            values,
        )
        self.assertEqual(status_code, 403)
        self.assertIn("Request not accepted", body)

    def test_privacy_page(self) -> None:
        status_code, _headers, body = self.request("GET", "/privacy")
        self.assertEqual(status_code, 200)
        self.assertIn("keyed hash", body)
        self.assertIn("hello@calloff.ie", body)

    def test_pricing_page(self) -> None:
        status_code, _headers, body = self.request("GET", "/pricing")
        self.assertEqual(status_code, 200)
        self.assertIn("Indicative early-access pricing", body)
        self.assertIn("may change before general availability", body)
        self.assertGreaterEqual(body.count('href="/early-access"'), 5)

    def test_health_endpoint(self) -> None:
        status_code, _headers, body = self.request("GET", "/health")
        self.assertEqual(status_code, 200)
        self.assertEqual(json.loads(body), {"status": "ok"})

    def test_static_route(self) -> None:
        status_code, headers, _body = self.request(
            "GET",
            "/static/assets/favicon.svg",
        )
        self.assertEqual(status_code, 200)
        self.assertIn("image/svg+xml", headers["content-type"])

    def test_public_internal_links_resolve(self) -> None:
        discovered: set[str] = set()
        for page in ("/", "/pricing", "/privacy", "/early-access", "/login"):
            status_code, _headers, body = self.request("GET", page)
            self.assertEqual(status_code, 200)
            parser = AnchorParser()
            parser.feed(body)
            for href in parser.links:
                if href.startswith("mailto:"):
                    self.assertTrue(href.endswith("@calloff.ie"))
                    continue
                self.assertFalse(href.startswith(("http://", "https://")))
                if href.startswith("#"):
                    continue
                target = urlsplit(href).path or "/"
                discovered.add(target)

        for target in sorted(discovered):
            status_code, _headers, _body = self.request("GET", target)
            self.assertLess(status_code, 400, target)

    def test_custom_404(self) -> None:
        status_code, _headers, body = self.request(
            "GET",
            "/this-page-does-not-exist",
        )
        self.assertEqual(status_code, 404)
        self.assertIn("Page not found", body)
        self.assertNotIn("Traceback", body)

    def test_api_404_remains_json(self) -> None:
        status_code, headers, body = self.request(
            "GET",
            "/api/this-route-does-not-exist",
            accept="application/json",
        )
        self.assertEqual(status_code, 404)
        self.assertIn("application/json", headers["content-type"])
        self.assertEqual(json.loads(body), {"detail": "Not Found"})

    def test_database_constraints_reject_invalid_interest(self) -> None:
        with self.session_factory() as database:
            database.add(
                EarlyAccessApplication(
                    full_name="Constraint Test",
                    work_email="constraint@example.com",
                    company_name="Constraint Company",
                    job_title="Manager",
                    subcontractor_type="Steel",
                    company_size="11-50",
                    active_projects="4-10",
                    current_tools="Email",
                    biggest_delivery_challenge="Deadlines",
                    interest_level="invalid",
                    ip_address_hash="a" * 64,
                    created_at=datetime.now(timezone.utc),
                )
            )
            with self.assertRaises(IntegrityError):
                database.commit()
            database.rollback()


if __name__ == "__main__":
    unittest.main()
