# Güvenlik ve veri gizliliği kontrol tablosu (Bölüm 10)

Son gözden geçirme: **2026-10-16**. Kanıtlar repodaki dosya ve testlere, canlı doğrulamalar Vercel/Supabase kontrollerine dayanır.

**Durum işaretleri:** ✅ tamam (otomatik testle korunuyor) · ✅c canlıda doğrulandı · ⚠️ kısmen / senin yapacağın bir adım var · ⏳ henüz doğrulanmadı

Testleri çalıştırmak: `python manage.py test` (her zaman yerel SQLite). Canlı ayarlı kara kutu denetimi: `tools/prod_audit.py` (54 kontrol, dosyanın başında nasıl çalıştırılacağı yazıyor).

## 10.1 Kimlik doğrulama ve parolalar

| Madde | Durum | Kanıt |
|---|---|---|
| `Argon2PasswordHasher` listenin başında | ✅ | `config/settings.py`; `accounts/tests.py` (parola `argon2` ile başlıyor), `core/tests.py::SettingsSafetyTests` |
| Doğrulayıcılar: benzerlik, **min. 10 karakter**, yaygın liste, sayısal değil; Türkçe mesaj | ✅ | `config/settings.py`; `accounts/tests.py::PasswordPolicyTests`, `accounts/test_auth.py::SignupTests` |
| Parola log'lanmaz, e-postalanmaz, şablona geri basılmaz | ✅ | `test_password_is_never_rendered_back`, `test_passwords_not_rendered_back`, `test_password_not_rendered_back_on_failure`; uygulama hiçbir e-posta göndermez; `tools/prod_audit.py` log taraması |
| Girişte oturum anahtarı yenilenir | ✅ | `accounts/test_auth.py::LoginTests.test_login_cycles_session_key` |
| Çıkış ve hesap silme yalnızca POST | ✅ | `LogoutTests`, `DeleteAccountTests.test_get_shows_confirmation_and_does_not_delete` |

## 10.2 Hız sınırlama

| Madde | Durum | Kanıt |
|---|---|---|
| Giriş (IP 10/15 dk, e-posta 5/15 dk), kayıt (20/saat), parola/hesap silme (5/15 dk), anket (10/saat), oy (30/dk), **admin girişi** | ✅ | `core/ratelimit.py`; `accounts/test_auth.py`, `polls/tests.py`, `polls/test_voting.py`, `core/test_hardening.py::AdminLoginRateLimitTests` |
| **Atomik** sayaç (aynı anda gelen istekler limiti aşamaz) | ✅ | `core/test_net_ratelimit.py::test_concurrent_requests_cannot_exceed_the_limit`, `core/test_hardening.py::LoginConcurrencyTests` |
| Cache anahtarlarında ham IP/e-posta yok (HMAC-SHA256), süresi pencere sonunda dolar | ✅ | `core/net.py::hash_identifier`; `test_cache_keys_contain_no_raw_ip_or_email`, `test_slots_expire_at_window_end_...` |
| 429 temalı sayfa, JSON isteğe JSON | ✅ | `templates/429.html`; `test_json_clients_get_json_429` |
| İstemci IP'si tek fonksiyondan; başlığa körü körüne güvenilmez | ✅ | `core/net.py::get_client_ip` (Vercel `X-Forwarded-For`'u kendisi yazar, en sağdaki değer alınır); `core/test_net_ratelimit.py::ClientIpTests` |
| Canlıda gerçek IP ile sınırın çalışması | ⏳ | Önerilen deneme: canlıda gizli pencerede 6 kez yanlış parolayla giriş dene, 6. denemede 429 beklenir |

## 10.3 Django güvenlik ayarları

| Madde | Durum | Kanıt |
|---|---|---|
| Çerezler HttpOnly + SameSite=Lax, oturum 14 gün | ✅ ✅c | `config/settings.py`; `tools/prod_audit.py`; canlıda `sessionid`/`csrftoken`/`kv_voter` HttpOnly ✓ Secure ✓ Lax ✓ (kullanıcı doğruladı) |
| `X_FRAME_OPTIONS=DENY`, nosniff, `Referrer-Policy=same-origin`, COOP | ✅ | `core/tests.py::SecurityHeadersTests`; `tools/prod_audit.py` |
| İstek gövdesi sınırlı, dosya yükleme yok | ✅ | `DATA_UPLOAD_MAX_MEMORY_SIZE`; hiçbir formda dosya alanı yok |
| Production: SSL yönlendirme, `X-Forwarded-Proto`, Secure çerezler, HSTS 1 yıl | ✅ ✅c | `core/test_production_settings.py` (alt süreçle `DEBUG=False`); canlıda `http→https` ve `strict-transport-security: max-age=31536000` doğrulandı |
| `ALLOWED_HOSTS`/`CSRF_TRUSTED_ORIGINS` ortam değişkeninden, joker yok | ✅ ✅c | `config/settings.py` (boşsa uygulama başlamaz); Vercel'de ayarlı |
| `check --deploy` uyarısız (gerekçeli istisnalar hariç) | ✅ | Yalnızca `W005` (HSTS includeSubDomains) ve `W021` (preload) var, ikisi bilinçli kapalı (özel alan adı alınınca yeniden değerlendirilecek) |
| `SECRET_KEY` yoksa ve `DEBUG=False` ise başlamaz; `DEBUG` varsayılan False | ✅ | `core/tests.py::SettingsSafetyTests` |
| Vercel'de `DEBUG=True` ya da `DATABASE_URL` yok ise başlamaz | ✅ | `core/test_production_settings.py` |

