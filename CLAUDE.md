# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**kararsızım**: Django ile yazılmış, kullanıcıların kararsız kaldıkları konularda anket açıp danıştığı bir web uygulaması. Ürün tanımı, veri modeli, güvenlik kuralları (Bölüm 10) ve fazlara bölünmüş geliştirme planı tek kaynakta tutulur:

@docs/Kararsizim.md

## Çalışma kuralları (özet)

- Her seferde yalnızca istenen fazı uygula; sonraki fazlara geçme. Mevcut durum: **Faz 0–3 tamam** (iskelet, ayarlar, CSP, `accounts.User`, tema; kayıt/giriş/hesap, hız sınırlama, gizlilik; anket oluşturma/akış/detay/silme; oy verme ve sonuçlar). Sıradaki Faz 4 (Supabase + Vercel). Supabase projesi "kararsizim" açıldı (bkz. hafıza notu), ama uygulama henüz yerel SQLite kullanıyor.
- Bölüm 10 (güvenlik/gizlilik) pazarlık konusu değildir; çelişki varsa dur ve sor.
- Yalnızca Bölüm 4'teki paketler; başkası gerekirse önce sor. Sürümler `requirements.txt`'te `==` ile sabit.
- Kod İngilizce, kullanıcıya görünen tüm metinler Türkçe. E-posta adresi hiçbir yerde görünmez (yalnızca `/hesap/`'ta sahibine).
- Faz sonunda: testleri çalıştır, kabul + güvenlik kriterlerini raporla, commit öner (commit'i kullanıcı onayıyla at).

## Komutlar

Yerelde `.venv` (Python 3.15) kullanılır; Windows'ta `.venv\Scripts\python.exe` ile çağır. İlk kurulum için `.env.example` dosyasını `.env` olarak kopyala (`DEBUG=True` verir; `.env` git'e girmez).

```bash
pip install -r requirements-dev.txt
python manage.py migrate
python manage.py createcachetable          # hız sınırlama için DB cache tablosu; migrate'ten ayrıdır
python manage.py runserver

python manage.py test                      # tüm testler
python manage.py test accounts             # tek uygulama
python manage.py test core.tests.SecurityHeadersTests.test_security_headers_present_on_home   # tek test

python manage.py check --deploy            # üretim uyarıları (DEBUG=False ve gerçek SECRET_KEY ile çalıştır)
pip-audit -r requirements.txt              # bağımlılık açık taraması
```

`check --deploy`'daki `W005` (HSTS include_subdomains) ve `W021` (HSTS preload) bilinçli olarak açık bırakılmıştır (özel alan adı alınınca yeniden değerlendirilecek).

## Mimari (birden fazla dosyayı okumadan görünmeyenler)

- **Ayarlar ortam değişkenlerinden okunur** (`config/settings.py`, yerelde `python-dotenv`). `DEBUG` varsayılanı `False`; `SECRET_KEY` yoksa ve `DEBUG=False` ise import sırasında `ImproperlyConfigured` fırlatılır (sahte anahtar yalnızca `DEBUG=True` iken kullanılır). Bu davranış `core/tests.py` içinde alt süreçle test edilir; boş string verilen env değişkenini `.env` ezmediği için `SECRET_KEY=""` hilesi kullanılır.
- **Veritabanı:** `DATABASE_URL` boşsa SQLite, doluysa `dj_database_url` ile PostgreSQL (SSL zorunlu; port `6543` Supabase transaction pooler ise server-side cursor kapatılır, `prepare_threshold=None`). Supabase yalnızca PostgreSQL olarak kullanılır; Data API ve anahtarlar projede yoktur.
- **CSP:** `config/middleware.py` her yanıta CSP + Permissions-Policy ekler. Politika `style-src 'self'` olduğu için şablonlarda inline `<script>`, `<style>`, `style=""`, `onclick=""` **yasak**; veri JS'e `data-*` ile geçer, çubuk genişliği JS ile `element.style` üzerinden ayarlanır. Gevşetme (`'unsafe-inline'` stil) yalnızca `settings.ADMIN_URL` yolu için geçerlidir. `DEBUG=True` iken Django'nun teknik 404/500 sayfaları bu CSP'ye takılır; normaldir.
- **Admin yolu** sabit değil: `ADMIN_URL` env'den gelir (`config/urls.py`), production'da `/admin/` olmamalı. Testler `settings.ADMIN_URL` kullanır.
- **`accounts.User`** (`AbstractUser` türevi): giriş alanı e-posta (`USERNAME_FIELD="email"`), `username` ayrı ve büyük/küçük harf duyarsız benzersiz (`UniqueConstraint(Lower("username"))`); `first_name`/`last_name` kaldırıldı; e-posta hem `clean()` hem `save()` içinde küçük harfe çevrilir; `__str__` her zaman kullanıcı adıdır (e-posta sızmasın diye). `UserManager.get_by_natural_key` e-postayı normalize ettiği için girişte harf büyüklüğü önemsizdir. Parola hash'i Argon2 (`PASSWORD_HASHERS` başında).
- **Hız sınırlama** (`core/ratelimit.py`): veritabanı cache'i (`kv_cache`) üzerinde sabit pencere sayacı; Vercel'de bellek içi paylaşım olmadığı için cache bellekte değil DB'de. Kurallar modülün başındaki sabitlerde (`LOGIN_IP`, `SIGNUP_IP`, …). Anahtarlarda ham IP/e-posta yok, `core/net.hash_identifier` (HMAC-SHA256) kullanılır. İki kullanım biçimi var: `hit()` her denemeyi sayar (kayıt, parola/hesap silme); giriş ise önce `is_limited()` ile bakar, yalnızca **başarısız** denemeleri `record()` ile sayar. Aşımda `rate_limited_response()` 429 döner (JSON isteğe JSON).
- **İstemci IP'si** yalnızca `core.net.get_client_ip` ile okunur: `TRUST_PROXY_IP_HEADER=True` iken `X-Forwarded-For`'un en sağdaki değeri (Vercel bu başlığı kendisi yazar), değilse `REMOTE_ADDR`. Yönlendirmelerde `next` yalnızca `core.net.get_safe_next` ile alınır (açık yönlendirme yok).
- **Hesap silme** (`accounts/views.py:delete_account`): `Vote` modeli Faz 3'te geleceği için oyları anonimleştirme kısmı `TODO(Faz 3)` olarak bırakıldı. `templates/core/privacy.html` ürünün tamamını (oy çerezi `kv_voter` dahil) anlatır; Faz 3/4'te metnin gerçeğe uyduğu tekrar kontrol edilmeli.
- **Şablonlar** `templates/` altında (proje seviyesi, `APP_DIRS` de açık). `500.html` bilerek `base.html`'den türemez: Django 500'ü bağlamsız render eder. Formlar `partials/form_field.html` / `form_errors.html` ile render edilir. Header'daki "Anket aç" bağlantısı Faz 2'de eklenecek.
- **Anket formu** (`polls/forms.py:PollForm`) Django alanlarıyla değil, aynı adlı (`option`) birden fazla input olarak çalışır; sunucu `request.POST.getlist("option")`'ı okur, boşları atar, 2–5 sınırını ve tekrarları kendisi doğrular (6. alan gönderilirse reddedilir). Şablon sabit 5 slot çizer (`form.option_slots`); JS yoksa 5'i de görünür, JS ilk 2'yi gösterip ekle/kaldır ekler. `author` formda yoktur, `form.save(author=request.user)` ile atanır. Oluşturma limiti (`POLL_CREATE_USER`) yalnızca **başarılı** kayıtlarda sayılır.
- **Yetki:** silme gibi işlemlerde sahiplik sorguda (`get_object_or_404(Poll, pk=pk, author=request.user)`) uygulanır; başkasının anketi 404 verir, var olmayan anketle aynı yanıt.
- **Akış sorgu sayısı** anket sayısından bağımsız olmalı. Tüm okuma view'ları `polls/utils.py:polls_queryset()` kullanır (yazar `select_related`, toplam oy `annotate(Count)`, seçenekler oy sayısıyla `Prefetch`). `annotate(Count)` `Meta.ordering`'i devre dışı bıraktığı için sıralama orada açıkça verilir; kaldırma. `attach_vote_state()` kullanıcının oylarını sayfa başına tek sorguyla alır (N+1 yok).
- **Oy verme** (`polls/views.py:vote`, `polls/utils.py`): `voter_key` üye için `u:<id>`, anonim için imzalı `kv_voter` çerezindeki `a:<uuid>`, silinmiş hesap için `d:<uuid>`. Tekrar oy engeli yalnızca `UniqueConstraint(poll, voter_key)`'tir; view önce kontrol etmez, `IntegrityError`'ı "zaten oy verdi" sayar (eşzamanlı istekler de böyle tek oya düşer). Bozuk/sahte çerez yok sayılır. Sonuçlar yalnızca oy vermiş kişiye ve anket sahibine gösterilir (toplam oy sayısı herkese); anket sahibi oy veremez (403). JSON yanıtında kullanıcı bilgisi/e-posta/`voter_key` yok. Hesap silmede `anonymize_votes()` oyları `user=NULL`, `voter_key="d:<uuid>"` yapar. `Vote` admin'de salt okunur ve kullanıcı/`voter_key` göstermez.
- **Oy JS'i** (`static/js/main.js`): `fetch` + `FormData(form, submitter)`; her hata/uyumsuzlukta `form.requestSubmit(submitter)` ile normal form gönderimine düşer (`data-no-ajax` döngüyü engeller). DOM'a kullanıcı metni yalnızca `textContent`/`createTextNode` ile yazılır (`polls/test_voting.py` yasaklı API'leri tarar). Çubuk genişliği `data-percent`'ten `element.style.width` ile ayarlanır (CSSOM, CSP'ye takılmaz).
- **Uygulamalar:** `accounts` (kullanıcı), `polls` (anket/seçenek/oy; Faz 0'da yalnızca boş akış view'ı), `core` (ortak yardımcılar: `net.py`, `ratelimit.py`, gizlilik sayfası). Oy sayıları sayaç alanında değil `Count` ile hesaplanacak; tekrar oy engeli `Vote(poll, voter_key)` benzersizlik kısıtıyla veritabanı seviyesinde (Bölüm 7).
