# Xultron Android App Implementation Planı

> Durum: Yalnızca plan. Android kodu henüz yazılmadı.
>
> Kaynak: `xultronappplanlama.md` ve mevcut Xultron repository incelemesi.
>
> Bu belge, kaynak şartnamenin kopyası değildir. Mevcut repository gerçekleri,
> Android kısıtlamaları, uygulanabilir mimari kararları ve ölçülebilir kabul
> kriterleriyle hazırlanmış implementation planıdır.

## Dürüst kapsam kararı

- Standart Android uygulaması telefonda sınırsız root veya sistem terminali sağlayamaz.
- `FULL ACCESS`, Android uygulamasının ve kullanıcının ayrıca etkinleştirdiği Termux,
  Shizuku veya root sağlayıcısının gerçekten erişebildiği en geniş kapsam demektir.
- `/storage/emulated/0/xultron` her Android sürümünde doğrudan POSIX çalışma dizini
  değildir. Varsayılan çözüm app-private storage ve kullanıcı tarafından seçilen SAF
  tree URI olacaktır.
- Arka planda mikrofon, wake-word ve yeniden başlatma Android, üretici ve kullanıcı
  ayarları tarafından sınırlandırılır. Uygulama bu sınırları bypass etmeyecektir.
- Beş wake-word kaydı enrollment akışını sağlar; production kalitesi FAR/FRR,
  replay, gürültü, CPU, thermal ve batarya testleri geçmeden garanti edilmeyecektir.
- Mevcut device command route'ları Android'e doğrudan bağlanmayacaktır. Mevcut
  `routes.py` yüzeyinde command payload/string, device auth proof, nonce, expiry,
  idempotency, result attestation ve yeterli testler bulunmadığından önce typed
  device-action control plane yapılmalıdır.

## 1. Existing Xultron Architecture

### Repository

```text
Xultron/
├── backend/       Flask, SQLAlchemy, SQLite, migrations, REST/SSE
├── frontend/      React, TypeScript, Vite, Tailwind, Framer Motion
├── cli/           npm ile dağıtılan xultron komutu
├── scripts/       bootstrap, development ve release scriptleri
└── docs/          architecture, API, acceptance ve validation belgeleri
```

### Mevcut backend

- Flask API `/api/v1` altında çalışır.
- SQLAlchemy ve SQLite kullanılır.
- Alembic/Flask-Migrate migration yapısı vardır.
- Browser authentication HttpOnly session cookie ve CSRF kullanır.
- Chat için normal JSON ve SSE stream endpoint'leri vardır.
- AI, STT ve TTS provider registry bulunur.
- Provider credential'ları backend tarafından şifrelenir ve maskeli döndürülür.
- Memory, settings, tasks, voice, OAuth ve agent ToolRegistry servisleri bulunur.
- Mevcut `POST /devices`, `POST /devices/{id}/commands` ve event yüzeyi Android
  için henüz güvenli production protokolü değildir.

### Mevcut frontend

- Auth ve guest mode
- Chat ve conversation history
- Provider CRUD, connection test ve model discovery
- Memory
- Voice
- Settings
- Core state machine
- Tasks
- Low-data ve reduced-motion davranışı
- PWA shell ve service worker

### Gerçek acceptance tabanı

Mevcut plan hazırlanırken şu sınırlar çalıştırıldı:

- Backend: 128 test geçti.
- Frontend: 17 test dosyası, 66 test geçti.
- TypeScript typecheck geçti.
- Vite production build 457 modülle tamamlandı.
- `bash -n scripts/bootstrap.sh` geçti.

Bu testler Android’in var olduğunu göstermez. Repository’de henüz `android/` modülü,
Android manifest’i, APK pipeline’ı veya device test hedefi yoktur.

## 2. Android Architecture Decision

### Karar: Native-first Jetpack Compose

```text
Kotlin + Jetpack Compose
        ↓
Native Android services and permissions
        ↓
Central Capability Engine
        ↓
Retrofit/Ktor + OkHttp
        ↓
Existing Flask REST/SSE backend
```