## 10.4 Güvenlik başlıkları ve CSP

| Madde | Durum | Kanıt |
|---|---|---|
| CSP + Permissions-Policy her yanıtta | ✅ ✅c | `config/middleware.py`; canlı yanıt başlıkları birebir doğrulandı (CSP, `permissions-policy: camera=(), microphone=(), geolocation=(), payment=()`) |
| Şablonlarda inline script/style/`style=`/`onclick=` yok | ✅ | `polls/test_voting.py::JavaScriptSafetyTests`; canlı konsolda CSP ihlali yok |
| Admin için gevşetme yalnızca admin yolunda (yalnızca stil) | ✅ | `core/tests.py::test_csp_relaxation_applies_only_to_admin` |
| Statik dosya yanıtlarında başlıklar (`nosniff`, CORP, sandbox CSP) | ✅c | `vercel.json`; canlıda `x-content-type-options: nosniff` doğrulandı (kullanıcı, 2026-10-16) |
| Statik dosyalarda hash'li adlar (cache-busting) | ⚠️ | `config/storage.py` yerelde hash'li adlar üretir, ama **Vercel çalışma ortamında manifest yok**: canlıda dosya adları hash'siz geldi (depolama çökmeden hash'siz adrese düşüyor). Bu yüzden `immutable` bilerek verilmiyor; `max-age=0, must-revalidate` ile eski dosya kalmaz. Gerçek cache-busting için manifestsiz `?v=<özet>` depolaması ileride eklenebilir |
| Konsoldaki sarı "Permissions-Policy" uyarıları | ✅c | Bizim başlığımızda değil: uyarılar tarayıcının tanımadığı Privacy Sandbox özelliklerini (`browsing-topics` vb.) anlatıyor, bizim başlığımız yalnızca `camera/microphone/geolocation/payment` içerir; kaynak Vercel/tarayıcı tarafı, zararsız |

## 10.5 XSS, injection ve yetkilendirme

| Madde | Durum | Kanıt |
|---|---|---|
| Otomatik kaçış açık; `\|safe`, `mark_safe`, `autoescape off` yok | ✅ | `JavaScriptSafetyTests.test_templates_have_no_inline_handlers_or_styles` şablonları tarar |
| Soru/seçenek/anket başlığı/OG etiketleri kaçışlanır | ✅ | `polls/tests.py::FeedTests.test_xss_...`, `polls/test_voting.py`, `core/test_static_and_meta.py::OpenGraphTests` |
| Yalnızca ORM; ham SQL yok (tek istisna: sabit rol adlarıyla DDL) | ✅ | `core/db_security.py` yalnızca sabit `anon`/`authenticated` ve `quote_name` kullanır; `test_only_known_roles_are_accepted` |
| Yetki sorgu seviyesinde, başkasının anketi 404 (var olmayanla aynı yanıt) | ✅ | `polls/tests.py::DeletePollTests`, `core/tests.py::test_error_pages_do_not_reveal_which_urls_exist` |
| `next` doğrulaması, açık yönlendirme yok (yalnızca `/...` yolları) | ✅ | `core/test_net_ratelimit.py::SafeNextTests`; `tools/prod_audit.py` (9 kötü örnek) |
| Tüm POST'lar CSRF korumalı, `csrf_exempt` yok | ✅ | Her uç noktanın `..._requires_csrf_token` testi |
| Formlar açık alan listesiyle (`__all__` yok) | ✅ | Tüm formlar `forms.Form`, `author` istekten okunmaz (`test_author_comes_from_session_not_request`) |
| Anket metninde görünmez/yön değiştiren karakterler temizlenir | ✅ | `core/test_hardening.py::TextNormalizationTests` |

