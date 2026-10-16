# kararsızım — Canlıya alma (Supabase + Vercel)

Bu belge uygulamayı **Supabase PostgreSQL** ve **Vercel** üzerinde güvenli şekilde yayınlama adımlarını anlatır. Gizli bilgiler (veritabanı parolası, `SECRET_KEY`, bağlantı adresleri) hiçbir zaman repoya, sohbete veya log'a yazılmaz; yalnızca yerel `.env` (git dışı) ve Vercel ortam değişkenlerinde bulunur.

## Nasıl çalışır

- Uygulama veritabanına **yalnızca Django üzerinden**, sunucu tarafında bağlanır. Supabase Auth/Storage/Realtime ve **Data API (REST/GraphQL) kullanılmaz**; `anon` / `service_role` anahtarları projede yoktur.
- **Vercel** `manage.py`'yi bulup `config.wsgi.application`'ı çalıştırır, `STATIC_ROOT` tanımlı olduğu için `collectstatic`'i kendisi çalıştırır ve statik dosyaları CDN'den sunar. `vercel.json` gerekmez. ([Vercel Django dokümanı](https://vercel.com/docs/frameworks/full-stack/django))
- **Python sürümü:** Vercel yalnızca 3.12 (varsayılan), 3.13 ve 3.14'ü destekler; 3.15 yoktur ve desteklenmeyen sürümde sessizce 3.12'ye düşer. Bu yüzden `.python-version` = `3.14` (yerelde 3.15 kullanılabilir, kod uyumludur; `core/test_db_security.py` bu dosyanın desteklenen bir sürümde kalmasını denetler).
- **İki farklı bağlantı adresi** kullanılır:

  | Nerede | Adres | Neden |
  |---|---|---|
  | Vercel (çalışan uygulama) | **Transaction pooler**, port `6543` | Sunucusuz, kısa ömürlü bağlantılar. Vercel yalnızca IPv4'tür; doğrudan bağlantı (`db.<ref>.supabase.co`) IPv6'dır ve çalışmaz. Prepared statement'lar kapatılır (otomatik). |
  | Yerel makine (migration vb.) | **Session pooler**, port `5432` | Migration'lar transaction pooler'da güvenilir çalışmaz. Session pooler IPv4'tür; ev ağın IPv6 desteklemese de çalışır. |

- Migration'lar **build sırasında değil**, yerelden çalıştırılır.

---

## 1. Supabase (bir kez)

Proje: **kararsizim** (Gader organizasyonu, `eu-central-1`). Yoksa yeni proje aç.

1. **Veritabanı parolasını belirle:** Dashboard → *Project Settings → Database → Reset database password*. Güçlü ve rastgele olsun (*Generate password* düğmesi). **Yalnızca harf ve rakam** içermesi önerilir; `@ : / ? # &` gibi karakterler bağlantı adresinde % ile kodlanmak zorundadır. Parolayı bir parola yöneticisine kaydet; sohbete/repoya yazma.
2. **Data API'yi kapat:** Dashboard → *Project Settings → API* → **Data API Settings** → *Enable Data API* **kapalı**. ([Supabase: Hardening the Data API](https://supabase.com/docs/guides/database/hardening-data-api)) Bu uygulama o API'yi hiç kullanmaz; `django_session` ve `accounts_user` (e-posta + parola hash'i) gibi tablolar bu şemadadır.
3. **Bağlantı adreslerini al:** Dashboard → üstteki **Connect** düğmesi:
   - **Session pooler** (port `5432`) → yerel `.env` için
   - **Transaction pooler** (port `6543`) → Vercel için

   İkisinde de `[YOUR-PASSWORD]` yerine 1. adımdaki parolayı yaz. Kullanıcı adı `postgres.<proje-ref>` biçimindedir; adresi olduğu gibi kopyala (host `aws-0-…` veya `aws-1-…` olabilir, tahmin etme).

## 2. Yerelden ilk kurulum (bir kez, sonra yeni migration'larda)

Yerel `.env` dosyana **session pooler** adresini yaz (dosya git'e girmez):

```
DATABASE_URL=postgresql://postgres.<proje-ref>:<PAROLA>@aws-0-<bolge>.pooler.supabase.com:5432/postgres
```

Sonra sırasıyla (Windows'ta `.venv\Scripts\python.exe`, aşağıda kısaca `python`):

```bash
python manage.py migrate          # tablolar + anon/authenticated yetkilerini kaldıran core migration'ı
python manage.py createcachetable # hız sınırlama için DB cache tablosu (kv_cache)
python manage.py secure_db        # tüm tablolarda RLS'i açar; yetkileri yeniden uygular (idempotent)
python manage.py createsuperuser  # e-posta + kullanıcı adı + güçlü ve benzersiz parola
```

`secure_db` her tablo eklendiğinde (`migrate` sonrası) yeniden çalıştırılmalıdır; `kv_cache` gibi Django dışı yollarla oluşan tablolar da kapsanır. Komut RLS'siz tablo kalırsa hata verir.

> `.env`'yi işin bitince tekrar SQLite'a döndürmek istersen `DATABASE_URL=` satırını boşalt.

## 3. Vercel

1. GitHub reposunu (`Voynichh/Kararsizim`) **Import** et. Framework otomatik **Django** algılanır; build/output ayarlarına dokunma. Proje adını `kararsizim` yaparsan adres `kararsizim.vercel.app` olur (alınmışsa `ALLOWED_HOSTS`'u gerçek adrese göre yaz).
2. *Settings → Environment Variables*: aşağıdakileri ekle. Hepsini **Sensitive** işaretle.

   **Production** ortamı (yalnızca Production seçili):

   | Değişken | Değer |
   |---|---|
   | `SECRET_KEY` | Yeni ve güçlü: `python -c "import secrets; print(secrets.token_urlsafe(64))"` (yereldekinden farklı) |
   | `DEBUG` | `False` |
   | `ALLOWED_HOSTS` | `kararsizim.vercel.app` (özel alan adı eklenirse virgülle ekle) |
   | `CSRF_TRUSTED_ORIGINS` | `https://kararsizim.vercel.app` |
   | `DATABASE_URL` | **Transaction pooler** adresi (port `6543`) |
   | `ADMIN_URL` | Tahmin edilemez: `python -c "import secrets; print('yonetim-' + secrets.token_urlsafe(12) + '/')"` |
   | `TRUST_PROXY_IP_HEADER` | `True` |

   **Preview** ortamı: hiçbir değişken **verme**. Uygulama Vercel'de `DATABASE_URL` yoksa bilerek başlamayı reddeder (SQLite'a düşmez), yani preview deployment'lar derlenemez/çalışmaz; bu istenen davranıştır (preview'lar production veritabanına asla bağlanmamalı ve içerik sunmamalı). Yalnızca `master` dalına push edildiği sürece zaten preview oluşmaz.

   **Adres notu:** Vercel `<proje-adı>.vercel.app` adresini vermeyebilir (başkası almışsa `kararsizim-ruddy.vercel.app` gibi ek getirir). İlk deploy'dan sonra gerçek adresi *Project → Domains* sayfasından oku ve `ALLOWED_HOSTS` / `CSRF_TRUSTED_ORIGINS` değerlerini ona göre yaz. `ALLOWED_HOSTS` boşsa uygulama artık sessizce 400 vermez, açık bir hatayla başlamaz (build logunda görünür).

   **Vercel Authentication:** Vercel, özel alan adı olmayan tüm adresleri (production dahil) varsayılan olarak Vercel girişiyle korur. Bu, siteyi doğrulayana kadar iyi bir şeydir; herkese açmak için *Settings → Deployment Protection* ayarını bilerek gevşetirsin.
3. *Settings → Deployment Protection*: **Standard Protection** (veya daha sıkısı) açık olsun; preview adreslerine yalnızca oturum açmış ekip erişebilsin.
4. *Deploy* et. Değişkenleri deploy'dan sonra eklediysen **Redeploy** gerekir.

## 4. Canlı doğrulama listesi

- [ ] `https://kararsizim.vercel.app/` açılıyor; CSS/JS yükleniyor; tarayıcı konsolunda CSP ihlali yok.
- [ ] Kayıt → anket açma → (başka tarayıcıdan) oy verme → hesap silme çalışıyor.
- [ ] `http://…` adresi HTTPS'e yönleniyor; yanıtta `Strict-Transport-Security` var; çerezler `Secure`:
  ```bash
  curl -sI http://kararsizim.vercel.app/ | head -n 5
  curl -sI https://kararsizim.vercel.app/ | grep -i -E "strict-transport|content-security|x-frame"
  ```
- [ ] `/admin/` **404** veriyor; admin yalnızca `ADMIN_URL` yolunda açılıyor.
- [ ] Rastgele bir adres (`/yok/`) Django debug ekranı değil, yalnızca "Aradığın sayfayı bulamadık." diyen temalı 404 gösteriyor (adres listesi, `admin/`, ayar veya hata detayı görünmemeli). Vercel'de `DEBUG` yanlışlıkla `True` kalırsa uygulama zaten başlamaz (`DEBUG=True Vercel'de kullanılamaz` hatası; Vercel → Deployments → build/runtime loglarında görünür).
- [ ] **Data API kapalı:** aşağıdaki istek veri döndürmemeli (hata veya 4xx beklenir):
  ```bash
  curl -s -i "https://<proje-ref>.supabase.co/rest/v1/accounts_user?select=*"
  ```
- [ ] Supabase *Advisors → Security Advisor* uyarısız.
- [ ] Preview deployment'a oturumsuz erişilemiyor (Deployment Protection).

## 5. Sonraki deploy'lar

Yeni migration içeren bir değişiklik canlıya çıkacaksa **önce** yerelden (session pooler ile) çalıştır, **sonra** push et:

```bash
python manage.py migrate
python manage.py secure_db
git push
```

Migration içermeyen değişiklikler için yalnızca `git push` yeterlidir. Bağımlılık güncellemelerinde `pip-audit -r requirements.txt` çalıştır.

## 6. Sorun giderme

| Belirti | Olası neden / çözüm |
|---|---|
| `400 Bad Request` (DisallowedHost) | `ALLOWED_HOSTS` gerçek alan adını içermiyor. |
| Form gönderiminde `403 CSRF` | `CSRF_TRUSTED_ORIGINS` `https://…` biçiminde alan adını içermeli. |
| `prepared statement … does not exist` | Transaction pooler'a bağlanırken `prepare_threshold` kapalı olmalı; adres port `6543` ise `settings.py` bunu otomatik yapar. Port'u kontrol et. |
| Yerelden `network is unreachable` / zaman aşımı | Doğrudan bağlantı (`db.<ref>.supabase.co`) IPv6'dır; **Session pooler** adresini kullan. |
| `password authentication failed` | Parolada özel karakter varsa % ile kodla ya da yalnızca harf/rakam içeren yeni parola belirle. |
| Girişte herkes aynı hız sınırına takılıyor | `TRUST_PROXY_IP_HEADER=True` değil; Vercel'de bu değişken tanımlı olmalı. |
| `ImproperlyConfigured: SECRET_KEY` | İlgili ortamda (Production/Preview) `SECRET_KEY` tanımlı değil. |
| `ImproperlyConfigured: ALLOWED_HOSTS` | `ALLOWED_HOSTS` tanımlı değil; canlı adresi yaz. |
| `ImproperlyConfigured: Vercel'de DATABASE_URL` | Production'da `DATABASE_URL` (Transaction pooler) eksik. |
| Vercel'in kendi "404: NOT_FOUND" sayfası | İstek uygulamaya hiç ulaşmamış demektir (Django 404'ü değil). *Deployments → ilgili deploy → Build Logs* ve *Runtime Logs*'a bak; Python/giriş noktası algılanmamış olabilir (`config/wsgi.py` ve `WSGI_APPLICATION` kontrol edilir). |

## Supabase loglarında görebileceğin normal "error" kayıtları

Dashboard'daki *Logs → Postgres* ekranında ERROR sayısının yüksek görünmesi tek başına bir sorun işareti değildir. Beklenen, zararsız olanlar:

| Kayıt | Anlamı |
|---|---|
| `schema "pg_pgrst_no_exposed_schemas" does not exist` (PostgREST, yarım dakikada bir) | Data API kapalı; PostgREST'in boş şema ayarını denemesi. Veri erişimi yok. |
| `relation "realtime.…" does not exist`, `terminating connection due to administrator command` | Proje oluşturulurken ilk kurulum/yeniden başlatma (yalnızca ilk dakikalarda). |
| `duplicate key value violates unique constraint "polls_vote_poll_voter_unique"` | Aynı kişinin ikinci oy denemesi; kısıt görevini yapıyor, uygulama bunu "zaten oy verdin" diye ele alır. |

Şunları görürsen incele: `permission denied`, `password authentication failed`, `too many connections`, sürekli tekrarlayan başka bir uygulama hatası. (`kv_cache_pkey` "duplicate key" kayıtları artık oluşmaz; hız sınırlayıcı düzeltildi.)

## Testler gerçek veritabanına bağlanmaz

`python manage.py test` komutu `.env`'deki `DATABASE_URL`'i **yok sayar** ve SQLite kullanır; bu yüzden yerel `.env`'de Supabase adresi dururken testleri güvenle çalıştırabilirsin. Testleri bilerek başka bir PostgreSQL'de çalıştırmak istersen `TEST_DATABASE_URL` ver.

## `check --deploy` notu

`python manage.py check --deploy` (production benzeri ortam değişkenleriyle) yalnızca şu iki uyarıyı verir, ikisi de bilinçlidir: `security.W005` (HSTS `includeSubDomains`) ve `security.W021` (HSTS `preload`). Özel alan adı alındığında yeniden değerlendirilecek.
