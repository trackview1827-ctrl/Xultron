# Xultron architecture

Xultron is a mobile-first personal AI system built as a clean monorepo. The old
prototype is not part of the runtime architecture.

## Repository layout

```text
frontend/                 React, TypeScript, Vite, Tailwind, Framer Motion
  src/components/         Reusable visual and accessibility primitives
  src/features/           Auth, chat, core, memory, providers, settings, voice
  src/layouts/            Application shell and route layouts
  src/services/           Typed API and browser service boundaries
  src/stores/             Context and reducer based application state
  src/theme/              Tokens and global visual language
backend/                  Flask application and REST/SSE API
  app/api/                Versioned blueprints and response helpers
  app/auth/               Authentication and server-side session services
  app/chat/               Conversation orchestration
  app/memory/             User-controlled memory
  app/models/             SQLAlchemy models
  app/providers/          AI, STT and TTS abstractions and adapters
  app/agent/              Metadata-driven tool registry and execution boundary
  app/security/           CSRF, encryption, redaction and request guards
  app/services/           Business logic without route coupling
  app/voice/              Transcription and synthesis orchestration
  migrations/             Alembic-compatible schema history
```

## Runtime boundaries

1. The browser only talks to `/api/v1` on the Xultron backend.
2. Provider credentials are submitted once and encrypted by the backend.
3. Stored credentials are never serialized back to the browser.
4. Every user-owned query is scoped by the authenticated session user.
5. Flask route handlers validate transport input and delegate to services.
6. Provider adapters implement stable AI, STT and TTS protocols.
7. The frontend state machine is the single source of truth for Core visuals.

## Authentication model

Xultron uses a signed, HttpOnly, SameSite session cookie plus a database-backed
session record. The cookie stores only the opaque session ID and CSRF token.
Logout and expiry revoke the database session immediately. Guest mode creates a
short-lived isolated guest user. Registering while in guest mode upgrades that
same user so its own conversation can continue without crossing user boundaries.

## Secret handling

Provider secrets are encrypted at rest with a server-side encryption key. API
responses expose only `configured` and a precomputed masked hint. Secrets are
redacted from logs, exceptions and provider error messages. Development secrets
may be generated into the ignored backend instance directory. Production refuses
to start without explicitly supplied application secrets.

## Provider architecture

The registry resolves a stored provider by `kind` and `adapter`:

- `AIProvider`: model discovery, connection test, completion and streaming.
- `STTProvider`: connection test and audio transcription.
- `TTSProvider`: connection test and speech synthesis.

Initial adapters support OpenAI-compatible HTTP APIs and local/custom endpoints.
Adding a provider is a registry change, not a route or UI rewrite.

The OpenAI Codex OAuth adapter is a separate transport from the OpenAI-compatible
API-key adapter. It opens `auth.openai.com` with PKCE, receives the callback on
the local Xultron origin, stores encrypted OAuth credentials, refreshes expired
access tokens, and sends only the Codex-required authorization headers to the
ChatGPT Responses backend. The browser handles the account login and consent;
Xultron never receives a password or verification code.

## Agent tool registry

Agent capabilities are declared as `ToolSpec` records in the shared
`app.agent.registry.ToolRegistry`. Each declaration contains an input/output
schema, permissions, availability check, side-effect flag, risk level,
reversibility, timeout, idempotency and verification strategy. The registry
rejects unknown tools and blocks side-effecting tools unless the caller passes
explicit permission. The current verification capabilities (`runtime`,
`termux`, `project`, `web`, `calculate` and `reasoning`) are dispatched through
this boundary rather than a command-specific execution tree.

Authenticated clients can inspect public metadata at `GET /api/v1/tools`.
Handlers and credentials are never serialized. A new capability can therefore
be added by registering metadata and a handler without changing the route or
model-selection contract.

## Core state machine

Valid states are `BOOTING`, `OFFLINE`, `CONNECTING`, `ONLINE`, `LISTENING`,
`THINKING`, `SPEAKING` and `ERROR`. Illegal transitions are ignored and surfaced
in development diagnostics. Network loss always wins over active transient states.
Every asynchronous operation has a `finally` recovery path so the Core cannot
remain permanently stuck in `THINKING`, `LISTENING` or `SPEAKING`.

## Low-data and PWA strategy

The app shell and static assets are cached by a service worker. API calls are
network-only and never imply offline AI. Low-data mode reduces motion, limits chat
context and history fetch sizes, avoids polling, and records approximate transfer
statistics locally without analytics. The shell opens offline and clearly reports
that provider-backed actions need a connection.
