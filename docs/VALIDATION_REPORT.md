# Xultron validation report

Date: 2026-08-26

## Release result

The current repository passes the complete automated release gate. The gate builds
and serves the production application from an isolated migrated SQLite database,
then exercises the public HTTP interface with sentinel credentials.

## Commands executed

```bash
make check
```

This command completed all nine stages:

1. Clean tracked-source profile check.
2. Xultron CLI unit tests and npm package dry run.
3. Backend pytest suite.
4. Backend bytecode compilation.
5. Strict frontend TypeScript checking.
6. Frontend Vitest suite.
7. Vite production build.
8. Manifest, service worker and icon artifact checks.
9. Isolated production HTTP smoke test.

Additional targeted checks included `git diff --check`, tracked-secret scans,
frontend storage/raw-HTML scans, production sourcemap inspection and fresh/upgrade
Alembic migration tests.

## Passed evidence

- Xultron CLI: **3 Node tests passed** covering argument parsing, runtime doctor,
  isolated install/update, dirty worktrees, unrelated directories and non-main branches.
- npm package: dry-run contains only the intended CLI, README and package metadata. A
  packed tarball installed into a fresh consumer project exposes `xultron 1.0.0`.
- Backend: **56 tests passed**.
- Frontend: **61 tests passed across 16 files**.
- Strict TypeScript: passed.
- Python compile check: passed.
- Vite build: passed with **457 transformed modules**.
- Production bundles:
  - CSS: 57.14 kB, 13.38 kB gzip.
  - JavaScript: 402.97 kB, 128.62 kB gzip.
  - No production sourcemaps were emitted.
- PWA build: valid manifest, service worker and 192/512 icons.
- Service worker: build-time hashed CSS and JavaScript assets are precached under a
  content-derived cache version. API traffic remains network-only.
- Live production HTTP smoke: passed static shell, SPA fallback, security headers,
  registration, guest mode, settings, encrypted provider credentials, provider
  test/model discovery, chat, SSE, STT, TTS, memory, user and guest isolation,
  safe provider failure, logout recovery and secret scans.
- Database: clean migrations and baseline-to-head upgrade passed. SQLite foreign
  keys, integrity and foreign-key checks passed.
- Secret handling: sentinel provider keys were absent from HTTP output, static
  assets, server logs and plaintext database bytes.
- Data profiles: chat, memory, sessions, local identity values, databases and
  provider credentials remain outside Git. The release gate rejects tracked runtime
  paths and non-placeholder local identity configuration.

## Failures found and fixed during validation

- A real HTTP SSE test exposed a detached SQLAlchemy user during streaming. The
  stream now reloads the identity inside its context, always emits a terminal event
  and converts unexpected errors to a safe envelope.
- Provider responses were checked only after buffering. External HTTP responses are
  now read incrementally with hard byte limits, redirects disabled and connections
  closed safely.
- Conversation ordering timestamps were stale after new messages. Message handling
  now refreshes the conversation timestamp.
- Private-history idempotency state was unbounded. It is now thread-safe, expiring
  and capped.
- Frontend asynchronous chat, voice, provider, settings and identity transitions
  had stale-response and cancellation risks. Generation guards and abort paths now
  prevent prior operations from overwriting current state.
- The PWA initially cached only stable shell paths. The Vite build now injects exact
  hashed bundles into the install-time service worker manifest.
- A standard `#!/usr/bin/env node` package launcher failed on Termux because Android
  does not provide `/usr/bin/env`. The package now uses a zero-network postinstall step
  that rewrites only the installed launcher to the active `process.execPath`; a fresh
  npm consumer install and direct binary execution pass on Termux.
- Direct shell-script execution failed under Termux because Android lacks the
  conventional `/usr/bin/env` path. Make targets now invoke the scripts through
  `bash` and the complete gate passes on Termux.
- Uploaded STT filenames are sanitized before being sent to a provider.
- The local development identity now uses an animated four-cell numeric PIN screen.
  Its requested PIN is represented by a one-way scrypt hash, login has a dedicated
  brute-force limit, and production keeps local PIN access disabled by default.
- Google Gemini now has a native adapter with header-based API-key authentication,
  bounded responses, model discovery, safe message conversion and AI-only validation.
- English and Turkish locale changes now update the document language and visible
  navigation, chat, memory, provider and settings surfaces immediately.
- Every provider-backed answer now runs through a deterministic backend verification
  plan. The backend exposes bounded runtime, project, calculation and fixed-host
  web evidence tools; device APIs such as Termux:API are not registered, so missing
  Android integrations cannot interrupt the verification or automation flow.
  Private search queries are blocked and no factual answer is returned when relevant
  verification fails.
- AI configuration now includes more than 30 presets covering native Gemini and
  Anthropic adapters, major OpenAI-compatible hosted services, and loopback local
  runtimes. Claude credentials use native `x-api-key` headers and bounded responses.
- Device date/time questions now use live GMT/UTC runtime evidence converted through
  the user's selected country time zone. Public web evidence includes named source
  domains and URLs so first-party and official documentation can be preferred.
  Verification labels remain internal and are removed from visible chat responses.
  Device battery, storage, network, location and Termux:API automations are disabled
  and fail closed without invoking Android commands.
- Short typo-bearing greetings are answered locally with standard spelling, avoiding
  an unnecessary provider request and rate-limit exposure.

## Environment-limited checks

Automated desktop browser screenshots and device emulation could not run because the
available browser bridge has no Linux ARM64 browser asset. Real-device microphone
permission, Bluetooth route changes, audio playback and Android PWA installation
therefore remain manual checks. The automated voice lifecycle, offline recovery,
responsive CSS, manifest and service worker behaviors passed, but this report does
not claim physical-device validation.

A configured real Gemini account was checked through model discovery and a minimal
completion; the selected model returned `OK` after an earlier transient HTTP 429.
External STT and TTS accounts were intentionally not called. Their success, malformed
response, redirect, timeout/failure, response-size and secret handling paths use
deterministic mock adapters and live local HTTP boundaries.
