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
- Her AI cevabından önce zorunlu doğrulama planı, canlı kanıt ve doğrulanamazsa cevap vermeme
- Türkçe karakter eksikliği ve küçük yazım hatalarında güvenli, sınırlandırılmış niyet eşleme
- Güvenli runtime ve GMT/UTC tabanlı ülke saat dilimi doğrulaması
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
- [`docs/DATA_PROFILES.md`](docs/DATA_PROFILES.md)
- [`SECURITY.md`](SECURITY.md)
- [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)

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

## NPM ve npx ile tek komut kurulum

Xultron CLI, npm paketini GitHub deposundan indirip gerçek uygulamayı varsayılan
olarak `~/.xultron/app` dizinine kurar. NPM Registry yayını beklenmeden doğrudan
GitHub üzerinden kullanılabilir:

```bash
# Gereksinimleri kontrol et
npx --yes github:trackview1827-ctrl/Xultron doctor

# Xultron'u kur
npx --yes github:trackview1827-ctrl/Xultron install

# Tek-origin arayüzü http://127.0.0.1:5000 üzerinde başlat
npx --yes github:trackview1827-ctrl/Xultron start

# Daha sonra güvenli fast-forward güncellemesi yap
npx --yes github:trackview1827-ctrl/Xultron update
```

Npm 11'de kullanıcı yapılandırmasında `allow-scripts=true` varsa GitHub
paketlerinin geçici hazırlık kurulumu bilerek durdurulabilir. Mevcut global
`~/.npmrc` dosyanı değiştirmeden Xultron'u geçici boş npm ayarıyla çalıştır:

```bash
XULTRON_NPMRC="$(mktemp)"
npm_config_userconfig="$XULTRON_NPMRC" npx --yes github:trackview1827-ctrl/Xultron install
rm -f "$XULTRON_NPMRC"
```

İstersen normal npm yapılandırmasındaki ayarı inceleyebilirsin:

```bash
npm config get allow-scripts
```

Yerel bir clone içinden npm kurulumu gerekmez; `xultron install` gerçek GitHub
clone'unun backend ve frontend bağımlılıklarını kendisi hazırlar. Yalnızca CLI
paketini yerel olarak denemek için proje kökünde `npm install` ve ardından
`npm test` çalıştırılabilir.

Farklı bir kurulum klasörü için her komuta `--dir` verilebilir:

```bash
npx --yes github:trackview1827-ctrl/Xultron install --dir "$HOME/apps/Xultron"
```

CLI, dolu ve ilgisiz bir klasörün üzerine yazmaz. `update`, commit edilmemiş yerel
değişiklik varsa durur ve yalnızca `origin/main` dalına fast-forward uygular. Normal
kurulum Python sanal ortamını, backend paketlerini, frontend paketlerini ve veritabanı
migrasyonlarını hazırlar. Termux'ta önce şu komutu çalıştır:

```bash
pkg install git nodejs python python-cryptography
```

Kök npm paketi NPM Registry'ye `npm publish` ile ayrıca yayımlandıktan sonra daha kısa
komutlar kullanılabilir:

```bash
npx xultron-ai-cli install
npm install --global xultron-ai-cli
xultron start
```

Registry yayını GitHub kurulumundan ayrıdır ve npm hesabı ile paket yayınlama yetkisi
gerektirir. Paket henüz Registry'ye yüklenmediyse GitHub tabanlı `npx` komutlarını
kullan.

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

Termux/Android üzerinde düşük kaynaklı yerel STT için `whisper.cpp` kurulabilir.
Bu projede tiny multilingual model yaklaşık 75 MiB diskte ve yaklaşık 273 MiB
RAM kullanır. Kurulu binary ve model ile `scripts/local-voice.sh start` komutu
localhost:8766 üzerinde yalnızca cihaz içi STT servisini başlatır. Web sitesiyle
birlikte otomatik başlatmak için `XULTRON_LOCAL_STT_AUTOSTART=1 xultron start`
kullanılır; varsayılan kapalıdır, böylece telefon boşuna RAM tüketmez. Xultron
ayarlarında STT adaptörü olarak **whisper.cpp (local)** seçilebilir.

Kokoro-82M'nin resmi ses listesinde Türkçe veya Azerice ses paketi yoktur. Bu
nedenle Kokoro'yu telefonda zorla kurup RAM tüketmek yerine Türkçe/Azerice TTS
ElevenLabs üzerinden, yerel STT ise whisper.cpp üzerinden çalıştırılır.

ChatGPT hesabı ile Codex OAuth kullanmak için AI Providers ekranında adaptör
olarak **ChatGPT account (Codex OAuth)** seç, sağlayıcıyı kaydet ve **CONNECT
CHATGPT ACCOUNT** düğmesine bas. Xultron resmi OpenAI OAuth linkini açar; giriş
ve onayı sen ChatGPT ekranında yaparsın. Başarılı olunca tarayıcı Xultron'a geri
döner ve tokenlar backend'de şifreli saklanır. Şifre veya doğrulama kodu Xultron'a
girilmez.

