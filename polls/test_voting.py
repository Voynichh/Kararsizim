from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import IntegrityError, connection, transaction
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext

from .models import Option, Poll, Vote
from .utils import COOKIE_NAME, COOKIE_SALT, distribute_percentages, percent_of

User = get_user_model()

PASSWORD = "mavi-bulut-kahve-42"
JSON = {"HTTP_ACCEPT": "application/json"}


def make_poll(author, question="Bugün sinemaya mı gitsem?", options=("Sinema", "Restoran")):
    poll = Poll.objects.create(author=author, question=question)
    Option.objects.bulk_create(
        [Option(poll=poll, text=text, order=i) for i, text in enumerate(options)]
    )
    return poll


class VoteTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.author = User.objects.create_user("yazar@example.com", "yazar", PASSWORD)
        self.member = User.objects.create_user("uye@example.com", "uye", PASSWORD)
        self.poll = make_poll(self.author)
        self.sinema, self.restoran = list(self.poll.options.all())

    def vote(self, option, client=None, poll=None, **extra):
        client = client or self.client
        poll = poll or self.poll
        option_id = option.pk if hasattr(option, "pk") else option
        return client.post(f"/anket/{poll.pk}/oy/", {"option": option_id}, **extra)

    def member_client(self, user=None):
        client = Client()
        client.force_login(user or self.member)
        return client


class AnonymousVoteTests(VoteTestCase):
    def test_anonymous_vote_is_saved_and_cookie_is_set(self):
        response = self.vote(self.sinema)
        self.assertRedirects(response, f"/anket/{self.poll.pk}/", fetch_redirect_response=False)
        vote = Vote.objects.get()
        self.assertEqual(vote.option, self.sinema)
        self.assertIsNone(vote.user)
        self.assertTrue(vote.voter_key.startswith("a:"))
        self.assertIn(COOKIE_NAME, response.cookies)

    def test_cookie_is_signed_httponly_samesite_lax_and_one_year(self):
        cookie = self.vote(self.sinema).cookies[COOKIE_NAME]
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["samesite"], "Lax")
        self.assertEqual(int(cookie["max-age"]), 60 * 60 * 24 * 365)
        self.assertEqual(bool(cookie["secure"]), not settings.DEBUG)
        # Imzali: "<uuid>:<zaman damgasi>:<imza>" bicimi, duz UUID degil.
        self.assertGreaterEqual(cookie.value.count(":"), 2)

    def test_second_vote_with_same_cookie_does_not_create_vote(self):
        self.vote(self.sinema)
        response = self.vote(self.restoran, follow=True)
        self.assertEqual(Vote.objects.count(), 1)
        self.assertEqual(Vote.objects.get().option, self.sinema)
        self.assertContains(response, "Bu ankete zaten oy verdin.")

    def test_results_are_visible_after_voting_and_on_reload(self):
        self.vote(self.sinema)
        for _ in range(2):
            response = self.client.get(f"/anket/{self.poll.pk}/")
            self.assertContains(response, "%100 · 1 oy")
            self.assertContains(response, "✓ senin oyun")
            self.assertNotContains(response, "option--button")

    def test_new_browser_without_cookie_can_vote_again_known_limitation(self):
        # Bilinen prototip siniri (dokuman Bolum 7): cerezsiz yeni tarayici yeni kimlik alir.
        self.vote(self.sinema)
        self.vote(self.sinema, client=Client())
        self.assertEqual(Vote.objects.count(), 2)

    def test_forged_cookie_does_not_crash_and_is_ignored(self):
        for value in ("a:123", "not-a-signed-value", "x" * 500, "", "a:00000000-0000-0000-0000-000000000000"):
            with self.subTest(cookie=value[:20]):
                client = Client()
                client.cookies[COOKIE_NAME] = value
                response = self.vote(self.sinema, client=client)
                self.assertEqual(response.status_code, 302)
                self.assertEqual(client.get("/").status_code, 200)
        self.assertEqual(Vote.objects.count(), 5)
        self.assertEqual(len(set(Vote.objects.values_list("voter_key", flat=True))), 5)

    def test_tampered_signature_is_ignored(self):
        first = Client()
        cookie = self.vote(self.sinema, client=first).cookies[COOKIE_NAME].value
        client = Client()
        client.cookies[COOKIE_NAME] = cookie[:-3] + ("AAA" if not cookie.endswith("AAA") else "BBB")
        self.vote(self.sinema, client=client)
        self.assertEqual(Vote.objects.count(), 2)

    def test_cookie_signed_with_other_salt_is_rejected(self):
        from django.core.signing import get_cookie_signer

        signer = get_cookie_signer(salt="baska.tuz")
        client = Client()
        client.cookies[COOKIE_NAME] = signer.sign("5f1f1b0e-2f55-4b0e-9d63-0a8f3a0f3c11")
        self.assertIsNone(client.get("/").context["polls"][0].voted_option_id)

    def test_cookie_with_signed_non_uuid_value_is_ignored(self):
        from django.core.signing import get_cookie_signer

        signer = get_cookie_signer(salt=COOKIE_SALT)
        client = Client()
        client.cookies[COOKIE_NAME] = signer.sign("u:1")
        self.assertEqual(self.vote(self.sinema, client=client).status_code, 302)
        self.assertTrue(Vote.objects.get().voter_key.startswith("a:"))


