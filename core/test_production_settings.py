"""Uretim ayarlari (DEBUG=False) testleri.

Testler normalde DEBUG=True ile calisir, bu yuzden SECURE_SSL_REDIRECT, Secure cerezler ve HSTS gibi
yalnizca uretimde acik ayarlar hic denenmiyordu. Bu testler ayarlari ayri bir surecte DEBUG=False ile
yukleyip gercek davranisi dogrular. Gercek veritabanina baglanilmaz (DATABASE_URL bos / sahte).
"""

import json
import os
import subprocess
import sys

from django.conf import settings
from django.test import SimpleTestCase

FAKE_URL = "postgresql://postgres.fakeref:fake-pass@aws-0-eu-central-1.pooler.supabase.com:6543/postgres"

HTTP_SCRIPT = r"""
import json, os, sys
sys.path.insert(0, os.getcwd())
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
import django
django.setup()
from django.test import Client
from django.test.utils import setup_test_environment
setup_test_environment()

c = Client()
out = {}
r = c.get("/gizlilik/")
out["http_status"], out["http_location"] = r.status_code, r.get("Location", "")
r = c.get("/gizlilik/", secure=True)
out["https_status"] = r.status_code
out["hsts"] = r.get("Strict-Transport-Security", "")
out["cache_control"] = r.get("Cache-Control", "")
out["csp"] = r.get("Content-Security-Policy", "")
r = c.get("/giris/", secure=True)
ck = r.cookies.get("csrftoken")
out["csrf_cookie"] = {"secure": bool(ck["secure"]), "httponly": bool(ck["httponly"]), "samesite": ck["samesite"]} if ck else None
r = c.get("/yok-bir-sayfa/", secure=True)
body = r.content.decode().lower()
out["404_status"] = r.status_code
out["404_leaks"] = [w for w in ("urlconf", "traceback", "debug = true", "request method", "settings.py") if w in body]
out["404_themed"] = "aradığın sayfayı bulamadık" in body
out["admin_default_path"] = c.get("/admin/", secure=True).status_code
out["bad_host"] = c.get("/gizlilik/", secure=True, HTTP_HOST="kotu-site.example").status_code
print(json.dumps(out))
"""

SETTINGS_SCRIPT = (
    "import json, config.settings as s; print(json.dumps({"
    "'debug': s.DEBUG, 'ssl_redirect': getattr(s, 'SECURE_SSL_REDIRECT', None), "
    "'session_secure': getattr(s, 'SESSION_COOKIE_SECURE', None), 'csrf_secure': getattr(s, 'CSRF_COOKIE_SECURE', None), "
    "'hsts': getattr(s, 'SECURE_HSTS_SECONDS', None), 'proxy_header': getattr(s, 'SECURE_PROXY_SSL_HEADER', None), "
    "'asgi': hasattr(s, 'ASGI_APPLICATION'), 'wsgi': getattr(s, 'WSGI_APPLICATION', None)}))"
)


def run(code, **env):
    full_env = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "config.settings",
        "DEBUG": "False",
        "SECRET_KEY": "x" * 50,
        "ALLOWED_HOSTS": "example.com",
        "DATABASE_URL": "",
        "ADMIN_URL": "yonetim-test/",
        "VERCEL": "",
        "TRUST_PROXY_IP_HEADER": "False",
    }
    full_env.update(env)
    return subprocess.run(
        [sys.executable, "-c", code], cwd=settings.BASE_DIR, env=full_env, capture_output=True, text=True
    )


class ProductionSettingsTests(SimpleTestCase):
    def test_production_only_security_settings_are_enabled(self):
        result = run(SETTINGS_SCRIPT)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertFalse(data["debug"])
        self.assertTrue(data["ssl_redirect"])
        self.assertTrue(data["session_secure"])
        self.assertTrue(data["csrf_secure"])
        self.assertEqual(data["hsts"], 31536000)
        self.assertEqual(data["proxy_header"], ["HTTP_X_FORWARDED_PROTO", "https"])

    def test_only_wsgi_entrypoint_is_declared_for_vercel(self):
        # Vercel, ikisi de tanimliysa ASGI'yi secer; uygulama WSGI icin tasarlandi.
        data = json.loads(run(SETTINGS_SCRIPT).stdout)
        self.assertEqual(data["wsgi"], "config.wsgi.application")
        self.assertFalse(data["asgi"])

    def test_refuses_to_start_without_allowed_hosts_in_production(self):
        result = run(SETTINGS_SCRIPT, ALLOWED_HOSTS="")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ALLOWED_HOSTS", result.stderr)

    def test_vercel_without_database_url_is_rejected_instead_of_falling_back_to_sqlite(self):
        result = run(SETTINGS_SCRIPT, VERCEL="1", DATABASE_URL="")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DATABASE_URL", result.stderr)

    def test_vercel_with_complete_configuration_starts(self):
        result = run(SETTINGS_SCRIPT, VERCEL="1", DATABASE_URL=FAKE_URL)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_vercel_refuses_debug_true(self):
        result = run(SETTINGS_SCRIPT, VERCEL="1", DEBUG="True", DATABASE_URL=FAKE_URL)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DEBUG=True Vercel", result.stderr)

    def test_real_http_behaviour_under_production_settings(self):
        result = run(HTTP_SCRIPT)
        self.assertEqual(result.returncode, 0, result.stderr)
        out = json.loads(result.stdout)
        # http -> https
        self.assertEqual(out["http_status"], 301)
        self.assertTrue(out["http_location"].startswith("https://"))
        # https
        self.assertEqual(out["https_status"], 200)
        self.assertIn("max-age=31536000", out["hsts"])
        self.assertIn("private", out["cache_control"])
        self.assertNotIn("unsafe", out["csp"])
        # cerezler
        self.assertEqual(out["csrf_cookie"], {"secure": True, "httponly": True, "samesite": "Lax"})
        # hata sayfalari
        self.assertEqual(out["404_status"], 404)
        self.assertTrue(out["404_themed"])
        self.assertEqual(out["404_leaks"], [])
        self.assertEqual(out["admin_default_path"], 404)
        self.assertEqual(out["bad_host"], 400)