Native-first seçilmesinin nedenleri:

- Foreground microphone service native lifecycle ister.
- Wake-word ekran kapalıyken WebView içinde güvenilir şekilde çalışmaz.
- Kamera, sensör, konum ve MediaProjection izinleri native akış ister.
- Terminal policy native execution sınırında enforce edilmelidir.
- Offline, battery ve process lifecycle için native kontrol gerekir.
- Overlay ve screen capture WebView bridge üzerinden verilirse güvenlik yüzeyi büyür.

WebView tüm uygulamanın yerine kullanılmayacaktır. Gerekirse yalnızca düşük riskli,
trusted-origin bir yüzey olarak ayrıca değerlendirilebilir. Privileged ekranlar Compose
olacaktır.

Paylaşılacak şey UI kodu değil, API şemaları, capability isimleri, error code'ları,
action schema'ları, state isimleri, feature inventory ve test senaryolarıdır.

### SDK seçimi

- `minSdk = 26` (Android 8): modern foreground service, notification, storage ve
  security API'leri için makul taban; daha eski sürümlerin ek compatibility yükü
  bu ürünün background/voice hedeflerine değmez.
- `compileSdk = 35` başlangıç baseline'ı: Android 15 API davranışları Phase 0'da
  derlenip test edilir.
- `targetSdk = 35` başlangıç baseline'ı: Android 15'in güncel permission ve
  foreground-service kuralları zorunlu olarak görülür.
- Release öncesi `compileSdk` ve `targetSdk`, Play ve Android'in o tarihteki
  güncel zorunlu API seviyesine yükseltilir. Bu yükseltme yapılmadan release kabul
  edilmez; Android 13, 14, 15 ve güncel sürüm matrisi yeniden çalıştırılır.

## 3. Module Structure

```text
android/
├── settings.gradle.kts
├── build.gradle.kts
├── gradle.properties
├── gradlew
├── app/
│   └── src/{main,test,androidTest}/
├── core/
│   ├── common/
│   ├── network/
│   ├── auth/
│   ├── security/
│   ├── database/
│   ├── datastore/
│   ├── permissions/
│   ├── capabilities/
│   └── audit/
├── feature-auth/
├── feature-chat/
├── feature-conversations/
├── feature-memory/
├── feature-providers/
├── feature-settings/
├── feature-terminal/
├── feature-voice/
├── feature-sensors/
├── feature-camera/
├── feature-location/
├── feature-notifications/
├── feature-diagnostics/
└── service/
```

Başlangıçta gereksiz Gradle modülü açılmayacak. `app`, `core` ve feature paketleriyle
başlanıp build süresi ve bağımlılık sınırları ölçülecek.

## 4. Permission Architecture

Android sistem izni ile Xultron kullanıcı politikası farklı katmanlardır:

```text
AI Action Request
 → schema validation
 → Capability Engine
 → user policy
 → Android permission
 → risk confirmation
 → input/path validation
 → execution
 → audit
```

### Capabilities

```text
MICROPHONE
CAMERA
LOCATION_FOREGROUND
LOCATION_BACKGROUND
SENSORS
NOTIFICATIONS
FILES_XULTRON
FILES_USER_SELECTED
TERMINAL_FULL
TERMINAL_RESTRICTED
TERMINAL_XULTRON_ONLY
TERMINAL_DISABLED
FOREGROUND_SERVICE_MICROPHONE
FOREGROUND_SERVICE_MEDIA_PROJECTION
DISPLAY_OVER_OTHER_APPS
SCREEN_CAPTURE
SCREENSHOT_UPLOAD
TERMUX_EXECUTION
SHIZUKU_EXECUTION
ROOT_EXECUTION
```

Her capability için `userEnabled`, `androidGranted`, `systemRestricted`,
`requiresConfirmation`, `lastCheckedAt` ve `lastDeniedReason` tutulur.

UI gerçek Android durumunu göstermelidir: Granted, Denied, While using, Allow all
the time, Restricted, Not available, Requires Settings ve Disabled by policy.