## 10.6 Veri gizliliği ve en aza indirme

| Madde | Durum | Kanıt |
|---|---|---|
| Yalnızca e-posta, kullanıcı adı, parola özeti, anket, oy, tarihler saklanır; IP kalıcı saklanmaz | ✅ | `accounts/models.py`, `core/ratelimit.py` (yalnızca HMAC özeti, pencere sonunda silinir) |
| E-posta yalnızca `/hesap/`'ta sahibine görünür (sayfalar, JSON, hata, log) | ✅ | `accounts/test_auth.py::HeaderAndPrivacyTests`; `tools/prod_audit.py` 4 farklı kullanıcı gözüyle tüm sayfaları tarar |
| Hesap hangi yolla silinirse silinsin (site, admin paneli, toplu silme) oylar kişiyle bağsız kalır (`user=NULL`, `voter_key=d:<uuid>`) | ✅ | `accounts/signals.py` (`pre_delete`); `polls/test_voting.py::AccountDeletionVoteTests` (ORM, queryset ve admin silme testleri) |
| Canlı güncelleme uçları (`/anket/sonuclar/`, `/anket/kartlar/`) oy gizliliğini bozmaz: seçenek sonuçları yalnızca oy vermiş kişiye/anket sahibine, yanıtta kimlik/`voter_key` yok, `no-store`, en fazla 20 id, XSS kaçışlı | ✅ | `polls/test_voting.py::LiveResultsTests`, `FeedLiveUpdateTests` |
| Kimin neye oy verdiği hiçbir kullanıcıya gösterilmez; JSON'da `voter_key` yok | ✅ | `polls/test_voting.py::VisibilityTests`, `JsonResponseTests`; admin'de de gizli (`AdminVoteTests`) |
| Çerezler yalnızca zorunlu olanlar (oturum, CSRF, `kv_voter`); izleme/harici istek yok | ✅ | `templates/core/privacy.html`; CSP `default-src 'self'` |
| `/gizlilik/` sade Türkçe, güncel | ✅ ⚠️ | Hukuki gözden geçirme (KVKK) gerçek kullanıcıya açmadan önce **senin/uzmanın yapacağı** adım |
| Log'larda kişisel veri/parola/çerez yok | ✅ | `tools/prod_audit.py` log yakalama kontrolü |
| Üretimde hata detayı gösterilmez | ✅ ✅c | `core/tests.py::test_404_pages_leak_no_internals`; canlıda rastgele adres temalı 404 |
| Arama motorları prototipi indekslemez | ✅ | `X-Robots-Tag: noindex, nofollow` + `robots.txt` (`ALLOW_SEARCH_INDEXING=False`), `core/test_static_and_meta.py::SearchIndexingTests` |

## 10.7 Supabase güvenliği

| Madde | Durum | Kanıt |
|---|---|---|
| 1. Data API kapalı | ✅c | Dashboard'dan kapatıldı; PostgREST'in "açık şema yok" kaydı (`pg_pgrst_no_exposed_schemas`) bunu destekliyor |
| 2. `anon`/`authenticated` yetkileri kaldırıldı | ✅ ✅c | `core/migrations/0001_revoke_supabase_api_access.py`; canlı sorgu: `anon` 0/14, `authenticated` 0/14 tabloda erişim |
| 3. Tüm tablolarda RLS (`secure_db`, idempotent) | ✅ ✅c | `core/management/commands/secure_db.py`; canlı sorgu: 14/14 tabloda RLS açık |
| 4. Security Advisor uyarısız | ✅c | 0 uyarı, 0 hata; 14 adet INFO ("RLS açık, politika yok" = bilinçli, tablolar kilitli) |
| 5. Veritabanı parolası güçlü ve yalnızca Vercel + yerel `.env`'de | ✅ | Taramalar (her commit öncesi) parolanın repoda olmadığını doğruladı |
| 6. `anon`/`service_role` anahtarları projede yok | ✅ | `core/test_db_security.py::test_no_supabase_keys_in_project` |
| Ek: Postgres'te SSL zorlaması (sunucu tarafı) | ⚠️ | İsteğe bağlı, dashboard'dan açılır (uygulama zaten `sslmode=require` ile bağlanıyor) |

## 10.8 Vercel güvenliği

