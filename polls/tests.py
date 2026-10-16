import re
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import IntegrityError, connection, transaction
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from .models import Option, Poll

User = get_user_model()

PASSWORD = "mavi-bulut-kahve-42"
XSS = "<script>alert(1)</script>"


def make_poll(author, question="Bugün sinemaya mı gitsem?", options=("Sinema", "Restoran")):
    poll = Poll.objects.create(author=author, question=question)
    Option.objects.bulk_create(
        [Option(poll=poll, text=text, order=i) for i, text in enumerate(options)]
    )
    return poll


class PollTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user("ali@example.com", "ali", PASSWORD)
        self.other = User.objects.create_user("veli@example.com", "veli", PASSWORD)

    def create_data(self, options=("Sinema", "Restoran"), question="Bugün nereye gitsem?", **extra):
        return {"question": question, "option": list(options), **extra}


class ModelTests(PollTestCase):
    def test_options_are_ordered_and_unique_per_poll_order(self):
        poll = make_poll(self.user, options=("A", "B", "C"))
        self.assertEqual([o.text for o in poll.options.all()], ["A", "B", "C"])
        with self.assertRaises(IntegrityError), transaction.atomic():
            Option.objects.create(poll=poll, text="D", order=0)

    def test_deleting_poll_deletes_options(self):
        poll = make_poll(self.user)
        poll.delete()
        self.assertEqual(Option.objects.count(), 0)

    def test_deleting_user_deletes_their_polls(self):
        make_poll(self.user)
        make_poll(self.other)
        self.user.delete()
        self.assertEqual(list(Poll.objects.values_list("author__username", flat=True)), ["veli"])

    def test_default_ordering_is_newest_first(self):
        first = make_poll(self.user, "Birinci soru?")
        second = make_poll(self.user, "İkinci soru?")
        self.assertEqual(list(Poll.objects.all()), [second, first])


