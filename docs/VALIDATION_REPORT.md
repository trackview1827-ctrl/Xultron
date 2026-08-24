# Xultron validation report

Date: 2026-08-24

## Release result

The current repository passes the complete automated release gate. The gate builds
and serves the production application from an isolated migrated SQLite database,
then exercises the public HTTP interface with sentinel credentials.

## Commands executed

```bash
make check
```

This command completed all seven stages:

1. Backend pytest suite.
2. Backend bytecode compilation.
3. Strict frontend TypeScript checking.
4. Frontend Vitest suite.
5. Vite production build.
6. Manifest, service worker and icon artifact checks.
7. Isolated production HTTP smoke test.

Additional targeted checks included `git diff --check`, tracked-secret scans,
frontend storage/raw-HTML scans, production sourcemap inspection and fresh/upgrade
Alembic migration tests.

## Passed evidence

- Backend: **34 tests passed**.
- Frontend: **53 tests passed across 14 files**.
- Strict TypeScript: passed.
- Python compile check: passed.
- Vite build: passed with **455 transformed modules**.
- Production bundles:
  - CSS: 38.65 kB, 9.42 kB gzip.
  - JavaScript: 394.65 kB, 126.71 kB gzip.
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

## Environment-limited checks

Automated desktop browser screenshots and device emulation could not run because the
available browser bridge has no Linux ARM64 browser asset. Real-device microphone
permission, Bluetooth route changes, audio playback and Android PWA installation
therefore remain manual checks. The automated voice lifecycle, offline recovery,
responsive CSS, manifest and service worker behaviors passed, but this report does
not claim physical-device validation.

Real external AI, STT and TTS accounts were intentionally not called. Provider
success, malformed response, redirect, timeout/failure, response-size and secret
handling paths use deterministic mock adapters and live local HTTP boundaries.
