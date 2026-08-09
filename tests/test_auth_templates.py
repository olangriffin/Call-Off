from __future__ import annotations

import unittest

from starlette.requests import Request

from app.backend.frontend_templates import build_frontend_templates
from app.main import create_app


class AuthTemplateTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = create_app()
        cls.templates = build_frontend_templates()

    def render_register(self, registration_enabled: bool) -> str:
        request = Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/register",
                "headers": [],
                "router": self.application.router,
            }
        )
        response = self.templates.TemplateResponse(
            request=request,
            name="auth/register.html",
            context={
                "page_title": "Create account",
                "company_name": "Call-Off",
                "registration_enabled": registration_enabled,
                "form_values": {},
            },
        )
        return response.body.decode("utf-8")

    def test_register_uses_login_visual_shell(self) -> None:
        body = self.render_register(registration_enabled=True)

        for expected in (
            'class="auth-marketing"',
            "app-shell-auth",
            "login-panel",
            "login-mark",
            'class="login-form"',
        ):
            self.assertIn(expected, body)

        self.assertIn('<form method="post" action="/register" class="login-form">', body)
        self.assertIn('name="csrf_token"', body)
        self.assertIn('href="/login"', body)
        self.assertNotIn('<aside class="sidebar">', body)

        for field_name in ("name", "email", "password", "confirm_password"):
            self.assertIn(f'name="{field_name}"', body)

    def test_unavailable_registration_uses_login_visual_shell(self) -> None:
        body = self.render_register(registration_enabled=False)

        self.assertIn('class="auth-marketing"', body)
        self.assertIn("app-shell-auth", body)
        self.assertIn("login-panel", body)
        self.assertIn("login-mark", body)
        self.assertIn("Registration unavailable", body)
        self.assertIn('href="/login"', body)
        self.assertNotIn('<form method="post" action="/register"', body)


if __name__ == "__main__":
    unittest.main()