class MemberVoteTests(VoteTestCase):
    def test_member_votes_once(self):
        client = self.member_client()
        self.vote(self.sinema, client=client)
        self.vote(self.restoran, client=client)
        vote = Vote.objects.get()
        self.assertEqual(vote.option, self.sinema)
        self.assertEqual(vote.user, self.member)
        self.assertEqual(vote.voter_key, f"u:{self.member.pk}")

    def test_member_does_not_get_anonymous_cookie(self):
        response = self.vote(self.sinema, client=self.member_client())
        self.assertNotIn(COOKIE_NAME, response.cookies)

    def test_owner_cannot_vote_on_own_poll(self):
        client = self.member_client(self.author)
        response = self.vote(self.sinema, client=client)
        self.assertEqual(Vote.objects.count(), 0)
        self.assertEqual(response.status_code, 302)
        json_response = self.vote(self.sinema, client=client, **JSON)
        self.assertEqual(json_response.status_code, 403)
        self.assertFalse(json_response.json()["ok"])

    def test_owner_sees_results_without_voting_and_no_buttons(self):
        self.vote(self.sinema, client=self.member_client())
        response = self.member_client(self.author).get(f"/anket/{self.poll.pk}/")
        self.assertContains(response, "%100 · 1 oy")
        self.assertContains(response, "Bu senin anketin")
        self.assertNotContains(response, "option--button")
        self.assertNotContains(response, "✓ senin oyun")

    def test_race_on_unique_constraint_yields_single_vote(self):
        # Eszamanli iki istek ayni anda ekleme yaparsa ikincisi IntegrityError alir;
        # view bunu "zaten oy verdi" olarak ele alir (on kontrol yok, kisit belirler).
        client = self.member_client()
        first = self.vote(self.sinema, client=client, **JSON)
        second = self.vote(self.restoran, client=client, **JSON)
        self.assertFalse(first.json()["already_voted"])
        self.assertTrue(second.json()["already_voted"])
        self.assertEqual(second.json()["selected_option_id"], self.sinema.pk)
        self.assertEqual(Vote.objects.count(), 1)

    def test_database_rejects_duplicate_poll_voter_key(self):
        Vote.objects.create(poll=self.poll, option=self.sinema, voter_key="a:x")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Vote.objects.create(poll=self.poll, option=self.restoran, voter_key="a:x")
        other_poll = make_poll(self.author, "Başka bir anket?")
        Vote.objects.create(poll=other_poll, option=other_poll.options.first(), voter_key="a:x")


