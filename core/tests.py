import os
import subprocess
import sys

from django.conf import settings
from django.template.loader import render_to_string
from django.test import SimpleTestCase, TestCase


class SecurityHeadersTests(TestCase):
    def test_security_headers_present_on_home(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        csp = response["Content-Security-Policy"]
        for directive in (
            "default-src 'self'",
            "script-src 'self'",
            "style-src 'self'",
            "font-src 'self'",
            "img-src 'self' data:",
            "connect-src 'self'",
            "form-action 'self'",
            "frame-ancestors 'none'",
            "base-uri 'self'",
            "object-src 'none'",
        ):
            self.assertIn(directive, csp)
        self.assertNotIn("unsafe-inline", csp)
        self.assertEqual(response["X-Frame-Options"], "DENY")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response["Referrer-Policy"], "same-origin")
        self.assertEqual(response["Cross-Origin-Opener-Policy"], "same-origin")
        self.assertEqual(
            response["Permissions-Policy"],
            "camera=(), microphone=(), geolocation=(), payment=()",
        )

    def test_security_headers_present_on_404(self):
        response = self.client.get("/yok-boyle-bir-sayfa/")
        self.assertEqual(response.status_code, 404)
        self.assertIn("Content-Security-Policy", response)
        self.assertEqual(response["X-Frame-Options"], "DENY")

    def test_csp_relaxation_applies_only_to_admin(self):
        admin_response = self.client.get("/" + settings.ADMIN_URL + "login/")
        self.assertIn("style-src 'self' 'unsafe-inline'", admin_response["Content-Security-Policy"])
        self.assertIn("script-src 'self';", admin_response["Content-Security-Policy"])
        home_response = self.client.get("/")
        self.assertNotIn("unsafe-inline", home_response["Content-Security-Policy"])


class PageTests(TestCase):
    def test_home_shows_empty_state_in_turkish(self):
        response = self.client.get("/")
        self.assertContains(response, "Henüz kimse kararsız değil.")
        self.assertContains(response, "İlk anketi sen aç!")
        self.assertContains(response, '<html lang="tr">')

    def test_templates_have_no_inline_script_style_or_handlers(self):
        html = self.client.get("/").content.decode()
        self.assertNotIn("style=", html)
        self.assertNotIn("onclick=", html)
        # Yalnizca src'li harici script etiketi olabilir.
        self.assertNotIn("<script>", html)

    def test_404_page_is_themed(self):
        response = self.client.get("/yok-boyle-bir-sayfa/")
        self.assertContains(response, "Aradığın sayfayı bulamadık.", status_code=404)
        self.assertContains(response, "css/main.css", status_code=404)

    def test_admin_served_only_at_admin_url(self):
        response = self.client.get("/" + settings.ADMIN_URL)
        self.assertEqual(response.status_code, 302)


class ErrorTemplateTests(SimpleTestCase):
    def test_error_templates_render(self):
        expected = {
            "400.html": "Bu isteği anlayamadık.",
            "403.html": "Bu sayfaya erişimin yok.",
            "404.html": "Aradığın sayfayı bulamadık.",
            "429.html": "Biraz yavaşla, birazdan tekrar dene.",
            "500.html": "Bir şeyler ters gitti.",
        }
        for name, text in expected.items():
            with self.subTest(template=name):
                self.assertIn(text, render_to_string(name))


class SettingsSafetyTests(SimpleTestCase):
    def _run_settings_import(self, **env_overrides):
        env = os.environ.copy()
        env.update(env_overrides)
        env["DJANGO_SETTINGS_MODULE"] = "config.settings"
        return subprocess.run(
            [sys.executable, "-c", "import config.settings"],
            cwd=settings.BASE_DIR,
            env=env,
            capture_output=True,
            text=True,
        )

    def test_refuses_to_start_without_secret_key_when_debug_false(self):
        # Bos deger: python-dotenv mevcut ortam degiskenini ezmez, yani .env'den dolmaz.
        result = self._run_settings_import(DEBUG="False", SECRET_KEY="")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("SECRET_KEY", result.stderr)

    def test_debug_defaults_to_false(self):
        result = subprocess.run(
            [sys.executable, "-c", "import config.settings as s; print(s.DEBUG)"],
            cwd=settings.BASE_DIR,
            env={**os.environ, "DEBUG": "", "SECRET_KEY": "x" * 50, "DJANGO_SETTINGS_MODULE": "config.settings"},
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "False")

    def test_password_hasher_order_and_validators(self):
        self.assertTrue(settings.PASSWORD_HASHERS[0].endswith("Argon2PasswordHasher"))
        min_length = [
            v for v in settings.AUTH_PASSWORD_VALIDATORS if v["NAME"].endswith("MinimumLengthValidator")
        ][0]
        self.assertEqual(min_length["OPTIONS"]["min_length"], 10)

    def test_cookie_settings(self):
        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)
        self.assertTrue(settings.CSRF_COOKIE_HTTPONLY)
        self.assertEqual(settings.SESSION_COOKIE_SAMESITE, "Lax")
        self.assertEqual(settings.CSRF_COOKIE_SAMESITE, "Lax")
