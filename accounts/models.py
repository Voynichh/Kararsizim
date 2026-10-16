from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.validators import RegexValidator
from django.db import models
from django.db.models.functions import Lower

username_validator = RegexValidator(
    regex=r"^[A-Za-z0-9_]{3,20}$",
    message="Kullanıcı adı 3–20 karakter olmalı; yalnızca harf (a-z), rakam ve _ içerebilir.",
)


# Kayit sirasinda alinamayan, yonetici/resmi hesap gibi gorunen adlar (taklit onlemi). Karsilastirma
# kucuk harfle, alt cizgiler atilarak ve basit rakam-harf benzetmeleri (adm1n -> admin) cozerek yapilir.
RESERVED_USERNAMES_EXACT = frozenset(
    {"root", "system", "sistem", "staff", "ekip", "mod", "owner", "sahip", "bot", "anonim", "anonymous",
     "null", "none", "undefined", "kararsiz"}
)
RESERVED_USERNAME_PARTS = ("admin", "yonetici", "yonetim", "moderator", "kararsizim", "destek", "support", "official")
_LOOKALIKES = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t"})


def is_reserved_username(username):
    folded = (username or "").lower().replace("_", "").translate(_LOOKALIKES)
    return folded in RESERVED_USERNAMES_EXACT or any(part in folded for part in RESERVED_USERNAME_PARTS)


class UserManager(BaseUserManager):
    use_in_migrations = True

    def get_by_natural_key(self, email):
        return self.get(email=self.normalize_email(email).strip().lower())

    def _create_user(self, email, username, password, **extra_fields):
        if not email:
            raise ValueError("E-posta zorunludur.")
        if not username:
            raise ValueError("Kullanıcı adı zorunludur.")
        user = self.model(
            email=self.normalize_email(email).strip().lower(),
            username=username,
            **extra_fields,
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, username, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, username, password, **extra_fields)

    def create_superuser(self, email, username, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields["is_staff"] is not True or extra_fields["is_superuser"] is not True:
            raise ValueError("Süper kullanıcı için is_staff ve is_superuser True olmalı.")
        return self._create_user(email, username, password, **extra_fields)


class User(AbstractUser):
    # Kullanilmayan alanlar (veri en aza indirme).
    first_name = None
    last_name = None

    email = models.EmailField("e-posta", unique=True)
    username = models.CharField(
        "kullanıcı adı",
        max_length=20,
        validators=[username_validator],
    )

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    class Meta:
        constraints = [
            models.UniqueConstraint(
                Lower("username"),
                name="accounts_user_username_ci_unique",
                violation_error_message="Bu kullanıcı adı zaten alınmış.",
            ),
        ]

    def clean(self):
        super().clean()
        self.email = self.email.strip().lower()

    def save(self, *args, **kwargs):
        self.email = self.email.strip().lower()
        super().save(*args, **kwargs)

    def get_full_name(self):
        return self.username

    def get_short_name(self):
        return self.username

    def __str__(self):
        # E-posta hicbir yerde gorunmemeli; yalnizca kullanici adi.
        return self.username
