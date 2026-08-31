# Xultron Android

`app` dalı, uygulama planındaki Phase 0-3 kapsamını içerir:

- Codespaces/CI tabanlı Android build ortamı
- Native mobil login, kayıt, misafir oturumu, rotating refresh ve revoke
- Keystore anahtarıyla AES-GCM şifreli yerel session
- Phase 0-3 baseline olarak chat, konuşmalar, memory, provider ve ayarlar Compose ekranları
- App-private SQLite tabanlı yerel backend modu; ağ olmadan temel hesap, chat,
  konuşma, provider ve ayar verilerini cihazda tutar
- Loading, empty, offline, hata ve bağlantı durumları
- Gerçek Android permission state, Settings yönlendirmeleri ve fail-closed
  Capability Engine

İleri fazlarda ortak ürün UI'sı web frontend'den beslenecektir: chat, konuşmalar,
memory, provider, standart ayarlar ve hesap görünümü React/Vite UI'sı olarak webde
ve uygulama içindeki güvenli WebView/container'da ortak tutulur. Terminal,
wake-word, foreground service, bildirim, overlay, MediaProjection, kamera, sensör,
konum, SAF ve uygulama yaşam döngüsü gibi uygulamaya özel yetenekler native Android
katmanında kalır. Token/Keystore sırları WebView JavaScript'ine aktarılmaz.

Phase 0-3 Android uygulamasında girişten sonra `Web UI` sekmesi mevcut backend'in
web frontend'ini güvenli container içinde açar. Termux kullanırken önce backend
çalışmalı ve Backend URL alanında `http://127.0.0.1:5000` kayıtlı olmalıdır. Native
Compose ekranları geçiş dönemi ve privileged özellikler için korunur; Web UI'ya
native bearer token aktarılmaz.

Terminal, wake-word, sürekli foreground service, overlay navbar, MediaProjection,
kamera ve sensör işlevlerinin kendisi Phase 4-7 kapsamındadır. Phase 3 yalnız izin
durumunu ve capability politikasını hazırlar; bu sonraki özellikleri çalıştırmaz.

## Hedef platform

- Minimum: Android 10 / API 29
- Compile ve target başlangıcı: API 35
- ABI: `arm64-v8a` ve `x86_64`
- Bilinçli olarak dışarıda: `x86` ve `armeabi-v7a` 32-bit paketleri
- Uygulama kimliği: `ai.xultron.app`

`x86_64`, 64-bit Android emülatörleri içindir. Fiziksel telefonlarda temel hedef
`arm64-v8a` olacaktır.

## Gerekli araçlar

- JDK 17 veya üstü
- Android SDK Platform 35
- Android SDK Build Tools güncel sürümü
- Gradle 8.9 uyumlu dağıtım veya Android Studio'nun Gradle entegrasyonu
- Android 10/API 29 ve Android 15/API 35 emülatör/device test hedefleri

`.devcontainer/devcontainer.json`, yeni Codespace oluşturulurken JDK 21, Android
SDK Platform 35, Build Tools 35 ve Gradle 8.9 wrapper ortamını hazırlar.
Telefon/Termux üzerinde APK derlenmez. Codespace build komutu:

```bash
export JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64
export ANDROID_HOME="$HOME/android-sdk"
export ANDROID_SDK_ROOT="$ANDROID_HOME"
./gradlew :app:assembleDebug
```

`app` dalına gönderilen Android değişiklikleri `.github/workflows/android.yml`
üzerinden unit test, lint ve debug APK derlemesini de çalıştırır. CI yalnız geçici
artifact üretir; GitHub Release yayımlamaz.

İlk başarılı Codespace buildinin ortam, boyut, SHA-256 ve kapsam sınırları
[`BUILD_EVIDENCE.md`](BUILD_EVIDENCE.md) içinde kayıtlıdır.

## Backend modları

Uygulama ilk açılışta yerel backend ile gelir. Bu mod `local://xultron` adresiyle
Android uygulamasının içinde çalışır, ağ portu açmaz ve verileri uygulamanın özel
SQLite veritabanında tutar. Yerel moddaki chat yanıtı basit yerel yanıttır; gerçek
AI sağlayıcı çağrıları için ayarlardan HTTPS uzak backend seçilmelidir.

Uzak backend kullanılırken Backend alanına yalnızca HTTPS kök adresi yazılır,
uygulama `/api/v1` yolunu kendisi ekler. Aynı telefondaki Termux Flask backendine
bağlanmak için yalnızca `http://127.0.0.1:5000` ve `http://localhost:5000`
loopback adreslerine izin verilir. Diğer tüm HTTP/IP adresleri güvenlik nedeniyle
reddedilir. Yerel SQLite verisi uygulama kaldırılınca silinir ve backup
kurallarıyla dışa aktarılmaz.

## Ağ ve sertifika yaklaşımı

- Android tarafı `Retrofit + OkHttp` kullanır.
- Cleartext HTTP kapalıdır.
- TLS sertifika doğrulaması Android sistem CA deposuyla yapılır.
- Üretim backend hostname'i kesinleşmeden statik certificate pin eklenmez.
  Pin uygulanırsa rotasyon ve yedek pin politikası ayrıca test edilmelidir.
- Android'e Python `requests` veya `certifi` kurulmaz. Backend tarafında
  `requests` ve doğrudan `certifi` gereksinimleri `backend/requirements.txt`
  içinde tutulur.
- API token, cookie ve refresh bilgileri loglanmaz; Keystore/şifreli yerel
  depolama kararı auth implementasyonunda uygulanır.

## İzin politikası

Manifest'te özelliklerin ihtiyaç duyacağı izinler tanımlıdır, fakat uygulama
izinleri açılışta otomatik vermez. İzinler ilgili özellik ilk kez etkinleştirilirken
kullanıcıya açıklanarak istenir:

- Mikrofon/kamera: aktif voice veya kamera akışı
- Konum: foreground; background konum yalnız açık özellik ve ayrı onayla
- Bildirim: Android 13+
- Overlay: wake-word navbarı için Settings üzerinden açık kullanıcı onayı
- MediaProjection: her ekran paylaşımı oturumu için sistem onayı
- Foreground service type: servis gerçekten ilgili kaynağı kullanırken

`MANAGE_EXTERNAL_STORAGE` ve geniş dosya erişimi eklenmedi. `/storage/emulated/0/xultron`
için SAF kullanıcı seçimi ve uygulama-özel depolama kullanılacaktır.
