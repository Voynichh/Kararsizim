"""Guvenlik denetimiyle bulunan sorunlarin gerileme testleri."""

from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase

from polls.forms import normalize_text
from polls.models import Option, Poll

User = get_user_model()
PASSWORD = "mavi-bulut-kahve-42"


class AdminLoginRateLimitTests(TestCase):
    def setUp(self):
        cache.clear()
        self.admin_url = "/" + settings.ADMIN_URL + "login/"
        self.root = User.objects.create_superuser("root@example.com", "root", PASSWORD)

    def attempt(self, email="root@example.com", password="yanlis-parola-123", addr="198.51.100.1", client=None):
        return (client or Client()).post(
            self.admin_url, {"username": email, "password": password}, REMOTE_ADDR=addr
        )

    def test_failed_admin_logins_are_limited_per_email(self):
        codes = [self.attempt(addr=f"203.0.113.{i}").status_code for i in range(7)]
        self.assertEqual(codes[:5], [200] * 5)
        self.assertEqual(codes[5], 429)

    def test_failed_admin_logins_are_limited_per_ip(self):
        codes = [self.attempt(email=f"x{i}@example.com").status_code for i in range(12)]
        self.assertEqual(codes[:10], [200] * 10)
        self.assertEqual(codes[10], 429)

    def test_correct_password_is_blocked_once_limit_is_reached(self):
        for _ in range(5):
            self.attempt()
        self.assertEqual(self.attempt(password=PASSWORD).status_code, 429)

    def test_successful_admin_logins_do_not_consume_the_limit(self):
        for _ in range(8):
            response = self.attempt(password=PASSWORD)
            self.assertEqual(response.status_code, 302)

    def test_get_login_page_is_not_limited(self):
        for _ in range(15):
            self.assertEqual(self.client.get(self.admin_url).status_code, 200)


class LoginConcurrencyTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user("ali@example.com", "ali", PASSWORD)

    def test_parallel_burst_cannot_try_more_passwords_than_the_limit(self):
        # Tum istekler sayaci "bos" gorse bile (yaris), yalnizca 5 deneme parola dogrulamasina ulasir.
        with mock.patch("core.ratelimit.cache.get_many", return_value={}), mock.patch(
            "accounts.forms.authenticate", return_value=None
        ) as auth:
            codes = [
                Client().post(
                    "/giris/",
                    {"email": "ali@example.com", "password": f"yanlis-parola-{i}"},
                    REMOTE_ADDR=f"203.0.113.{i}",
                ).status_code
                for i in range(30)
            ]
        self.assertEqual(auth.call_count, 5)
        self.assertEqual(codes.count(429), 25)

    def test_successful_login_gives_the_attempt_back(self):
        for _ in range(4):
            Client().post("/giris/", {"email": "ali@example.com", "password": "yanlis-parola-123"})
        for _ in range(3):
            c = Client()
            self.assertEqual(c.post("/giris/", {"email": "ali@example.com", "password": PASSWORD}).status_code, 302)
        # 4 basarisiz + basarili girisler iade edildi: 5. basarisiz hak hala kullanilabilir.
        self.assertEqual(
            Client().post("/giris/", {"email": "ali@example.com", "password": "yanlis-parola-123"}).status_code, 200
        )
        self.assertEqual(
            Client().post("/giris/", {"email": "ali@example.com", "password": "yanlis-parola-123"}).status_code, 429
        )


class CacheControlTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ali@example.com", "ali", PASSWORD)

    def test_personal_pages_are_never_stored(self):
        self.client.force_login(self.user)
        for path in ("/hesap/", "/hesap/parola/", "/hesap/sil/"):
            with self.subTest(path=path):
                cache_control = self.client.get(path)["Cache-Control"]
                self.assertIn("no-store", cache_control)
                self.assertIn("private", cache_control)

    def test_other_pages_are_private_and_revalidated(self):
        for path in ("/", "/giris/", "/gizlilik/", "/yok-bir-sayfa/"):
            with self.subTest(path=path):
                cache_control = self.client.get(path)["Cache-Control"]
                self.assertIn("private", cache_control)
                self.assertNotIn("public", cache_control)
                self.assertNotIn("s-maxage", cache_control)

    def test_vote_json_is_not_cacheable(self):
        owner = User.objects.create_user("o@example.com", "sahip", PASSWORD)
        poll = Poll.objects.create(author=owner, question="Cache testi sorusu?")
        option = Option.objects.create(poll=poll, text="A", order=0)
        Option.objects.create(poll=poll, text="B", order=1)
        response = self.client.post(f"/anket/{poll.pk}/oy/", {"option": option.pk}, HTTP_ACCEPT="application/json")
        self.assertIn("private", response["Cache-Control"])


class CsrfFailurePageTests(TestCase):
    def test_csrf_failure_shows_themed_page_without_internals(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post("/giris/", {"email": "a@example.com", "password": "x"})
        self.assertContains(response, "Güvenlik doğrulaması başarısız.", status_code=403)
        body = response.content.decode().lower()
        for forbidden in ("reason given", "csrf_trusted_origins", "referer", "origin checking"):
            self.assertNotIn(forbidden, body)


class TextNormalizationTests(TestCase):
    def test_invisible_and_directional_characters_are_removed(self):
        self.assertEqual(normalize_text("A​B﻿C­D"), "ABCD")
        self.assertEqual(normalize_text("‮evil‬ metin"), "evil metin")
        self.assertEqual(normalize_text("a⁦b⁩c"), "abc")

    def test_control_characters_are_removed_but_whitespace_is_collapsed(self):
        self.assertEqual(normalize_text("a\x00b\x1b[31mc"), "ab[31mc")
        self.assertEqual(normalize_text("  a \t\n  b  "), "a b")

    def test_emoji_and_turkish_characters_survive(self):
        self.assertEqual(normalize_text("Çay mı, kahve mi? ığüşöç İĞÜŞÖÇ"), "Çay mı, kahve mi? ığüşöç İĞÜŞÖÇ")
        family = "👨‍👩‍👧"  # ZWJ dizisi bozulmamali
        self.assertEqual(normalize_text(family), family)

    def test_invisible_only_option_counts_as_empty(self):
        user = User.objects.create_user("ali@example.com", "ali", PASSWORD)
        self.client.force_login(user)
        response = self.client.post(
            "/anket/yeni/", {"question": "Gorunmez secenek testi?", "option": ["Gercek secenek", "​​", "‮"]}
        )
        self.assertContains(response, "En az 2 seçenek girmelisin.")
        self.assertEqual(Poll.objects.count(), 0)

    def test_stored_text_has_no_hidden_characters(self):
        user = User.objects.create_user("ali@example.com", "ali", PASSWORD)
        self.client.force_login(user)
        self.client.post(
            "/anket/yeni/",
            {"question": "Sorun​‮ burada?", "option": ["Se​c‮e", "Di\x00ğer"]},
        )
        poll = Poll.objects.get()
        self.assertEqual(poll.question, "Sorun burada?")
        self.assertEqual([o.text for o in poll.options.all()], ["Sece", "Diğer"])