class CreatePollTests(PollTestCase):
    def test_anonymous_is_redirected_to_login_and_back_to_form(self):
        response = self.client.get("/anket/yeni/")
        self.assertRedirects(response, "/giris/?next=/anket/yeni/", fetch_redirect_response=False)
        login = self.client.post(
            "/giris/?next=/anket/yeni/", {"email": "ali@example.com", "password": PASSWORD}
        )
        self.assertRedirects(login, "/anket/yeni/", fetch_redirect_response=False)
        self.assertEqual(self.client.get("/anket/yeni/").status_code, 200)

    def test_anonymous_cannot_post(self):
        response = self.client.post("/anket/yeni/", self.create_data())
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Poll.objects.count(), 0)

    def test_valid_poll_is_created_and_redirects_to_detail(self):
        self.client.force_login(self.user)
        response = self.client.post("/anket/yeni/", self.create_data(), follow=True)
        poll = Poll.objects.get()
        self.assertRedirects(response, f"/anket/{poll.pk}/")
        self.assertContains(response, "Anketin yayında!")
        self.assertEqual(poll.author, self.user)
        self.assertEqual([o.text for o in poll.options.all()], ["Sinema", "Restoran"])
        self.assertEqual([o.order for o in poll.options.all()], [0, 1])

    def test_two_and_five_options_accepted(self):
        self.client.force_login(self.user)
        for count in (2, 5):
            with self.subTest(count=count):
                options = [f"Seçenek {i}" for i in range(count)]
                response = self.client.post("/anket/yeni/", self.create_data(options=options))
                self.assertEqual(response.status_code, 302)
                self.assertEqual(Poll.objects.order_by("-pk").first().options.count(), count)

    def test_one_option_rejected(self):
        self.client.force_login(self.user)
        response = self.client.post("/anket/yeni/", self.create_data(options=["Sadece biri", "", ""]))
        self.assertContains(response, "En az 2 seçenek girmelisin.")
        self.assertEqual(Poll.objects.count(), 0)

    def test_six_options_rejected_by_server(self):
        self.client.force_login(self.user)
        options = [f"Seçenek {i}" for i in range(6)]
        response = self.client.post("/anket/yeni/", self.create_data(options=options))
        self.assertContains(response, "En fazla 5 seçenek girebilirsin.")
        self.assertEqual(Poll.objects.count(), 0)

    def test_blank_options_are_ignored_and_gaps_allowed(self):
        self.client.force_login(self.user)
        self.client.post("/anket/yeni/", self.create_data(options=["A", "", "B", "  ", "C"]))
        poll = Poll.objects.get()
        self.assertEqual([(o.order, o.text) for o in poll.options.all()], [(0, "A"), (1, "B"), (2, "C")])

    def test_duplicate_options_rejected_case_and_space_insensitive(self):
        self.client.force_login(self.user)
        response = self.client.post("/anket/yeni/", self.create_data(options=["Sinema", "  sinema ", "x"]))
        self.assertContains(response, "Bu seçenek zaten var.")
        self.assertEqual(Poll.objects.count(), 0)

    def test_option_too_long_rejected(self):
        self.client.force_login(self.user)
        response = self.client.post("/anket/yeni/", self.create_data(options=["a" * 81, "b"]))
        self.assertContains(response, "Seçenek en fazla 80 karakter olabilir.")
        self.assertEqual(Poll.objects.count(), 0)

    def test_short_or_long_question_rejected(self):
        self.client.force_login(self.user)
        short = self.client.post("/anket/yeni/", self.create_data(question="  abc  "))
        self.assertContains(short, "Soru en az 5 karakter olmalı.")
        long = self.client.post("/anket/yeni/", self.create_data(question="a" * 201))
        self.assertEqual(long.status_code, 200)
        self.assertEqual(Poll.objects.count(), 0)

    def test_question_is_trimmed_and_whitespace_collapsed(self):
        self.client.force_login(self.user)
        self.client.post("/anket/yeni/", self.create_data(question="  Bugün   nereye\tgitsem?  "))
        self.assertEqual(Poll.objects.get().question, "Bugün nereye gitsem?")

    def test_author_comes_from_session_not_request(self):
        self.client.force_login(self.user)
        data = self.create_data(author=self.other.pk, author_id=self.other.pk)
        self.client.post("/anket/yeni/", data)
        self.assertEqual(Poll.objects.get().author, self.user)

    def test_failed_poll_creation_leaves_nothing_behind(self):
        self.client.force_login(self.user)
        self.client.post("/anket/yeni/", self.create_data(options=["A", "A"]))
        self.assertEqual(Poll.objects.count(), 0)
        self.assertEqual(Option.objects.count(), 0)

    def test_form_keeps_entered_values_on_error(self):
        self.client.force_login(self.user)
        response = self.client.post("/anket/yeni/", self.create_data(options=["Sinema", ""], question="Uzun bir soru?"))
        self.assertContains(response, 'value="Sinema"')
        self.assertContains(response, 'value="Uzun bir soru?"')

    def test_form_renders_five_option_fields_with_first_two_required(self):
        self.client.force_login(self.user)
        html = self.client.get("/anket/yeni/").content.decode()
        self.assertEqual(html.count('name="option"'), 5)
        self.assertEqual(html.count('name="option" id="id_option_1"'), 1)
        self.assertIn('id="id_option_1" value="" maxlength="80" autocomplete="off" required', html)
        self.assertIn('id="id_option_2" value="" maxlength="80" autocomplete="off" required', html)
        self.assertNotIn('id="id_option_3" value="" maxlength="80" autocomplete="off" required', html)

    def test_create_requires_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        response = client.post("/anket/yeni/", self.create_data())
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Poll.objects.count(), 0)

    def test_poll_creation_is_rate_limited_per_user(self):
        self.client.force_login(self.user)
        for i in range(10):
            response = self.client.post("/anket/yeni/", self.create_data(question=f"Soru numarası {i}?"))
            self.assertEqual(response.status_code, 302)
        response = self.client.post("/anket/yeni/", self.create_data())
        self.assertEqual(response.status_code, 429)
        self.assertEqual(Poll.objects.count(), 10)
        # Baska kullanicinin limiti ayri.
        other_client = Client()
        other_client.force_login(self.other)
        self.assertEqual(other_client.post("/anket/yeni/", self.create_data()).status_code, 302)

    def test_failed_attempts_do_not_consume_the_limit(self):
        self.client.force_login(self.user)
        for _ in range(12):
            self.client.post("/anket/yeni/", self.create_data(options=["tek"]))
        self.assertEqual(self.client.post("/anket/yeni/", self.create_data()).status_code, 302)


