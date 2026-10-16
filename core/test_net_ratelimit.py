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

    def test_only_site_relative_paths_are_accepted(self):
        # Mutlak URL'ler (kendi host'umuz dahil) ve "/" ile baslamayan baglı yollar reddedilir.
        for value in ("http://testserver/hesap/", "hesap/", "%2f%2fkotu-site.com", "?x=1", "/\\kotu-site.com"):
            with self.subTest(next=value):
                self.assertEqual(get_safe_next(self.factory.get("/giris/", {"next": value})), "")

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

    def test_is_limited_does_not_consume_attempts(self):
        for _ in range(10):
            self.assertFalse(ratelimit.is_limited("t", "kimlik", self.RULE))
        for _ in range(3):
            self.assertIsNotNone(ratelimit.reserve("t", "kimlik", self.RULE))
        self.assertTrue(ratelimit.is_limited("t", "kimlik", self.RULE))
        self.assertIsNone(ratelimit.reserve("t", "kimlik", self.RULE))

    def test_release_gives_the_attempt_back(self):
        slots = [ratelimit.reserve("t", "kimlik", self.RULE) for _ in range(3)]
        self.assertIsNone(ratelimit.reserve("t", "kimlik", self.RULE))
        ratelimit.release(slots[1])
        self.assertIsNotNone(ratelimit.reserve("t", "kimlik", self.RULE))
        ratelimit.release(None)  # None guvenle yok sayilir

    def test_concurrent_requests_cannot_exceed_the_limit(self):
        # Yaris durumunu belirleyici sekilde simule eder: tum istekler sayaci "bos" gorur (get_many bayat),
        # yine de yalnizca `limit` kadari yuva alabilir, cunku cache.add() atomiktir.
        from unittest import mock

        with mock.patch.object(ratelimit.cache, "get_many", return_value={}):
            results = [ratelimit.reserve("race", "kimlik", self.RULE) for _ in range(25)]
        self.assertEqual(sum(slot is not None for slot in results), 3)
        self.assertEqual(len({slot for slot in results if slot}), 3)  # her yuva yalnizca bir kez

    def _expiry_seconds_from_now(self):
        from datetime import datetime, timezone as dt_timezone
        import time as _time

        with connection.cursor() as cursor:
            cursor.execute("SELECT expires FROM kv_cache")
            rows = cursor.fetchall()
        deltas = []
        for (expires,) in rows:
            if isinstance(expires, str):
                expires = datetime.fromisoformat(expires)
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=dt_timezone.utc)
            deltas.append(expires.timestamp() - _time.time())
        return deltas

    def test_slots_expire_at_window_end_not_after_cache_default_timeout(self):
        # Varsayilan 300 sn'lik omur uzun pencereleri (15 dk, 1 saat) fiilen kisaltirdi.
        import time as _time

        rule = (3, 3600)
        for _ in range(3):
            ratelimit.reserve("ttl", "kimlik", rule)
        expected = 3600 - (_time.time() % 3600) + 1
        deltas = self._expiry_seconds_from_now()
        self.assertEqual(len(deltas), 3)
        for delta in deltas:
            self.assertAlmostEqual(delta, expected, delta=5)

    def test_reserve_skips_occupied_slots_without_failing_inserts(self):
        # Dolu yuvalar icin cache.add() denenmemeli (veritabani loguna "duplicate key" duserdi).
        from unittest import mock

        for _ in range(2):
            ratelimit.reserve("t", "kimlik", self.RULE)
        with mock.patch.object(ratelimit.cache, "add", wraps=ratelimit.cache.add) as add:
            ratelimit.reserve("t", "kimlik", self.RULE)
        self.assertEqual(add.call_count, 1)

    def test_cache_is_configured_with_a_large_max_entries(self):
        # Varsayilan MAX_ENTRIES=300 asilinca aktif sayaclar rastgele silinebilirdi.
        from django.conf import settings

        self.assertGreaterEqual(settings.CACHES["default"]["OPTIONS"]["MAX_ENTRIES"], 100_000)

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
