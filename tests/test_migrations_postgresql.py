from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import unittest

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from app.backend.core.config import get_settings


MIGRATION_TEST_DATABASE_URL = os.getenv("MIGRATION_TEST_DATABASE_URL")
RESET_ALLOWED = os.getenv("ALLOW_MIGRATION_TEST_DATABASE_RESET") == "1"
CURRENT_HEAD = "c4e21d8a3f70"
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class MigrationSQLSafetyTestCase(unittest.TestCase):
    def test_offline_upgrade_does_not_modify_external_version_table_or_seed(self) -> None:
        environment = os.environ.copy()
        environment.update(
            {
                "DATABASE_URL": "postgresql+psycopg://unused:unused@localhost/unused",
                "ENVIRONMENT": "test",
            }
        )
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head", "--sql"],
            cwd=REPOSITORY_ROOT,
            env=environment,
            capture_output=True,
            check=False,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("DROP TABLE alembic_version", result.stdout)
        self.assertNotIn("9d530e5b-9bae-4337-8e8a-a04b2203a0bb", result.stdout)
        self.assertNotIn("KBYBmC68tnIxyYhC0x4ckE3iRRm9Vm8q", result.stdout)
        self.assertIn("CREATE TABLE calloff_alembic_version", result.stdout)
        self.assertIn(CURRENT_HEAD, result.stdout)


@unittest.skipUnless(
    MIGRATION_TEST_DATABASE_URL and RESET_ALLOWED,
    "requires an explicitly enabled disposable PostgreSQL database",
)
class PostgreSQLMigrationTestCase(unittest.TestCase):
    """Exercise the supported migration starting states on real PostgreSQL."""

    @classmethod
    def setUpClass(cls) -> None:
        assert MIGRATION_TEST_DATABASE_URL is not None
        if not MIGRATION_TEST_DATABASE_URL.startswith(
            ("postgresql://", "postgresql+psycopg://")
        ):
            raise RuntimeError("MIGRATION_TEST_DATABASE_URL must use PostgreSQL.")

        cls.database_url = MIGRATION_TEST_DATABASE_URL
        cls.engine = create_engine(cls.database_url)

        os.environ["DATABASE_URL"] = cls.database_url
        os.environ["ENVIRONMENT"] = "test"
        get_settings.cache_clear()

        cls.alembic_config = Config("alembic.ini")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.engine.dispose()
        get_settings.cache_clear()

    def setUp(self) -> None:
        self._reset_database()

    def _reset_database(self) -> None:
        with self.engine.begin() as connection:
            connection.execute(text("DROP SCHEMA IF EXISTS neon_auth CASCADE"))
            connection.execute(text("DROP SCHEMA public CASCADE"))
            connection.execute(text("CREATE SCHEMA public"))
            connection.execute(text("CREATE SCHEMA neon_auth"))
            connection.execute(
                text(
                    'CREATE TABLE neon_auth."user" ('
                    "id uuid PRIMARY KEY, marker text NOT NULL)"
                )
            )
            connection.execute(
                text(
                    "CREATE TABLE public.organization ("
                    "id text PRIMARY KEY, marker text NOT NULL)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO neon_auth.\"user\" (id, marker) "
                    "VALUES ('00000000-0000-0000-0000-000000000001', "
                    "'auth-user-preserved')"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO public.organization (id, marker) "
                    "VALUES ('migration-test-org', 'organisation-preserved')"
                )
            )

    def _upgrade(self, revision: str) -> None:
        get_settings.cache_clear()
        command.upgrade(self.alembic_config, revision)

    def _assert_head_and_auth_prerequisites(self) -> None:
        with self.engine.connect() as connection:
            revision = connection.scalar(
                text("SELECT version_num FROM calloff_alembic_version")
            )
            user_marker = connection.scalar(
                text(
                    "SELECT marker FROM neon_auth.\"user\" "
                    "WHERE id = '00000000-0000-0000-0000-000000000001'"
                )
            )
            organisation_marker = connection.scalar(
                text(
                    "SELECT marker FROM organization "
                    "WHERE id = 'migration-test-org'"
                )
            )

        self.assertEqual(revision, CURRENT_HEAD)
        self.assertEqual(user_marker, "auth-user-preserved")
        self.assertEqual(organisation_marker, "organisation-preserved")

    def test_empty_application_schema_upgrades_to_head_twice(self) -> None:
        self._upgrade("head")
        self._upgrade("head")

        self._assert_head_and_auth_prerequisites()

        with self.engine.connect() as connection:
            membership_count = connection.scalar(text("SELECT count(*) FROM memberships"))

        self.assertEqual(membership_count, 0)

    def test_upgrade_from_pre_cleanup_without_external_version_table(self) -> None:
        self._upgrade("d8b88096af86")
        self._upgrade("head")

        self._assert_head_and_auth_prerequisites()

    def test_upgrade_preserves_external_version_table(self) -> None:
        self._upgrade("d8b88096af86")
        with self.engine.begin() as connection:
            connection.execute(
                text("CREATE TABLE alembic_version (marker text NOT NULL)")
            )
            connection.execute(
                text("INSERT INTO alembic_version (marker) VALUES ('preserved')")
            )

        self._upgrade("head")
        self._assert_head_and_auth_prerequisites()

        with self.engine.connect() as connection:
            marker = connection.scalar(text("SELECT marker FROM alembic_version"))

        self.assertEqual(marker, "preserved")

    def test_intermediate_cleanup_revisions_upgrade_to_head(self) -> None:
        for revision in ("d9aae884c197", "8f3fb8b12f5e"):
            with self.subTest(revision=revision):
                self._reset_database()
                self._upgrade(revision)
                self._upgrade("head")
                self._assert_head_and_auth_prerequisites()

    def test_current_head_upgrade_is_safe(self) -> None:
        self._upgrade("head")
        self._upgrade("head")

        self._assert_head_and_auth_prerequisites()


if __name__ == "__main__":
    unittest.main()
