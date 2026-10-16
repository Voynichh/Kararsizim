"""Atomik, sabit pencereli hiz sinirlama (veritabani cache'i uzerinde).

Her izin verilen deneme, pencere icin ayrilmis `limit` adet "yuva" anahtarindan birini
`cache.add()` ile talep eder. `add()` veritabaninda benzersiz anahtar eklemedir, yani atomiktir:
ayni anda gelen yuzlerce istek bile ayni yuvayi iki kez alamaz ve limitin ustune cikamaz.
(Eski "oku, artir, yaz" sayaci yaris durumunda limiti asabiliyordu.)

Cache anahtarlarinda ham IP/e-posta yer almaz (HMAC ozeti kullanilir) ve kayitlar pencere bitince
kendiliginden gecersiz olur; hicbir kisisel veri kalici saklanmaz.
"""

import time

from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import render

from .net import hash_identifier

MINUTE = 60
HOUR = 60 * MINUTE

# (limit, pencere saniye)
LOGIN_IP = (10, 15 * MINUTE)
LOGIN_EMAIL = (5, 15 * MINUTE)
ADMIN_LOGIN_IP = (10, 15 * MINUTE)
ADMIN_LOGIN_EMAIL = (5, 15 * MINUTE)
SIGNUP_IP = (20, HOUR)  # ortak Wi-Fi/mobil IP'deki bir arkadas grubu birlikte kayit olabilsin
ACCOUNT_SENSITIVE_USER = (5, 15 * MINUTE)  # parola degistirme / hesap silme
POLL_CREATE_USER = (10, HOUR)
VOTE_IP = (30, MINUTE)


def _slots(scope, identifier, rule):
    """(yuva anahtarlari, pencere sonuna kalan saniye)."""
    limit, window = rule
    now = time.time()
    bucket = int(now // window)
    base = f"rl:{scope}:{hash_identifier(f'{scope}:{identifier}')}:{bucket}"
    timeout = int(window - (now % window)) + 1  # pencerenin bitisine kadar
    return [f"{base}:{i}" for i in range(limit)], timeout


def is_limited(scope, identifier, rule):
    """Yuva talep etmeden, limite ulasilip ulasilmadigina bakar."""
    keys, _ = _slots(scope, identifier, rule)
    return len(cache.get_many(keys)) >= len(keys)


def reserve(scope, identifier, rule):
    """Bir deneme hakki ayirir. Basariliysa yuva anahtarini, limit dolduysa None dondurur.

    Deneme basarili olursa hak `release()` ile iade edilebilir (ornegin dogru parola girisi).
    """
    keys, timeout = _slots(scope, identifier, rule)
    taken = cache.get_many(keys)
    for key in keys:
        if key in taken:
            continue
        if cache.add(key, 1, timeout=timeout):
            return key
    return None


def release(key):
    """`reserve()` ile ayrilmis hakki iade eder."""
    if key:
        cache.delete(key)


def hit(scope, identifier, rule):
    """Bir deneme hakki harcar; limit dolduysa True dondurur (deneme reddedilmeli)."""
    return reserve(scope, identifier, rule) is None


def rate_limited_response(request):
    if "application/json" in request.headers.get("Accept", ""):
        return JsonResponse(
            {"ok": False, "error": "Biraz yavaşla, birazdan tekrar dene."}, status=429
        )
    return render(request, "429.html", status=429)