class FeedTests(PollTestCase):
    def test_empty_state(self):
        response = self.client.get("/")
        self.assertContains(response, "Henüz kimse kararsız değil.")

    def test_newest_first_with_author_and_relative_time(self):
        old = make_poll(self.user, "Eski soru burada?")
        Poll.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(hours=2))
        make_poll(self.other, "Yeni soru burada?")
        response = self.client.get("/")
        content = response.content.decode()
        self.assertLess(content.index("Yeni soru burada?"), content.index("Eski soru burada?"))
        self.assertContains(response, "@veli")
        self.assertContains(response, "@ali")
        self.assertContains(response, "2 saat önce")

    def test_page_size_is_twenty(self):
        for i in range(25):
            make_poll(self.user, f"Soru numarası {i:02d}?")
        first = self.client.get("/")
        self.assertEqual(len(first.context["page"].object_list), 20)
        second = self.client.get("/?page=2")
        self.assertEqual(len(second.context["page"].object_list), 5)
        self.assertContains(first, "Sonraki")
        self.assertContains(second, "Önceki")

    def test_invalid_page_numbers_fall_back_without_error(self):
        for i in range(25):
            make_poll(self.user, f"Soru numarası {i:02d}?")
        for value in ("abc", "0", "-1", "", "1.5", "99999"):
            with self.subTest(page=value):
                response = self.client.get("/", {"page": value})
                self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get("/?page=99999").context["page"].number, 2)
        self.assertEqual(self.client.get("/?page=abc").context["page"].number, 1)

    def _query_count(self, path):
        self.client.get(path)  # isinma
        with CaptureQueriesContext(connection) as ctx:
            self.client.get(path)
        return len(ctx)

    def test_query_count_does_not_depend_on_number_of_polls(self):
        make_poll(self.user, "Tek anket burada?", options=("A", "B"))
        few = self._query_count("/")
        for i in range(19):
            make_poll(self.other, f"Başka soru {i:02d}?", options=("A", "B", "C", "D", "E"))
        many = self._query_count("/")
        self.assertEqual(few, many)

    def test_query_count_is_constant_for_logged_in_user_too(self):
        self.client.force_login(self.user)
        make_poll(self.user, "Tek anket burada?")
        few = self._query_count("/")
        for i in range(19):
            make_poll(self.other, f"Başka soru {i:02d}?")
        self.assertEqual(few, self._query_count("/"))

    def test_xss_in_question_and_options_is_escaped(self):
        make_poll(self.user, f"{XSS} soru", options=(XSS, "<b>kalın</b>"))
        for path in ("/", "/anket/%d/" % Poll.objects.get().pk):
            with self.subTest(path=path):
                html = self.client.get(path).content.decode()
                self.assertNotIn(XSS, html)
                self.assertNotIn("<b>kalın</b>", html)
                self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)

    def test_no_email_addresses_in_feed_or_detail(self):
        poll = make_poll(self.user)
        for path in ("/", f"/anket/{poll.pk}/"):
            html = self.client.get(path).content.decode()
            self.assertNotIn("ali@example.com", html)
            self.assertNotIn("veli@example.com", html)

    def test_feed_shows_create_button_to_everyone(self):
        self.assertContains(self.client.get("/"), "/anket/yeni/")


class DetailTests(PollTestCase):
    def test_detail_shows_question_author_and_options_in_order(self):
        poll = make_poll(self.user, "Hangisi daha iyi?", options=("Çay", "Kahve", "Su"))
        response = self.client.get(f"/anket/{poll.pk}/")
        self.assertContains(response, "Hangisi daha iyi?")
        self.assertContains(response, "@ali")
        # Rastgele CSRF token'indaki metinlerle karismasin diye yalnizca secenek butonlarina bakilir.
        texts = re.findall(r'option--button"[^>]*>([^<]*)<', response.content.decode())
        self.assertEqual(texts, ["Çay", "Kahve", "Su"])

    def test_missing_poll_is_themed_404(self):
        response = self.client.get("/anket/99999/")
        self.assertContains(response, "Aradığın sayfayı bulamadık.", status_code=404)

    def test_delete_button_only_for_owner(self):
        poll = make_poll(self.user)
        self.assertNotContains(self.client.get(f"/anket/{poll.pk}/"), "Anketi sil")
        self.client.force_login(self.other)
        self.assertNotContains(self.client.get(f"/anket/{poll.pk}/"), "Anketi sil")
        self.client.force_login(self.user)
        self.assertContains(self.client.get(f"/anket/{poll.pk}/"), "Anketi sil")


