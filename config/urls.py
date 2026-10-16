from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from core.admin_login import rate_limited_admin_login

# Admin giris sayfasi da kaba kuvvete karsi hiz sinirli (admin.site.urls'ten once uygulanmali).
admin.site.login = rate_limited_admin_login(admin.site.login)

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    path("", include("accounts.urls")),
    path("", include("core.urls")),
    path("", include("polls.urls")),
]
