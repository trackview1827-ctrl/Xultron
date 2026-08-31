# Android Phase 0 build evidence

This report records the first successful Codespace build of the Android scaffold. It does not claim that the planned product features are implemented.

## Environment

- Branch: `app`
- Minimum Android: API 29 / Android 10
- Compile and target SDK: API 35
- Build host architecture: `x86_64`
- JDK: OpenJDK 21.0.12
- Gradle Wrapper: 8.9
- Packaged ABIs: `arm64-v8a`, `x86_64`

## Command

```bash
export JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64
export ANDROID_HOME="$HOME/android-sdk"
export ANDROID_SDK_ROOT="$ANDROID_HOME"
./gradlew :app:assembleDebug
```

## Observed result

```text
BUILD SUCCESSFUL
Artifact: app/build/outputs/apk/debug/app-debug.apk
Size: 28,803,064 bytes
SHA-256: 253a92a18812e891a3e5d58af0da884249794c7deae0710183348a898f505ccb
```

The checksum describes the ephemeral Codespace debug artifact signed with that environment's debug key. It is evidence of the observed build, not a reproducible release checksum.

## Implemented scope

- Android project and Gradle wrapper
- Compose launcher screen
- Android 10 minimum and 64-bit ABI policy
- Manifest permission declarations
- HTTPS-only network security configuration
- Retrofit, OkHttp, Kotlin serialization, DataStore and WorkManager dependencies

## Not implemented yet

Authentication, chat, wake word, overlay navbar, terminal execution, camera, location, sensors, screen sharing, screenshot upload, background services and the other features in `docs/ANDROID_APP_PLAN.md` remain implementation work.

Device or emulator installation and runtime validation have not been performed yet.