Android 13+ notification, background location, microphone FGS, camera FGS ve
MediaProjection kuralları ayrı ayrı uygulanacaktır. Uygulama kullanıcıdan izin ister,
izinleri kendisi vermez ve sistem kısıtlamasını sahte şekilde aşmaz.

## 5. Terminal Architecture

### Execution provider’ları

```text
AppProcessExecutor
TermuxExecutor
ShizukuExecutor
RootExecutor
```

`AppProcessExecutor` yalnız uygulamanın UID sandbox’ında ve kullanıcı tarafından
seçilen SAF alanlarında çalışır. Termux, Shizuku ve root ayrı opt-in advanced
entegrasyonlardır. Hiçbiri temel çalışma için zorunlu değildir.

### Modlar

#### FULL ACCESS

Android/provider sınırları içindeki en geniş izin. Root veya başka uygulamaların data
alanlarına otomatik erişim anlamına gelmez. Destructive işlemler yine onay ister.

#### RESTRICTED ACCESS

- Versioned action/command allowlist
- Allowed executable allowlist
- Allowed root directories
- Environment allowlist
- Timeout
- Output byte limit
- Network policy
- Destructive action block

#### XULTRON DIRECTORY ONLY

- Canonical path kontrolü
- `..` reddi
- Symlink çözümleme
- Root boundary kontrolü
- Null byte reddi
- Shell expansion reddi
- Environment expansion reddi
- Subshell ve command chaining reddi
- TOCTOU riskinin azaltılması

SAF URI, POSIX path veya shell `cwd` gibi yorumlanmayacaktır.

#### NO TERMINAL ACCESS

Execution katmanına hiç ulaşmadan fail-closed reddedilir. UI’de terminal alanı
bulunsa bile command çalışmaz.

AI veya backend’den gelen raw string şu şekilde çalıştırılmayacaktır:

```text
sh -c "<untrusted string>"
```

Bunun yerine typed `actionId`, versioned input ve doğrulanmış argv kullanılacaktır.

## 6. Voice Architecture

### Aktif konuşma

```text
Wake word
 → local VAD
 → STT
 → Xultron backend/AI
 → TTS
```

### Uyku modu

Uyku modunda yalnızca local wake-word detector çalışır:

- Cloud STT yok.
- Backend’e raw microphone stream yok.
- Polling yok.
- Sürekli WebSocket yok.
- AI ve TTS yok.
- Ağ trafiği uygulama seviyesinde mümkün olduğunca 0 byte olur.

### Five-sample enrollment

Kullanıcı:

1. `Voice > Wake Word` ekranında ifadeyi yazar.
2. Mikrofon izni verir.
3. Aynı ifadeyi beş ayrı kez söyler.
4. Her kaydın kalite, süre, gürültü ve speech-detected durumu kontrol edilir.
5. Feature vector/profile oluşturulur.
6. Ham ses varsayılan olarak silinir.
7. Profile local encrypted saklanır.

Model seçimi şu ölçümler tamamlanmadan sabitlenmez:

- FAR ve FRR
- Türkçe telaffuz ve aksan
- Gürültü, mesafe ve ses yüksekliği
- Replay attack
- CPU, RAM ve thermal
- Battery tüketimi
- Android ABI ve lisans

`Low`, `Normal` ve `High` sensitivity gerçek threshold davranışına bağlanacaktır.

## 7. Background Execution

Wake-word dinleme için kullanıcı tarafından başlatılan microphone foreground service
kullanılır. Persistent service notification zorunludur.

Screen capture kullanılırsa ayrıca `mediaProjection` foreground service type ve
Android sürümüne uygun manifest izinleri gerekir.

### Lifecycle matrisi

