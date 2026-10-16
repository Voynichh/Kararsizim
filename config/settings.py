import os
import sys
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def env_list(name, default=""):
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


# --- Temel ayarlar ---------------------------------------------------------

# Varsayilan False; yalnizca acikca True verilirse acilir.
DEBUG = env_bool("DEBUG", False)

# Vercel her ortamda VERCEL=1 tanimlar. DEBUG acik kalirsa teknik 404/500 sayfalari adres kaliplarini,
# ayarlari ve yigin izlerini herkese gosterir; bu yuzden Vercel'de DEBUG=True ile baslamayi reddet.
if DEBUG and os.environ.get("VERCEL"):
    raise ImproperlyConfigured("DEBUG=True Vercel'de kullanılamaz; DEBUG ortam değişkenini False yap.")

SECRET_KEY = os.environ.get("SECRET_KEY", "").strip()
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured("SECRET_KEY ortam değişkeni tanımlı olmalı.")
    # Yalnizca yerel gelistirme (DEBUG=True) icin; production'da asla kullanilmaz.
    SECRET_KEY = "yerel-gelistirme-icin-sahte-deger"

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1" if DEBUG else "")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")

# Admin yolu: basinda "/" olmaz, sonunda "/" olur.
ADMIN_URL = os.environ.get("ADMIN_URL", "admin/").strip().strip("/") + "/"

# Yalnizca Vercel'de True: istemci IP'si proxy basligindan okunur (core/net.py).
TRUST_PROXY_IP_HEADER = env_bool("TRUST_PROXY_IP_HEADER", False)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "accounts",
    "polls",
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "config.middleware.SecurityHeadersMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# --- Veritabani ------------------------------------------------------------

_database_url = os.environ.get("DATABASE_URL", "").strip()
if len(sys.argv) > 1 and sys.argv[1] == "test":
    # `manage.py test` gercek (Supabase) veritabanina asla baglanmaz: varsayilan SQLite'tir.
    # Ozellikle baska bir PostgreSQL'de test etmek icin TEST_DATABASE_URL verilir.
    _database_url = os.environ.get("TEST_DATABASE_URL", "").strip()
if _database_url:
    DATABASES = {
        "default": dj_database_url.parse(
            _database_url,
            conn_max_age=0,
            ssl_require=_database_url.startswith(("postgres://", "postgresql://")),
        )
    }
    if DATABASES["default"].get("PORT") in (6543, "6543"):
        # Supabase transaction pooler (port 6543)
        DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = True
        DATABASES["default"].setdefault("OPTIONS", {})["prepare_threshold"] = None
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# Hiz sinirlama icin veritabani cache'i (tablo: manage.py createcachetable).
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "kv_cache",
    }
}

# --- Kimlik dogrulama ------------------------------------------------------

AUTH_USER_MODEL = "accounts.User"

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "polls:feed"
LOGOUT_REDIRECT_URL = "polls:feed"

# --- Yerellestirme ---------------------------------------------------------

LANGUAGE_CODE = "tr"
TIME_ZONE = "Europe/Istanbul"
USE_I18N = True
USE_TZ = True

# --- Statik dosyalar -------------------------------------------------------

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Guvenlik (her ortamda) ------------------------------------------------

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14

CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"

X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"

# Dosya yukleme yok (hicbir formda dosya alani tanimlanmaz); istek govdesi sinirli.
DATA_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024

# --- Guvenlik (yalnizca production, DEBUG=False) ---------------------------

if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_HSTS_PRELOAD = False

# --- Log -------------------------------------------------------------------
# Kisisel veri, parola, cerez veya oturum bilgisi loglanmaz. Django'nun varsayilan
# log ayarlari kullanilir; istek govdesi/cerezleri hicbir yerde ozellikle loglanmaz.
