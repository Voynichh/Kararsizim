from django.conf import settings

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
        return response