| Durum | Beklenen davranış |
|---|---|
| Foreground | UI, chat, settings, active voice |
| Background | Yetkili FGS devam edebilir |
| Ekran kapalı | Sistem ve policy izin verirse local detector |
| Kilitli | Hassas içerik notification’a yazılmaz |
| Doze | Polling durur, sistem kuralları uygulanır |
| İnternet yok | Local wake-word/settings çalışır |
| Wi-Fi → mobile | Network policy yeniden değerlendirilir |
| Mikrofon kaldırıldı | Listening durur |
| Notification kaldırıldı | Service durumu kullanıcıya bildirilir |
| FGS öldürüldü | Sonsuz restart yapılmaz |
| Process kill | Recovery policy uygulanır |
| Force-stop | Otomatik restart garanti edilmez |
| Reboot | Android’in izin verdiği recovery denenir |
| Backend restart | Exponential backoff reconnect |
| Samsung restriction | Üretici ayar yönergeleri gösterilir |

## 8. Security Architecture

### Threat model

- Malicious prompt ve prompt injection
- Compromised backend
- Stolen token
- WebView/bridge injection
- Intent/deep-link injection
- Shell injection
- Path traversal ve symlink escape
- Malicious file upload
- Localhost abuse
- Exported component abuse
- Insecure WebSocket ve MITM
- Log credential leakage
- Wake-word replay
- Overlay clickjacking
- İzinsiz ekran görüntüsü veya ekran paylaşımı

### Kontroller

- Android client backend action’ını güvenilmez kabul eder.
- Capability, policy, permission ve confirmation local olarak tekrar kontrol edilir.
- Action schema versioned, typed, expiry’li, nonce’lu ve idempotent olur.
- Device-bound access token/proof-of-possession değerlendirilir.
- TLS zorunludur.
- Secret, token, password, raw audio, screenshot ve hassas dosya içeriği loglanmaz.
- Manifest exported component’leri minimum tutulur.
- WebView varsa trusted-origin allowlist, CSP, mixed content kapatma, file access
  kapatma, debugging kapatma ve unrestricted JavaScript bridge yasağı uygulanır.

## 9. Backend Changes

### Native authentication

```text
POST /api/v1/device-auth/enroll
POST /api/v1/device-auth/login
POST /api/v1/device-auth/refresh
POST /api/v1/device-auth/logout
POST /api/v1/device-auth/revoke
GET  /api/v1/device-auth/sessions
```

Access token kısa ömürlü, refresh token rotating ve backend’de hash’li tutulur.
Device revoke ve session revoke desteklenir.

### Device API

```text
POST   /api/v1/devices/register
GET    /api/v1/devices
GET    /api/v1/devices/{id}
PATCH  /api/v1/devices/{id}
DELETE /api/v1/devices/{id}
```

### Typed action control plane

```text
POST /api/v1/devices/{id}/action-requests
GET  /api/v1/devices/{id}/action-requests
POST /api/v1/devices/{id}/action-requests/{requestId}/ack
POST /api/v1/devices/{id}/action-requests/{requestId}/result
```

Action alanları:

```text
schemaVersion
requestId
actionId
deviceId
capability
input
risk
requiresConfirmation
expiresAt
nonce
idempotencyKey
userContext
resultStatus
auditCorrelationId
```

Raw shell command yerine action ID kullanılacaktır.

### Screen capture upload

Ayrı endpoint önerisi:

```text
POST /api/v1/devices/{id}/screen-captures
```

Zorunlu kontroller:

- Device-bound access token
- Tek kullanımlık action token
- Nonce ve idempotency
- En fazla 60 saniye expiry
- `retention=none` varsayılanı
- Boyut ve süre limiti
- Upload sonucu ve correlation ID

Backend screenshot’ı varsayılan olarak kalıcı saklamaz. Geçici buffer en geç 60
saniyede silinir. Kalıcı saklama ayrıca kullanıcı ayarı, retention, silme endpoint’i,
replica ve backup politikası gerektirir.

### Audit ve push

```text
POST   /api/v1/devices/{id}/audit-events
GET    /api/v1/devices/{id}/audit-events
DELETE /api/v1/devices/{id}/audit-events
POST   /api/v1/devices/{id}/push-tokens
DELETE /api/v1/devices/{id}/push-tokens/{tokenId}
```

Audit yalnız action tipi, sonuç, süre, boyut, risk ve correlation ID taşır.

