#!/usr/bin/env bash
set -euo pipefail

ANDROID_HOME="${ANDROID_HOME:-$HOME/android-sdk}"
TOOLS_VERSION="11076708"
TOOLS_SHA256="2d2d50857e4eb553af5a6dc3ad507a17adf43d115264b1afc116f95c92e5e258"
ARCHIVE="commandlinetools-linux-${TOOLS_VERSION}_latest.zip"
URL="https://dl.google.com/android/repository/${ARCHIVE}"

if [[ ! -x "$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager" ]]; then
  workdir="$(mktemp -d)"
  trap 'rm -rf "$workdir"' EXIT
  curl --fail --location --retry 3 "$URL" --output "$workdir/$ARCHIVE"
  echo "$TOOLS_SHA256  $workdir/$ARCHIVE" | sha256sum --check --status
  mkdir -p "$ANDROID_HOME/cmdline-tools/latest"
  unzip -q "$workdir/$ARCHIVE" -d "$workdir/unpacked"
  mv "$workdir/unpacked/cmdline-tools"/* "$ANDROID_HOME/cmdline-tools/latest/"
fi

export PATH="$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools:$PATH"
yes | sdkmanager --licenses >/dev/null
sdkmanager "platform-tools" "platforms;android-35" "build-tools;35.0.0"

./android/gradlew -p android --version
