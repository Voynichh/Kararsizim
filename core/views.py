from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET


def privacy(request):
    return render(request, "core/privacy.html")


@require_GET
def robots_txt(request):
    if settings.ALLOW_SEARCH_INDEXING:
        # Admin yolu burada yazilmaz (gizli kalmali); oturum/hesap sayfalari taranmasin.
        lines = ["User-agent: *", "Disallow: /hesap/", "Disallow: /giris/", "Disallow: /kayit/", "Disallow: /anket/yeni/"]
    else:
        lines = ["User-agent: *", "Disallow: /"]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain; charset=utf-8")
