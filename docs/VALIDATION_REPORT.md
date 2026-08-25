# Xultron validation report

Date: 2026-08-25

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

- Backend: **54 tests passed**.
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
- Every provider-backed answer now runs through a deterministic backend verification
  plan. The backend exposes only bounded read-only Termux, project, calculation and fixed-host
  web evidence tools; injects live terminal/Termux:API capability evidence into every
  final model call; blocks private search queries; and returns no factual answer when
  relevant verification fails.
- AI configuration now includes more than 30 presets covering native Gemini and
  Anthropic adapters, major OpenAI-compatible hosted services, and loopback local
  runtimes. Claude credentials use native `x-api-key` headers and bounded responses.
- Device date/time questions now use live runtime clock evidence. Public web evidence
  includes named source domains and URLs so first-party and official documentation can
  be preferred. Verification labels remain internal and are removed from visible chat
  responses. Provider output and timeout defaults were raised to prevent abrupt answers.
- The bounded intent router now tolerates missing Turkish diacritics, common suffixes,
  and small spelling mistakes for clock, battery, storage, network, Termux and project
  questions. Location remains fail-closed and cannot be enabled by fuzzy matching. The
  matching design is attributed to the MIT-licensed OpenClaw patterns it adapts.

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
