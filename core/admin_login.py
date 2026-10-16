"""Django admin giris sayfasina kaba kuvvet korumasi (uygulama girisindekiyle ayni mantik)."""

import functools

from . import ratelimit
from .net import get_client_ip


def rate_limited_admin_login(login_view):
    """`admin.site.login` gorunumunu sarar: IP ve e-posta basina basarisiz deneme limiti."""

    @functools.wraps(login_view)
    def wrapper(request, *args, **kwargs):
        if request.method != "POST":
            return login_view(request, *args, **kwargs)

        ip = get_client_ip(request)
        email = (request.POST.get("username") or "").strip().lower()[:254]
        ip_slot = ratelimit.reserve("admin_login_ip", ip, ratelimit.ADMIN_LOGIN_IP)
        email_slot = (
            ratelimit.reserve("admin_login_email", email, ratelimit.ADMIN_LOGIN_EMAIL) if email else None
        )
        if ip_slot is None or (email and email_slot is None):
            ratelimit.release(ip_slot)
            ratelimit.release(email_slot)
            return ratelimit.rate_limited_response(request)

        response = login_view(request, *args, **kwargs)
        if response.status_code in (301, 302):  # basarili giris yonlendirir; hak iade edilir
            ratelimit.release(ip_slot)
            ratelimit.release(email_slot)
        return response

    return wrapper