## 10. Frontend Changes

### Feature parity inventory

| Web feature | Android implementation | Katman | Backend |
|---|---|---|---|
| Auth/guest | Compose auth | Native | Device auth |
| Chat/stream | Compose + SSE | Native/shared contract | Mevcut API |
| Conversations | Compose list/detail | Native | Mevcut API |
| Memory/auto memory | Compose + backend | Shared | Mevcut API |
| AI/STT/TTS providers | Compose settings | Native | Mevcut API |
| Model discovery | Compose provider UI | Native | Mevcut API |
| Attachments/images/files | SAF/picker/upload | Native | Validation/upload |
| Voice | Native recorder/VAD | Native | Mevcut voice API |
| Agent actions | Typed action UI | Shared policy | Yeni device API |
| Terminal | Native policy engine | Native | Yeni action API |
| Tasks/state | Compose | Shared | Existing/new task API |
| Connection/offline | Native state machine | Shared contract | Health/reconnect |
| Notifications | Android channels | Native | Push token |
| Wake-word | Local FGS | Native | Gerekmez |
| Sensors/camera/location | Native APIs | Native | İsteğe bağlı action |
| Diagnostics/activity log | Compose | Native | Safe metadata |

Web’deki hiçbir mevcut feature sessizce atlanmayacak. Her feature için implementation,
backend change ve status ayrı traceability tablosunda tutulacak.

## 11. Android Components

```text
MainActivity
XultronApplication

AuthViewModel
ChatViewModel
ConversationViewModel
MemoryViewModel
ProviderViewModel
SettingsViewModel
PermissionViewModel
TerminalViewModel
VoiceViewModel
ScreenCaptureViewModel
DiagnosticsViewModel

XultronForegroundService
WakeWordService
ScreenCaptureService
BootReceiver

CapabilityEngine
AndroidPermissionManager
TerminalPolicyManager
ProcessExecutionManager
WakeWordManager
VADManager
SensorManagerFacade
CameraManager
LocationManagerFacade
NotificationManagerFacade
OverlayManager
MediaProjectionManager
BatteryOptimizationManager
```

Tek bir action/capability boundary bütün privileged işlemlerde kullanılmalıdır.

## 12. Data Model

### DataStore

```text
theme
locale
lowDataMode
sleepModeEnabled
sleepTimeout
wakeWordEnabled
wakeWordSensitivity
terminalMode
askBeforeSensitiveActions
locationMode
overlayEnabled
screenCaptureEnabled
screenshotPreviewRequired
selectedDeviceId
```

### Keystore

Keystore içinde kriptografik anahtar tutulur. Plaintext parola, token veya raw audio
saklanmış sayılmaz. Refresh token, wake profile ve local database gerektiğinde bu
anahtarlarla şifrelenir. Backup kapsamı açıkça kapatılır veya kontrollü yönetilir.

### Room

```text
DeviceEntity
ConversationCacheEntity
PendingActionEntity
AuditEventEntity
ConnectionEventEntity
WakeProfileEntity
PermissionSnapshotEntity
ScreenCaptureEventEntity
```

Projection Intent/result data/token Room veya DataStore’a yazılmaz.

## 13. Network Protocol

- HTTPS only.
- Native auth için Bearer access token.
- Rotating refresh token.
- Request ID, nonce, expiry ve idempotency key.
- Retrofit/Ktor + OkHttp.
- Kotlin serialization.
- SSE stream için state, conversation, delta, done, error event’leri.
- Exponential backoff reconnect.
- Offline action kuyruğuna terminal, camera, location sharing veya destructive action
  bırakılmaz.
- Screenshot upload varsayılan olarak `retention=none` ile tek action olarak işlenir.
- Upload timeout/network error sonunda buffer, ImageReader, VirtualDisplay ve upload
  job temizlenir.

## 14. Development Phases

### Phase 0: Foundation

Android Gradle projesi, Kotlin, Compose, JDK/SDK, min/target SDK kararı,
Codespaces ve GitHub Actions.

### Phase 1: Login + Backend

