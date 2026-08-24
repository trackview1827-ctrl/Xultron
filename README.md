# Xultron

Xultron, sağlayıcıdan bağımsız çalışan mobil öncelikli bir kişisel AI sistemidir.
React tabanlı PWA arayüzü, Flask API'si, şifreli sağlayıcı kimlik bilgileri,
metin ve ses akışları, kullanıcı kontrollü hafıza ve izole misafir modu içerir.

Arayüz, klasik bir dashboard veya sohbet klonu yerine **Signal Spine** görsel
dilini kullanır. Xultron Core gerçek uygulama durumunu `BOOTING`, `OFFLINE`,
`CONNECTING`, `ONLINE`, `LISTENING`, `THINKING`, `SPEAKING` ve `ERROR`
durumlarıyla gösterir.

## Öne çıkan özellikler

- React, TypeScript, Vite, Tailwind CSS ve Framer Motion ile mobil PWA
- Flask, SQLAlchemy, SQLite ve Alembic uyumlu migrasyonlar
- Kayıt, giriş, çıkış, iptal edilebilir sunucu oturumları ve misafir yükseltme
- AI, STT ve TTS için ortak sağlayıcı soyutlamaları
- Ayarlar ekranından sağlayıcı ekleme, düzenleme, test etme ve model keşfi
- Fernet ile şifrelenmiş API anahtarları ve yalnızca maskelenmiş geri bildirim
- SSE tabanlı sohbet akışı, idempotent istekler ve ağ kurtarma davranışı
- Tarayıcı mikrofonu, STT transkripsiyonu ve TTS ses oynatma akışı
- Aranabilir ve tamamen kullanıcı kontrollü kişisel hafıza
- Gizlilik, Düşük Veri Modu, Reduced Motion ve oturum veri sayacı
- Çevrimdışı uygulama kabuğu, manifest ve service worker
- Raspberry Pi, ESP32 ve Bluetooth için ayrılmış cihaz servis sınırı

## Proje yapısı

```text
frontend/   React ve TypeScript PWA
backend/    Flask REST/SSE API ve SQLAlchemy veri katmanı
docs/       Ürün şartnamesi, mimari, API, UI ve kabul matrisi
scripts/    Yerel geliştirme ve doğrulama yardımcıları
```

Ayrıntılı belgeler:

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- [`docs/API_CONTRACT.md`](docs/API_CONTRACT.md)
- [`docs/UI_SYSTEM.md`](docs/UI_SYSTEM.md)
- [`docs/ACCEPTANCE.md`](docs/ACCEPTANCE.md)
- [`docs/VALIDATION_REPORT.md`](docs/VALIDATION_REPORT.md)
- [`SECURITY.md`](SECURITY.md)

## Gereksinimler

- Python 3.11 veya daha yeni
- Node.js 20 veya daha yeni
- npm
- Güvenli sağlayıcı anahtarı saklama için `pyca/cryptography`

Termux üzerinde resmi paketi kullan:

```bash
pkg install python-cryptography
python -m venv --system-site-packages backend/.venv
```

Standart Linux veya macOS ortamında normal sanal ortam yeterlidir:

```bash
python -m venv backend/.venv
```

## Kurulum

```bash
cd Xultron

make setup
```

Bu komut backend sanal ortamını ve frontend bağımlılıklarını kurar, ardından
Alembic migrasyonlarını uygular. Elle kurulum gerekirse:

```bash
cd Xultron

# Backend
backend/.venv/bin/python -m pip install -r backend/requirements.txt
cp backend/.env.example backend/.env
cd backend
.venv/bin/flask --app run.py db upgrade
cd ..

# Frontend
npm --prefix frontend install
```

Geliştirme ortamında uygulama sırları yoksa backend, Git dışında kalan
`backend/instance` dizininde kalıcı ve rastgele yerel sırlar üretir. Üretimde
`SECRET_KEY` ve `ENCRYPTION_KEY` açıkça sağlanmalıdır.

## Geliştirme sunucuları

İki terminal kullan:

```bash
# Terminal 1
cd Xultron/backend
.venv/bin/python run.py
```

```bash
# Terminal 2
cd Xultron
npm --prefix frontend run dev
```

Arayüz `http://127.0.0.1:5173`, API `http://127.0.0.1:5000` adresinde açılır.
Vite, `/api` isteklerini Flask'a iletir.

## Tek origin üretim önizlemesi

```bash
cd Xultron
npm --prefix frontend run build
cd backend
.venv/bin/flask --app run.py db upgrade
.venv/bin/python run.py
```

Frontend build'i varsa Flask uygulamayı `http://127.0.0.1:5000` üzerinden PWA
olarak sunar. İnternete açık üretim dağıtımında HTTPS reverse proxy ve uygun bir
WSGI sunucusu kullan.

## Sağlayıcı yapılandırma

Xultron API anahtarı olmadan açılır. Sağlayıcı olmadığında bu durum normal ve
açıklayıcı bir sistem durumu olarak gösterilir.

1. **Systems → AI Providers** bölümünü aç.
2. Sağlayıcı türünü ve HTTPS veya izin verilen yerel base URL'yi seç.
3. API anahtarını bir kez gönder.
4. **Test Connection** ile bağlantıyı doğrula.
5. Destekleniyorsa modelleri yenile veya model ID'sini elle gir.

Aynı akış STT ve TTS sağlayıcıları için de geçerlidir. Saklanan anahtar hiçbir
listeleme veya ayar yanıtında tarayıcıya geri gönderilmez.

## Test ve kalite komutları

```bash
# Tüm birim, entegrasyon, build, PWA ve izole üretim smoke kontrolleri
cd Xultron
make check

# Yalnız izole üretim HTTP akışı. Önce frontend build edilir.
make smoke
```

Kabul kontrolleri kullanıcı izolasyonu, API anahtarı sızıntısı, sağlayıcı
hataları, sohbet ve SSE, STT/TTS mock akışları, ağ kurtarma, Core geçişleri, PWA
ve mobil davranışı kapsar. Smoke testi geçici bir üretim veritabanı ve rastgele
anahtarlarla gerçek HTTP sunucusu başlatır, ardından çıktılarda ve veritabanında
sentinel API anahtarı sızıntısı arar. Ayrıntılı matris için
[`docs/ACCEPTANCE.md`](docs/ACCEPTANCE.md) dosyasına bak.

## Güvenlik notları

- `.env`, veritabanı, log ve instance dosyalarını commit etme.
- Üretimde güçlü ve birbirinden bağımsız `SECRET_KEY` ile `ENCRYPTION_KEY` kullan.
- Sağlayıcı anahtarlarını URL, frontend ortam değişkeni veya tarayıcı depolamasına koyma.
- Audio kaydı ve analitik varsayılan olarak kapalıdır.
- Her kullanıcı kaynağı aktif oturum kullanıcısıyla birlikte sorgulanır.

Eski prototip silinmedi. Geri alınabilir arşiv konumu
[`.legacy-backup-location`](.legacy-backup-location) dosyasında kayıtlıdır.
