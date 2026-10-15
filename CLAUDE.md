# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**kararsızım**: Django ile yazılmış, kullanıcıların kararsız kaldıkları konularda anket açıp danıştığı bir web uygulaması. Ürün tanımı, veri modeli, güvenlik kuralları (Bölüm 10) ve fazlara bölünmüş geliştirme planı tek kaynakta tutulur:

@docs/Kararsizim.md

## Çalışma kuralları (özet)

- Her seferde yalnızca istenen fazı uygula; sonraki fazlara geçme. Mevcut durum: **Faz 0 tamam** (iskelet, ayarlar, CSP, `accounts.User`, tema). Sıradaki Faz 1.
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
- **Cache = veritabanı cache'i** (`kv_cache` tablosu). Vercel'de bellek içi paylaşım olmadığı için hız sınırlama bunun üzerine kurulacak (Faz 1, `core/ratelimit.py`).
- **Şablonlar** `templates/` altında (proje seviyesi, `APP_DIRS` de açık). `500.html` bilerek `base.html`'den türemez: Django 500'ü bağlamsız render eder. Header giriş durumuna bağlı bağlantıları Faz 1'de alacak; `LOGIN_URL = "accounts:login"` gibi URL isimleri henüz tanımsız olabilir (Faz 1'de eklenir).
- **Uygulamalar:** `accounts` (kullanıcı), `polls` (anket/seçenek/oy; Faz 0'da yalnızca boş akış view'ı), `core` (ortak yardımcılar; `net.py`, `ratelimit.py`, gizlilik sayfası sonraki fazlarda). Oy sayıları sayaç alanında değil `Count` ile hesaplanacak; tekrar oy engeli `Vote(poll, voter_key)` benzersizlik kısıtıyla veritabanı seviyesinde (Bölüm 7).
