from django.conf import settings
from django.test import TestCase, override_settings


class MaintenanceModeTests(TestCase):
    """MAINTENANCE_MODE: tum sayfalar 503 "Bakimdayiz"; admin yolu ve statik dosyalar acik kalir."""

    def test_site_is_open_by_default(self):
        self.assertEqual(self.client.get("/").status_code, 200)

    @override_settings(MAINTENANCE_MODE=True)
    def test_pages_return_503_with_maintenance_message(self):
        for path in ("/", "/kayit/", "/giris/", "/gizlilik/", "/anket/1/", "/anket/sonuclar/", "/yok-bir-sayfa/"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 503, path)
            self.assertContains(response, "Bakımdayız", status_code=503)
            self.assertEqual(response["Retry-After"], "600")
            self.assertEqual(response["Cache-Control"], "no-store")
            self.assertIn("default-src", response["Content-Security-Policy"])

    @override_settings(MAINTENANCE_MODE=True)
    def test_posts_are_blocked_too(self):
        self.assertEqual(self.client.post("/anket/1/oy/", {"option": "1"}).status_code, 503)
        self.assertEqual(self.client.post("/giris/", {"email": "a@b.co", "password": "x"}).status_code, 503)
        self.assertEqual(self.client.post("/kayit/", {}).status_code, 503)

    @override_settings(MAINTENANCE_MODE=True)
    def test_json_requests_get_json_503(self):
        response = self.client.get("/anket/sonuclar/?ids=1", HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["ok"], False)

    @override_settings(MAINTENANCE_MODE=True)
    def test_admin_login_stays_reachable(self):
        response = self.client.get("/" + settings.ADMIN_URL + "login/")
        self.assertEqual(response.status_code, 200)

    @override_settings(MAINTENANCE_MODE=True)
    def test_maintenance_page_leaks_nothing(self):
        body = self.client.get("/").content.decode().lower()
        for word in ("traceback", "urlconf", "settings.py", settings.ADMIN_URL.strip("/").lower(), "@"):
            self.assertNotIn(word, body)
