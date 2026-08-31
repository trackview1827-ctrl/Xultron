# Xultron Android hazırlık iskeleti

Bu dal, Android uygulamasının Phase 0 temelini içerir. Tam özellikler henüz
uygulanmadı.

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

Codespace içinde JDK 21, Android SDK Platform 35, Build Tools ve Gradle 8.9 wrapper
kuruludur. Telefon/Termux üzerinde APK derlenmez. Codespace build komutu:

```bash
export JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64
export ANDROID_HOME="$HOME/android-sdk"
export ANDROID_SDK_ROOT="$ANDROID_HOME"
./gradlew :app:assembleDebug
```

İlk başarılı Codespace buildinin ortam, boyut, SHA-256 ve kapsam sınırları
[`BUILD_EVIDENCE.md`](BUILD_EVIDENCE.md) içinde kayıtlıdır.

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
