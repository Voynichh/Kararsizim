"""Basit sabit pencere hiz sinirlama (veritabani cache'i uzerinde).

Cache anahtarlarinda ham IP/e-posta yer almaz (HMAC ozeti kullanilir) ve kayitlar pencere
bitince kendiliginden gecersiz olur; hicbir kisisel veri kalici saklanmaz.
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
SIGNUP_IP = (5, HOUR)
ACCOUNT_SENSITIVE_USER = (5, 15 * MINUTE)  # parola degistirme / hesap silme
POLL_CREATE_USER = (10, HOUR)
VOTE_IP = (30, MINUTE)


def _key(scope, identifier, window):
    bucket = int(time.time() // window)
    return f"rl:{scope}:{hash_identifier(f'{scope}:{identifier}')}:{bucket}"


def is_limited(scope, identifier, rule):
    """Sayaci artirmadan, limite ulasilip ulasilmadigina bakar."""
    limit, window = rule
    return cache.get(_key(scope, identifier, window), 0) >= limit


def record(scope, identifier, rule):
    """Sayaci bir artirir ve yeni degeri dondurur."""
    _, window = rule
    key = _key(scope, identifier, window)
    timeout = window + 1
    if cache.add(key, 1, timeout=timeout):
        return 1
    try:
        return cache.incr(key)
    except ValueError:  # anahtar araya giren sure dolumuyla silindi
        cache.set(key, 1, timeout=timeout)
        return 1


def hit(scope, identifier, rule):
    """Sayaci artirir; limit asildiysa True dondurur."""
    limit, _ = rule
    return record(scope, identifier, rule) > limit


def rate_limited_response(request):
    if "application/json" in request.headers.get("Accept", ""):
        return JsonResponse(
            {"ok": False, "error": "Biraz yavaşla, birazdan tekrar dene."}, status=429
        )
    return render(request, "429.html", status=429)
