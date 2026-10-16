# İlerleme notları ve kaldığımız yer

Son güncelleme: **2026-10-16**. Yeni bir oturumda önce `CLAUDE.md`'yi, sonra bu dosyayı oku. Gizli bilgiler (parola, anahtar, bağlantı adresi, admin yolu) bu dosyada **yoktur**.

## Özet

Uygulama (Faz 0–5) kodlanmış, testli ve **canlıda çalışıyor**. Site **herkese açık** (arkadaş testi): Vercel koruması yalnızca preview'larda, davet kodu yok, `noindex` açık, kayıt serbest (hesap yalnızca anket açmak için; bakmak ve oy vermek üyelik istemez). Güvenlik incelemesi (skill: `code-review-security`) yapıldı: kritik/yüksek bulgu yok; açık kalanlar aşağıda.

| | |
|---|---|
| Canlı adres | https://kararsizim-blush.vercel.app |
| Vercel | takım `gader1`, proje `kararsizim` (`prj_3XxVMmlwF3ZOAZUVOftRThvB7Dho`); `master`'a her push otomatik production deploy eder; fonksiyon bölgesi `fra1` (veritabanıyla aynı) |
| Supabase | proje `kararsizim`, ref `aegjryeihvhzymamuonp`, `eu-central-1`; Data API kapalı (alan adı çözülmüyor); 14/14 tabloda RLS, `anon`/`authenticated` yetkisi 0 |
| GitHub | https://github.com/Voynichh/Kararsizim (`master`) |
| Testler | 298 test geçiyor (`python manage.py test`, her zaman SQLite); `tools/prod_audit.py` 54/54; `pip-audit` temiz |
| Python / Django | yerel 3.15, canlı 3.14 (`.python-version`, Vercel 3.15'i desteklemiyor) / Django 6.1 |

## Yapılanlar

- **Faz 0–3:** iskelet, güvenlik temeli, `accounts.User` (e-posta ile giriş), kayıt/giriş/hesap/parola değiştirme/hesap silme, anket oluşturma/akış/detay/silme, oy verme (üye + imzalı `kv_voter` çerezi), sonuç çubukları.
- **Faz 4:** Supabase'e geçiş (`migrate`, `createcachetable`, `secure_db`), Vercel kurulumu, `DEPLOY.md`.
- **Faz 5:** favicon, `h1` düzeni, ≥44px dokunma alanları, Open Graph/meta, "Linki kopyala", `noindex` + `robots.txt`, **Bölüm 10 kontrol tablosu** (`docs/guvenlik-kontrol-tablosu.md`), denetim betiği `tools/prod_audit.py`.
- **İlk güvenlik denetimi:** atomik hız sınırı, admin giriş sınırı, `Cache-Control`, ayar korumaları, görünmez/yön karakteri temizliği, `next` yalnızca `/...`.
- **Canlıya alındıktan sonra (2026-10-16):**
  - Davet kodu denendi ve kaldırıldı; Vercel koruması `preview`'a çekildi; kayıt hız sınırı IP başına **20/saat**.
  - **Canlı güncelleme:** sayılar, yeni açılan ve silinen anketler F5'siz yansır (uyarlanabilir yoklama: 10→30 sn, 2 dk etkileşimsizlikte durur; Vercel kotası için). Uçlar: `/anket/sonuclar/`, `/anket/kartlar/`.
  - **Hız:** fonksiyon bölgesi `iad1`→`fra1`; ana sayfa 1,2 sn → 0,27 sn.
  - **Bakım modu** (`MAINTENANCE_MODE`) ve **admin anahtarı** (`ADMIN_ENABLED`, varsayılan açık); panel olmadan parola sıfırlama: `manage.py changepassword`.
  - **Hesap silme** hangi yolla olursa olsun (site/admin/toplu) oyları anonimleştirir (`pre_delete` sinyali).
  - **İnceleme düzeltmeleri:** üretimde `ADMIN_URL` boş/`admin/` ise uygulama başlamaz; `admin`/`yonetici`/`kararsizim` gibi kullanıcı adları kayıtta alınamaz; yüzdeler toplamı hep 100; gizlilik metnine üç beyan eklendi (yönetici e-postayı görür, üyenin oyu veritabanında hesapla eşleşik, Vercel IP loglayabilir).

## Alınan kararlar

- **E-posta altyapısı şimdilik YOK:** alan adı ve e-posta hesabı istenmiyor. Parola sıfırlama yönetici destekli (panel ya da `changepassword`). Gerçek e-posta doğrulama + parola sıfırlama halka açılışta eklenecek.
- **Uçtan uca şifreleme ve sütun şifrelemesi gereksiz** (şimdilik): sunucu içeriği okumalı, e-posta giriş/bildirim için düz gerekli; koruma RLS + kapalı Data API + SSL + Argon2.
- **Admin paneli açık** (gizli `ADMIN_URL`, hız sınırlı giriş). Vercel'de `ADMIN_ENABLED=False` + Redeploy ile tamamen kapanır. Süper kullanıcı oluşturuldu; admin yolu ve parolası kullanıcıda (Vercel'de Sensitive olduğu için okunamaz).
- Vercel çalışma ortamında `collectstatic` manifesti **yok**: statik dosya adları canlıda hash'siz, bu yüzden `vercel.json` `immutable` vermez (`must-revalidate`).

