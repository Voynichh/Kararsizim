from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.template.loader import render_to_string

CSP_DIRECTIVES = [
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self'",
    "font-src 'self'",
    "img-src 'self' data:",
    "connect-src 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "object-src 'none'",
]

# Django admin bazi yerlerde inline stil kullanir; gevsetme yalnizca admin yolu icindir.
ADMIN_CSP_DIRECTIVES = [
    "style-src 'self' 'unsafe-inline'" if directive.startswith("style-src") else directive
    for directive in CSP_DIRECTIVES
]

CONTENT_SECURITY_POLICY = "; ".join(CSP_DIRECTIVES)
ADMIN_CONTENT_SECURITY_POLICY = "; ".join(ADMIN_CSP_DIRECTIVES)
PERMISSIONS_POLICY = "camera=(), microphone=(), geolocation=(), payment=()"


class SecurityHeadersMiddleware:
    """Her yanita CSP ve Permissions-Policy basliklarini ekler."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith("/" + settings.ADMIN_URL):
            policy = ADMIN_CONTENT_SECURITY_POLICY
        else:
            policy = CONTENT_SECURITY_POLICY
        response.headers["Content-Security-Policy"] = policy
        response.headers["Permissions-Policy"] = PERMISSIONS_POLICY
        # Sayfalar kisiye gore degisir (oy durumu, oturum); ortak onbellekler (CDN/proxy) saklamasin.
        # Daha siki bir deger (ornegin never_cache) koyan view'lara dokunulmaz.
        if "Cache-Control" not in response.headers:
            response.headers["Cache-Control"] = "private, no-cache"
        if not settings.ALLOW_SEARCH_INDEXING:
            response.headers["X-Robots-Tag"] = "noindex, nofollow"
        return response


class MaintenanceMiddleware:
    """MAINTENANCE_MODE=True iken siteyi kapatir: sayfalar 503 "Bakimdayiz", JSON istekler 503 JSON.

    Admin yolu (acikssa) ve statik dosyalar acik kalir; boylece yonetici bakim sirasinda calisabilir.
    SecurityHeadersMiddleware'in icinde calisir, yani 503 yanitina da CSP vb. basliklar eklenir.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if settings.MAINTENANCE_MODE and not self._exempt(request.path):
            if "application/json" in request.headers.get("Accept", ""):
                response = JsonResponse({"ok": False, "error": "Bakımdayız, birazdan tekrar dene."}, status=503)
            else:
                response = HttpResponse(render_to_string("maintenance.html"), status=503)
            response["Retry-After"] = "600"
            response["Cache-Control"] = "no-store"
            return response
        return self.get_response(request)

    @staticmethod
    def _exempt(path):
        if path.startswith("/" + settings.STATIC_URL.lstrip("/")):
            return True
        return settings.ADMIN_ENABLED and path.startswith("/" + settings.ADMIN_URL)
