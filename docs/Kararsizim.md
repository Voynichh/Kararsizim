# kararsızım — Proje Rehberi

Bu dosya, Claude Code'un projeyi geliştirirken başvuracağı tek kaynak belgedir. Ürün tanımı, teknik kararlar, veri modeli, **güvenlik ve veri gizliliği kuralları**, arayüz kuralları ve fazlara bölünmüş geliştirme planı burada yer alır.

---

## 1. Claude Code için çalışma kuralları

1. **Her seferde yalnızca istenen fazı uygula.** Sonraki fazların işine başlama, "hazır olsun" diye fazladan özellik ekleme.
2. **Güvenlik kuralları (Bölüm 10) pazarlık konusu değildir.** Hız, kolaylık veya "prototip" gerekçesiyle gevşetilmez. Bir güvenlik kuralı ile başka bir istek çelişirse dur ve sor.
3. Her fazın sonunda:
   - `python manage.py test` çalıştır, testler geçmeden fazı bitmiş sayma.
   - O fazın **kabul kriterlerini** ve **güvenlik kriterlerini** madde madde kontrol et ve sonucu raporla.
   - Ne yaptığını kısaca özetle; kullanıcının elle yapması gereken bir şey varsa (ör. Supabase panelinde bir ayar) açıkça yaz.
   - Anlamlı bir git commit'i öner. Commit'lenecek dosyalarda gizli bilgi olmadığını kontrol et.
4. **Bağımlılıklar:** Yalnızca Bölüm 4'teki paketleri kullan. Başka bir paket gerekiyorsa önce gerekçesiyle sor.
5. **Dil:** Kod, değişken, fonksiyon, model ve dosya adları İngilizce; kullanıcının gördüğü tüm metinler (arayüz, hata mesajları, form etiketleri) Türkçe.
6. **Gizli bilgiler** (`SECRET_KEY`, veritabanı adresi ve parolası vb.) asla koda, commit'e, log'a veya ekrana yazılmaz; ortam değişkenlerinden okunur. `.env` git'e girmez, `.env.example` (sahte değerlerle) girer.
7. **E-posta adresleri hiçbir yerde görünmez:** şablonlarda, JSON yanıtlarında, hata mesajlarında, sayfa kaynağında, log'larda. Kullanıcı yalnızca kullanıcı adıyla temsil edilir.
8. Prototip aşamasındayız: **basit ve okunabilir çözüm** her zaman tercih edilir. Ayrı frontend framework'ü, build aracı, Celery, Redis, Docker vb. kullanılmaz. Ancak basitlik, güvenlikten ödün vermek anlamına gelmez.

---

## 2. Ürün tanımı

**kararsızım**, kullanıcıların kararsız kaldıkları konularda diğer kullanıcılara anket açıp danışabildiği bir web uygulamasıdır.

Örnek: *"Bugün sinemaya mı gitsem, restorana mı?"* — iki seçenekli bir anket açılır, diğer kullanıcılar oy verir.

### Temel kurallar

| Konu | Kural |
|---|---|
| Anket seçenekleri | En az **2**, en fazla **5** seçenek |
| Takip sistemi | **Yok.** Herkes tüm anketleri tek bir ortak akışta görür |
| Anket görüntüleme | Üye olmadan da mümkün |
| Oy verme | Üye olmadan da mümkün |
| Anket oluşturma | **Yalnızca üyeler** |
| Kayıt bilgileri | E-posta + kullanıcı adı + parola |
| Görünürlük | Anketlerde **kullanıcı adı** görünür, **e-posta asla görünmez** |
| Oy sayısı | Her ziyaretçi/üye bir ankete **bir kez** oy verebilir |
| Oy gizliliği | **Kimin neye oy verdiği hiçbir kullanıcıya gösterilmez**, anket sahibine de. Yalnızca toplam sonuçlar görünür |

### Prototip için alınan ürün kararları
(Daha sonra değiştirilebilir; şimdilik bu şekilde uygulanacak.)

- **Sonuçlar oy verdikten sonra görünür.** Oy vermeyen ziyaretçi sadece seçenekleri görür. Anket sahibi kendi anketinin sonuçlarını her zaman görebilir.
- **Oy değiştirme yok.** Verilen oy kesindir.
- Anket sahibi kendi anketini **silebilir**. Düzenleme yok.
- Anketin süresi/kapanması yok; anketler süresiz açık kalır.
- Anket sahibi kendi anketine **oy veremez**; yalnızca sonuçları görür (oy butonu gösterilmez).
- Kullanıcı **parolasını değiştirebilir** ve **hesabını silebilir** (veri üzerinde kontrol hakkı).

---

## 3. Teknik mimari

- **Backend:** Python ve Django'nun kurulum anındaki en güncel kararlı sürümleri (şu an Python 3.15 + Django 6.1). Vercel'in desteklediği Python sürümü Faz 4'te doğrulanır.
- **Şablonlar:** Django Templates (sunucu tarafında render)
- **Frontend:** Saf HTML, CSS, JavaScript. Framework yok, build adımı yok.
- **Veritabanı:** Supabase (yalnızca **PostgreSQL veritabanı** olarak). Supabase Auth, Storage, Realtime ve **Data API (REST/GraphQL) kullanılmaz**; uygulama veritabanına sadece Django üzerinden, sunucu tarafında bağlanır. Supabase'in `anon` / `service_role` anahtarları projede **hiçbir yerde** bulunmaz.
- **Geliştirme ortamı veritabanı:** `DATABASE_URL` tanımlı değilse SQLite'a düşer.
- **Deployment:** Vercel. Vercel, kök dizindeki `manage.py` üzerinden Django projesini otomatik algılar ve `STATIC_ROOT` tanımlıysa build sırasında `collectstatic` çalıştırıp statik dosyaları CDN'den sunar. Bu yüzden prototipte `vercel.json` ve WhiteNoise **gerekmez**. (Deployment fazında güncel dokümanı kontrol et: https://vercel.com/docs/frameworks/full-stack/django)

### Mimari ilkeler
- Sayfalar sunucuda render edilir. JavaScript yalnızca **ilerletici iyileştirme** içindir: JS kapalıyken de her şey normal form gönderimiyle çalışmalı.
- Oy sayıları ayrı bir sayaç alanında tutulmaz; `Count` ile hesaplanır.
- Vercel'de kalıcı dosya sistemi ve paylaşılan bellek yoktur: dosya yükleme eklenmez, SQLite production'da kullanılmaz, hız sınırlama için bellek içi cache değil **veritabanı cache'i** kullanılır.

---

## 4. Bağımlılıklar

