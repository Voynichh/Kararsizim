import unicodedata

from django import forms
from django.core.exceptions import ValidationError
from django.db import transaction

from .models import (
    MAX_OPTIONS,
    MIN_OPTIONS,
    OPTION_MAX_LENGTH,
    QUESTION_MAX_LENGTH,
    QUESTION_MIN_LENGTH,
    Option,
    Poll,
)


# Gorunmez ya da metnin yonunu/gorunumunu bozan karakterler: sifir genisluklu bosluk, kelime birlestirici,
# BOM, yumusak tire, yon gecersiz kilma/gomme/izolasyon karakterleri (U+202A-202E, U+2066-2069).
# ZWJ/ZWNJ (U+200D/200C) emoji ve bazi yazi sistemleri icin gerektiginden korunur.
_STRIPPED_CHARS = {0x200B, 0x2060, 0xFEFF, 0x00AD, 0x180E, *range(0x202A, 0x202F), *range(0x2066, 0x206A)}


def normalize_text(value):
    """Kullanici metnini temizler: kontrol/gorunmez karakterleri atar, bosluklari tek bosluga indirir."""
    kept = [
        ch
        for ch in (value or "")
        if ord(ch) not in _STRIPPED_CHARS and (ch.isspace() or unicodedata.category(ch) != "Cc")
    ]
    return " ".join("".join(kept).split())


class PollForm(forms.Form):
    """Soru + 2-5 secenek.

    Secenekler ayni adli (`option`) birden fazla input olarak gelir; boslar yok sayilir,
    dolu olanlar 2-5 araliginda olmali. `author` formda yoktur: view'da request.user'dan atanir.
    """

    question = forms.CharField(
        label="Sorun",
        max_length=QUESTION_MAX_LENGTH,
        widget=forms.TextInput(attrs={"placeholder": "Bugün sinemaya mı gitsem, restorana mı?"}),
    )

    def __init__(self, data=None, *args, **kwargs):
        super().__init__(data, *args, **kwargs)
        raw = data.getlist("option") if data is not None else []
        self._raw_options = raw
        self.option_errors = {}  # slot indeksi -> hata mesaji
        self.options = []  # temizlenmis secenek metinleri

    def clean_question(self):
        question = normalize_text(self.cleaned_data["question"])
        if len(question) < QUESTION_MIN_LENGTH:
            raise ValidationError(f"Soru en az {QUESTION_MIN_LENGTH} karakter olmalı.")
        return question

    def clean(self):
        cleaned = super().clean()
        seen = {}
        options = []
        for index, raw_text in enumerate(self._raw_options):
            text = normalize_text(raw_text)
            if not text:
                continue
            if len(text) > OPTION_MAX_LENGTH:
                self._slot_error(index, f"Seçenek en fazla {OPTION_MAX_LENGTH} karakter olabilir.")
                continue
            key = text.lower()
            if key in seen:
                self._slot_error(index, "Bu seçenek zaten var.")
                continue
            seen[key] = index
            options.append(text)

        if self.option_errors:
            self.add_error(None, "Seçeneklerde düzeltilmesi gereken yerler var.")
        if len(options) < MIN_OPTIONS:
            self.add_error(None, f"En az {MIN_OPTIONS} seçenek girmelisin.")
        elif len(options) > MAX_OPTIONS:
            self.add_error(None, f"En fazla {MAX_OPTIONS} seçenek girebilirsin.")
        self.options = options
        return cleaned

    def _slot_error(self, index, message):
        self.option_errors[index] = message

    @property
    def option_slots(self):
        """Sablonda cizilecek MAX_OPTIONS adet secenek alani."""
        slots = []
        for index in range(MAX_OPTIONS):
            value = self._raw_options[index] if index < len(self._raw_options) else ""
            slots.append(
                {
                    "number": index + 1,
                    "value": value,
                    "error": self.option_errors.get(index, ""),
                    "required": index < MIN_OPTIONS,
                    "maxlength": OPTION_MAX_LENGTH,
                }
            )
        return slots

    def save(self, author):
        with transaction.atomic():
            poll = Poll.objects.create(author=author, question=self.cleaned_data["question"])
            Option.objects.bulk_create(
                [Option(poll=poll, text=text, order=order) for order, text in enumerate(self.options)]
            )
        return poll
