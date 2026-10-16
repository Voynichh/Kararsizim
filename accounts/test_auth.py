from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase

from core import ratelimit

User = get_user_model()

PASSWORD = "mavi-bulut-kahve-42"
NEW_PASSWORD = "yesil-deniz-cay-77"


class AuthTestCase(TestCase):
    def setUp(self):
        cache.clear()

    def make_user(self, email="ali@example.com", username="ali", password=PASSWORD):
        return User.objects.create_user(email, username, password)

    def signup_data(self, **overrides):
        data = {
            "email": "yeni@example.com",
            "username": "yeni_kullanici",
            "password1": PASSWORD,
            "password2": PASSWORD,
        }
        data.update(overrides)
        return data


class SignupTests(AuthTestCase):
    def test_valid_signup_creates_user_logs_in_and_redirects(self):
        response = self.client.post("/kayit/", self.signup_data(), follow=True)
        self.assertRedirects(response, "/")
        user = User.objects.get(email="yeni@example.com")
        self.assertEqual(user.username, "yeni_kullanici")
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)
        self.assertContains(response, "@yeni_kullanici")
        self.assertContains(response, "Hoş geldin")

    def test_email_is_lowercased(self):
        self.client.post("/kayit/", self.signup_data(email="  Yeni@Example.COM "))
        self.assertTrue(User.objects.filter(email="yeni@example.com").exists())

    def test_duplicate_email_rejected_with_generic_message(self):
        self.make_user(email="ali@example.com", username="ali")
        response = self.client.post("/kayit/", self.signup_data(email="ALI@example.com"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Bu e-posta ile kayıt oluşturulamadı. Zaten hesabın varsa giriş yap.")
        self.assertEqual(User.objects.count(), 1)

    def test_duplicate_username_rejected_case_insensitively(self):
        self.make_user(username="Ali")
        response = self.client.post("/kayit/", self.signup_data(username="aLI"))
        self.assertContains(response, "Bu kullanıcı adı zaten alınmış.")
        self.assertEqual(User.objects.count(), 1)

    def test_invalid_username_rejected(self):
        for bad in ("ab", "x" * 21, "ali veli", "ali-veli", "çağlar"):
            with self.subTest(username=bad):
                response = self.client.post("/kayit/", self.signup_data(username=bad))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "Kullanıcı adı 3–20 karakter olmalı")
        self.assertEqual(User.objects.count(), 0)

    def test_short_password_rejected(self):
        response = self.client.post(
            "/kayit/", self.signup_data(password1="kisa1234", password2="kisa1234")
        )
        self.assertContains(response, "En az 10 karakter")
        self.assertEqual(User.objects.count(), 0)

    def test_password_too_similar_to_username_rejected(self):
        response = self.client.post(
            "/kayit/",
            self.signup_data(
                username="yeni_kullanici",
                password1="yeni_kullanici1",
                password2="yeni_kullanici1",
            ),
        )
        self.assertEqual(User.objects.count(), 0)
        self.assertEqual(response.status_code, 200)

    def test_password_mismatch_rejected(self):
        response = self.client.post("/kayit/", self.signup_data(password2=PASSWORD + "x"))
        self.assertContains(response, "Parolalar eşleşmiyor.")
        self.assertEqual(User.objects.count(), 0)

    def test_password_is_never_rendered_back(self):
        response = self.client.post("/kayit/", self.signup_data(username="x"))
        self.assertNotContains(response, PASSWORD)

    def test_password_stored_with_argon2(self):
        self.client.post("/kayit/", self.signup_data())
        user = User.objects.get(email="yeni@example.com")
        self.assertTrue(user.password.startswith("argon2"))

    def test_signup_is_rate_limited_per_ip(self):
        for _ in range(ratelimit.SIGNUP_IP[0]):
            response = self.client.post("/kayit/", self.signup_data(username="x"))
            self.assertEqual(response.status_code, 200)
        response = self.client.post("/kayit/", self.signup_data())
        self.assertEqual(response.status_code, 429)
        self.assertContains(response, "Biraz yavaşla, birazdan tekrar dene.", status_code=429)
        self.assertEqual(User.objects.count(), 0)

    def test_authenticated_user_is_redirected_away(self):
        self.client.force_login(self.make_user())
        self.assertRedirects(self.client.get("/kayit/"), "/")

    def test_signup_requires_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post("/kayit/", self.signup_data())
        self.assertEqual(response.status_code, 403)
        self.assertEqual(User.objects.count(), 0)


class ReservedUsernameTests(AuthTestCase):
    def test_staff_like_usernames_are_rejected_at_signup(self):
        for name in ("admin", "Admin", "ADMIN_", "adm1n", "a_d_m_i_n", "yonetici", "Yonetim_Ekibi",
                     "kararsizim", "kararsizim_destek", "moderator", "root", "Anonim", "support_ali", "0fficial"):
            with self.subTest(name=name):
                cache.clear()
                response = self.client.post("/kayit/", self.signup_data(username=name))
                self.assertContains(response, "Bu kullanıcı adı kullanılamaz.")
                self.assertFalse(User.objects.filter(username__iexact=name).exists())

    def test_ordinary_usernames_are_accepted(self):
        for index, name in enumerate(("ali", "ayse_k", "mehmet99", "zeynep_t", "kedi_sever")):
            with self.subTest(name=name):
                cache.clear()
                client = Client()
                response = client.post(
                    "/kayit/", self.signup_data(username=name, email=f"kisi{index}@example.com")
                )
                self.assertRedirects(response, "/")
                self.assertTrue(User.objects.filter(username=name).exists())

    def test_staff_can_still_create_such_accounts_outside_the_signup_form(self):
        # createsuperuser / yonetici islemleri etkilenmez; kural yalnizca kayit formundadir.
        User.objects.create_superuser("yonetici@example.com", "admin", PASSWORD)
        self.assertTrue(User.objects.filter(username="admin", is_superuser=True).exists())


class LoginTests(AuthTestCase):
    def login(self, email="ali@example.com", password=PASSWORD, **extra):
        return self.client.post("/giris/", {"email": email, "password": password, **extra})

    def test_login_with_email_and_password(self):
        self.make_user()
        response = self.login()
        self.assertRedirects(response, "/", fetch_redirect_response=False)
        self.assertIn("_auth_user_id", self.client.session)

    def test_login_email_is_case_insensitive(self):
        self.make_user()
        self.login(email=" ALI@Example.com ")
        self.assertIn("_auth_user_id", self.client.session)

    def test_login_cycles_session_key(self):
        self.make_user()
        session = self.client.session
        session["x"] = 1
        session.save()
        old_key = session.session_key
        self.login()
        self.assertNotEqual(self.client.session.session_key, old_key)

    def test_error_does_not_reveal_which_field_is_wrong(self):
        self.make_user()
        wrong_password = self.login(password="yanlis-parola-123")
        unknown_email = self.login(email="yok@example.com")
        for response in (wrong_password, unknown_email):
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "E-posta veya parola hatalı.")
            self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(
            wrong_password.content.decode().count("E-posta veya parola hatalı."),
            unknown_email.content.decode().count("E-posta veya parola hatalı."),
        )

    def test_inactive_user_cannot_login(self):
        user = self.make_user()
        user.is_active = False
        user.save()
        response = self.login()
        self.assertContains(response, "E-posta veya parola hatalı.")

    def test_repeated_failures_for_same_email_return_429(self):
        self.make_user()
        for _ in range(5):
            self.assertEqual(self.login(password="yanlis-parola-123").status_code, 200)
        # Dogru parola bile limit dolunca engellenir.
        response = self.login()
        self.assertEqual(response.status_code, 429)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_repeated_failures_from_same_ip_return_429(self):
        for i in range(10):
            response = self.login(email=f"kimse{i}@example.com", password="yanlis-parola-123")
            self.assertEqual(response.status_code, 200)
        response = self.login(email="baska@example.com", password="yanlis-parola-123")
        self.assertEqual(response.status_code, 429)

    def test_successful_logins_do_not_count_toward_limit(self):
        self.make_user()
        for _ in range(7):
            self.login()
            self.client.post("/cikis/")
        self.assertRedirects(self.login(), "/", fetch_redirect_response=False)

    def test_open_redirect_blocked(self):
        self.make_user()
        for evil in ("https://kotu-site.com", "//kotu-site.com", "https:kotu-site.com", "javascript:alert(1)"):
            with self.subTest(next=evil):
                self.client.post("/cikis/")
                response = self.login(next=evil)
                self.assertRedirects(response, "/", fetch_redirect_response=False)

    def test_safe_next_is_followed(self):
        self.make_user()
        response = self.login(next="/hesap/")
        self.assertRedirects(response, "/hesap/", fetch_redirect_response=False)

    def test_next_in_query_string_is_validated_too(self):
        self.make_user()
        response = self.client.post(
            "/giris/?next=https://kotu-site.com", {"email": "ali@example.com", "password": PASSWORD}
        )
        self.assertRedirects(response, "/", fetch_redirect_response=False)

    def test_login_required_redirects_with_next(self):
        response = self.client.get("/hesap/")
        self.assertRedirects(response, "/giris/?next=/hesap/", fetch_redirect_response=False)

    def test_evil_next_is_not_rendered_into_login_form(self):
        response = self.client.get("/giris/?next=https://kotu-site.com")
        self.assertNotContains(response, "kotu-site.com")

    def test_login_requires_csrf_token(self):
        self.make_user()
        client = Client(enforce_csrf_checks=True)
        response = client.post("/giris/", {"email": "ali@example.com", "password": PASSWORD})
        self.assertEqual(response.status_code, 403)

    def test_password_not_rendered_back_on_failure(self):
        self.make_user()
        response = self.login(password="yanlis-parola-123")
        self.assertNotContains(response, "yanlis-parola-123")


