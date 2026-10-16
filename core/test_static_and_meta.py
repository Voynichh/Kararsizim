"""Hash'li statik dosyalar, Open Graph etiketleri, arama motoru ve baglanti kopyalama testleri."""

import json
import re
import tempfile
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.storage import staticfiles_storage
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings

from polls.models import Option, Poll

User = get_user_model()


class HashedStaticFilesTests(SimpleTestCase):
    def test_manifest_storage_is_configured_and_forgiving(self):
        backend = settings.STORAGES["staticfiles"]["BACKEND"]
        self.assertEqual(backend, "config.storage.ForgivingManifestStaticFilesStorage")
        from config.storage import ForgivingManifestStaticFilesStorage

        self.assertFalse(ForgivingManifestStaticFilesStorage.manifest_strict)

    def test_collectstatic_produces_hashed_names_and_manifest(self):
        with tempfile.TemporaryDirectory() as tmp, override_settings(STATIC_ROOT=tmp, DEBUG=False):
            call_command("collectstatic", interactive=False, verbosity=0)
            manifest = json.loads((Path(tmp) / "staticfiles.json").read_text(encoding="utf-8"))
            self.assertIn("css/main.css", manifest["paths"])
            for name, pattern in (
                ("css/main.css", r"^/static/css/main\.[0-9a-f]{12}\.css$"),
                ("js/main.js", r"^/static/js/main\.[0-9a-f]{12}\.js$"),
                ("favicon.svg", r"^/static/favicon\.[0-9a-f]{12}\.svg$"),
            ):
                with self.subTest(file=name):
                    self.assertRegex(staticfiles_storage.url(name), pattern)
                    hashed = Path(tmp) / staticfiles_storage.url(name).removeprefix("/static/")
                    self.assertTrue(hashed.exists())

    def test_missing_manifest_falls_back_to_plain_names_instead_of_crashing(self):
        with tempfile.TemporaryDirectory() as tmp, override_settings(STATIC_ROOT=tmp, DEBUG=False):
            self.assertEqual(staticfiles_storage.url("css/main.css"), "/static/css/main.css")

    def test_vercel_json_sets_long_cache_and_nosniff_for_static_only(self):
        config = json.loads((Path(settings.BASE_DIR) / "vercel.json").read_text(encoding="utf-8"))
        (rule,) = config["headers"]
        self.assertEqual(rule["source"], "/static/(.*)")
        headers = {h["key"]: h["value"] for h in rule["headers"]}
        self.assertIn("immutable", headers["Cache-Control"])
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertIn("sandbox", headers["Content-Security-Policy"])
        # Uygulama sayfalarinin onbellegi vercel.json'dan degil Django'dan gelir.
        self.assertNotIn("rewrites", config)


