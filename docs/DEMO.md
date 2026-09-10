# Xultron demo and Android builds

## Local demo

The local demo uses the same Flask API and PWA that the project ships. It is the recommended path when evaluating Xultron because it exercises authentication, provider configuration, SSE streaming, privacy controls, and the service worker together.

```bash
make setup
make serve
```

Then open [http://127.0.0.1:5000](http://127.0.0.1:5000). Create a local account, configure a provider from Settings, and start a conversation. Use a disposable provider key for demonstrations.

## Android debug builds

Debug APKs are published as prerelease assets on the [GitHub Releases page](https://github.com/trackview1827-ctrl/Xultron/releases). They are intended for internal testing, not Play Store distribution.

1. Download the debug APK from a release whose target is the `app` branch.
2. Verify its SHA-256 checksum when the release provides one.
3. Enable installation from the source application only if you trust the downloaded release.
4. Install the APK, then test a fresh launch, sign-in, local backend mode, and logout before sharing it with a tester.

## Build your own APK

Use an Android SDK-equipped Linux, macOS, or CI environment:

```bash
cd android
export ANDROID_HOME="$HOME/android-sdk"
export ANDROID_SDK_ROOT="$ANDROID_HOME"
./gradlew test lint assembleDebug --stacktrace
sha256sum app/build/outputs/apk/debug/app-debug.apk
```

A debug APK is installable, but it is not a signed production artifact. Before a store rollout, build a signed release candidate, test it on physical devices, upload symbols, and follow the checklist in [android/README.md](../android/README.md).
