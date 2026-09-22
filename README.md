# Xultron

> **Mobile-first, self-hosted AI assistant for Android & Termux — voice, memory, multiple LLM providers, and a low-data PWA.**

[![npm](https://img.shields.io/npm/v/xultron-ai.svg?label=npm)](https://www.npmjs.com/package/xultron-ai)
[![Android](https://img.shields.io/badge/Android-debug%20builds-3DDC84.svg)](https://github.com/trackview1827-ctrl/Xultron/releases)
[![PWA](https://img.shields.io/badge/PWA-ready-5EEAD4.svg)](frontend/)
[![License: MIT](https://img.shields.io/badge/License-MIT-7C3AED.svg)](LICENSE)

<p align="center">
  <img src="docs/media/xultron-overview.gif" alt="Xultron mobile AI assistant product walkthrough" width="720">
</p>

<p align="center">
  <strong>Your AI workspace, under your control.</strong><br>
  Run it on Android, Termux, Linux, or macOS with your preferred AI provider.
</p>

## Why Xultron?

Xultron is a private, provider-agnostic personal AI assistant that stays useful on a phone and remains deployable on your own hardware. It combines a mobile-first PWA with a Flask API, voice features, searchable memory, and a native Android shell.

### Built for real use

- **Voice in and out** — browser microphone, speech-to-text, and text-to-speech flows
- **Multiple AI providers** — switch providers and discover supported models from Settings
- **Personal memory** — searchable, user-controlled memory instead of an opaque profile
- **Android and Termux ready** — use the shared PWA on Android or run the stack locally in Termux
- **Low-data PWA** — offline app shell, recovery behavior, reduced-motion support, and a data-use counter
- **Privacy by design** — encrypted provider keys, isolated guest mode, masked feedback, and explicit runtime boundaries
- **Streaming conversations** — SSE responses, idempotent requests, and network recovery

## Quick start

### Try the launcher with `npx`

```bash
npx --yes xultron-ai
```

The launcher installs Xultron into `~/.xultron/app`, checks the local prerequisites, and starts the application. For an installed command, use:

```bash
npm install --global xultron-ai
xultron doctor
xultron start
```

### Run from source

Requirements: Python 3.11+, Node.js 20+, npm, Git, and `make`.

```bash
git clone https://github.com/trackview1827-ctrl/Xultron.git
cd Xultron
make setup
make serve
```

Then open **http://127.0.0.1:5000**.

On Termux, install the packaged cryptography dependency first:

```bash
pkg install git nodejs python python-cryptography
python -m venv --system-site-packages backend/.venv
```

## Product demo

The checked-in walkthrough above shows the Xultron product surface. The supported live demo uses the actual Flask backend and PWA:

```bash
make setup
make serve
```

For the complete demo flow, Android debug-build instructions, and validation boundaries, see [docs/DEMO.md](docs/DEMO.md). Published Android debug builds are available on the [Releases page](https://github.com/trackview1827-ctrl/Xultron/releases). They are test artifacts, not Play Store releases.

## What is inside?

| Area | Stack | Purpose |
| --- | --- | --- |
| Mobile PWA | React, TypeScript, Vite, Tailwind | Responsive UI, offline shell, voice client |
| API | Flask, SQLAlchemy, SQLite, Alembic | Auth, chat, memory, provider and session data |
| AI integrations | Provider abstractions | AI, STT, and TTS backends without locking the app to one vendor |
| Android | Native WebView shell | Mobile container and explicit native capability boundary |
| Launcher | `xultron-ai` on npm | Install, update, start, develop, and diagnose Xultron |

## CLI commands

```bash
xultron install   # clone and bootstrap a clean installation
xultron update    # update a clean installation
xultron start     # run the installed app
xultron dev       # run backend and frontend development servers
xultron doctor    # check prerequisites
xultron help      # show help
```

## Architecture

```text
frontend/   React + TypeScript PWA, service worker, UI, voice client
backend/    Flask REST/SSE API, SQLAlchemy data layer, migrations
android/    Native Android WebView container and secure mobile integration
cli/        Zero-dependency installer and launcher published as xultron-ai
docs/       Product, API, architecture, security, demo, and validation docs
scripts/    Setup, development, smoke-test, and cleanup helpers
```

The frontend streams chat through SSE. The backend provides shared abstractions for AI, STT, and TTS. Native Android capabilities are scoped behind explicit permission and origin checks.

## Development and validation

```bash
npm test                              # CLI tests
npm --prefix frontend run typecheck   # TypeScript checks
npm --prefix frontend test            # PWA tests
make test                             # backend + frontend tests
make build                            # production PWA build
make smoke                            # isolated production smoke flow
```

For an Android debug candidate, use a machine with the Android SDK configured:

```bash
cd android
./gradlew test lint assembleDebug --stacktrace
sha256sum app/build/outputs/apk/debug/app-debug.apk
```

## Documentation

- [Demo and Android builds](docs/DEMO.md)
- [Architecture](docs/ARCHITECTURE.md)
- [API contract](docs/API_CONTRACT.md)
- [UI system](docs/UI_SYSTEM.md)
- [Acceptance matrix](docs/ACCEPTANCE.md)
- [Validation report](docs/VALIDATION_REPORT.md)
- [Security policy](SECURITY.md)
- [Contributing and commit conventions](CONTRIBUTING.md)
- [Türkçe README](README.tr.md)

## Security and privacy

Do not commit `.env` files, API keys, generated `backend/instance` secrets, Android signing keys, or personal data. Review [SECURITY.md](SECURITY.md) before reporting a vulnerability or configuring a production deployment.

## License

Xultron is released under the [MIT License](LICENSE).