`requirements.txt` (sürümler kurulum anındaki güncel kararlı sürümlerle **tam olarak sabitlenir**, `==` ile):

```
Django==...          # kurulumda en güncel kararlı sürüme sabitle
psycopg[binary]==3.* # kurulumda tam sürüme sabitle
dj-database-url==... 
python-dotenv==...
argon2-cffi==...     # parola hash'leme
```

`requirements-dev.txt` (yalnızca geliştirme ortamı, Vercel'e gitmez):

```
-r requirements.txt
pip-audit==...       # bağımlılıklarda bilinen açık taraması
```

- Python sürümü `.python-version` dosyasında belirtilir (şu an `3.15`).
- `.github/dependabot.yml` ile pip bağımlılıkları için haftalık güncelleme kontrolü açılır.

---

## 5. Klasör yapısı

```
kararsizim/
├── manage.py
├── requirements.txt
├── requirements-dev.txt
├── .python-version
├── .env.example
├── .gitignore
├── CLAUDE.md
├── DEPLOY.md               # Faz 4'te yazılır
├── .github/
│   └── dependabot.yml
├── config/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   ├── middleware.py       # güvenlik başlıkları (CSP vb.)
│   ├── wsgi.py
│   └── asgi.py
├── core/                   # ortak yardımcılar
│   ├── ratelimit.py        # hız sınırlama
│   ├── net.py              # istemci IP'sini güvenli okuma + hash'leme
│   └── views.py            # gizlilik sayfası, hata sayfaları
├── accounts/               # Kullanıcı modeli, kayıt, giriş, çıkış, hesap ayarları
│   ├── models.py
│   ├── forms.py
│   ├── views.py
│   ├── urls.py
│   ├── admin.py
│   └── tests.py
├── polls/                  # Anket, seçenek, oy
│   ├── models.py
│   ├── forms.py
│   ├── views.py
│   ├── urls.py
│   ├── admin.py
│   ├── utils.py            # voter_key üretimi
│   └── tests.py
├── templates/
│   ├── base.html
│   ├── 400.html, 403.html, 404.html, 500.html, 429.html
│   ├── partials/
│   │   ├── header.html
│   │   ├── messages.html
│   │   └── poll_card.html
│   ├── core/
│   │   └── privacy.html
│   ├── accounts/
│   │   ├── signup.html
│   │   ├── login.html
│   │   ├── settings.html
│   │   ├── password_change.html
│   │   └── delete_account.html
│   └── polls/
│       ├── feed.html
│       ├── detail.html
│       ├── create.html
│       └── confirm_delete.html
└── static/
    ├── css/main.css
    ├── js/main.js
```

---

## 6. Ayarlar (`config/settings.py`)

Tüm ortam bağımlı değerler ortam değişkenlerinden okunur. Yerelde `python-dotenv` ile `.env` yüklenir.

`.env.example`:

```
SECRET_KEY=yerel-gelistirme-icin-sahte-deger
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=http://localhost:8000
# Boş bırakılırsa SQLite kullanılır
DATABASE_URL=
# Admin paneli yolu (production'da tahmin edilemez bir değer kullan)
ADMIN_URL=admin/
# Sadece Vercel'de True: istemci IP'si proxy başlığından okunur
TRUST_PROXY_IP_HEADER=False
```

Genel ayarlar:

- `LANGUAGE_CODE = "tr"`, `TIME_ZONE = "Europe/Istanbul"`, `USE_TZ = True`
- `AUTH_USER_MODEL = "accounts.User"`
- `INSTALLED_APPS` içinde `django.contrib.humanize` olsun.
- `STATIC_URL = "static/"`, `STATICFILES_DIRS = [BASE_DIR / "static"]`, `STATIC_ROOT = BASE_DIR / "staticfiles"`
- `TEMPLATES["DIRS"] = [BASE_DIR / "templates"]`
- `LOGIN_URL = "accounts:login"`, `LOGIN_REDIRECT_URL = "polls:feed"`, `LOGOUT_REDIRECT_URL = "polls:feed"`
- `SECRET_KEY` ortam değişkeninde yoksa ve `DEBUG=False` ise uygulama **başlamamalı** (varsayılan bir anahtara düşmemeli).
- `DEBUG` varsayılanı `False`'tur; yalnızca açıkça `True` verilirse açılır.

Veritabanı:

```python
DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=0,
    )
}
```

- PostgreSQL ise bağlantı **SSL zorunlu** olmalı (`sslmode=require`).
- Supabase **transaction pooler** (port `6543`) için:
  - `DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = True`
  - `OPTIONS` içine `"prepare_threshold": None`

Cache (hız sınırlama için):

```python
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "kv_cache",
    }
}
```

(Tablo `python manage.py createcachetable` ile oluşturulur. Bu komut kurulum ve deploy adımlarına yazılmalı.)

Güvenlik ayarlarının tamamı Bölüm 10.3'te.

---

## 7. Veri modeli

### `accounts.User`

`AbstractUser`'dan türetilir. **Bu model ilk `migrate` komutundan önce oluşturulmalıdır.**

| Alan | Tip | Kural |
|---|---|---|
| `email` | EmailField | Zorunlu, benzersiz (büyük/küçük harf duyarsız), **giriş için kullanılır** |
| `username` | CharField | Zorunlu, benzersiz (büyük/küçük harf duyarsız), 3–20 karakter, yalnızca harf, rakam ve `_` (`^[A-Za-z0-9_]{3,20}$`) |
| `password` | — | Argon2 ile hash'lenir (Bölüm 10.1) |

- `USERNAME_FIELD = "email"`, `REQUIRED_FIELDS = ["username"]`
- E-posta kaydedilmeden önce kırpılır ve küçük harfe çevrilir.
- Kullanıcı adı yazıldığı gibi saklanır, benzersizlik `UniqueConstraint(Lower("username"))` ile.
- Kullanılmayan `first_name` / `last_name` alanları formlarda hiç yer almaz (veri en aza indirme).
- `createsuperuser` sorunsuz çalışmalı; gerekirse özel bir `UserManager` yaz.
- **Saklanan kişisel veri yalnızca:** e-posta, kullanıcı adı, parola hash'i, son giriş zamanı, kayıt tarihi. IP adresi, cihaz bilgisi vb. **kalıcı olarak saklanmaz.**

### `polls.Poll`

| Alan | Tip | Kural |
|---|---|---|
| `author` | FK → User | `on_delete=CASCADE`, `related_name="polls"` |
| `question` | CharField(200) | Zorunlu, en az 5 karakter, baş/son boşluklar kırpılır |
| `created_at` | DateTimeField | `auto_now_add=True` |

- Varsayılan sıralama: `-created_at`, bu alana index.

### `polls.Option`

| Alan | Tip | Kural |
|---|---|---|
| `poll` | FK → Poll | `on_delete=CASCADE`, `related_name="options"` |
| `text` | CharField(80) | Zorunlu, boş olamaz |
| `order` | PositiveSmallIntegerField | Gösterim sırası (0'dan başlar) |

- `UniqueConstraint(poll, order)`
- Bir ankette 2–5 seçenek bulunur (form katmanında doğrulanır).
- Aynı ankette aynı metne sahip iki seçenek olamaz (kırpılmış ve küçük harfe çevrilmiş hali karşılaştırılır).

### `polls.Vote`

| Alan | Tip | Kural |
|---|---|---|
| `poll` | FK → Poll | `on_delete=CASCADE`, `related_name="votes"` |
| `option` | FK → Option | `on_delete=CASCADE`, `related_name="votes"` |
| `user` | FK → User | `null=True, blank=True`, `on_delete=SET_NULL` |
| `voter_key` | CharField(64) | Oy veren kişinin kimliği (aşağıya bak) |
| `created_at` | DateTimeField | `auto_now_add=True` |

- `UniqueConstraint(poll, voter_key)` → aynı kişi aynı ankete ikinci kez oy veremez (veritabanı seviyesinde garanti).
- Kaydetmeden önce `option.poll_id == poll_id` kontrol edilir.

### Tekrar oy vermeyi engelleme: `voter_key`

- **Üye ise:** `voter_key = f"u:{user.pk}"`
- **Anonim ise:** `voter_key = f"a:{uuid4}"`. Bu UUID, `kv_voter` adlı **imzalı** bir çerezde (`set_signed_cookie`, kendine özgü `salt` ile) saklanır: `httponly=True`, `samesite="Lax"`, `secure=True` (production), ömrü 1 yıl. Çerez yoksa ilk oy anında oluşturulur. İmzası bozuk veya geçersiz bir çerez gelirse yok sayılır ve yeni anahtar üretilir.
- **Hesap silindiğinde** kullanıcının diğer anketlere verdiği oylar sayımda kalır ama kişiyle bağı koparılır: `user=NULL` ve `voter_key = f"d:{uuid4}"` olarak güncellenir.
- Yardımcı fonksiyonlar `polls/utils.py` içinde.

**Bilinen prototip sınırlamaları** (kabul edilmiştir):
- Anonim kullanıcı çerezlerini silerse veya gizli sekme açarsa tekrar oy verebilir (IP bazlı hız sınırı bunu yavaşlatır ama tamamen engellemez).
- Anonim oy veren biri sonradan giriş yaparsa aynı ankete üye olarak bir kez daha oy verebilir.

---

## 8. Sayfalar ve URL'ler

| URL | View | Erişim | Açıklama |
|---|---|---|---|
| `/` | `polls:feed` | Herkes | Tüm anketlerin akışı, en yeni üstte, sayfa başına 20 anket (`?page=`) |
| `/anket/<int:pk>/` | `polls:detail` | Herkes | Tek anketin sayfası |
| `/anket/yeni/` | `polls:create` | Sadece üyeler | Anket oluşturma formu |
| `/anket/<int:pk>/oy/` | `polls:vote` | Herkes | **Sadece POST.** Oy kaydeder |
| `/anket/<int:pk>/sil/` | `polls:delete` | Sadece anket sahibi | GET: onay sayfası, POST: siler |
| `/kayit/` | `accounts:signup` | Giriş yapmamış | Kayıt formu |
| `/giris/` | `accounts:login` | Giriş yapmamış | E-posta + parola ile giriş |
| `/cikis/` | `accounts:logout` | Üye | **Sadece POST** |
| `/hesap/` | `accounts:settings` | Üye | Hesap sayfası: kullanıcı adı, e-posta (yalnızca sahibine görünür), parola değiştir ve hesabı sil bağlantıları |
| `/hesap/parola/` | `accounts:password_change` | Üye | Mevcut parola + yeni parola |
| `/hesap/sil/` | `accounts:delete` | Üye | Parola tekrar girilerek hesabı kalıcı silme |
| `/gizlilik/` | `core:privacy` | Herkes | Hangi verinin neden toplandığını anlatan sade gizlilik sayfası |
| `ADMIN_URL` | Django admin | Superuser | Yol ortam değişkeninden gelir, production'da `/admin/` **değildir** |

### Davranış detayları

**Anket akışı (`/`)**
- Her kart: soru, `@kullaniciadi`, göreli zaman ("2 saat önce"), toplam oy sayısı, seçenekler.
- Kullanıcı bu ankete henüz oy vermediyse: seçenekler tıklanabilir butonlardır, doğrudan karttan oy verilebilir.
- Oy verdiyse (veya anketin sahibiyse): sonuç çubukları gösterilir, kullanıcının kendi seçtiği seçenek (yalnızca kendisine) vurgulanır.
- Sorgular verimli olmalı: `select_related("author")`, `prefetch_related("options")`, `annotate(Count(...))`. Mevcut kullanıcının hangi anketlere oy verdiği tek sorguda alınır (N+1 yok).
- `?page=` geçersizse ilk/son sayfaya düşülür, hata verilmez.
- Hiç anket yoksa: "Henüz kimse kararsız değil. İlk anketi sen aç!"

**Anket oluşturma (`/anket/yeni/`)**
- Giriş yapmamış kullanıcı giriş sayfasına yönlendirilir (`?next=` ile geri döner).
- Form: soru + başlangıçta 2 seçenek alanı. "Seçenek ekle" (JS) ile 5'e kadar alan eklenir; 2'nin altına inilemez.
- JS kapalıysa: 5 seçenek alanı gösterilir, ilk 2'si zorunlu, boş olanlar yok sayılır.
- **Sunucu tarafı doğrulama her zaman yapılır:** boş olmayan seçenek sayısı 2–5, tekrarsız, karakter sınırları içinde. Form yalnızca tanımlı alanları kabul eder; `author` her zaman `request.user`'dan atanır, istekten asla okunmaz.
- Kayıt `transaction.atomic()` içinde yapılır.
- Başarıda detay sayfasına yönlendirilir: "Anketin yayında!"

**Oy verme (`POST /anket/<pk>/oy/`)**
- Gövdede `option` (seçenek id'si) gelir. CSRF korumalıdır.
- Seçenek bu ankete ait değilse veya geçerli bir tam sayı değilse 400.
- Zaten oy verilmişse yeni oy oluşturulmaz; "Bu ankete zaten oy verdin" bilgisi döner (IntegrityError yakalanır).
- İstek `Accept: application/json` ile geldiyse JSON döner:
  ```json
  {
    "ok": true,
    "already_voted": false,
    "selected_option_id": 12,
    "total_votes": 34,
    "options": [
      {"id": 11, "text": "Sinema", "votes": 20, "percent": 59},
      {"id": 12, "text": "Restoran", "votes": 14, "percent": 41}
    ]
  }
  ```
  JSON'da kullanıcı bilgisi, e-posta veya `voter_key` **yer almaz**.
- Normal form gönderimiyse anket sayfasına veya güvenli olduğu doğrulanmış `next` adresine yönlendirir.
- Yüzdeler tam sayıya yuvarlanır; toplam oy 0 ise tüm yüzdeler 0.

**Kayıt, giriş, hesap**
- Kayıt formu: e-posta, kullanıcı adı, parola, parola tekrar. Hata mesajları Türkçe, alan altında.
- Kullanıcı adı alınmışsa açıkça söylenir (kullanıcı adları zaten herkese açık).
- E-posta kayıtlıysa genel bir mesaj verilir: "Bu e-posta ile kayıt oluşturulamadı. Zaten hesabın varsa giriş yap." (Hız sınırıyla birlikte e-posta tarama riskini azaltır.)
- Giriş hatasında hangi alanın yanlış olduğu belirtilmez: "E-posta veya parola hatalı."
- Parola değişince diğer cihazlardaki oturumlar sonlanır, mevcut oturum açık kalır (`update_session_auth_hash`).
- Hesap silme: parola tekrar istenir, onaydan sonra kullanıcı, anketleri (ve o anketlere gelen oylar) silinir; kullanıcının başka anketlere verdiği oylar Bölüm 7'deki gibi anonimleştirilir. Oturum kapatılır, "Hesabın silindi" mesajı gösterilir.
- Prototipte e-posta doğrulama ve parola sıfırlama **yok** (Bölüm 13).

---

## 9. Arayüz ve tasarım

### Genel his
Genç, sakin ve temiz. Koyu arka plan, göz yormayan kontrast, bol boşluk, büyük ve kolay tıklanan alanlar. Tek sütunlu, rahat kaydırılan bir akış.

### Renk tokenları (`static/css/main.css` içinde `:root`)

```css
:root {
  --bg:          #0e1014;
  --surface:     #161a21;
  --surface-2:   #1d222b;
  --border:      #262c37;
  --text:        #e7e9ee;
  --text-muted:  #98a1b0;
  --accent:      #8b7cf6;
  --accent-soft: rgba(139, 124, 246, 0.16);
  --accent-2:    #3ddc97;
  --danger:      #f2667a;
  --radius:      14px;
  --radius-sm:   10px;
  --shadow:      0 6px 24px rgba(0, 0, 0, 0.35);
}
```

- Metin/arka plan kontrastı en az WCAG AA. Tek tema (koyu).

### Tipografi
- Font: **sistem fontu** (`system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`). Harici font yüklenmez (ziyaretçilerin IP'si üçüncü tarafa gitmesin ve CSP sade kalsın diye); font dosyası ve `@font-face` yoktur.
- Taban 16px, anket sorusu 18–20px ve 600 ağırlıkta.
- Logo: küçük harflerle **kararsızım**, sonunda vurgu renginde bir **?**. Görsel dosyası gerekmez.

### Düzen
- Mobil öncelikli; içerik sütunu en fazla `640px`, ortalı; mobilde 16px yan boşluk; yatay kaydırma yok.
- **Header:** solda logo; sağda giriş yapmamışsa "Giriş yap" + "Kayıt ol", giriş yapmışsa `@kullaniciadi` (hesap sayfasına link) + "Anket aç" (vurgulu) + "Çıkış". Mobilde "Anket aç" her zaman görünür.
- **Footer:** küçük, muted bir "Gizlilik" bağlantısı.
- **Anket kartı:** `--surface`, `--radius`, ince `--border`, 20px iç boşluk. Üstte `@kullaniciadi · 2 saat önce`, altında soru, seçenekler, en altta "34 oy".
- **Seçenek butonları:** tam genişlik, `--surface-2`, hover'da `--accent` çerçeve, en az 44px yükseklik.
- **Sonuç çubukları:** yüzde kadar dolan arka plan çubuğu, sağda `%59 · 20 oy`. Kullanıcının seçimi `--accent` çerçeve ve "✓ senin oyun" etiketi; en çok oy alan çubuk `--accent-2` tonunda; yüklemede kısa dolma animasyonu.
  - CSP gereği şablonda **inline `style` kullanılmaz**: yüzde `data-percent` niteliğine yazılır, çubuk genişliğini JS ayarlar. JS kapalıyken yüzde metin olarak yine görünür.
- **Formlar:** etiketler üstte, input'lar `--surface-2`, odakta `--accent` çerçeve + görünür focus halkası, hata metinleri `--danger`. Parola alanlarında `autocomplete="current-password"` / `"new-password"`, e-postada `autocomplete="email"`.
- **Mesajlar:** Django `messages` üstte toast olarak; birkaç saniye sonra JS ile kaybolur.
- **Tehlikeli işlemler** (anket silme, hesap silme) `--danger` renkli butonla ve ayrı onay ekranıyla yapılır.

### Erişilebilirlik
- Tüm etkileşimli öğeler klavyeyle kullanılabilir, görünür focus durumu var.
- `prefers-reduced-motion` açıksa animasyonlar kapatılır.
- Form alanlarının `label`'ı var; anlam yalnızca renkle taşınmaz.
- `<html lang="tr">`, Türkçe karakterler her yerde doğru.

### JavaScript (`static/js/main.js`)
Tek dosya, framework yok:
1. **Fetch ile oy verme:** Form `fetch` ile gönderilir; CSRF token formdaki gizli `csrfmiddlewaretoken` alanından okunur (CSRF çerezi JS'e kapalıdır). Dönen JSON ile kart sonuç görünümüne çevrilir. Hata olursa normal form gönderimine düşülür.
2. **Seçenek ekle/kaldır** (2–5 sınırı).
3. **Sonuç çubuklarının genişliği** `data-percent` değerinden ayarlanır.
4. **Toast mesajlarını** gizleme.

JS kuralları: Kullanıcıdan gelen hiçbir metin `innerHTML` ile DOM'a yazılmaz; yalnızca `textContent` / `createElement` kullanılır. `eval`, `new Function`, inline event handler (`onclick="..."`) yok.

---

## 10. Güvenlik ve veri gizliliği

Bu bölümdeki her madde **zorunludur**. Her faz, kendi kapsamına giren maddeleri uygular ve faz sonunda raporlar.

### 10.1 Kimlik doğrulama ve parolalar
- `PASSWORD_HASHERS` listesinin başında `Argon2PasswordHasher` olur (eski hash'ler girişte otomatik yükseltilir).
- `AUTH_PASSWORD_VALIDATORS`: kullanıcı bilgisine benzerlik, en az **10 karakter**, yaygın parola listesi, tamamen sayısal olmama. Hata mesajları Türkçe.
- Parolalar hiçbir zaman log'lanmaz, e-postalanmaz, şablona geri basılmaz (hatalı form tekrar gösterilirken parola alanları boş gelir).
- Girişte oturum anahtarı yenilenir (Django `login()` bunu yapar; özel kod bunu bozmamalı).
- Çıkış ve hesap silme işlemleri yalnızca POST ile yapılır.

### 10.2 Hız sınırlama (brute force ve spam koruması)
`core/ratelimit.py` içinde, Django cache'i (veritabanı backend'i) kullanan basit bir sabit pencere sayacı yazılır. Sınır aşılınca `429` ve temalı `429.html` ("Biraz yavaşla, birazdan tekrar dene.") döner; JSON isteğe JSON hata döner.

| İşlem | Anahtar | Sınır |
|---|---|---|
| Giriş denemesi | IP | 10 / 15 dk |
| Giriş denemesi | e-posta | 5 / 15 dk |
| Kayıt | IP | 5 / saat |
| Parola değiştirme / hesap silme denemesi | kullanıcı | 5 / 15 dk |
| Anket oluşturma | kullanıcı | 10 / saat |
| Oy verme | IP | 30 / dakika |

- Cache anahtarlarında ham IP veya e-posta **kullanılmaz**; `HMAC-SHA256(SECRET_KEY, değer)` ile hash'lenmiş hali kullanılır. Kayıtlar pencere sonunda kendiliğinden geçersiz olur; IP hiçbir yerde kalıcı saklanmaz.
- İstemci IP'si `core/net.py` içinde tek bir fonksiyondan okunur: `TRUST_PROXY_IP_HEADER=True` ise (yalnızca Vercel'de) Vercel'in eklediği istemci IP başlığından, değilse `REMOTE_ADDR`'dan. Hangi başlığın güvenilir olduğunu Vercel dokümanından doğrula; istemcinin gönderebileceği başlıklara körü körüne güvenme.

### 10.3 Django güvenlik ayarları

Her ortamda:
- `SESSION_COOKIE_HTTPONLY = True`, `SESSION_COOKIE_SAMESITE = "Lax"`, `SESSION_COOKIE_AGE = 60 * 60 * 24 * 14`
- `CSRF_COOKIE_HTTPONLY = True`, `CSRF_COOKIE_SAMESITE = "Lax"`
- `X_FRAME_OPTIONS = "DENY"`, `SECURE_CONTENT_TYPE_NOSNIFF = True`
- `SECURE_REFERRER_POLICY = "same-origin"`, `SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"`
- `DATA_UPLOAD_MAX_MEMORY_SIZE` varsayılan veya daha düşük; dosya yükleme kapalı.

`DEBUG=False` (production) iken ek olarak:
- `SECURE_SSL_REDIRECT = True`, `SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")`
- `SESSION_COOKIE_SECURE = True`, `CSRF_COOKIE_SECURE = True`
- `SECURE_HSTS_SECONDS = 31536000` (`INCLUDE_SUBDOMAINS` ve `PRELOAD` şimdilik kapalı; özel alan adı alınınca yeniden değerlendirilir)
- `ALLOWED_HOSTS` ve `CSRF_TRUSTED_ORIGINS` ortam değişkeninden; joker yalnızca gerektiği kadar.
- `python manage.py check --deploy` uyarı vermemeli (verenler bilinçli olarak gerekçelendirilir).

### 10.4 Güvenlik başlıkları ve CSP
`config/middleware.py` içinde bir middleware her yanıta şu başlıkları ekler:

```
Content-Security-Policy:
  default-src 'self';
  script-src 'self';
  style-src 'self';
  font-src 'self';
  img-src 'self' data:;
  connect-src 'self';
  form-action 'self';
  frame-ancestors 'none';
  base-uri 'self';
  object-src 'none'
Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=()
```

- Bu yüzden şablonlarda **inline `<script>`, inline `<style>`, `style="..."` ve `onclick="..."` yasaktır.** Sunucudan JS'e veri `data-*` nitelikleriyle aktarılır.
- Django admin CSP ile sorun çıkarırsa politika yalnızca admin yolu için gevşetilir, uygulamanın geri kalanı için değil.

### 10.5 XSS, injection ve yetkilendirme
- Django şablonlarında otomatik kaçış **asla kapatılmaz**; kullanıcı içeriğinde `|safe`, `mark_safe`, `{% autoescape off %}` kullanılmaz.
- Veritabanına yalnızca ORM ile erişilir. Ham SQL gerekirse yalnızca parametreli sorgu; string birleştirme/f-string ile SQL **yasak**.
- **Yetki kontrolü sorgu seviyesinde yapılır:** silme gibi işlemlerde nesne `Poll.objects.get(pk=pk, author=request.user)` gibi sahiplik filtresiyle alınır; başkasının anketine erişim 404 döner (varlığı bile sızdırılmaz).
- Yönlendirmelerde kullanılan `next` parametresi `url_has_allowed_host_and_scheme` ile doğrulanır; geçersizse ana sayfaya gidilir (açık yönlendirme yok).
- Tüm POST işlemleri CSRF korumalıdır; `@csrf_exempt` kullanılmaz.
- Formlar açık alan listesiyle tanımlanır (`fields = "__all__"` yok).

### 10.6 Veri gizliliği ve en aza indirme
- Toplanan veri: e-posta, kullanıcı adı, parola hash'i, anketler, oylar. Fazlası toplanmaz.
- E-posta yalnızca sahibine (`/hesap/`) ve admin'e görünür. Başka hiçbir sayfada, JSON'da, hata mesajında veya log'da yer almaz.
- Oylar kişiyle ilişkilendirilerek hiçbir kullanıcıya gösterilmez; "kim neye oy verdi" listesi yapılmaz.
- Kullanılan çerezler yalnızca zorunlu olanlardır: oturum, CSRF, `kv_voter`. Analitik veya üçüncü taraf takip kodu, harici font/CDN çağrısı **yok**.
- `/gizlilik/` sayfası sade Türkçeyle şunları açıklar: hangi veriler toplanıyor ve neden, hangi çerezler var, IP'nin kalıcı saklanmadığı, verilerin nerede tutulduğu (Supabase/Vercel), hesap silmenin nasıl yapıldığı ve silinince ne olduğu. (Not: Bu metin hukuki danışmanlık yerine geçmez; uygulama gerçek kullanıcıya açılmadan önce KVKK açısından gözden geçirilmeli.)
- Log'lara kişisel veri, parola, çerez veya oturum bilgisi yazılmaz. Production'da hata detayı kullanıcıya gösterilmez.

### 10.7 Supabase güvenliği (kritik)
Django tabloları Supabase'in `public` şemasında oluşur. Supabase'in otomatik **Data API**'si (REST/GraphQL) bu şemayı varsayılan olarak dışarıya açabilir ve proje URL'sini bilen biri RLS kapalı tablolara erişebilir. Bu uygulamada `django_session` (aktif oturumlar), `accounts_user` (e-posta ve parola hash'leri) gibi tablolar olduğu için bu **kesinlikle** kapatılmalıdır. Katmanlı önlem:

1. **Data API'yi tamamen kapat:** Supabase Dashboard → API Settings → Data API Settings → "Enable Data API" kapalı. Uygulama bu API'yi hiç kullanmıyor.
2. **`anon` ve `authenticated` rollerinin yetkilerini kaldır** (bir migration ile, yalnızca PostgreSQL'de çalışacak şekilde):
   ```sql
   revoke all on all tables in schema public from anon, authenticated;
   revoke all on all sequences in schema public from anon, authenticated;
   revoke all on all functions in schema public from anon, authenticated;
   alter default privileges for role postgres in schema public revoke all on tables from anon, authenticated;
   alter default privileges for role postgres in schema public revoke all on sequences from anon, authenticated;
   alter default privileges for role postgres in schema public revoke all on functions from anon, authenticated;
   ```
3. **Tüm tablolarda RLS'i aç** (politika tanımlamadan; tablo sahibi olan Django bağlantısı etkilenmez, diğer roller hiçbir satır göremez). Bunu yapan bir management komutu (`python manage.py secure_db`) yaz; `migrate` ve `createcachetable` sonrasında her deploy'da çalıştırılır ve idempotent'tir.
4. Supabase Dashboard'daki **Security Advisor** uyarısız olmalı.
5. Veritabanı parolası güçlü ve rastgele; yalnızca Vercel ortam değişkeninde ve yerel `.env`'de bulunur.
6. Supabase `anon` / `service_role` anahtarları projeye **hiç eklenmez**.

(Supabase'in güncel dokümanını kontrol et: https://supabase.com/docs/guides/database/hardening-data-api)

### 10.8 Vercel güvenliği
- Ortam değişkenleri Vercel'de **Sensitive** olarak işaretlenir.
- Production `DATABASE_URL` ve `SECRET_KEY` yalnızca **Production** ortamına tanımlanır. Preview deployment'lar production veritabanına bağlanmaz (ya veritabanı verilmez ya da ayrı bir veritabanı kullanılır) ve Vercel Deployment Protection ile korunur.
- `ADMIN_URL` production'da tahmin edilemez bir yol olur; superuser parolası güçlü ve benzersizdir.

### 10.9 Bağımlılık ve kod hijyeni
- `requirements.txt` sürümleri sabitlenmiştir; Dependabot açıktır.
- `pip-audit -r requirements.txt` Faz 4'te ve her bağımlılık güncellemesinde çalıştırılır; bilinen açık varsa giderilir.
- `.gitignore`: `.env`, `.env.*` (`.env.example` hariç), `db.sqlite3`, `staticfiles/`, `__pycache__/`, `.venv/`, `*.log`.
- Commit öncesi gizli bilgi taraması: `git diff --cached` içinde anahtar/parola/bağlantı adresi olmadığı kontrol edilir.

---

## 11. Testler

Her faz kendi testlerini ekler. En az şunlar test edilmeli:

**İşlevsel**
- Kayıt: geçerli kayıt kullanıcı oluşturur ve giriş yapar; aynı e-posta / kullanıcı adı (farklı harf büyüklüğüyle bile) reddedilir; geçersiz kullanıcı adı reddedilir.
- Giriş: e-posta + parola ile çalışır.
- Anket oluşturma: anonim kullanıcı yönlendirilir; 1 ve 6 seçenek reddedilir; 2 ve 5 kabul edilir; tekrarlı seçenek reddedilir.
- Oy: anonim oy verir ve çerez alır; aynı çerezle ikinci oy oluşmaz; üye bir kez oy verir; başka ankete ait seçenek reddedilir; GET reddedilir.

**Güvenlik**
- Parolalar Argon2 ile hash'lenmiş (`password` alanı `argon2` ile başlıyor).
- 10 karakterden kısa parola reddedilir.
- Hız sınırı: limit aşılınca 429 dönüyor (giriş, kayıt, oy).
- Gizlilik: akış, detay, oy JSON'u ve hata sayfalarında hiçbir kullanıcının e-postası geçmiyor; JSON'da `voter_key` yok.
- XSS: `<script>alert(1)</script>` içeren bir anket sorusu/seçeneği kaçışlanmış olarak görünüyor.
- Yetki: başkasının anketini silme denemesi 404; hesap silme yanlış parolayla başarısız.
- Açık yönlendirme: `next=https://kotu-site.com` ana sayfaya yönlendiriyor.
- CSRF: CSRF token'sız POST reddediliyor (`Client(enforce_csrf_checks=True)`).
- Bozuk/sahte `kv_voter` çerezi uygulamayı çökertmiyor.
- Güvenlik başlıkları (CSP, X-Frame-Options, nosniff) yanıtlarda mevcut.
- Hesap silme: kullanıcının anketleri silinmiş, diğer anketlerdeki oyları sayımda kalmış ama `user` boş ve `voter_key` `d:` ile başlıyor.

---

## 12. Geliştirme fazları

Her faz Claude Code'a ayrı ayrı verilir. **"Komut"** bölümleri doğrudan kopyalanabilir.

---

### Faz 0 — Proje iskeleti, güvenlik temeli ve tema

**Hedef:** Güvenli varsayılanlarla kurulmuş boş bir Django projesi, özel kullanıcı modeli ve koyu temalı temel şablon.

Yapılacaklar:
- Bölüm 5'teki klasör yapısı, `requirements.txt` (sabit sürümler), `requirements-dev.txt`, `.python-version`, `.env.example`, `.gitignore`, `.github/dependabot.yml`.
- `config/settings.py`: Bölüm 6 ve Bölüm 10.1, 10.3'teki ayarlar (Argon2, parola doğrulayıcıları, çerez ayarları, production koşullu ayarlar, `ADMIN_URL`, veritabanı cache'i).
- `config/middleware.py`: Bölüm 10.4'teki güvenlik başlıkları.
- `accounts.User` modeli (Bölüm 7) **ilk migrate'ten önce**, admin'e kayıtlı.
- `base.html`, header, footer, mesajlar; `main.css` (tokenlar, tipografi, `@font-face`, header, buton, kart). Inline script/stil yok.
- Temalı `404.html`, `500.html`, `403.html`, `400.html`, `429.html`.
- Ana sayfa şimdilik boş durum mesajını gösterir.

**Kabul kriterleri:**
- [ ] `pip install -r requirements-dev.txt && python manage.py migrate && python manage.py createcachetable && python manage.py runserver` hatasız çalışıyor.
- [ ] `createsuperuser` e-posta + kullanıcı adı + parola istiyor; admin `ADMIN_URL` yolunda açılıyor.
- [ ] Ana sayfa koyu temayla mobil ve masaüstünde düzgün görünüyor; tarayıcı konsolunda CSP ihlali yok.

**Güvenlik kriterleri:**
- [ ] Yanıtlarda CSP, X-Frame-Options, nosniff, Referrer-Policy, Permissions-Policy başlıkları var.
- [ ] `DEBUG=False` ve `SECRET_KEY` yokken uygulama başlamayı reddediyor.
- [ ] Repoda gizli bilgi yok; `.env` git tarafından yok sayılıyor.

**Komut:**
> CLAUDE.md dosyasını baştan sona, özellikle Bölüm 10'u dikkatle oku. Ardından yalnızca **Faz 0**'ı uygula. Bitince kabul ve güvenlik kriterlerini tek tek kontrol edip raporla ve yerelde çalıştırmam için gereken komutları yaz.

---

### Faz 1 — Kayıt, giriş, hesap yönetimi

**Hedef:** Güvenli kayıt, giriş, çıkış; parola değiştirme, hesap silme ve gizlilik sayfası.

Yapılacaklar:
- `core/net.py` ve `core/ratelimit.py` (Bölüm 10.2).
- Kayıt, giriş, çıkış (POST), hesap sayfası, parola değiştirme, hesap silme (Bölüm 8). Hesap silmede oy anonimleştirme, `Vote` modeli Faz 3'te geleceği için bu fazda yalnızca kullanıcı silme + yapılacak işin `TODO` notu bırakılır; Faz 3'te tamamlanır.
- Giriş, kayıt, parola ve hesap silme için hız sınırları.
- `next` parametresi doğrulaması.
- `/gizlilik/` sayfası (Bölüm 10.6).
- Header giriş durumuna göre değişir.
- Bölüm 11'deki ilgili işlevsel ve güvenlik testleri.

**Kabul kriterleri:**
- [ ] Kayıt sonrası otomatik giriş ve ana sayfaya yönlendirme; header'da `@kullaniciadi`.
- [ ] Mükerrer e-posta / kullanıcı adı Türkçe mesajla reddediliyor.
- [ ] Parola değiştirme ve hesap silme çalışıyor.
- [ ] Testler geçiyor.

**Güvenlik kriterleri:**
- [ ] Parolalar Argon2 ile saklanıyor; 10 karakter altı reddediliyor.
- [ ] Art arda hatalı girişte 429 dönüyor; hata mesajı hangi alanın yanlış olduğunu söylemiyor.
- [ ] `next` ile dış siteye yönlendirme yapılamıyor.
- [ ] E-posta yalnızca `/hesap/` sayfasında, yalnızca sahibine görünüyor.

**Komut:**
> CLAUDE.md'ye göre **Faz 1**'i uygula. Faz 0 tamamlandı. Yalnızca bu fazın kapsamında kal, bitince testleri çalıştır ve kabul ile güvenlik kriterlerini raporla.

---

### Faz 2 — Anket oluşturma, akış, detay, silme

**Hedef:** Üyeler anket açabilir; herkes akışı ve detay sayfasını görebilir.

Yapılacaklar:
- `Poll` ve `Option` modelleri + migration + admin (seçenekler inline).
- Anket formu, sunucu tarafı doğrulama (Bölüm 8), anket oluşturma hız sınırı.
- Views: akış (sayfalama 20), detay, oluşturma (`login_required`), silme (sahiplik filtresiyle, onay sayfası).
- `partials/poll_card.html`; bu fazda seçenekler sadece listelenir.
- `main.js`: seçenek ekle/kaldır.
- Bölüm 11'deki ilgili testler (XSS ve yetki testleri dahil).

**Kabul kriterleri:**
- [ ] Anonim kullanıcı "Anket aç"a basınca girişe, girişten sonra forma dönüyor.
- [ ] 2–5 seçenek sınırı hem arayüzde hem sunucuda; JS kapalıyken de form çalışıyor.
- [ ] Akışta en yeni üstte; kartlarda `@kullaniciadi` ve göreli zaman.
- [ ] Akış sayfası anket sayısından bağımsız, sabit sayıda sorgu yapıyor.
- [ ] Testler geçiyor.

**Güvenlik kriterleri:**
- [ ] Script içeren soru/seçenek kaçışlanarak gösteriliyor.
- [ ] Başkasının anketini silme denemesi 404.
- [ ] `author` istekten değil, oturumdan atanıyor.

**Komut:**
> CLAUDE.md'ye göre **Faz 2**'yi uygula. Faz 0 ve 1 tamamlandı. Oy verme özelliğini bu fazda ekleme. Bitince testleri çalıştır ve kabul ile güvenlik kriterlerini raporla.

---

### Faz 3 — Oy verme ve sonuçlar

**Hedef:** Üye olan ve olmayan herkes her ankete bir kez oy verebilir, ardından sonuçları görür.

Yapılacaklar:
- `Vote` modeli + migration + admin (salt okunur).
- `polls/utils.py`: `voter_key` ve imzalı `kv_voter` çerezi (Bölüm 7).
- `POST /anket/<pk>/oy/`: form ve JSON yanıtı, oy hız sınırı.
- Kartlarda iki görünüm (seçenek butonları / sonuç çubukları), `data-percent` ile çubuk genişliği.
- `main.js`: fetch ile oy verme (`textContent` ile DOM güncelleme), hata durumunda form gönderimine düşme.
- Faz 1'de bırakılan hesap silme `TODO`'sunu tamamla: oyların anonimleştirilmesi.
- Bölüm 11'deki oy, gizlilik ve hesap silme testleri.

**Kabul kriterleri:**
- [ ] Gizli sekmede anonim oy verilebiliyor; yenilemede sonuçlar görünmeye devam ediyor, tekrar oy verilemiyor.
- [ ] Üye ikinci kez oy veremiyor; eşzamanlı iki istekte bile tek oy oluşuyor.
- [ ] JS açıkken sayfa yenilemeden, kapalıyken form gönderimiyle çalışıyor.
- [ ] Testler geçiyor.

**Güvenlik kriterleri:**
- [ ] Oy JSON'unda kullanıcı bilgisi, e-posta veya `voter_key` yok.
- [ ] `kv_voter` çerezi imzalı, `HttpOnly`, `SameSite=Lax`; sahte çerez uygulamayı çökertmiyor.
- [ ] Oy hız sınırı çalışıyor.
- [ ] Hesap silinince oylar anonimleşiyor.

**Komut:**
> CLAUDE.md'ye göre **Faz 3**'ü uygula. Faz 0–2 tamamlandı. Bitince testleri çalıştır, kabul ve güvenlik kriterlerini raporla ve anonim oy akışını nasıl elle test edebileceğimi kısaca yaz.

---

### Faz 4 — Supabase ve Vercel'e güvenli taşıma

**Hedef:** Uygulama Supabase PostgreSQL ile Vercel'de güvenli şekilde canlı çalışır.

Kullanıcının elle yapacakları (Claude Code adım adım anlatmalı):
1. Supabase'de yeni proje oluştur; **güçlü, rastgele** bir veritabanı parolası belirle.
2. **Data API'yi kapat** (Bölüm 10.7, madde 1).
3. **Connect** bölümünden iki bağlantı adresi al: Transaction pooler (`6543`) → Vercel için; Session pooler (`5432`) → yerelden migration için.
4. Projeyi GitHub'a gönder (önce gizli bilgi kontrolü), Vercel'de içe aktar.
5. Vercel ortam değişkenleri (Sensitive, yalnızca Production): `SECRET_KEY` (yeni ve güçlü), `DEBUG=False`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `DATABASE_URL` (transaction pooler, `sslmode=require`), `ADMIN_URL` (tahmin edilemez), `TRUST_PROXY_IP_HEADER=True`.
6. Preview deployment'lar için Deployment Protection'ı aç.

Claude Code'un yapacakları:
- Projenin Vercel zero-config algılamaya uygun olduğunu güncel dokümandan doğrula; gerekmedikçe `vercel.json` ekleme.
- Pooler ayarları, SSL zorunluluğu.
- Bölüm 10.7'deki yetki kaldırma migration'ı ve `secure_db` management komutu.
- Vercel'de istemci IP'sinin hangi başlıktan güvenle okunacağını dokümandan doğrula, `core/net.py`'yi buna göre ayarla.
- `DEPLOY.md`: migration'ların **build sırasında değil**, yerelden session pooler ile çalıştırılacağı sıra: `migrate` → `createcachetable` → `secure_db` → `createsuperuser`.
- `python manage.py check --deploy` ve `pip-audit -r requirements.txt` çalıştır, bulguları düzelt.

**Kabul kriterleri:**
- [ ] Canlı adreste kayıt, giriş, anket açma, oy verme, hesap silme çalışıyor; CSS/JS/fontlar yükleniyor, konsolda CSP ihlali yok.
- [ ] Canlıda hata sayfaları Django debug ekranı göstermiyor.

**Güvenlik kriterleri:**
- [ ] `https://<proje>.supabase.co/rest/v1/accounts_user` gibi bir istek veri döndürmüyor (Data API kapalı).
- [ ] Supabase Security Advisor uyarısız.
- [ ] `check --deploy` ve `pip-audit` temiz (veya her uyarı gerekçeli).
- [ ] HTTP istekleri HTTPS'e yönleniyor; HSTS başlığı var; çerezler `Secure`.
- [ ] `/admin/` 404 veriyor, admin yalnızca `ADMIN_URL`'de.
- [ ] Preview deployment'lar production veritabanına erişemiyor.

**Komut:**
> CLAUDE.md'ye göre **Faz 4**'ü uygula. Önce benim Supabase ve Vercel panellerinde yapmam gerekenleri sırayla listele, sonra koddaki değişiklikleri yap ve DEPLOY.md'yi yaz. Bir değere ihtiyacın olursa uydurma, bana sor. Gizli bilgileri bana tekrar yazdırma veya ekrana basma.

---

### Faz 5 — Arayüz cilası ve son güvenlik gözden geçirmesi

**Hedef:** Prototipi kullanıcıya gösterilebilir hale getirmek.

Yapılacaklar:
- Tüm sayfaları 360px, 768px, 1280px genişliklerde gözden geçir.
- Boş durumlar ve hata sayfalarının son hali.
- Anket detay sayfasına "Linki kopyala" butonu (Clipboard API).
- Sayfa başlıkları ve temel meta etiketleri (Open Graph başlığı = anket sorusu, kaçışlanmış).
- Basit favicon (static altında SVG dosyası, vurgu renginde "?").
- Odak durumları, kontrast, `prefers-reduced-motion`.
- **Son güvenlik gözden geçirmesi:** Bölüm 10'daki her maddeyi baştan sona tek tek kontrol et ve bir tablo halinde raporla (madde → durum → kanıt/dosya).

**Kabul kriterleri:**
- [ ] Mobilde yatay kaydırma yok, tüm butonlar en az 44px.
- [ ] Var olmayan anket adresinde temalı 404.
- [ ] Bölüm 10 kontrol tablosunda açık madde kalmadı.

**Komut:**
> CLAUDE.md'ye göre **Faz 5**'i uygula. Yeni özellik ekleme, sadece listelenen cilaları yap. Sonunda Bölüm 10'un tamamı için güvenlik kontrol tablosunu çıkar.

---

## 13. Kapsam dışı (sonraki aşamalar için)

Prototipte **yapılmayacak**; sonra tek tek değerlendirilecek:

- E-posta doğrulama ve parola sıfırlama (bir e-posta gönderim servisi gerektirir)
- İki adımlı doğrulama (2FA)
- Oy değiştirme / geri alma
- Anket süresi ve otomatik kapanma
- Arama, filtreleme, sıralama seçenekleri
- Kullanıcı profil sayfası (`/@kullaniciadi`)
- Anonim oyları giriş yapınca hesaba bağlama; anonim oylarda daha güçlü kötüye kullanım önlemleri (ör. bot doğrulama)
- Anket raporlama / moderasyon, küfür filtresi
- Kullanıcının verilerini indirebilmesi (veri taşınabilirliği)
- Yorumlar, açık tema, anket görseli
