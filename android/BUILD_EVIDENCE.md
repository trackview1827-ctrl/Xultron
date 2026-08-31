# Android Phase 0-3 build evidence

This report records the successful Codespace validation of the Android Phase 0-3 implementation. It does not claim that later phases or physical-device behavior are complete.

## Environment

- Branch: `app`
- App version: `0.3.0` (`versionCode` 3)
- Minimum Android: API 29 / Android 10
- Compile and target SDK: API 35
- Build host architecture: `x86_64`
- JDK: OpenJDK 21.0.12
- Gradle Wrapper: 8.9
- Packaged ABIs: `arm64-v8a`, `x86_64`

## Commands

```bash
export JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64
export ANDROID_HOME="$HOME/android-sdk"
export ANDROID_SDK_ROOT="$ANDROID_HOME"
./gradlew test lint assembleDebug --stacktrace
```

Backend validation was run separately with the full `pytest` suite and a blank-SQLite migration upgrade/downgrade/upgrade round trip.

## Observed result

```text
BUILD SUCCESSFUL
Tasks: test, lint, assembleDebug
Artifact: app/build/outputs/apk/debug/app-debug.apk
Size: 29,377,925 bytes
SHA-256: 84a7d48aeb977c23e0344211ef04c9cadb1efd4d4fb9502da16641388278ea64
```

The checksum describes the ephemeral Codespace debug artifact signed with that environment's debug key. It is evidence of the observed build, not a reproducible release checksum.

## Implemented scope

- Phase 0 Android project, Gradle wrapper, Codespace provisioning and CI workflow
- Native mobile login, registration, guest, rotating refresh and logout session flows
- Keystore-backed encrypted local session storage and HTTPS-only Retrofit client
- Compose shell for chat, conversations, memory, providers and settings
- Offline, loading, empty and error UI states
- App-private SQLite local backend mode for basic local auth, chat, conversations,
  providers and settings; it opens no network listener
- Android permission state model for microphone, camera, foreground/background location, sensors, notifications and overlay special access
- Fail-closed local capability engine and Android Settings redirects
- Android 10 minimum, API 35 target and 64-bit `arm64-v8a` plus `x86_64` packaging
- Backup and device-transfer exclusions for application data

## Explicitly not implemented in Phase 0-3

Wake-word listening, foreground services, overlay navbar, MediaProjection screen sharing, screenshot upload, terminal execution, camera capture, continuous location/sensor collection and the remaining Phase 4-7 features in `docs/ANDROID_APP_PLAN.md` are not implemented.

Physical-device installation and live end-to-end operation against a deployed backend have not yet been validated. The Android public build path and backend API paths were validated independently in Codespace and backend tests.

The local backend mode is implemented in Android, but its physical-device UX and
data migration behavior still require device acceptance testing.