AI ekranında 30'dan fazla hazır sağlayıcı seçeneği bulunur. Google Gemini ve
Anthropic Claude native REST adaptörleriyle; OpenAI, xAI/Grok, NVIDIA NIM, Hugging
Face, Groq, OpenRouter, Mistral, Cohere, DeepSeek, Together, Fireworks, Cerebras,
SambaNova, Perplexity, Qwen, Kimi ve diğer OpenAI uyumlu servisler hazır güvenli
base URL'lerle sunulur. Ollama, LM Studio, LocalAI, vLLM, llama.cpp ve Jan için
loopback yerel presetleri de vardır. Gemini anahtarı `x-goog-api-key`, Anthropic
anahtarı `x-api-key`, diğer uyumlu servislerin anahtarları Bearer başlığıyla yalnızca
backend tarafından gönderilir.

## Terminal ve zorunlu doğrulama

Xultron, AI sağlayıcısına her kullanıcı sorusunda kalıcı bir terminal ve doğrulama
politikası gönderir. Backend soruyu önce sabit, sınırlandırılmış niyet kurallarıyla
planlar; yalnızca izin verilen bir aracı çalıştırdıktan ve kullanılabilir kanıt elde
ettikten sonra nihai cevap çağrısına izin verir. Selamlaşma, saat, hesaplama ve
desteklenen canlı telefon durumları sağlayıcıya ikinci kez sorulmadan kısa ve doğrudan
yanıtlanır. Bu kontrol kullanıcıya cevap başında gösterilmez; yanıt doğrudan sorunun
cevabıyla başlar. Kontrol başarısızsa Xultron tahmin üretmez.

Niyet eşleme Türkçe karakter eksikliği, tek harflik yazım hataları ve yaygın ekleri
sınırlı bir araç sözlüğünde tolere eder. Konum gibi özel veri işlemleri bulanık
eşlemeyle otomatik açılmaz ve açık izin şartını korur. Bu tasarım OpenClaw'ın MIT
lisanslı sınırlı Levenshtein ve korumalı eşleme desenlerinden uyarlanmıştır; ayrıntılı
atıf [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) dosyasındadır.

Desteklenen doğrulama yolları:

- GMT/UTC temelinden seçilen ülke saat dilimine dönüştürülen canlı saat ve tarih
- Xultron kaynak ağacında sınırlandırılmış proje araması
- Güvenli aritmetik değerlendirme
- Sabit HTTPS arama adresi üzerinden kaynak alan adı ve URL içeren güncel web kanıtı

Cihaz bataryası, depolama, ağ ve konum gibi Termux:API otomasyonları bu sürümde
kapalıdır. Böylece eksik veya hatalı Android izinleri sohbet akışını kesmez.

Modelin serbest biçimli shell komutu çalıştırmasına izin verilmez. Dosya silme,
mesaj gönderme, kamera, satın alma ve diğer yan etkili komutlar otomatik araç
listesinde bulunmaz. Web doğrulaması parola, PIN, API anahtarı, token veya e-posta
benzeri özel veri algılarsa sorguyu dışarı göndermez. Web doğrulaması
`VERIFICATION_WEB_ENABLED=false` ile kapatıldığında ilgili sorular cevap yerine
kapalı biçimde doğrulama hatası alır.

## Yerel PIN girişi

Geliştirme kurulumu isteğe bağlı tek kullanıcı için dört haneli PIN ekranı sunar.
Gerçek kullanıcı adı ve PIN hash'i kaynakta tutulmaz; yalnızca Git tarafından yok
sayılan `backend/instance/secrets.env` veya süreç ortamından okunur. Yerel giriş
ekranındaki kullanıcı ve görünen ad `frontend/.env.local` dosyasında tutulabilir.
Örnek değerler için `backend/.env.example` dosyasına bak. Mevcut yerel hesabı yeniden
hazırlamak için `cd backend && .venv/bin/flask --app run.py provision-local-pin`
komutunu çalıştır. Bu kolaylık üretim ortamında varsayılan olarak kapalıdır. Arayüz
dili Sistemler → Genel bölümünden İngilizce ve Türkçe arasında anında değiştirilebilir.

GitHub sürümü kişisel veri içermeyen temiz kaynak profilidir. Sohbet, hafıza,
oturum, sağlayıcı kimlik bilgileri ve yerel kimlik yapılandırması yalnızca Git dışı
runtime profilinde kalır. Ayrıntılar ve silme komutu için
[`docs/DATA_PROFILES.md`](docs/DATA_PROFILES.md) belgesine bak.

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
