# kararsızım

![Python](https://img.shields.io/badge/Python-3.14-3776AB?logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-6.1-092E20?logo=django&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/Supabase-PostgreSQL-3FCF8E?logo=supabase&logoColor=white)
![Vercel](https://img.shields.io/badge/Vercel-deploy-000000?logo=vercel&logoColor=white)

**kararsızım**, kararsız kaldığın konularda anket açıp diğer kullanıcılara danışabildiğin bir web uygulamasıdır.
*"Bugün sinemaya mı gitsem, restorana mı?"* — iki seçenekli bir anket aç, herkes oy versin, sonucu gör.

🔗 **Canlı demo:** https://kararsizim-blush.vercel.app

<!-- Ekran görüntüsü eklemek için: resmi docs/ klasörüne koy ve aşağıdaki satırın başındaki/sonundaki yorum işaretlerini kaldır -->
<!-- ![kararsızım ekran görüntüsü](docs/ekran.png) -->

## Özellikler

- **Anket aç:** 2–5 seçenekli anketler (yalnızca üyeler açabilir).
- **Üye olmadan oy ver:** Anketleri görmek ve oy vermek için üyelik gerekmez; her kişi bir ankete bir kez oy verir.
- **Ortak akış:** Takip sistemi yok, herkes tüm anketleri tek akışta görür.
- **Oy gizliliği:** Kimin neye oy verdiği hiç kimseye gösterilmez, anket sahibine bile. Yalnızca toplam sonuçlar görünür.
- **E-posta asla görünmez:** Kullanıcılar yalnızca kullanıcı adıyla temsil edilir.
- **Hesap kontrolü:** Parola değiştirme ve hesabı silme.
- **JavaScript'siz de çalışır:** Sayfalar sunucuda oluşturulur; JS yalnızca deneyimi iyileştirir.

## Güvenlik

- Parolalar **Argon2** ile saklanır; giriş, kayıt ve oy uçlarında **hız sınırlama** (brute force / spam koruması).
- Sıkı **Content-Security-Policy** ve güvenlik başlıkları, CSRF koruması, tahmin edilemez admin yolu.
- Veritabanına yalnızca Django üzerinden, sunucu tarafında bağlanılır; Supabase Data API kapalıdır, `anon` / `service_role` anahtarları projede yoktur.
- Gizli bilgiler (`SECRET_KEY`, veritabanı adresi) yalnızca ortam değişkenlerindedir; `.env` repoya girmez.

## Teknoloji

| | |
| --- | --- |
| Backend | Python 3.14, Django 6.1 (sunucu tarafında render edilen şablonlar) |
| Frontend | Saf HTML, CSS, JavaScript — framework ve build adımı yok |
| Veritabanı | Yerelde SQLite, canlıda Supabase PostgreSQL |
| Yayın | Vercel |

## Kendi bilgisayarında çalıştırma

Gereken tek şey **Python 3.14** (en az 3.12) → [python.org/downloads](https://www.python.org/downloads/). Windows'ta kurarken **"Add python.exe to PATH"** kutusunu işaretle. Yerelde veritabanı kurmana gerek yok; otomatik olarak SQLite kullanılır.

```bash
# 1. Projeyi indir
git clone https://github.com/Voynichh/Kararsizim.git
cd Kararsizim

# 2. Sanal ortam oluştur ve etkinleştir
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # macOS / Linux

# 3. Paketleri yükle
pip install -r requirements.txt

# 4. Ayar dosyasını oluştur (içindeki değerler yerel geliştirme için hazırdır)
copy .env.example .env          # Windows
cp .env.example .env            # macOS / Linux

# 5. Veritabanı tablolarını oluştur ve sunucuyu başlat
python manage.py migrate
python manage.py runserver
```

Tarayıcıda **http://localhost:8000** adresini aç. Bir hesap oluşturup ilk anketini açabilirsin.

Yönetim paneli için (isteğe bağlı): `python manage.py createsuperuser`, ardından http://localhost:8000/admin/

> Git kullanmıyorsan: bu sayfanın üstündeki yeşil **Code** düğmesi → **Download ZIP** ile indirip klasörü ayıkla, 2. adımdan devam et.

## Testler

```bash
pip install -r requirements-dev.txt
python manage.py test
```

Testler gerçek veritabanına bağlanmaz.

## Proje yapısı

```
config/      ayarlar, URL'ler, güvenlik middleware'i
accounts/    kayıt, giriş, hesap ayarları, parola değiştirme, hesap silme
polls/       anket oluşturma, akış, detay, oy verme, sonuçlar
core/        gizlilik sayfası, hız sınırlama, bakım modu, veritabanı güvenliği
templates/   Django şablonları
static/      CSS ve JavaScript
docs/        proje rehberi, güvenlik kontrol tablosu, ilerleme notları
DEPLOY.md    Supabase + Vercel'e adım adım yayınlama rehberi
```

## Canlıya alma

Kendi Supabase + Vercel kurulumunu yapmak istersen tüm adımlar [DEPLOY.md](DEPLOY.md) dosyasında.