class LogoutTests(AuthTestCase):
    def test_logout_requires_post(self):
        self.client.force_login(self.make_user())
        self.assertEqual(self.client.get("/cikis/").status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)

    def test_logout_post_logs_out(self):
        self.client.force_login(self.make_user())
        response = self.client.post("/cikis/")
        self.assertRedirects(response, "/", fetch_redirect_response=False)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout_requires_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.make_user())
        self.assertEqual(client.post("/cikis/").status_code, 403)


class HeaderAndPrivacyTests(AuthTestCase):
    def test_header_for_anonymous(self):
        response = self.client.get("/")
        self.assertContains(response, "Giriş yap")
        self.assertContains(response, "Kayıt ol")
        self.assertNotContains(response, "Çıkış")

    def test_header_for_member_shows_username_and_logout_form(self):
        self.client.force_login(self.make_user(username="ali"))
        response = self.client.get("/")
        self.assertContains(response, "@ali")
        self.assertContains(response, 'action="/cikis/"')
        self.assertNotContains(response, "Giriş yap")

    def test_email_is_visible_only_on_account_page_to_owner(self):
        user = self.make_user(email="gizli.adres@example.com", username="ali")
        self.client.force_login(user)
        self.assertContains(self.client.get("/hesap/"), "gizli.adres@example.com")
        for path in ("/", "/gizlilik/", "/hesap/parola/", "/hesap/sil/", "/yok-boyle-bir-sayfa/"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertNotContains(response, "gizli.adres@example.com", status_code=response.status_code)

    def test_email_not_visible_to_anonymous_or_other_users(self):
        self.make_user(email="gizli.adres@example.com", username="ali")
        self.assertNotContains(self.client.get("/"), "gizli.adres@example.com")
        self.client.force_login(self.make_user(email="baska@example.com", username="veli"))
        self.assertNotContains(self.client.get("/hesap/"), "gizli.adres@example.com")

    def test_account_page_requires_login(self):
        for path in ("/hesap/", "/hesap/parola/", "/hesap/sil/"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 302)

    def test_privacy_page_discloses_admin_access_vote_link_and_host_logs(self):
        html = self.client.get("/gizlilik/").content.decode()
        self.assertIn("Site yöneticisi, hesapları yönetebilmek için e-posta adresini görebilir", html)
        self.assertIn("veritabanında hesabınla eşleşik tutulur", html)
        self.assertIn("Barındırma hizmeti (Vercel)", html)
        self.assertIn("istek kayıtları (IP adresi dahil)", html)

    def test_privacy_page_is_public_and_explains_data(self):
        response = self.client.get("/gizlilik/")
        self.assertContains(response, "Hangi verileri topluyoruz")
        self.assertContains(response, "IP adresin")
        self.assertContains(response, "Hesabını silmek")
        self.assertContains(self.client.get("/"), "/gizlilik/")


class PasswordChangeTests(AuthTestCase):
    def setUp(self):
        super().setUp()
        self.user = self.make_user()
        self.client.force_login(self.user)

    def change(self, old=PASSWORD, new=NEW_PASSWORD, confirm=None):
        return self.client.post(
            "/hesap/parola/",
            {"old_password": old, "new_password1": new, "new_password2": confirm or new},
        )

    def test_password_change_works_and_keeps_current_session(self):
        response = self.change()
        self.assertRedirects(response, "/hesap/", fetch_redirect_response=False)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(NEW_PASSWORD))
        self.assertTrue(self.user.password.startswith("argon2"))
        self.assertEqual(self.client.get("/hesap/").status_code, 200)

    def test_other_sessions_are_logged_out(self):
        other = Client()
        other.force_login(self.user)
        self.assertEqual(other.get("/hesap/").status_code, 200)
        self.change()
        self.assertEqual(other.get("/hesap/").status_code, 302)

    def test_wrong_old_password_rejected(self):
        response = self.change(old="yanlis-parola-123")
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(PASSWORD))

    def test_short_new_password_rejected(self):
        response = self.change(new="kisa1234")
        self.assertContains(response, "En az 10 karakter")
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(PASSWORD))

    def test_passwords_not_rendered_back(self):
        response = self.change(old="yanlis-parola-123", new="bambaska-bir-parola-9")
        self.assertNotContains(response, "yanlis-parola-123")
        self.assertNotContains(response, "bambaska-bir-parola-9")

    def test_password_change_is_rate_limited(self):
        for _ in range(5):
            self.assertEqual(self.change(old="yanlis-parola-123").status_code, 200)
        self.assertEqual(self.change().status_code, 429)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(PASSWORD))


class DeleteAccountTests(AuthTestCase):
    def setUp(self):
        super().setUp()
        self.user = self.make_user()
        self.client.force_login(self.user)

    def test_get_shows_confirmation_and_does_not_delete(self):
        response = self.client.get("/hesap/sil/")
        self.assertContains(response, "kalıcı olarak")
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_wrong_password_fails(self):
        response = self.client.post("/hesap/sil/", {"password": "yanlis-parola-123"})
        self.assertContains(response, "Parola hatalı.")
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_correct_password_deletes_account_and_logs_out(self):
        response = self.client.post("/hesap/sil/", {"password": PASSWORD}, follow=True)
        self.assertRedirects(response, "/")
        self.assertContains(response, "Hesabın silindi.")
        self.assertFalse(User.objects.filter(pk=self.user.pk).exists())
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_delete_is_rate_limited(self):
        for _ in range(5):
            self.assertEqual(
                self.client.post("/hesap/sil/", {"password": "yanlis-parola-123"}).status_code, 200
            )
        self.assertEqual(self.client.post("/hesap/sil/", {"password": PASSWORD}).status_code, 429)
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_delete_requires_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post("/hesap/sil/", {"password": PASSWORD}).status_code, 403)
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())