class OpenGraphTests(TestCase):
    def setUp(self):
        owner = User.objects.create_user("o@example.com", "sahip", "uzun-bir-parola-123")
        self.poll = Poll.objects.create(author=owner, question='Soru "tirnak" <b>kalin</b> & ozel?')
        Option.objects.create(poll=self.poll, text="Sinema", order=0)
        Option.objects.create(poll=self.poll, text="Restoran <i>", order=1)

    def test_default_meta_tags_on_normal_pages(self):
        html = self.client.get("/gizlilik/").content.decode()
        self.assertIn('<meta name="description" content="Kararsız kaldığın', html)
        self.assertIn('<meta property="og:site_name" content="kararsızım">', html)
        self.assertIn('<meta property="og:locale" content="tr_TR">', html)

    def test_canonical_url_has_no_query_string_and_only_on_feed_and_detail(self):
        feed = self.client.get("/?page=1&next=https://kotu-site.com").content.decode()
        self.assertIn('<meta property="og:url" content="http://testserver/">', feed)
        # Meta etiketleri sorgu dizisini yansitmaz (oy formundaki gizli `next` bilerek sayfa adresini tasir).
        self.assertNotIn("kotu-site", feed.split("</head>")[0])
        detail = self.client.get(f"/anket/{self.poll.pk}/?x=1").content.decode()
        self.assertIn(f'<meta property="og:url" content="http://testserver/anket/{self.poll.pk}/">', detail)
        for path in ("/giris/", "/kayit/", "/gizlilik/", "/yok-sayfa/"):
            self.assertNotIn("og:url", self.client.get(path).content.decode())

    def test_poll_detail_uses_question_and_options_escaped(self):
        html = self.client.get(f"/anket/{self.poll.pk}/").content.decode()
        self.assertIn("&quot;tirnak&quot;", html)
        self.assertIn("&lt;b&gt;kalin&lt;/b&gt; &amp; ozel?", html)
        self.assertNotIn("<b>kalin</b>", html)
        self.assertNotIn("<i>", html)
        self.assertRegex(html, r'<meta property="og:title" content="Soru &quot;tirnak&quot;')
        self.assertRegex(html, r'<meta name="description" content="Sinema / Restoran &lt;i&gt; — sen ne dersin\?">')

    def test_link_preview_does_not_reveal_results_before_voting(self):
        voter = Option.objects.get(poll=self.poll, order=0)
        self.client.post(f"/anket/{self.poll.pk}/oy/", {"option": voter.pk})
        html = Client_fresh().get(f"/anket/{self.poll.pk}/").content.decode()
        head = html.split("</head>")[0]
        self.assertNotRegex(head, r"%\d+|\d+ oy")

    def test_error_pages_without_request_context_do_not_crash(self):
        self.assertEqual(self.client.get("/", HTTP_HOST="kotu-site.example").status_code, 400)


def Client_fresh():
    from django.test import Client

    return Client()


class SearchIndexingTests(TestCase):
    def test_indexing_is_blocked_by_default(self):
        response = self.client.get("/")
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow")
        robots = self.client.get("/robots.txt")
        self.assertEqual(robots.status_code, 200)
        self.assertEqual(robots["Content-Type"], "text/plain; charset=utf-8")
        self.assertIn("Disallow: /\n", robots.content.decode())

    @override_settings(ALLOW_SEARCH_INDEXING=True)
    def test_indexing_can_be_enabled_explicitly_without_revealing_admin_path(self):
        self.assertNotIn("X-Robots-Tag", self.client.get("/"))
        body = self.client.get("/robots.txt").content.decode()
        self.assertNotIn("Disallow: /\n", body)
        self.assertIn("Disallow: /hesap/", body)
        self.assertNotIn(settings.ADMIN_URL.strip("/"), body)

    def test_robots_txt_is_get_only(self):
        self.assertEqual(self.client.post("/robots.txt").status_code, 405)


class CopyLinkTests(TestCase):
    def setUp(self):
        owner = User.objects.create_user("o@example.com", "sahip", "uzun-bir-parola-123")
        self.poll = Poll.objects.create(author=owner, question="Link kopyalama testi sorusu?")
        Option.objects.create(poll=self.poll, text="A", order=0)
        Option.objects.create(poll=self.poll, text="B", order=1)

    def test_detail_has_hidden_copy_button_that_js_reveals(self):
        html = self.client.get(f"/anket/{self.poll.pk}/").content.decode()
        self.assertRegex(html, r'<button type="button" class="btn" data-copy-link hidden>Linki kopyala</button>')

    def test_copy_button_only_on_detail_page(self):
        self.assertNotIn("data-copy-link", self.client.get("/").content.decode())

    def test_js_copies_only_origin_and_path(self):
        source = (Path(settings.BASE_DIR) / "static" / "js" / "main.js").read_text(encoding="utf-8")
        self.assertIn("window.location.origin + window.location.pathname", source)
        self.assertIn("navigator.clipboard.writeText", source)
        self.assertNotRegex(source, r"location\.(search|hash|href)\b.*writeText")
