# İlerleme notları ve kaldığımız yer

Son güncelleme: **2026-10-16**. Yeni bir oturumda önce `CLAUDE.md`'yi, sonra bu dosyayı oku. Gizli bilgiler (parola, anahtar, bağlantı adresi) bu dosyada **yoktur**.

## Özet

Uygulama (Faz 0–5) kodlanmış, testli ve **canlıda çalışıyor**. Site **herkese açık canlı** (arkadaş testi): Vercel koruması yalnızca preview'larda, davet kodu yok, noindex açık. Sıradaki iş **akrabalarla kapalı test** için hazırlık (süper kullanıcı, korumayı gevşetme).

| | |
|---|---|
| Canlı adres | https://kararsizim-blush.vercel.app (Vercel Authentication açık) |
| Vercel | takım `gader1`, proje `kararsizim` (`prj_3XxVMmlwF3ZOAZUVOftRThvB7Dho`); `master`'a her push otomatik production deploy eder |
| Supabase | proje `kararsizim`, ref `aegjryeihvhzymamuonp`, `eu-central-1`; Data API kapalı; **şu an boş** (0 kullanıcı/anket/oy) |
| GitHub | https://github.com/Voynichh/Kararsizim (`master`) |
| Son commit | `3ef2190` (vercel.json: statik dosyalara immutable verme) |
| Testler | 253 test geçiyor (`python manage.py test`, her zaman SQLite) |
| Python / Django | yerel 3.15, canlı 3.14 (`.python-version`, Vercel 3.15'i desteklemiyor) / Django 6.1 |

## Yapılanlar

- **Faz 0–3:** iskelet, güvenlik temeli, `accounts.User` (e-posta ile giriş), kayıt/giriş/hesap/parola değiştirme/hesap silme, anket oluşturma/akış/detay/silme, oy verme (üye + imzalı `kv_voter` çerezi), sonuç çubukları.
- **Faz 4:** Supabase'e geçiş (`migrate`, `createcachetable`, `secure_db`: 14 tabloda RLS, `anon`/`authenticated` erişimi 0), Vercel kurulumu, `DEPLOY.md`.
- **Faz 5:** favicon, `h1` düzeni, ≥44px dokunma alanları, Open Graph/meta, "Linki kopyala", `noindex` + `robots.txt`, **Bölüm 10 kontrol tablosu** (`docs/guvenlik-kontrol-tablosu.md`), denetim betiği `tools/prod_audit.py` (54 kontrol).
- **Güvenlik denetimi bulguları düzeltildi:** atomik hız sınırı, admin giriş sınırı, `Cache-Control`, ayar korumaları (`ALLOWED_HOSTS` boşsa, Vercel'de `DEBUG=True` veya `DATABASE_URL` yoksa uygulama başlamaz), görünmez/yön karakteri temizliği, `next` yalnızca `/...`.
- **Canlıda doğrulanan (kullanıcı + Supabase):** HTTPS yönlendirme ve HSTS, güvenlik başlıkları (CSP, Permissions-Policy, cache-control), çerezler (`sessionid`/`csrftoken`/`kv_voter` HttpOnly+Secure+Lax), temalı 404, `/admin/` 404, kayıt, anket, anonim oy (oy yenilemede kalıyor, ikinci oy yok), **hesap silme** (veri tamamen gitti), `robots.txt`, `nosniff`. Supabase Security Advisor: 0 uyarı.

## Alınan kararlar

- **E-posta altyapısı şimdilik YOK:** alan adı ve e-posta hesabı istenmiyor. Kapalı akraba testi için: **yönetici destekli parola sıfırlama** (süper kullanıcı admin panelinden geçici parola). Gerçek e-posta doğrulama + parola sıfırlama, halka açılışta (alan adı + e-posta sağlayıcısı alınınca) eklenecek. Doğrulanmamış kullanıcı: giriş yapar, **anket açamaz** (karar verildi, henüz kodlanmadı).
- **Uçtan uca şifreleme anlamlı değil** (sunucu içeriği okumalı); aktarım TLS + Supabase SSL var. Parolalar Argon2.
- Süper kullanıcı oluşturuldu. Web admin paneli **açık** (gizli `ADMIN_URL` yolunda, varsayılan). İsteğe bağlı kapatma: Vercel'de `ADMIN_ENABLED=False` + Redeploy. Panel olmadan parola sıfırlama: yerelden `python manage.py changepassword <e-posta>` (canlı DB'ye yazar). Vercel'de eskiden eklenen `ADMIN_ENABLED=True` değişkeni artık gereksiz (zararsız, silinebilir).
- Vercel çalışma ortamında `collectstatic` manifesti **yok**: statik dosya adları canlıda hash'siz, bu yüzden `vercel.json` `immutable` vermez (`must-revalidate`).

## Bekleyen / sıradaki işler (öncelik sırasıyla)

1. ~~Önbellek başlığı teyidi~~ — tamam (2026-10-16): `main.css` `must-revalidate` görünüyor; Supabase 14/14 tabloda RLS aktif.
2. ~~Davet kodu~~ — denendi ve **kaldırıldı** (2026-10-16): hesap yalnızca anket açmak için gerekiyor, oy vermek/bakmak üyelik istemiyor; arkadaş çevresi için kayıt kapısı gereksiz sürtünme bulundu. Vercel'de `SIGNUP_INVITE_CODE` değişkeni kullanıcı tarafından silinecek (kod artık okumuyor, kalması zararsız).
3. **Süper kullanıcı** oluşturma (güçlü, benzersiz parola) ve parola sıfırlama akışının dokümante edilmesi.
4. ~~Vercel korumasını gevşetme~~ — YAPILDI (2026-10-16): `ssoProtection` = `preview` (yalnızca preview'lar korumalı). Site herkese açık; `curl` ile doğrulandı (/, /kayit/ 200; /admin/ ve bilinmeyen yol 404; HSTS/CSP/nosniff/noindex başlıkları var; CSRF'siz POST 403; HTTP→HTTPS 308; geçici deploy adresleri 400). Kayıt hız sınırı IP başına 20/saat.
5. Canlıda **hız sınırı denemesi** (6 hatalı girişte 429) ve kontrol tablosundaki ⏳ maddelerinin kapatılması.
6. Kullanıcı teyitleri: GitHub'da **Dependabot** etkin mi; (isteğe bağlı) Supabase'de **SSL zorlaması**.
7. **Halka açılıştan önce:** alan adı + e-posta sağlayıcısı, e-posta doğrulama, parola sıfırlama, gizlilik metninin KVKK incelemesi, `ALLOW_SEARCH_INDEXING` kararı. İsteğe bağlı: manifestsiz `?v=<özet>` cache-busting depolaması.

## Yerel durum

- `db.sqlite3` (git dışı): `deneme_test` hesabı, 9 örnek anket, sahte yazarlar (`ayse_k`, `mehmet_y`, `zeynep_t`) ve ~460 anonim oy; giriş bilgisi `.env.devuser` (git dışı). Silmek serbest.
- `.env` (git dışı) Supabase **Session pooler (5432)** adresini içerir: `migrate`, `secure_db`, `createsuperuser` gibi komutlar **canlı veritabanına** yazar. `manage.py test` ise `.env`'deki `DATABASE_URL`'i yok sayar (SQLite).
- Çalışan yerel sunucu yok. Önizleme için geçici dosyalar proje dışındaki scratchpad'de (`preview_settings.py`); gerekirse yeniden oluşturulur, repoda yok.

## Hatırlanması gereken tuzaklar

- **PowerShell boş ortam değişkenini siler** (`$env:DATABASE_URL=""` değişkeni kaldırır, `.env`'deki Supabase adresi yüklenir). Veritabanını boşaltmak gereken komutlarda **Git Bash** kullan: `DATABASE_URL="" python ...`. `tools/prod_audit.py` ve duman testleri bunu `assert connection.vendor` ile korur.
- Komut yolları Git Bash ve PowerShell'de çalışsın diye `./.venv/Scripts/python.exe` biçiminde yazılır.
- Kod değişikliği: `git push` → Vercel otomatik deploy. **Ortam değişkeni** değişikliği: Vercel'de Redeploy. **Şema değişikliği:** yerelden `migrate` + `secure_db`, sonra push.
- `ALLOWED_HOSTS`/`CSRF_TRUSTED_ORIGINS` canlı adrese (`kararsizim-blush.vercel.app`) göre yazılı olmalı (Vercel proje adından farklı bir adres verebilir).
- Vercel MCP bağlantısı proje meta verisini okur ama **logları ve korumalı adresi okuyamaz** (403); gerekirse bağlantı "Gader" ekibi için yeniden yetkilendirilir, aksi halde kullanıcıdan ekran görüntüsü/log satırı istenir.
- Commit/push yalnızca kullanıcı isteyince yapılır; her commit öncesi gizli bilgi taraması (veritabanı parolası, anahtar kalıpları) çalıştırılır.
