import json
import os
import subprocess
import sys
from io import StringIO
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase

from core import db_security

FAKE_POOLER_URL = "postgresql://postgres.fakeref:fake-pass@aws-0-eu-central-1.pooler.supabase.com:{port}/postgres"


class FakeCursor:
    """execute edilen SQL'i toplar; fetchall icin siradaki sonucu dondurur."""

    def __init__(self, results=()):
        self.statements = []
        self._results = list(results)

    def execute(self, sql, params=None):
        self.statements.append(sql)

    def fetchall(self):
        return self._results.pop(0) if self._results else []


class RevokeStatementTests(SimpleTestCase):
    def test_statements_cover_tables_sequences_functions_and_defaults(self):
        for role in ("anon", "authenticated"):
            statements = db_security.revoke_statements(role)
            self.assertEqual(len(statements), 6)
            text = "\n".join(statements)
            for expected in (
                f"REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {role}",
                f"REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM {role}",
                f"REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM {role}",
                f"ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public REVOKE ALL ON TABLES FROM {role}",
                f"ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public REVOKE ALL ON SEQUENCES FROM {role}",
                f"ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public REVOKE ALL ON FUNCTIONS FROM {role}",
            ):
                self.assertIn(expected, text)

    def test_only_known_roles_are_accepted(self):
        with self.assertRaises(ValueError):
            db_security.revoke_statements("anon; DROP TABLE accounts_user")

    def test_revoke_runs_only_for_roles_that_exist(self):
        cursor = FakeCursor(results=[[("anon",)]])
        roles = db_security.revoke_api_access(cursor)
        self.assertEqual(roles, ["anon"])
        executed = "\n".join(cursor.statements)
        self.assertIn("FROM anon", executed)
        self.assertNotIn("FROM authenticated", executed)

    def test_revoke_is_a_noop_without_supabase_roles(self):
        cursor = FakeCursor(results=[[]])
        self.assertEqual(db_security.revoke_api_access(cursor), [])
        self.assertEqual(len(cursor.statements), 1)  # yalnizca rol sorgusu

    def test_rls_enabled_on_every_public_table_with_quoted_names(self):
        cursor = FakeCursor(results=[[("accounts_user",), ("polls_vote",)]])
        tables = db_security.enable_rls_on_all_tables(cursor, lambda name: f'"{name}"')
        self.assertEqual(tables, ["accounts_user", "polls_vote"])
        self.assertIn('ALTER TABLE public."accounts_user" ENABLE ROW LEVEL SECURITY', cursor.statements)
        self.assertIn('ALTER TABLE public."polls_vote" ENABLE ROW LEVEL SECURITY', cursor.statements)


class SecureDbCommandTests(TestCase):
    def run_command(self):
        out = StringIO()
        call_command("secure_db", stdout=out)
        return out.getvalue()

    def test_noop_on_sqlite(self):
        self.assertIn("atlandı", self.run_command())

    def test_postgres_flow_applies_revoke_rls_and_verifies(self):
        with mock.patch.object(db_security, "is_postgres", return_value=True), mock.patch.object(
            db_security, "revoke_api_access", return_value=["anon", "authenticated"]
        ) as revoke, mock.patch.object(
            db_security, "enable_rls_on_all_tables", return_value=["a", "b"]
        ) as rls, mock.patch.object(db_security, "tables_without_rls", return_value=[]), mock.patch(
            "core.management.commands.secure_db.connection"
        ) as connection:
            connection.cursor.return_value.__enter__.return_value = FakeCursor()
            output = self.run_command()
        revoke.assert_called_once()
        rls.assert_called_once()
        self.assertIn("Yetkiler kaldırıldı: anon, authenticated", output)
        self.assertIn("RLS açıldı: 2 tablo", output)

    def test_command_fails_if_any_table_is_left_without_rls(self):
        with mock.patch.object(db_security, "is_postgres", return_value=True), mock.patch.object(
            db_security, "revoke_api_access", return_value=[]
        ), mock.patch.object(db_security, "enable_rls_on_all_tables", return_value=["a"]), mock.patch.object(
            db_security, "tables_without_rls", return_value=["unprotected_table"]
        ), mock.patch("core.management.commands.secure_db.connection") as connection:
            connection.cursor.return_value.__enter__.return_value = FakeCursor()
            with self.assertRaisesMessage(CommandError, "unprotected_table"):
                self.run_command()


