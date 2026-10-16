"""Gercek URETIM ayarlariyla (DEBUG=False) kara kutu guvenlik/mahremiyet denetimi.

Her sey tek islemde calisir ve geri alinir; YEREL SQLite kullanir (gercek veritabanina baglanmayi
reddeder). Calistirmak icin (Git Bash; bos DATABASE_URL onemli, PowerShell bos degiskeni siler):

    DEBUG=False SECRET_KEY="$(python -c 'import secrets;print(secrets.token_urlsafe(50))')" \\
    ALLOWED_HOSTS="testserver,localhost" DATABASE_URL="" ADMIN_URL="yonetim-denetim99/" ADMIN_ENABLED=True \\
    CSRF_TRUSTED_ORIGINS="https://testserver" .venv/Scripts/python.exe tools/prod_audit.py

Cikti her kontrol icin OK/SORUN yazar; sonda "N/N kontrol gecti" ozeti verir.
"""
import logging
import os
import re
import statistics
import sys
import time

sys.path.insert(0, os.getcwd())
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"

import django

django.setup()

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.db import connection, transaction
from django.test import Client
from django.test.utils import setup_test_environment

setup_test_environment()
assert connection.vendor == "sqlite" and not settings.DEBUG

from polls.models import Option, Poll, Vote

User = get_user_model()
PW = "mavi-bulut-kahve-42"
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
results = []


def check(name, ok, detail=""):
    results.append((ok, name, detail))


class Capture(logging.Handler):
    def __init__(self):
        super().__init__(logging.DEBUG)
        self.lines = []

    def emit(self, record):
        self.lines.append(self.format(record))


class Rollback(Exception):
    pass


def https(client, method, path, *args, **kw):
    return getattr(client, method)(path, *args, secure=True, **kw)


def set_cookie_attrs(response, name):
    c = response.cookies.get(name)
    if c is None:
        return None
    return {"secure": bool(c["secure"]), "httponly": bool(c["httponly"]), "samesite": c["samesite"], "max-age": c["max-age"]}


