from django.core.cache import cache
from django.db import connection
from django.test import RequestFactory, TestCase, override_settings

from core import ratelimit
from core.net import get_client_ip, get_safe_next, hash_identifier


class ClientIpTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @override_settings(TRUST_PROXY_IP_HEADER=False)
    def test_forwarded_header_ignored_when_not_trusted(self):
        request = self.factory.get("/", REMOTE_ADDR="10.0.0.1", HTTP_X_FORWARDED_FOR="6.6.6.6")
        self.assertEqual(get_client_ip(request), "10.0.0.1")

    @override_settings(TRUST_PROXY_IP_HEADER=True)
    def test_forwarded_header_used_when_trusted(self):
        request = self.factory.get("/", REMOTE_ADDR="10.0.0.1", HTTP_X_FORWARDED_FOR="203.0.113.7")
        self.assertEqual(get_client_ip(request), "203.0.113.7")

    @override_settings(TRUST_PROXY_IP_HEADER=True)
    def test_rightmost_value_is_used_so_client_cannot_prepend_a_fake_ip(self):
        request = self.factory.get(
            "/", REMOTE_ADDR="10.0.0.1", HTTP_X_FORWARDED_FOR="6.6.6.6, 203.0.113.7"
        )
        self.assertEqual(get_client_ip(request), "203.0.113.7")

    @override_settings(TRUST_PROXY_IP_HEADER=True)
    def test_invalid_header_falls_back_to_remote_addr(self):
        request = self.factory.get("/", REMOTE_ADDR="10.0.0.1", HTTP_X_FORWARDED_FOR="not-an-ip")
        self.assertEqual(get_client_ip(request), "10.0.0.1")

    @override_settings(TRUST_PROXY_IP_HEADER=True)
    def test_missing_header_falls_back_to_remote_addr(self):
        request = self.factory.get("/", REMOTE_ADDR="10.0.0.1")
        self.assertEqual(get_client_ip(request), "10.0.0.1")


class SafeNextTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_relative_path_allowed(self):
        self.assertEqual(get_safe_next(self.factory.get("/giris/", {"next": "/hesap/"})), "/hesap/")

    def test_external_urls_rejected(self):
        for evil in ("https://kotu-site.com", "//kotu-site.com", "http://testserver.evil.com/"):
            with self.subTest(next=evil):
                self.assertEqual(get_safe_next(self.factory.get("/giris/", {"next": evil})), "")

    def test_same_host_absolute_url_allowed(self):
        request = self.factory.get("/giris/", {"next": "http://testserver/hesap/"})
        self.assertEqual(get_safe_next(request), "http://testserver/hesap/")

    def test_missing_next_returns_empty(self):
        self.assertEqual(get_safe_next(self.factory.get("/giris/")), "")


class RateLimitTests(TestCase):
    RULE = (3, 60)

    def setUp(self):
        cache.clear()

    def test_hit_blocks_after_limit(self):
        results = [ratelimit.hit("t", "kimlik", self.RULE) for _ in range(5)]
        self.assertEqual(results, [False, False, False, True, True])

    def test_scopes_and_identifiers_are_independent(self):
        for _ in range(4):
            ratelimit.hit("a", "x", self.RULE)
        self.assertFalse(ratelimit.hit("b", "x", self.RULE))
        self.assertFalse(ratelimit.hit("a", "y", self.RULE))

    def test_is_limited_does_not_increment(self):
        for _ in range(10):
            self.assertFalse(ratelimit.is_limited("t", "kimlik", self.RULE))
        for _ in range(3):
            ratelimit.record("t", "kimlik", self.RULE)
        self.assertTrue(ratelimit.is_limited("t", "kimlik", self.RULE))

    def test_cache_keys_contain_no_raw_ip_or_email(self):
        ratelimit.hit("login_ip", "203.0.113.7", self.RULE)
        ratelimit.hit("login_email", "gizli.adres@example.com", self.RULE)
        with connection.cursor() as cursor:
            cursor.execute("SELECT cache_key FROM kv_cache")
            keys = [row[0] for row in cursor.fetchall()]
        self.assertTrue(keys)
        for key in keys:
            self.assertNotIn("203.0.113.7", key)
            self.assertNotIn("gizli.adres", key)
            self.assertNotIn("example.com", key)

    def test_hash_identifier_is_stable_and_not_plaintext(self):
        digest = hash_identifier("203.0.113.7")
        self.assertEqual(digest, hash_identifier("203.0.113.7"))
        self.assertNotIn("203.0.113.7", digest)
        self.assertEqual(len(digest), 64)

    def test_json_clients_get_json_429(self):
        request = RequestFactory().post("/", HTTP_ACCEPT="application/json")
        response = ratelimit.rate_limited_response(request)
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response["Content-Type"], "application/json")
