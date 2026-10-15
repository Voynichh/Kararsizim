import hashlib
import hmac
import ipaddress

from django.conf import settings
from django.utils.http import url_has_allowed_host_and_scheme


def _parse_ip(value):
    try:
        return str(ipaddress.ip_address(value.strip()))
    except ValueError:
        return None


def get_client_ip(request):
    """Istemci IP'sini tek yerden okur.

    TRUST_PROXY_IP_HEADER=True (yalnizca Vercel) ise X-Forwarded-For okunur: Vercel bu basligi
    kendisi yazar ve disaridan gelen IP'leri iletmez (IP sahteciligini onlemek icin; bkz.
    https://vercel.com/docs/headers/request-headers). Yine de en sagdaki (proxy'nin ekledigi)
    deger alinir ve gecerli bir IP degilse REMOTE_ADDR'a dusulur.
    Aksi halde yalnizca REMOTE_ADDR kullanilir; istemcinin gonderebilecegi baslik okunmaz.
    """
    if settings.TRUST_PROXY_IP_HEADER:
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded:
            ip = _parse_ip(forwarded.split(",")[-1])
            if ip:
                return ip
    return _parse_ip(request.META.get("REMOTE_ADDR", "")) or "0.0.0.0"


def hash_identifier(value):
    """Ham IP/e-posta yerine cache anahtarlarinda kullanilan HMAC-SHA256 ozeti."""
    return hmac.new(
        settings.SECRET_KEY.encode(), value.encode(), hashlib.sha256
    ).hexdigest()


def get_safe_next(request):
    """`next` parametresi bu siteye aitse dondurur, degilse bos string (acik yonlendirme yok)."""
    url = request.POST.get("next") or request.GET.get("next") or ""
    if url and url_has_allowed_host_and_scheme(
        url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return url
    return ""