def run():
    cap = Capture()
    logging.getLogger().addHandler(cap)
    logging.getLogger().setLevel(logging.DEBUG)

    owner = User.objects.create_user("sahip.gizli@example.com", "sahip", PW)
    voter = User.objects.create_user("uye.gizli@example.com", "uye", PW)
    root = User.objects.create_superuser("root.gizli@example.com", "root", PW)
    poll = Poll.objects.create(author=owner, question="<script>alert(1)</script> soru metni")
    o1 = Option.objects.create(poll=poll, text="<img src=x onerror=alert(1)>", order=0)
    o2 = Option.objects.create(poll=poll, text="güvenli", order=1)
    emails = ["sahip.gizli@example.com", "uye.gizli@example.com", "root.gizli@example.com"]

    anon = Client()

    # 1) HTTPS yonlendirmesi ve HSTS
    r = anon.get("/")  # http
    check("http -> https yonlendirir (301)", r.status_code == 301 and r["Location"].startswith("https://"), f"{r.status_code} {r.get('Location')}")
    r = https(anon, "get", "/")
    hsts = r.get("Strict-Transport-Security", "")
    check("HSTS basligi var (>=1 yil)", "max-age=31536000" in hsts, hsts)

    # 2) Guvenlik basliklari (cesitli yanit turlerinde)
    for path in ("/", "/giris/", "/kayit/", "/gizlilik/", f"/anket/{poll.pk}/", "/yok-sayfa/", "/anket/99999/"):
        r = https(anon, "get", path)
        missing = [h for h in ("Content-Security-Policy", "X-Frame-Options", "X-Content-Type-Options", "Referrer-Policy", "Permissions-Policy", "Cross-Origin-Opener-Policy") if h not in r]
        check(f"guvenlik basliklari tam: {path}", not missing, f"eksik: {missing}")
    csp = https(anon, "get", "/")["Content-Security-Policy"]
    check("CSP: unsafe-inline/eval yok (uygulama)", "unsafe" not in csp, csp)

    # 3) Hata sayfalari sizinti yapmiyor
    for path in ("/yok-sayfa/", "/anket/99999/", "/anket/99999/sil/", "/admin/"):
        body = https(anon, "get", path).content.decode().lower()
        leaks = [w for w in ("urlconf", "traceback", "debug = true", "request method", "settings.py", "django version") if w in body]
        check(f"404 sizinti yok: {path}", not leaks, str(leaks))
    r = https(anon, "get", "/admin/")
    check("/admin/ -> 404", r.status_code == 404, r.status_code)
    r = https(anon, "get", "/" + settings.ADMIN_URL)
    check("gercek admin yolu giris sayfasina yonlendirir", r.status_code in (200, 302), r.status_code)
    r = https(anon, "get", "/" + settings.ADMIN_URL + "login/")
    check("admin yolunda CSP sadece stil icin gevsek", "style-src 'self' 'unsafe-inline'" in r["Content-Security-Policy"] and "script-src 'self';" in r["Content-Security-Policy"])
    r = https(anon, "get", "/", HTTP_HOST="kotu-site.example")
    check("gecersiz Host -> 400 (sayfa sizdirmaz)", r.status_code == 400 and "kotu-site" not in r.content.decode(), r.status_code)

    # 4) HTTP metodlari
    check("GET /cikis/ -> 405", https(anon, "get", "/cikis/").status_code == 405)
    check(f"GET /anket/{poll.pk}/oy/ -> 405", https(anon, "get", f"/anket/{poll.pk}/oy/").status_code == 405)
    check("DELETE / -> 405 veya guvenli", https(anon, "delete", "/").status_code in (200, 405))

    # 5) CSRF
    c = Client(enforce_csrf_checks=True)
    r = https(c, "post", "/giris/", {"email": "a@b.co", "password": "x"})
    check("CSRF tokensiz POST -> 403", r.status_code == 403, r.status_code)
    body = r.content.decode().lower()
    check("CSRF 403 sayfasi sizinti yapmiyor", "reason given" not in body and "csrf_trusted" not in body and "origin" not in body.replace("origins", ""), body[:200])

    # 6) Cerezler (uretim ayarlariyla)
    r = https(anon, "get", "/giris/")
    a = set_cookie_attrs(r, "csrftoken")
    check("csrftoken cerezi: Secure+HttpOnly+Lax", a and a["secure"] and a["httponly"] and a["samesite"] == "Lax", str(a))
    login = Client()
    https(login, "get", "/giris/")
    r = https(login, "post", "/giris/", {"email": "uye.gizli@example.com", "password": PW})
    a = set_cookie_attrs(r, "sessionid")
    check("sessionid cerezi: Secure+HttpOnly+Lax", a and a["secure"] and a["httponly"] and a["samesite"] == "Lax", str(a))
    v = Client()
    r = https(v, "post", f"/anket/{poll.pk}/oy/", {"option": o2.pk})
    a = set_cookie_attrs(r, "kv_voter")
    check("kv_voter cerezi: Secure+HttpOnly+Lax+1yil", a and a["secure"] and a["httponly"] and a["samesite"] == "Lax" and str(a["max-age"]) == str(60 * 60 * 24 * 365), str(a))
    check("kv_voter degeri imzali (':' icerir, duz uuid degil)", r.cookies["kv_voter"].value.count(":") >= 2)

    # 7) XSS: kaçışlama
    for path in ("/", f"/anket/{poll.pk}/"):
        body = https(Client(), "get", path).content.decode()
        check(f"XSS kacisli: {path}", "<script>alert(1)</script>" not in body and "<img src=x" not in body and "&lt;script&gt;" in body)
    voted = Client()
    https(voted, "post", f"/anket/{poll.pk}/oy/", {"option": o1.pk})
    body = https(voted, "get", f"/anket/{poll.pk}/").content.decode()
    check("XSS kacisli (sonuc gorunumu)", "<img src=x" not in body and "&lt;img" in body)

    # 8) E-posta gizliligi: tum sayfalar
    pages = ["/", "/giris/", "/kayit/", "/gizlilik/", f"/anket/{poll.pk}/", "/yok/", "/anket/99999/"]
    clients = {"anonim": Client(), "sahip": Client(), "uye": Client(), "oy veren": voted}
    clients["sahip"].force_login(owner)
    clients["uye"].force_login(voter)
    leak = []
    for who, cl in clients.items():
        for path in pages + ["/anket/yeni/", "/hesap/parola/", "/hesap/sil/"]:
            r = https(cl, "get", path, follow=False)
            if r.status_code in (301, 302):
                continue
            found = EMAIL_RE.findall(r.content.decode())
            found = [e for e in found if e.endswith("example.com") or e in emails]
            if found:
                leak.append((who, path, found))
        # oy JSON
        jr = https(cl, "post", f"/anket/{poll.pk}/oy/", {"option": o1.pk}, HTTP_ACCEPT="application/json")
        txt = jr.content.decode()
        if EMAIL_RE.search(txt) or "voter" in txt.lower() or '"user' in txt.lower():
            leak.append((who, "oy JSON", txt[:120]))
    check("e-posta/voter_key hicbir sayfada veya JSON'da yok", not leak, str(leak))
    r = https(clients["sahip"], "get", "/hesap/")
    check("e-posta yalnizca /hesap/ sayfasinda sahibine gorunur", "sahip.gizli@example.com" in r.content.decode() and "uye.gizli@example.com" not in r.content.decode())
    sess_data = [s.get_decoded() for s in __import__("django.contrib.sessions.models", fromlist=["Session"]).Session.objects.all()]
    check("oturum verisinde e-posta/parola yok", not any(EMAIL_RE.search(str(d)) or PW in str(d) for d in sess_data), str(sess_data)[:150])

    # 9) Acik yonlendirme
    evil = ["https://kotu-site.com", "//kotu-site.com", "/\\kotu-site.com", "https:kotu-site.com", "javascript:alert(1)", "%2f%2fkotu-site.com", "http://localhost.kotu-site.com", "///kotu-site.com", "\\\\kotu-site.com"]
    bad = []
    for e in evil:
        c = Client()
        https(c, "get", "/giris/")
        r = https(c, "post", "/giris/?next=" + e, {"email": "uye.gizli@example.com", "password": PW, "next": e})
        loc = r.get("Location", "")
        if "kotu-site" in loc:
            bad.append((e, loc))
        r2 = https(Client(), "post", f"/anket/{poll.pk}/oy/", {"option": o2.pk, "next": e})
        if "kotu-site" in r2.get("Location", ""):
            bad.append((e, r2["Location"]))
    check("acik yonlendirme yok (giris + oy)", not bad, str(bad))

    # 10) IDOR / yetki
    other = Client()
    other.force_login(voter)
    check("baskasinin anketini silme -> 404", https(other, "post", f"/anket/{poll.pk}/sil/").status_code == 404 and Poll.objects.filter(pk=poll.pk).exists())
    check("anonim silme -> girise yonlendirir", https(Client(), "post", f"/anket/{poll.pk}/sil/").status_code == 302)
    own = Client()
    own.force_login(owner)
    check("sahip kendi anketine oy veremez (403)", https(own, "post", f"/anket/{poll.pk}/oy/", {"option": o1.pk}, HTTP_ACCEPT="application/json").status_code == 403)

    # 11) Sahte/bozuk cerez
    for val in ("a:1", "x" * 600, "", "AAAA:BBBB:CCCC", "a" * 4097):
        c = Client()
        c.cookies["kv_voter"] = val
        c.cookies["sessionid"] = val
        r = https(c, "get", "/")
        r2 = https(c, "post", f"/anket/{poll.pk}/oy/", {"option": o2.pk})
        check(f"bozuk cerez cokertmiyor ({val[:8]!r})", r.status_code == 200 and r2.status_code in (200, 302), f"{r.status_code}/{r2.status_code}")

    # 12) Hiz sinirlari (uretim ayariyla)
    from core.ratelimit import SIGNUP_IP

    SIGNUP_LIMIT = SIGNUP_IP[0]
    cl = Client()
    codes = [https(cl, "post", "/giris/", {"email": f"x{i}@example.com", "password": "yanlis-parola-1"}, REMOTE_ADDR="198.51.100.7").status_code for i in range(12)]
    check("giris IP limiti: 10 hatadan sonra 429", codes[:10] == [200] * 10 and codes[10] == 429, str(codes))
    codes = [https(Client(), "post", "/giris/", {"email": "uye.gizli@example.com", "password": "yanlis-parola-1"}, REMOTE_ADDR=f"203.0.113.{i}").status_code for i in range(7)]
    check("giris e-posta limiti: 5 hatadan sonra 429", codes[:5] == [200] * 5 and codes[5] == 429, str(codes))
    codes = [https(Client(), "post", "/kayit/", {"email": "q", "username": "x", "password1": "a", "password2": "b"}, REMOTE_ADDR="198.51.100.9").status_code for i in range(SIGNUP_LIMIT + 2)]
    check(f"kayit limiti: {SIGNUP_LIMIT}'den sonra 429", codes[:SIGNUP_LIMIT] == [200] * SIGNUP_LIMIT and codes[SIGNUP_LIMIT] == 429, str(codes))
    codes = [https(Client(), "post", f"/anket/{poll.pk}/oy/", {"option": o2.pk}, REMOTE_ADDR="198.51.100.11").status_code for i in range(32)]
    check("oy limiti: 30'dan sonra 429", 429 in codes and codes.index(429) in (30, 31), str(codes.index(429) if 429 in codes else None))

    # 13) Paralel (yaris) dayanikliligi: ayni anda cok istek limiti asabilir mi?
    from core import ratelimit
    n_allowed = 0
    for _ in range(40):  # ardisik; atomiklik ayri test edilir
        if not ratelimit.hit("audit", "kimlik", (5, 60)):
            n_allowed += 1
    check("hit(): limit 5 ise tam 5 izin verir", n_allowed == 5, str(n_allowed))

    # 14) Admin giris limiti (kaba kuvvet)
    ac = Client()
    codes = [https(ac, "post", "/" + settings.ADMIN_URL + "login/?next=/" + settings.ADMIN_URL, {"username": "root.gizli@example.com", "password": "yanlis-parola-1"}, REMOTE_ADDR="198.51.100.21").status_code for i in range(14)]
    check("admin girisi hiz siniri (429 gelmeli)", 429 in codes, str(codes))

    # 15) Onbellek basliklari (kisiye ozel sayfalar)
    for path in ("/hesap/", "/hesap/parola/", "/hesap/sil/"):
        r = https(clients["sahip"], "get", path)
        cc = r.get("Cache-Control", "")
        check(f"kisiye ozel sayfa onbelleklenmez: {path}", "no-store" in cc or "private" in cc, cc or "(Cache-Control yok)")
    r = https(clients["sahip"], "get", "/")
    check("akis (kisiye gore degisir) paylasimli onbellege girmez", "private" in r.get("Cache-Control", "") or "no-store" in r.get("Cache-Control", "") or "Cookie" in r.get("Vary", ""), f"CC={r.get('Cache-Control')} Vary={r.get('Vary')}")

    # 16) Zamanlama: kullanici sayimi (authenticate)
    def timeit(email):
        ts = []
        for _ in range(12):
            t = time.perf_counter()
            authenticate(username=email, password="yanlis-parola-1")
            ts.append(time.perf_counter() - t)
        return statistics.median(ts)

    t_exist, t_missing = timeit("uye.gizli@example.com"), timeit("yok.yok@example.com")
    ratio = max(t_exist, t_missing) / max(min(t_exist, t_missing), 1e-9)
    check("giriste kullanici varligi zamanlama farki yok (<%35)", ratio < 1.35, f"var={t_exist*1000:.1f}ms yok={t_missing*1000:.1f}ms oran={ratio:.2f}")

    # 17) Log: kisisel veri yok
    text = "\n".join(cap.lines)
    check("loglarda e-posta/parola/cerez yok", not EMAIL_RE.search(text) and PW not in text and "sessionid" not in text and "kv_voter" not in text, text[:200] if EMAIL_RE.search(text) else "")

    logging.getLogger().removeHandler(cap)
    raise Rollback


try:
    with transaction.atomic():
        run()
except Rollback:
    pass

width = max(len(n) for _, n, _ in results)
fails = 0
for ok, name, detail in results:
    print(("OK    " if ok else "SORUN ") + name + ("" if ok or not detail else f"   -> {detail}"))
    fails += 0 if ok else 1
print(f"\n{len(results) - fails}/{len(results)} kontrol gecti, {fails} sorun")