class InvalidVoteTests(VoteTestCase):
    def test_get_is_rejected(self):
        self.assertEqual(self.client.get(f"/anket/{self.poll.pk}/oy/").status_code, 405)
        self.assertEqual(Vote.objects.count(), 0)

    def test_option_from_another_poll_is_rejected(self):
        other = make_poll(self.author, "Başka bir anket?", options=("X", "Y"))
        response = self.vote(other.options.first())
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.vote(other.options.first(), **JSON).status_code, 400)
        self.assertEqual(Vote.objects.count(), 0)

    def test_malformed_option_values_are_rejected(self):
        for bad in ("abc", "", "1.5", "-1", "1e3", " 1", "99999999999999999999999", "0"):
            with self.subTest(option=bad):
                self.assertEqual(self.vote(bad).status_code, 400)
        self.assertEqual(self.client.post(f"/anket/{self.poll.pk}/oy/", {}).status_code, 400)
        self.assertEqual(Vote.objects.count(), 0)

    def test_unknown_poll_is_404(self):
        self.assertEqual(self.client.post("/anket/99999/oy/", {"option": 1}).status_code, 404)

    def test_vote_requires_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post(f"/anket/{self.poll.pk}/oy/", {"option": self.sinema.pk})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Vote.objects.count(), 0)

    def test_vote_is_rate_limited_per_ip(self):
        for _ in range(30):
            self.assertEqual(self.vote(self.sinema).status_code, 302)
        response = self.vote(self.sinema)
        self.assertEqual(response.status_code, 429)
        json_response = self.vote(self.sinema, **JSON)
        self.assertEqual(json_response.status_code, 429)
        self.assertFalse(json_response.json()["ok"])


class RedirectTests(VoteTestCase):
    def test_safe_next_is_followed_with_fragment(self):
        url = f"/anket/{self.poll.pk}/oy/"
        response = self.client.post(url, {"option": self.sinema.pk, "next": "/?page=2#poll-1"})
        self.assertRedirects(response, "/?page=2#poll-1", fetch_redirect_response=False)

    def test_external_next_is_ignored(self):
        for evil in ("https://kotu-site.com", "//kotu-site.com", "javascript:alert(1)"):
            with self.subTest(next=evil):
                client = Client()
                response = client.post(
                    f"/anket/{self.poll.pk}/oy/", {"option": self.sinema.pk, "next": evil}
                )
                self.assertRedirects(
                    response, f"/anket/{self.poll.pk}/", fetch_redirect_response=False
                )


class JsonResponseTests(VoteTestCase):
    def test_json_shape_and_values(self):
        response = self.vote(self.sinema, **JSON)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")
        data = response.json()
        self.assertEqual(set(data), {"ok", "already_voted", "selected_option_id", "total_votes", "options"})
        self.assertEqual(
            data,
            {
                "ok": True,
                "already_voted": False,
                "selected_option_id": self.sinema.pk,
                "total_votes": 1,
                "options": [
                    {"id": self.sinema.pk, "text": "Sinema", "votes": 1, "percent": 100},
                    {"id": self.restoran.pk, "text": "Restoran", "votes": 0, "percent": 0},
                ],
            },
        )
        for option in data["options"]:
            self.assertEqual(set(option), {"id", "text", "votes", "percent"})

    def test_json_contains_no_user_info_email_or_voter_key(self):
        response = self.vote(self.sinema, client=self.member_client(), **JSON)
        body = response.content.decode().lower()
        for forbidden in ("voter", "uye@example.com", "yazar@example.com", "email", "username", '"user'):
            self.assertNotIn(forbidden, body)
        self.assertNotIn(f"u:{self.member.pk}", body)

    def test_percentages_round_to_integers(self):
        self.vote(self.sinema)
        self.vote(self.sinema, client=Client())
        data = self.vote(self.restoran, client=Client(), **JSON).json()
        self.assertEqual(data["total_votes"], 3)
        self.assertEqual([o["percent"] for o in data["options"]], [67, 33])
        self.assertEqual([o["votes"] for o in data["options"]], [2, 1])

    def test_percent_helper_handles_zero_total(self):
        self.assertEqual(percent_of(0, 0), 0)
        self.assertEqual(percent_of(1, 2), 50)
        self.assertEqual(percent_of(1, 3), 33)
        self.assertEqual(percent_of(2, 3), 67)
        self.assertEqual(percent_of(1, 8), 13)  # 12.5 -> yari yukari

    def test_already_voted_response(self):
        client = Client()
        self.vote(self.sinema, client=client)
        data = self.vote(self.restoran, client=client, **JSON).json()
        self.assertTrue(data["ok"])
        self.assertTrue(data["already_voted"])
        self.assertEqual(data["selected_option_id"], self.sinema.pk)
        self.assertEqual(data["total_votes"], 1)

    def test_no_cookie_set_when_already_voted_with_existing_identity(self):
        client = Client()
        self.vote(self.sinema, client=client)
        response = self.vote(self.restoran, client=client, **JSON)
        self.assertNotIn(COOKIE_NAME, response.cookies)