Native device auth, guest mode, token rotation, revoke, device registration.

### Phase 2: Android UI

Dark Xultron visual language, chat, conversation, memory, provider, settings,
offline ve connection state.

### Phase 3: Native Permission Bridge

Capability Engine, gerçek Android permission state, Settings yönlendirmeleri,
fail-closed policy.

### Phase 4: Terminal

Typed action protocol, AppProcessExecutor, dört erişim modu, path validation,
confirmation, audit, Termux/Shizuku/root opt-in adaptörleri.

### Phase 5: Voice/Wake Word

Beş örnek enrollment, local profile, model benchmark, local detector, VAD, STT/TTS.
Model başarı kriterleri geçmezse fixed wake-word veya sonraki sürüm kararı verilir.

### Phase 6: Background Service

Microphone FGS, sleep mode, persistent notification, screen-off, lock, Doze,
process kill, force-stop ve Samsung testleri.

### Phase 7: Sensors/Camera/Location/Overlay

Sensor toggles, CameraX, Fused Location, SAF, overlay navbar, MediaProjection,
screenshot preview ve upload. Bu fazda overlay ve projection izinleri hiçbir zaman
sessizce verilmez.

### Phase 8: Security Hardening

Threat model, manifest, deep link, token leakage, terminal fuzzing, action replay,
clickjacking, upload retention ve log redaction.

### Phase 9: Testing

Unit, integration, security, emulator, fiziksel cihaz, Android 13/14/15/current,
Samsung One UI, Wi-Fi, LTE/5G, airplane, Doze, kill, reboot, backend restart.

### Phase 10: Release

Debug/release APK, signing secret, GitHub Actions artifact, Play policy, privacy
policy, data safety, crash redaction, rollback ve README.

## 15. Risks / Android Limitations

### Overlay

`SYSTEM_ALERT_WINDOW` / Display over other apps izni kullanıcı tarafından verilir.
Overlay sistem permission, projection, biyometrik, kilit ekranı ve parola alanları
üzerinde görünmeyecek. Sistem diyaloğu açılmadan kaldırılıp diyalog kapanmadan
tekrar açılmayacak. Alttaki uygulamaya touch-through veya touch injection yapılmayacak.

### Wake-word sonrası navbar

Wake-word algılandığında ve overlay policy/permission açıksa alttan Xultron navbar’ı
kısa süreli açılır. İzin yoksa uygulama içi ekran veya bildirim fallback’i kullanılır.
Navbar konuşmayı başlatma/durdurma, Xultron’u kapatma, screenshot ve screen-share
action’larını gösterebilir.

### MediaProjection

Her screen-share session yeni, tek kullanımlık sistem consent akışıyla başlar.
Consent token saklanmaz ve tekrar kullanılmaz. Projection callback, service destruction,
process death, lock, error ve replacement session durumlarının tamamı teardown yapar.

### Screenshot

Screenshot varsayılan olarak upload öncesi preview ve confirmation gösterir.
Otomatik PII redaction kusursuz kabul edilmez. Backend retention none varsayılanı,
60 saniyelik geçici buffer limiti ve no-backup politikası uygular.

### Storage

Logo build asset’i ile runtime logo farklıdır. Build logo’su APK `res/mipmap` içine
konur. Runtime `/storage/emulated/0/xultron` erişimi SAF tree URI ile kullanıcı
seçimine bağlıdır. `MANAGE_EXTERNAL_STORAGE` temel çözüm olmayacaktır.

### Background

Force-stop, OEM battery manager, reboot, Android FGS başlangıç kısıtları ve process
kill sonrası sonsuz çalışma garanti edilmez.

## 16. File-by-file Implementation Map

