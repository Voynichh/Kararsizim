from django.conf import settings
from django.core.validators import MinLengthValidator
from django.db import models

QUESTION_MIN_LENGTH = 5
QUESTION_MAX_LENGTH = 200
OPTION_MAX_LENGTH = 80
MIN_OPTIONS = 2
MAX_OPTIONS = 5


class Poll(models.Model):
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="polls",
        verbose_name="yazar",
    )
    question = models.CharField(
        "soru",
        max_length=QUESTION_MAX_LENGTH,
        validators=[MinLengthValidator(QUESTION_MIN_LENGTH)],
    )
    created_at = models.DateTimeField("oluşturulma zamanı", auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        verbose_name = "anket"
        verbose_name_plural = "anketler"

    def __str__(self):
        return self.question[:60]


class Option(models.Model):
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name="options")
    text = models.CharField("metin", max_length=OPTION_MAX_LENGTH)
    order = models.PositiveSmallIntegerField("sıra")

    class Meta:
        ordering = ["order"]
        verbose_name = "seçenek"
        verbose_name_plural = "seçenekler"
        constraints = [
            models.UniqueConstraint(fields=["poll", "order"], name="polls_option_poll_order_unique"),
        ]

    def __str__(self):
        return self.text