class DeploymentConfigTests(SimpleTestCase):
    """Vercel zero-config dagitimi icin gerekli dosya ve ayarlar."""

    def read(self, name):
        return (Path(settings.BASE_DIR) / name).read_text(encoding="utf-8")

    def test_python_version_is_supported_by_vercel(self):
        # Vercel yalnizca 3.12 (varsayilan), 3.13 ve 3.14'u destekler; digerleri sessizce 3.12'ye duser.
        self.assertIn(self.read(".python-version").strip(), {"3.12", "3.13", "3.14"})

    def test_requirements_are_exactly_pinned(self):
        for name in ("requirements.txt", "requirements-dev.txt"):
            for line in self.read(name).splitlines():
                line = line.split("#")[0].strip()
                if line and not line.startswith("-r"):
                    self.assertIn("==", line, f"{name}: {line}")

    def test_vercel_can_find_wsgi_entrypoint_and_static_root(self):
        self.assertEqual(settings.WSGI_APPLICATION, "config.wsgi.application")
        self.assertTrue((Path(settings.BASE_DIR) / "manage.py").exists())
        self.assertTrue(str(settings.STATIC_ROOT))

    def test_no_secrets_or_local_files_are_committable(self):
        ignored = self.read(".gitignore").splitlines()
        for pattern in (".env", "db.sqlite3", "staticfiles/", ".venv/"):
            self.assertIn(pattern, ignored)
        for line in self.read(".env.example").splitlines():
            if line.startswith("DATABASE_URL="):
                self.assertEqual(line, "DATABASE_URL=")  # gercek adres yok

    def test_no_supabase_keys_in_project(self):
        for name in ("config/settings.py", ".env.example", "requirements.txt"):
            text = self.read(name).lower()
            for forbidden in ("service_role", "anon_key", "supabase_key", "supabase_url"):
                self.assertNotIn(forbidden, text, f"{name}: {forbidden}")


class DatabaseSettingsTests(SimpleTestCase):
    """DATABASE_URL ayarlarini alt surecte, sahte bir adresle dogrular (baglanti kurulmaz)."""

    SCRIPT = (
        "import json, config.settings as s; d = s.DATABASES['default']; "
        "print(json.dumps({'engine': d['ENGINE'], 'port': str(d.get('PORT')), 'options': d.get('OPTIONS', {}), "
        "'cursors': d.get('DISABLE_SERVER_SIDE_CURSORS', False), 'conn_max_age': d.get('CONN_MAX_AGE')}))"
    )

    def load(self, database_url):
        env = {**os.environ, "DATABASE_URL": database_url, "DEBUG": "True", "SECRET_KEY": "x" * 50}
        env["DJANGO_SETTINGS_MODULE"] = "config.settings"
        result = subprocess.run(
            [sys.executable, "-c", self.SCRIPT],
            cwd=settings.BASE_DIR,
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_transaction_pooler_disables_server_side_cursors_and_prepared_statements(self):
        data = self.load(FAKE_POOLER_URL.format(port=6543))
        self.assertEqual(data["engine"], "django.db.backends.postgresql")
        self.assertEqual(data["port"], "6543")
        self.assertEqual(data["options"]["sslmode"], "require")
        self.assertIn("prepare_threshold", data["options"])
        self.assertIsNone(data["options"]["prepare_threshold"])
        self.assertTrue(data["cursors"])
        self.assertEqual(data["conn_max_age"], 0)

    def test_session_pooler_requires_ssl_without_transaction_workarounds(self):
        data = self.load(FAKE_POOLER_URL.format(port=5432))
        self.assertEqual(data["options"]["sslmode"], "require")
        self.assertNotIn("prepare_threshold", data["options"])
        self.assertFalse(data["cursors"])

    def test_no_database_url_falls_back_to_sqlite(self):
        data = self.load("")
        self.assertEqual(data["engine"], "django.db.backends.sqlite3")

    def _load_as_test_command(self, **extra_env):
        script = "import sys; sys.argv = ['manage.py', 'test']; " + self.SCRIPT
        env = {**os.environ, "DEBUG": "True", "SECRET_KEY": "x" * 50, "DJANGO_SETTINGS_MODULE": "config.settings"}
        env["DATABASE_URL"] = FAKE_POOLER_URL.format(port=5432)
        env.update(extra_env)
        result = subprocess.run(
            [sys.executable, "-c", script], cwd=settings.BASE_DIR, env=env, capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_test_command_never_uses_database_url(self):
        # `manage.py test`, .env'deki gercek (Supabase) adresine baglanmamali.
        data = self._load_as_test_command()
        self.assertEqual(data["engine"], "django.db.backends.sqlite3")

    def test_test_command_can_use_explicit_test_database_url(self):
        data = self._load_as_test_command(TEST_DATABASE_URL=FAKE_POOLER_URL.format(port=5432))
        self.assertEqual(data["engine"], "django.db.backends.postgresql")
