"""Sayfa yapisi (erisilebilirlik/isaretleme) ile ilgili gerileme testleri."""

import re

from django.contrib.auth import get_user_model
from django.test import TestCase

from polls.models import Option, Poll

User = get_user_model()


class MarkupTests(TestCase):
    def setUp(self):
        owner = User.objects.create_user("o@example.com", "sahip", "uzun-bir-parola-123")
        self.poll = Poll.objects.create(author=owner, question="Baslik testi sorusu burada?")
        Option.objects.create(poll=self.poll, text="A", order=0)
        Option.objects.create(poll=self.poll, text="B", order=1)

    def h1_count(self, path):
        return len(re.findall(r"<h1[ >]", self.client.get(path).content.decode()))

    def test_every_page_has_exactly_one_h1(self):
        for path in ("/", f"/anket/{self.poll.pk}/", "/giris/", "/kayit/", "/gizlilik/", "/yok-sayfa/"):
            with self.subTest(path=path):
                self.assertEqual(self.h1_count(path), 1)

    def test_poll_detail_question_is_the_h1(self):
        html = self.client.get(f"/anket/{self.poll.pk}/").content.decode()
        self.assertRegex(html, r'<h1 class="poll-card__question">Baslik testi sorusu burada\?</h1>')

    def test_feed_keeps_questions_as_h2_links(self):
        html = self.client.get("/").content.decode()
        self.assertIn('<h2 class="poll-card__question">', html)

    def test_pages_declare_a_favicon_that_exists(self):
        from django.contrib.staticfiles import finders

        for path in ("/", "/giris/", "/yok-sayfa/"):
            self.assertIn('rel="icon"', self.client.get(path).content.decode())
        self.assertIsNotNone(finders.find("favicon.svg"))

    def test_html_lang_is_turkish_everywhere(self):
        for path in ("/", "/giris/", "/gizlilik/", "/yok-sayfa/"):
            self.assertIn('<html lang="tr">', self.client.get(path).content.decode())