class VisibilityTests(VoteTestCase):
    def test_results_hidden_from_people_who_have_not_voted(self):
        self.vote(self.sinema, client=Client())
        self.vote(self.restoran, client=Client())
        for path in ("/", f"/anket/{self.poll.pk}/"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertNotContains(response, "data-percent")
                self.assertNotContains(response, "result__stat")
                self.assertNotContains(response, "✓ senin oyun")
                self.assertContains(response, "option--button")
                self.assertContains(response, "2 oy")  # toplam sayi gorunur, dagilim degil

    def test_own_choice_is_marked_only_for_the_voter(self):
        a, b = self.member_client(), self.member_client(self.author)
        c = Client()
        self.vote(self.sinema, client=a)
        self.vote(self.restoran, client=c)
        html_a = a.get(f"/anket/{self.poll.pk}/").content.decode()
        html_c = c.get(f"/anket/{self.poll.pk}/").content.decode()
        for html, mine in ((html_a, "Sinema"), (html_c, "Restoran")):
            self.assertEqual(html.count("✓ senin oyun"), 1)
            marked = html.split("✓ senin oyun")[0].rsplit("result__label", 1)[1]
            self.assertIn(mine, marked)
        html_owner = b.get(f"/anket/{self.poll.pk}/").content.decode()
        self.assertNotIn("✓ senin oyun", html_owner)

    def test_top_option_is_marked(self):
        self.vote(self.sinema, client=Client())
        self.vote(self.sinema, client=Client())
        self.vote(self.restoran, client=Client())
        html = self.member_client(self.author).get("/").content.decode()
        self.assertEqual(html.count("result--top"), 1)

    def test_pages_never_expose_voter_identity_or_email(self):
        self.vote(self.sinema, client=self.member_client())
        self.vote(self.sinema, client=Client())
        owner = self.member_client(self.author)
        for client in (self.client, owner, self.member_client()):
            for path in ("/", f"/anket/{self.poll.pk}/", "/hesap/"):
                body = client.get(path).content.decode()
                self.assertNotIn("voter", body.lower())
                self.assertNotIn(f"u:{self.member.pk}", body)
                if path != "/hesap/":
                    self.assertNotIn("uye@example.com", body)
                    self.assertNotIn("yazar@example.com", body)

    def test_vote_form_posts_back_to_current_page_with_csrf(self):
        html = self.client.get("/?page=1").content.decode()
        self.assertIn(f'action="/anket/{self.poll.pk}/oy/"', html)
        self.assertIn("csrfmiddlewaretoken", html)
        self.assertIn(f'name="next" value="/?page=1#poll-{self.poll.pk}"', html)

    def test_xss_in_option_is_escaped_in_results_and_buttons(self):
        xss = "<script>alert(1)</script>"
        poll = make_poll(self.author, "XSS denemesi burada?", options=(xss, "güvenli"))
        buttons = self.client.get(f"/anket/{poll.pk}/").content.decode()
        self.assertNotIn(xss, buttons)
        self.assertIn("&lt;script&gt;", buttons)
        self.vote(poll.options.first(), poll=poll)
        results = self.client.get(f"/anket/{poll.pk}/").content.decode()
        self.assertNotIn(xss, results)
        self.assertIn("&lt;script&gt;", results)
        data = self.vote(poll.options.first(), poll=poll, **JSON).json()
        self.assertEqual(data["options"][0]["text"], xss)  # JSON'da ham metin, DOM'a textContent ile yazilir


class QueryCountTests(VoteTestCase):
    def _count(self, client, path="/"):
        client.get(path)
        with CaptureQueriesContext(connection) as ctx:
            client.get(path)
        return len(ctx)

    def _populate(self, voters):
        for i in range(19):
            poll = make_poll(self.author, f"Başka soru {i:02d}?", options=("A", "B", "C", "D", "E"))
            for client in voters:
                client.post(f"/anket/{poll.pk}/oy/", {"option": poll.options.first().pk})

    def test_feed_query_count_is_constant_for_anonymous_with_cookie(self):
        voter = Client()
        self.vote(self.sinema, client=voter)
        few = self._count(voter)
        self._populate([voter, Client()])
        self.assertEqual(few, self._count(voter))

    def test_feed_query_count_is_constant_for_member(self):
        member = self.member_client()
        self.vote(self.sinema, client=member)
        few = self._count(member)
        self._populate([member, Client()])
        self.assertEqual(few, self._count(member))

    def test_feed_query_count_is_constant_without_identity(self):
        few = self._count(self.client)
        self._populate([Client()])
        self.assertEqual(few, self._count(self.client))

    def test_totals_in_feed_are_correct_per_poll(self):
        self.vote(self.sinema, client=Client())
        self.vote(self.restoran, client=Client())
        other = make_poll(self.author, "İkinci anket burada?")
        self.vote(other.options.first(), poll=other, client=Client())
        polls = {p.pk: p for p in self.client.get("/").context["polls"]}
        self.assertEqual(polls[self.poll.pk].total_votes, 2)
        self.assertEqual(polls[other.pk].total_votes, 1)


class LiveResultsTests(VoteTestCase):
    """GET /anket/sonuclar/: canli guncelleme ucu; gorunurluk kurali sayfalarla aynidir."""

    def live(self, client=None, ids=None, **extra):
        client = client or self.client
        ids = ids if ids is not None else str(self.poll.pk)
        return client.get(f"/anket/sonuclar/?ids={ids}", **extra)

    def item(self, response):
        (item,) = response.json()["polls"]
        return item

    def test_visitor_who_has_not_voted_gets_only_total_votes(self):
        self.vote(self.sinema, client=Client())
        item = self.item(self.live())
        self.assertEqual(item, {"id": self.poll.pk, "total_votes": 1})

    def test_voter_gets_live_option_counts(self):
        voter = Client()
        self.vote(self.sinema, client=voter)
        self.vote(self.restoran, client=Client())
        self.vote(self.restoran, client=Client())
        item = self.item(self.live(client=voter))
        self.assertEqual(item["total_votes"], 3)
        counts = {o["id"]: (o["votes"], o["percent"]) for o in item["options"]}
        self.assertEqual(counts, {self.sinema.pk: (1, 33), self.restoran.pk: (2, 67)})

    def test_owner_gets_options_without_voting(self):
        self.vote(self.sinema, client=Client())
        item = self.item(self.live(client=self.member_client(self.author)))
        self.assertEqual(item["total_votes"], 1)
        self.assertEqual(len(item["options"]), 2)

    def test_counts_change_between_requests(self):
        voter = Client()
        self.vote(self.sinema, client=voter)
        self.assertEqual(self.item(self.live(client=voter))["total_votes"], 1)
        self.vote(self.restoran, client=Client())
        self.assertEqual(self.item(self.live(client=voter))["total_votes"], 2)

    def test_response_has_no_identity_and_is_not_cacheable(self):
        self.vote(self.sinema, client=self.member_client())
        response = self.live(client=self.member_client())
        body = response.content.decode()
        for forbidden in ("uye@example.com", "yazar@example.com", "voter_key", "u:", "a:", "username"):
            self.assertNotIn(forbidden, body)
        self.assertIn("no-store", response["Cache-Control"])

    def test_invalid_and_extra_ids_are_ignored(self):
        other = make_poll(self.author, "İkinci anket burada?")
        response = self.live(ids=f"abc,-1,{other.pk},1e3,,{self.poll.pk}")
        ids = sorted(item["id"] for item in response.json()["polls"])
        self.assertEqual(ids, sorted([self.poll.pk, other.pk]))
        self.assertEqual(self.live(ids="").json(), {"ok": True, "polls": [], "new_ids": []})

    def test_at_most_twenty_ids_are_read(self):
        polls = [make_poll(self.author, f"Soru numarası {i} burada?") for i in range(25)]
        response = self.live(ids=",".join(str(p.pk) for p in polls))
        self.assertEqual(len(response.json()["polls"]), 20)

    def test_query_count_does_not_depend_on_poll_count(self):
        def count(ids):
            with CaptureQueriesContext(connection) as ctx:
                self.live(ids=ids)
            return len(ctx)

        one = count(str(self.poll.pk))
        polls = [make_poll(self.author, f"Soru numarası {i} burada?") for i in range(10)]
        many = count(",".join(str(p.pk) for p in polls))
        self.assertEqual(one, many)

    def test_post_is_not_allowed(self):
        self.assertEqual(self.client.post("/anket/sonuclar/").status_code, 405)

    def test_cards_carry_data_attributes_for_live_updates(self):
        voter = Client()
        self.vote(self.sinema, client=voter)
        html = voter.get("/").content.decode()
        self.assertIn(f'data-poll-id="{self.poll.pk}"', html)
        self.assertIn('data-live-url="/anket/sonuclar/"', html)
        self.assertIn(f'data-option-id="{self.sinema.pk}"', html)


class FeedLiveUpdateTests(VoteTestCase):
    """Yeni acilan / silinen anketlerin F5'siz yansimasi icin sunucu tarafi."""

    def live(self, query, client=None):
        return (client or self.client).get(f"/anket/sonuclar/?{query}")

    def test_new_ids_lists_polls_newer_than_after(self):
        newer = [make_poll(self.author, f"Yeni soru numarası {i} burada?") for i in range(3)]
        data = self.live(f"ids={self.poll.pk}&after={self.poll.pk}").json()
        self.assertEqual(data["new_ids"], [p.pk for p in reversed(newer)])  # en yeni once

    def test_new_ids_is_empty_when_nothing_is_newer_or_after_missing_or_invalid(self):
        self.assertEqual(self.live(f"ids={self.poll.pk}&after={self.poll.pk}").json()["new_ids"], [])
        self.assertEqual(self.live(f"ids={self.poll.pk}").json()["new_ids"], [])
        self.assertEqual(self.live("ids=&after=abc").json()["new_ids"], [])
        self.assertEqual(self.live("ids=&after=-1").json()["new_ids"], [])

    def test_new_ids_is_capped_at_twenty(self):
        for i in range(25):
            make_poll(self.author, f"Kalabalık soru {i} burada?")
        self.assertEqual(len(self.live("ids=&after=0").json()["new_ids"]), 20)

    def test_deleted_poll_is_missing_from_response(self):
        other = make_poll(self.author, "Silinecek anket burada?")
        other.delete()
        data = self.live(f"ids={self.poll.pk},{other.pk}").json()
        self.assertEqual([p["id"] for p in data["polls"]], [self.poll.pk])

    def test_cards_returns_html_fragment_with_escaped_text(self):
        evil = make_poll(self.author, "<script>alert(1)</script> soru metni")
        response = self.client.get(f"/anket/kartlar/?ids={evil.pk}")
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn(f'data-poll-id="{evil.pk}"', html)
        self.assertNotIn("<html", html)
        self.assertIn("no-store", response["Cache-Control"])

    def test_cards_next_field_points_to_feed_not_to_fragment(self):
        html = self.client.get(f"/anket/kartlar/?ids={self.poll.pk}").content.decode()
        self.assertIn(f'name="next" value="/#poll-{self.poll.pk}"', html)
        self.assertNotIn("kartlar", html)

    def test_cards_respect_result_visibility(self):
        voter = Client()
        self.vote(self.sinema, client=voter)
        voted_html = voter.get(f"/anket/kartlar/?ids={self.poll.pk}").content.decode()
        self.assertIn("data-results", voted_html)
        self.assertIn("✓ senin oyun", voted_html)
        stranger_html = Client().get(f"/anket/kartlar/?ids={self.poll.pk}").content.decode()
        self.assertNotIn("data-results", stranger_html)
        self.assertIn("data-vote-form", stranger_html)

    def test_cards_has_no_identity_and_ignores_bad_ids(self):
        html = self.client.get(f"/anket/kartlar/?ids=abc,{self.poll.pk},-5").content.decode()
        self.assertEqual(html.count('class="card poll-card"'), 1)
        for forbidden in ("yazar@example.com", "uye@example.com", "voter_key"):
            self.assertNotIn(forbidden, html)

    def test_cards_empty_ids_returns_empty_body(self):
        self.assertEqual(self.client.get("/anket/kartlar/?ids=").content.strip(), b"")

    def test_cards_post_not_allowed(self):
        self.assertEqual(self.client.post("/anket/kartlar/").status_code, 405)

    def test_feed_first_page_is_live_and_later_pages_are_not(self):
        for i in range(25):
            make_poll(self.author, f"Sayfalama sorusu {i} burada?")
        first = self.client.get("/").content.decode()
        self.assertIn("data-feed-live", first)
        self.assertIn('data-cards-url="/anket/kartlar/"', first)
        second = self.client.get("/?page=2").content.decode()
        self.assertNotIn("data-feed-live", second)

    def test_empty_feed_still_has_live_container_and_empty_state(self):
        Poll.objects.all().delete()
        html = self.client.get("/").content.decode()
        self.assertIn("data-feed-live", html)
        self.assertIn("data-empty-state", html)
        self.assertIn("Henüz kimse kararsız değil.", html)


class PercentageDistributionTests(VoteTestCase):
    def test_known_cases_always_sum_to_100(self):
        self.assertEqual(distribute_percentages([1, 1, 1]), [34, 33, 33])
        self.assertEqual(distribute_percentages([2, 1]), [67, 33])
        self.assertEqual(distribute_percentages([1, 1]), [50, 50])
        self.assertEqual(distribute_percentages([1, 0]), [100, 0])
        self.assertEqual(distribute_percentages([0, 0, 0]), [0, 0, 0])
        self.assertEqual(distribute_percentages([5]), [100])
        self.assertEqual(distribute_percentages([1, 1, 1, 1, 1, 1]), [17, 17, 17, 17, 16, 16])

    def test_sum_is_100_for_every_small_combination(self):
        for a in range(0, 9):
            for b in range(0, 9):
                for c in range(0, 9):
                    counts = [a, b, c]
                    result = distribute_percentages(counts)
                    if sum(counts):
                        self.assertEqual(sum(result), 100, counts)
                    else:
                        self.assertEqual(result, [0, 0, 0])
                    # Daha fazla oy alan secenegin yuzdesi hicbir zaman daha dusuk olmaz.
                    for i in range(3):
                        for j in range(3):
                            if counts[i] > counts[j]:
                                self.assertGreaterEqual(result[i], result[j], counts)
                    # Her yuzde gercek orandan en fazla 1 puan sapar.
                    for count, percent in zip(counts, result):
                        if sum(counts):
                            self.assertLess(abs(percent - count * 100 / sum(counts)), 1, counts)

    def test_page_and_json_show_percentages_summing_to_100(self):
        poll = make_poll(self.author, "Üç seçenekli anket burada?", options=("A", "B", "C"))
        for option in poll.options.all():
            self.vote(option, poll=poll, client=Client())
        voter = Client()
        self.vote(poll.options.first(), poll=poll, client=voter)
        data = voter.get(f"/anket/sonuclar/?ids={poll.pk}").json()["polls"][0]
        self.assertEqual(sum(o["percent"] for o in data["options"]), 100)


class AccountDeletionVoteTests(VoteTestCase):
    def test_votes_survive_account_deletion_but_are_anonymized(self):
        client = self.member_client()
        self.vote(self.sinema, client=client)
        other_poll = make_poll(self.author, "İkinci anket burada?")
        self.vote(other_poll.options.first(), poll=other_poll, client=client)
        self.vote(self.restoran, client=Client())

        client.post("/hesap/sil/", {"password": PASSWORD})

        self.assertFalse(User.objects.filter(pk=self.member.pk).exists())
        self.assertEqual(Vote.objects.count(), 3)
        anonymized = Vote.objects.filter(voter_key__startswith="d:")
        self.assertEqual(anonymized.count(), 2)
        self.assertFalse(anonymized.exclude(user=None).exists())
        self.assertEqual(len(set(anonymized.values_list("voter_key", flat=True))), 2)
        counts = {o.text: o.votes.count() for o in self.poll.options.all()}
        self.assertEqual(counts, {"Sinema": 1, "Restoran": 1})

    def _assert_member_votes_anonymized(self):
        self.assertFalse(User.objects.filter(pk=self.member.pk).exists())
        self.assertEqual(Vote.objects.count(), 2)
        self.assertEqual(Vote.objects.filter(voter_key__startswith="d:").count(), 1)
        self.assertFalse(Vote.objects.filter(voter_key__startswith="u:").exists())
        self.assertFalse(Vote.objects.exclude(user=None).exists())

    def _vote_as_member_and_stranger(self):
        self.vote(self.sinema, client=self.member_client())
        self.vote(self.restoran, client=Client())

    def test_orm_delete_anonymizes_votes(self):
        self._vote_as_member_and_stranger()
        self.member.delete()
        self._assert_member_votes_anonymized()

    def test_queryset_delete_anonymizes_votes(self):
        self._vote_as_member_and_stranger()
        User.objects.filter(pk=self.member.pk).delete()
        self._assert_member_votes_anonymized()

    def test_admin_delete_anonymizes_votes(self):
        self._vote_as_member_and_stranger()
        admin = User.objects.create_superuser("yonetici@example.com", "yonetici", PASSWORD)
        client = Client()
        client.force_login(admin)
        url = f"/{settings.ADMIN_URL}accounts/user/{self.member.pk}/delete/"
        response = client.post(url, {"post": "yes"})
        self.assertEqual(response.status_code, 302)
        self._assert_member_votes_anonymized()

    def test_deleting_author_removes_polls_and_their_votes_only(self):
        self.vote(self.sinema, client=Client())
        member_poll = make_poll(self.member, "Üyenin anketi burada?")
        self.vote(member_poll.options.first(), poll=member_poll, client=Client())
        self.member_client().post("/hesap/sil/", {"password": PASSWORD})
        self.assertFalse(Poll.objects.filter(pk=member_poll.pk).exists())
        self.assertTrue(Poll.objects.filter(pk=self.poll.pk).exists())
        self.assertEqual(Vote.objects.filter(poll=self.poll).count(), 1)
        self.assertEqual(Vote.objects.filter(poll_id=member_poll.pk).count(), 0)

    def test_anonymous_votes_are_untouched_by_account_deletion(self):
        self.vote(self.sinema, client=Client())
        self.member_client().post("/hesap/sil/", {"password": PASSWORD})
        self.assertTrue(Vote.objects.get().voter_key.startswith("a:"))

    def test_poll_deletion_removes_votes(self):
        self.vote(self.sinema, client=Client())
        self.member_client(self.author).post(f"/anket/{self.poll.pk}/sil/")
        self.assertEqual(Vote.objects.count(), 0)


class AdminVoteTests(VoteTestCase):
    def test_vote_admin_is_read_only_and_hides_identity(self):
        self.vote(self.sinema, client=self.member_client())
        root = User.objects.create_superuser("root@example.com", "root", PASSWORD)
        client = self.member_client(root)
        base = "/" + settings.ADMIN_URL + "polls/vote/"
        changelist = client.get(base)
        self.assertEqual(changelist.status_code, 200)
        body = changelist.content.decode()
        self.assertNotIn("u:", body.replace("polls/vote", ""))
        self.assertNotIn("uye@example.com", body)
        self.assertEqual(client.get(base + "add/").status_code, 403)
        vote = Vote.objects.get()
        detail = client.get(f"{base}{vote.pk}/change/")
        self.assertEqual(detail.status_code, 200)
        self.assertNotContains(detail, "voter_key")
        self.assertNotContains(detail, "uye@example.com")
        self.assertEqual(client.post(f"{base}{vote.pk}/delete/", {"post": "yes"}).status_code, 403)


class JavaScriptSafetyTests(TestCase):
    def test_main_js_never_uses_dangerous_apis(self):
        source = (Path(settings.BASE_DIR) / "static" / "js" / "main.js").read_text(encoding="utf-8")
        for forbidden in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval(", "new Function"):
            self.assertNotIn(forbidden, source)

    def test_templates_have_no_inline_handlers_or_styles(self):
        templates = Path(settings.BASE_DIR) / "templates"
        for path in templates.rglob("*.html"):
            text = path.read_text(encoding="utf-8")
            for forbidden in (" onclick=", " onsubmit=", " onload=", " style=", "<style", "|safe", "mark_safe", "autoescape off"):
                self.assertNotIn(forbidden, text, f"{path.name}: {forbidden}")
            inline_scripts = [
                line for line in text.splitlines() if "<script" in line and "src=" not in line
            ]
            self.assertEqual(inline_scripts, [], path.name)