## Bekleyen / sıradaki işler (öncelik sırasıyla)

1. **O1 kararı (kullanıcıdan bekleniyor):** canlı sonuçlar küçük grupta "kim neye oy verdi" çıkarımına açık (biri oy verince sayı değişiyor). Seçenekler: **A** seçenek bazlı sonuçlar toplam oy ≥5 olana kadar gizli (önerilen), **B** canlıda yalnızca toplam güncellensin, yüzdeler F5'te, **C** olduğu gibi + gizlilik metnine not. Hiçbiri zamanlama sızıntısını tamamen kapatmaz. Karar verilmeden kodlanmaz.
2. **O2 (kullanıcı, Vercel paneli):** Firewall'da okuma uçları (`/`, `/anket/sonuclar/`, `/anket/kartlar/`) için IP başına ~120 istek/dk hız sınırı kuralı (fonksiyon kotası/erişilebilirlik). Mevcut Firewall kuralları MCP'den okunamadı.
3. **Kullanıcı teyitleri:** GitHub'da **Dependabot** etkin mi; Supabase'de **SSL zorlaması** ve yedekler; Vercel/Supabase/GitHub hesaplarında **2FA**.
4. **Vercel'de gereksiz değişkenler (silinebilir, zararsız):** `SIGNUP_INVITE_CODE`, `ADMIN_ENABLED` (varsayılan zaten açık). `MAINTENANCE_MODE` `False` değerinde duruyor.
5. **Düşük bulgular (açık):** süresi dolmuş oturum/cache satırları için `clearsessions` zamanlanmadı (D4); yanlış e-postayla girişler başkasını 15 dk kilitleyebilir (D5); yönetici hesabında 2FA yok (D6).
6. **Halka açılıştan önce:** alan adı + e-posta sağlayıcısı, e-posta doğrulama (e-posta işgali, O4), parola sıfırlama, moderasyon/raporlama (O6), bot doğrulaması (anonim oy şişirme, O5), gizlilik metninin KVKK incelemesi, `ALLOW_SEARCH_INDEXING` kararı. İsteğe bağlı: manifestsiz `?v=<özet>` cache-busting depolaması.

## Yerel durum

- `db.sqlite3` (git dışı): `deneme_test` hesabı, örnek anketler, sahte yazarlar ve anonim oylar; giriş bilgisi `.env.devuser` (git dışı). Silmek serbest.
- `.env` (git dışı) Supabase **Session pooler (5432)** adresini içerir: `migrate`, `secure_db`, `createsuperuser`, `changepassword` gibi komutlar ve `.env` ile açılan `runserver` **canlı veritabanına** yazar. `manage.py test` ise `.env`'deki `DATABASE_URL`'i yok sayar (SQLite).
- Çalışan yerel sunucu yok.

## Hatırlanması gereken tuzaklar

- **PowerShell boş ortam değişkenini siler** (`$env:DATABASE_URL=""` değişkeni kaldırır, `.env`'deki Supabase adresi yüklenir). Yerel sunucu/betik için **Git Bash** kullan: `DATABASE_URL="" python ...` ve `assert connection.vendor == "sqlite"` ile doğrula.
- Komut yolları Git Bash ve PowerShell'de çalışsın diye `./.venv/Scripts/python.exe` biçiminde yazılır. Çok satırlı Python'u Bash heredoc yerine betik dosyası olarak (scratchpad) çalıştır.
- Kod değişikliği: `git push` → Vercel otomatik deploy. **Ortam değişkeni** değişikliği: Vercel'de Redeploy (ya da boş commit). **Şema değişikliği:** yerelden `migrate` + `secure_db`, sonra push.
- **Proje duraklatılmışsa (Pause) yeni deploy'lar BLOCKED olur** ve devam ettirilince otomatik yeniden denenmez; Resume'dan sonra yeni commit/Redeploy gerekir. Site duraklatılmışken `DEPLOYMENT_PAUSED` 503 verir (Vercel'in kendi sayfası, değiştirilemez; temalı sayfa için bakım modunu kullan).
- `DEBUG=False` ile ayar yükleyen testler/betikler `ADMIN_URL` vermelidir (aksi halde uygulama başlamaz).
- `ALLOWED_HOSTS`/`CSRF_TRUSTED_ORIGINS` canlı adrese (`kararsizim-blush.vercel.app`) göre yazılı olmalı; deploy'ların geçici adresleri bilerek 400 verir.
- Vercel MCP: bağlantı yetkilendirilirken **Gader** takımı seçilmelidir (aksi halde deployment/log okuma 403). Sensitive değişken değerleri okunamaz; MCP'de değişken silme aracı yok (oluşturma/düzenleme var).
- Commit/push yalnızca kullanıcı isteyince yapılır; her commit öncesi gizli bilgi taraması (veritabanı parolası, anahtar kalıpları, admin yolu) çalıştırılır.