| Dosya/grup | Amaç |
|---|---|
| `android/app/src/main/AndroidManifest.xml` | Permission, service type, receiver ve exported component sınırları |
| `android/.../MainActivity.kt` | Compose host, navigation, deep-link ve permission sonucu |
| `android/.../XultronApplication.kt` | Dependency graph, database, DataStore ve notification kurulumu |
| `android/core/network/` | HTTPS client, auth interceptor, SSE ve network state |
| `android/core/auth/` | Access/refresh token, session, logout ve revoke |
| `android/core/security/` | Keystore, encryption, redacted logging ve backup policy |
| `android/core/permissions/` | Gerçek Android permission state ve Settings yönlendirmeleri |
| `android/core/capabilities/` | Merkezi capability policy ve fail-closed action gate |
| `android/core/audit/` | Hassas içerik olmadan local activity log |
| `android/core/database/` | Room entities, migrations ve offline state |
| `android/core/datastore/` | Küçük ayarların kalıcı saklanması |
| `android/feature-auth/` | Login, register, guest ve device session ekranları |
| `android/feature-chat/` | Chat, SSE stream ve recovery UI |
| `android/feature-conversations/` | Conversation list/detail/history |
| `android/feature-memory/` | Memory görüntüleme ve yönetimi |
| `android/feature-providers/` | AI/STT/TTS provider CRUD, test ve model seçimi |
| `android/feature-settings/` | General, voice, permission, terminal, overlay ve capture ayarları |
| `android/feature-terminal/` | Policy, argv validation, path boundary ve execution adapter’ları |
| `android/feature-voice/` | Wake-word enrollment, detector, VAD ve aktif voice pipeline |
| `android/feature-sensors/` | Sensor discovery, per-sensor policy ve sampling lifecycle |
| `android/feature-camera/` | CameraX capture, preview ve temporary media cleanup |
| `android/feature-location/` | Fused location, foreground/background policy ve battery control |
| `android/feature-notifications/` | Service, Tasks, Alerts ve General notification channels |
| `android/feature-diagnostics/` | Backend, WebSocket, wake-word, mic, FGS, battery, terminal ve son 20 event |
| `android/feature-screen-capture/` | Overlay navbar, preview, MediaProjection ve screenshot upload UI |
| `android/service/XultronForegroundService.kt` | Wake-word microphone foreground service |
| `android/service/WakeWordService.kt` | Local detector lifecycle ve sleep/active state |
| `android/service/ScreenCaptureService.kt` | MediaProjection capture, upload ve stop handling |
| `android/service/ProjectionTeardown.kt` | Callback, error, lock, process death ve replacement cleanup |
| `android/service/BootReceiver.kt` | Android’in izin verdiği reboot recovery davranışı |
| `backend/app/auth/native.py` | Native device auth ve token endpoints |
| `backend/app/devices/routes.py` | Device registration, action ve result transport |
| `backend/app/services/device_auth.py` | Token rotation, device binding ve revoke logic |
| `backend/app/services/device_actions.py` | Typed action schema, expiry, nonce ve idempotency |
| `backend/app/services/device_audit.py` | Redacted privileged action audit |
| `backend/app/services/screen_capture.py` | `retention=none`, size limit ve temporary processing |
| `backend/app/security/native_tokens.py` | Native bearer/proof-of-possession validation |
| `backend/migrations/versions/0007_android_devices.py` | Device/session/action/audit schema |
| `frontend/src/features/devices/` | Web device/session management |
| `frontend/src/features/permissions/` | Shared capability visibility |
| `frontend/src/features/activity-log/` | Web redacted activity log |
| `frontend/src/features/screen-capture/` | Web-side device capture status, not silent capture |
| `frontend/src/services/devicesApi.ts` | Device and action API client |
| `frontend/src/services/capabilitiesApi.ts` | Capability metadata API client |
| `.devcontainer/devcontainer.json` | Codespaces JDK, Android SDK ve build araçları |
| `.github/workflows/android.yml` | Test, lint ve debug APK pipeline |
| `.github/workflows/android-security.yml` | Static/security checks |
| `.github/workflows/android-release.yml` | Protected signing ve release artifact pipeline |

Signing key repository’ye commit edilmeyecek. Cihazdaki logo dosyası Codespace’ten
otomatik okunmayacağı için build asset upload/import süreci ayrıca tanımlanacak.

## 17. Acceptance Criteria

### Foundation ve release