| Madde | Durum | Kanıt |
|---|---|---|
| Ortam değişkenleri **Sensitive** | ✅c | Vercel API: 7 değişkenin tamamı `type: sensitive` |
| `SECRET_KEY`/`DATABASE_URL` yalnızca **Production** | ✅c | Vercel API: hepsi `target: production` |
| Preview deployment production veritabanına erişemez | ✅ ✅c | Preview ortamına değişken tanımlı değil; Vercel'de `DATABASE_URL` yoksa uygulama zaten başlamaz (`core/test_production_settings.py`) |
| Deployment Protection | ✅c | Vercel API: `ssoProtection` açık (özel alan adı yokken production dahil) |
| `ADMIN_URL` tahmin edilemez, `/admin/` 404 | ✅c | Canlıda `/admin/` 404 (kullanıcı doğruladı) |
| Üretimde panel açıkken `ADMIN_URL` boş/`admin/` ise uygulama başlamaz (yanlış yapılandırmada panel tahmin edilebilir yolda açılmaz) | ✅ | `config/settings.py`; `core/test_production_settings.py::AdminUrlGuardTests` |
| Yönetici/resmi hesap gibi görünen kullanıcı adları kayıtta alınamaz (taklit önlemi) | ✅ | `accounts/models.py:is_reserved_username`; `accounts/test_auth.py::ReservedUsernameTests` |
| Gizlilik metni: yönetici e-postayı görebilir, üyenin oyu veritabanında hesapla eşleşik, Vercel IP'yi loglayabilir | ✅ | `templates/core/privacy.html`; `accounts/test_auth.py` |
| Admin yalnızca gizli `ADMIN_URL` yolunda; `ADMIN_ENABLED=False` ile tamamen kapatılabilir (yol hiç kayıtlı değil, 404) | ✅ | `config/urls.py`; `core/test_production_settings.py::AdminSwitchTests` |
| Süper kullanıcı parolası güçlü ve benzersiz | ⏳ | Henüz süper kullanıcı oluşturulmadı; oluşturulunca güçlü parola seçilmeli |

## 10.9 Bağımlılık ve kod hijyeni

| Madde | Durum | Kanıt |
|---|---|---|
| Sürümler `==` ile sabit | ✅ | `core/test_db_security.py::test_requirements_are_exactly_pinned` |
| Dependabot | ⚠️ | `.github/dependabot.yml` repoda; GitHub → Settings → Code security'de etkin olduğunu **senin** teyit etmen gerekir |
| `pip-audit` temiz | ✅ | 2026-10-16: bilinen açık yok |
| `.gitignore` (`.env`, `.env.*`, `db.sqlite3`, `staticfiles/`, `.venv/` …) | ✅ | `core/test_db_security.py::test_no_secrets_or_local_files_are_committable` |
| Commit öncesi gizli bilgi taraması | ✅ | Her commit'te yapıldı (veritabanı parolası, anahtar kalıpları) |

## Faz 5 kabul kriterleri

| Kriter | Durum | Kanıt |
|---|---|---|
| Mobilde yatay kaydırma yok, tüm butonlar ≥ 44px | ✅ | 360/768/1280px tarayıcı ölçümü (taşma yok, tüm düğme/alanlar ≥ 44px) |
| Var olmayan adreste temalı 404 | ✅c | Canlıda doğrulandı |
| Bölüm 10 tablosunda açık madde kalmadı | ⚠️ | Aşağıdaki "Açık kalanlar" |

## Açık kalanlar (hepsi senin eyleminle veya canlı denemeyle kapanır)

1. ⚠️ Statik dosyalarda canlıda hash'li ad yok (yukarıya bak); zararsız, `must-revalidate` ile güvenli.
2. ⏳ Canlıda hız sınırı denemesi (6 hatalı giriş → 429).
3. ⏳ Süper kullanıcı oluşturulurken güçlü parola.
4. ⚠️ Dependabot'un GitHub'da etkin olduğunu teyit et.
5. ⚠️ Supabase'de SSL zorlamasını aç (isteğe bağlı).
6. ⚠️ Gerçek kullanıcıya açmadan önce: gizlilik metninin KVKK açısından incelenmesi, e-posta doğrulama ve parola sıfırlama (alan adı + e-posta sağlayıcısı gerektirir).

## Bilinen, bilinçle kabul edilen sınırlar

- Çerezsiz yeni tarayıcıyla aynı ankete tekrar oy verilebilir (doküman Bölüm 7).
- Bir e-postaya 5 hatalı giriş denemesi o e-postayı 15 dakika kilitler (kaba kuvvet korumasının bedeli).
- Veritabanında `Vote.user` ve `created_at` birlikte durduğu için veritabanı yöneticisi teknik olarak hangi hesabın hangi seçeneğe oy verdiğini görebilir; uygulamada ve admin panelinde kimseye gösterilmez.
- E-posta doğrulaması ve parola sıfırlama yok: parolayı unutan kullanıcının hesabına yönetici (süper kullanıcı) müdahalesi gerekir.