class DeletePollTests(PollTestCase):
    def test_owner_sees_confirmation_and_get_does_not_delete(self):
        poll = make_poll(self.user)
        self.client.force_login(self.user)
        response = self.client.get(f"/anket/{poll.pk}/sil/")
        self.assertContains(response, "kalıcı olarak")
        self.assertTrue(Poll.objects.filter(pk=poll.pk).exists())

    def test_owner_can_delete(self):
        poll = make_poll(self.user)
        self.client.force_login(self.user)
        response = self.client.post(f"/anket/{poll.pk}/sil/", follow=True)
        self.assertRedirects(response, "/")
        self.assertContains(response, "Anketin silindi.")
        self.assertFalse(Poll.objects.filter(pk=poll.pk).exists())
        self.assertEqual(Option.objects.count(), 0)

    def test_other_user_gets_404_and_poll_survives(self):
        poll = make_poll(self.user)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(f"/anket/{poll.pk}/sil/").status_code, 404)
        self.assertEqual(self.client.post(f"/anket/{poll.pk}/sil/").status_code, 404)
        self.assertTrue(Poll.objects.filter(pk=poll.pk).exists())

    def test_404_for_other_user_matches_404_for_missing_poll(self):
        poll = make_poll(self.user)
        self.client.force_login(self.other)
        existing = self.client.get(f"/anket/{poll.pk}/sil/")
        missing = self.client.get("/anket/99999/sil/")
        self.assertEqual(existing.status_code, missing.status_code)
        self.assertNotContains(existing, poll.question, status_code=404)

    def test_anonymous_is_sent_to_login_and_poll_survives(self):
        poll = make_poll(self.user)
        response = self.client.post(f"/anket/{poll.pk}/sil/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/giris/", response["Location"])
        self.assertTrue(Poll.objects.filter(pk=poll.pk).exists())

    def test_delete_requires_csrf_token(self):
        poll = make_poll(self.user)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(f"/anket/{poll.pk}/sil/").status_code, 403)
        self.assertTrue(Poll.objects.filter(pk=poll.pk).exists())


class AccountDeletionTests(PollTestCase):
    def test_account_deletion_removes_users_polls(self):
        make_poll(self.user)
        make_poll(self.other, "Veli'nin sorusu?")
        self.client.force_login(self.user)
        self.client.post("/hesap/sil/", {"password": PASSWORD})
        self.assertEqual([p.question for p in Poll.objects.all()], ["Veli'nin sorusu?"])


class HeaderTests(PollTestCase):
    def test_create_link_in_header_for_members_only(self):
        header = lambda html: html.split("</header>")[0]
        self.assertNotIn("Anket aç", header(self.client.get("/").content.decode()))
        self.client.force_login(self.user)
        self.assertIn("Anket aç", header(self.client.get("/").content.decode()))

    def test_option_script_is_external_and_no_inline_code(self):
        self.client.force_login(self.user)
        html = self.client.get("/anket/yeni/").content.decode()
        self.assertIn('src="/static/js/main.js"', html)
        self.assertNotIn("<script>", html)
        self.assertNotIn("style=", html)
        self.assertNotIn("onclick=", html)


class AdminTests(PollTestCase):
    def test_admin_changelist_and_add_page_work(self):
        from django.conf import settings

        admin_user = User.objects.create_superuser("root@example.com", "root", PASSWORD)
        make_poll(self.user)
        self.client.force_login(admin_user)
        base = "/" + settings.ADMIN_URL + "polls/poll/"
        self.assertEqual(self.client.get(base).status_code, 200)
        self.assertEqual(self.client.get(base + "add/").status_code, 200)