- Codespace’te `./gradlew test`, `./gradlew lint` ve `./gradlew assembleDebug` geçer.
- Signing key ve secret Git geçmişinde yoktur.
- Debug ve release artifact’leri üretilebilir.

### Auth ve API

- Plaintext parola/token local storage’da bulunamaz.
- Logout/revoke sonrası token çalışmaz.
- Başka kullanıcı device veya action göremez.
- Expired, nonce-reused, wrong-device ve replay action istekleri reddedilir.
- Mevcut web cookie/CSRF akışı bozulmaz.

### Capability ve terminal

- Her privileged action Capability Engine’den geçer.
- Disabled mode’da hiçbir command çalışmaz.
- Restricted mode whitelist dışını reddeder.
- `../`, symlink, shell expansion, environment expansion, subshell ve chaining
  testleri reddedilir.
- Unknown action/schema/field fail-closed olur.
- Timeout ve output limitleri çalışır.
- Termux, Shizuku veya root yokken temel uygulama çalışır.

### Voice ve background

- Beş enrollment kaydı kalite kontrolünden geçer.
- Wake profile encrypted local saklanır.
- Sleep mode’da cloud STT veya raw audio upload yoktur.
- FAR/FRR, replay, noise, CPU, thermal ve battery sonuçları kaydedilir.
- Persistent microphone notification görünür.
- Doze, screen-off, locked, process kill, force-stop, reboot ve Samsung testleri
  ayrı sonuçlarla raporlanır.

### Overlay

- Overlay izni olmadan navbar overlay açılmaz; fallback çalışır.
- System permission, projection, biometric, lock-screen ve password UI üzerinde
  overlay görünür piksel ve tıklanabilir alanı sıfırdır.
- Overlay alttaki uygulamaya dokunma geçişi veya injection yapmaz.
- Wake-word navbar görünür, kapanır ve policy’ye uyar.

### MediaProjection ve screenshot

- Her projection oturumu sistem onayı ister.
- Consent Intent/result/token persist edilmez.
- Stop callback, service destruction, process death, lock, error ve replacement
  session sonunda aktif ImageReader, VirtualDisplay, MediaProjection, buffer ve
  upload job sayısı sıfırdır.
- Screenshot upload yalnız capability, user policy, confirmation, device-bound token,
  nonce, expiry ve idempotency kontrollerinden sonra yapılır.
- Yetkisiz, süresi geçmiş, farklı device’a ait veya replay edilmiş upload `401`,
  `403` veya `409` ile reddedilir.
- `retention=none` sonrasında screenshot byte’ı DB, temp, cache, queue, backup ve
  loglarda bulunmaz.
- Audit log’da parola, token, raw image, OCR text veya hassas ekran içeriği bulunmaz.

### Storage ve device features

- SAF tree permission kaybı yönetilir.
- Runtime logo ile APK launcher/splash asset’i ayrıdır.
- Kamera gizlice açık kalmaz.
- Location last-known/fused/adaptive interval ile gereksiz çalışmaz.
- Sensor listener’ları iş bitince kapanır.
- Temp audio/image dosyaları güvenli şekilde silinir.

### Test stratejisi

```text
Unit:
- Capability Engine
- terminal policy
- path validation
- auth/session
- wake-word state machine
- overlay state machine
- projection teardown

Integration:
- Android ↔ backend
- reconnect/SSE
- native action protocol
- permissions
- overlay
- MediaProjection
- screenshot upload

Security:
- command injection
- traversal/symlink
- bridge/intent/deep-link abuse
- token leakage
- replay/expiry
- clickjacking
- retention and backup leakage

Device:
- Android 13, 14, 15 and current
- screen on/off
- locked
- Doze
- Wi-Fi/LTE/5G
- airplane mode
- process kill/force-stop/reboot
- Samsung One UI
```

Bir özellik yalnızca UI’da gösterildiği için tamamlanmış sayılmaz. İlgili Android
cihaz, backend integration, security ve acceptance testleri geçmeden production
özelliği olarak raporlanmayacaktır.
