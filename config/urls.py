from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from core.admin_login import rate_limited_admin_login

# Admin giris sayfasi da kaba kuvvete karsi hiz sinirli (admin.site.urls'ten once uygulanmali).
admin.site.login = rate_limited_admin_login(admin.site.login)

urlpatterns = [
    path("", include("accounts.urls")),
    path("", include("core.urls")),
    path("", include("polls.urls")),
]

# Kapaliyken admin yolu hic kayitli degildir: istek temali 404'e duser (varligi bile belli olmaz).
if settings.ADMIN_ENABLED:
    urlpatterns.insert(0, path(settings.ADMIN_URL, admin.site.urls))
