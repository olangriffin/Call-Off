from __future__ import annotations

import os
from functools import lru_cache
from urllib.parse import urlparse

from pydantic import EmailStr, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed application settings with production safeguards."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        hide_input_in_errors=True,
    )

    environment: str = "development"
    debug: bool = False
    database_url: str
    app_base_url: str = "http://127.0.0.1:8000"
    trusted_hosts: str = "127.0.0.1,localhost,testserver"

    contact_email: EmailStr | None = None
    legal_entity_name: str | None = None
    privacy_retention_days: int = Field(default=365, ge=30, le=3650)

    neon_auth_base_url: str | None = None
    auth_cookie_secure: bool = False
    allow_public_registration: bool = False

    ip_hash_secret: str = "calloff-local-development-ip-hash-secret"
    early_access_rate_limit: int = Field(default=5, ge=1, le=100)
    early_access_rate_window_minutes: int = Field(default=60, ge=1, le=1440)

    turnstile_site_key: str | None = None
    turnstile_secret_key: SecretStr | None = None
    turnstile_verify_url: str = (
        "https://challenges.cloudflare.com/turnstile/v0/siteverify"
    )

    smtp_host: str | None = None
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_use_tls: bool = True
    smtp_from_email: EmailStr | None = None
    early_access_notification_email: EmailStr | None = None

    @field_validator(
        "environment",
        "database_url",
        "app_base_url",
        "trusted_hosts",
        "ip_hash_secret",
        "turnstile_verify_url",
        mode="before",
    )
    @classmethod
    def strip_required_strings(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug_mode(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"release", "production"}:
                return False
        return value

    @field_validator(
        "legal_entity_name",
        "neon_auth_base_url",
        "turnstile_site_key",
        "turnstile_secret_key",
        "smtp_host",
        "smtp_username",
        "smtp_password",
        mode="before",
    )
    @classmethod
    def strip_optional_strings(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip() or None
        return value

    @model_validator(mode="after")
    def validate_configuration(self) -> Settings:
        self.environment = self.environment.lower()

        if self.environment not in {"development", "test", "production"}:
            raise ValueError("ENVIRONMENT must be development, test, or production.")

        parsed_base_url = urlparse(self.app_base_url)
        if (
            parsed_base_url.scheme not in {"http", "https"}
            or not parsed_base_url.netloc
        ):
            raise ValueError("APP_BASE_URL must be an absolute HTTP or HTTPS URL.")

        if bool(self.turnstile_site_key) != bool(self.turnstile_secret_key):
            raise ValueError(
                "TURNSTILE_SITE_KEY and TURNSTILE_SECRET_KEY must be configured together."
            )

        if self.smtp_host and not (
            self.smtp_from_email and self.early_access_notification_email
        ):
            raise ValueError(
                "SMTP_FROM_EMAIL and EARLY_ACCESS_NOTIFICATION_EMAIL are required "
                "when SMTP_HOST is configured."
            )

        if self.environment == "production":
            missing_or_unsafe: list[str] = []

            if self.debug:
                missing_or_unsafe.append("DEBUG must be false")
            if parsed_base_url.scheme != "https":
                missing_or_unsafe.append("APP_BASE_URL must use HTTPS")
            if not self.auth_cookie_secure:
                missing_or_unsafe.append("AUTH_COOKIE_SECURE must be true")
            if not self.neon_auth_base_url:
                missing_or_unsafe.append("NEON_AUTH_BASE_URL is required")
            elif urlparse(self.neon_auth_base_url).scheme != "https":
                missing_or_unsafe.append("NEON_AUTH_BASE_URL must use HTTPS")
            if not self.database_url.startswith(
                ("postgresql://", "postgresql+psycopg://")
            ):
                missing_or_unsafe.append("DATABASE_URL must use PostgreSQL")
            if len(self.ip_hash_secret) < 32:
                missing_or_unsafe.append(
                    "IP_HASH_SECRET must be at least 32 characters"
                )
            elif self.ip_hash_secret.startswith("calloff-local-development"):
                missing_or_unsafe.append(
                    "IP_HASH_SECRET must not use the development value"
                )
            if not self.turnstile_site_key or not self.turnstile_secret_key:
                missing_or_unsafe.append("Cloudflare Turnstile keys are required")
            if self.turnstile_verify_url != (
                "https://challenges.cloudflare.com/turnstile/v0/siteverify"
            ):
                missing_or_unsafe.append(
                    "TURNSTILE_VERIFY_URL must use Cloudflare's verification endpoint"
                )
            if not self.legal_entity_name or self.legal_entity_name.lower().startswith(
                "replace"
            ):
                missing_or_unsafe.append("LEGAL_ENTITY_NAME is required")
            if not self.contact_email:
                missing_or_unsafe.append("CONTACT_EMAIL is required")
            elif not str(self.contact_email).lower().endswith("@calloff.ie"):
                missing_or_unsafe.append("CONTACT_EMAIL must use the calloff.ie domain")
            if "*" in self.trusted_host_list:
                missing_or_unsafe.append("TRUSTED_HOSTS must not contain a wildcard")
            if parsed_base_url.hostname not in self.trusted_host_list:
                missing_or_unsafe.append(
                    "TRUSTED_HOSTS must include the APP_BASE_URL hostname"
                )
            if self.smtp_host and not self.smtp_use_tls:
                missing_or_unsafe.append(
                    "SMTP_USE_TLS must be true when SMTP is enabled"
                )

            if missing_or_unsafe:
                raise ValueError(
                    "Invalid production configuration: "
                    + "; ".join(missing_or_unsafe)
                    + "."
                )

        return self

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def trusted_host_list(self) -> list[str]:
        hosts = [host.strip() for host in self.trusted_hosts.split(",") if host.strip()]

        render_hostname = os.getenv("RENDER_EXTERNAL_HOSTNAME", "").strip()

        if render_hostname and render_hostname not in hosts:
            hosts.append(render_hostname)

        return hosts

    @property
    def turnstile_enabled(self) -> bool:
        return bool(self.turnstile_site_key and self.turnstile_secret_key)

    @property
    def email_notifications_enabled(self) -> bool:
        return bool(
            self.smtp_host
            and self.smtp_from_email
            and self.early_access_notification_email
        )

    @property
    def public_contact_email(self) -> str:
        return str(self.contact_email or "hello@calloff.ie")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
