# Xultron API contract

All endpoints are under `/api/v1`. JSON uses camelCase. Mutating requests use the
`X-CSRF-Token` returned by `GET /auth/session`. Authentication uses an HttpOnly
same-origin session cookie. Secrets never appear in a response.

## Common responses

Success responses use a resource-specific object. Errors use:

```json
{
  "error": {
    "code": "provider_authentication_failed",
    "message": "Authentication was rejected by the provider.",
    "retryable": false,
    "requestId": "req_..."
  }
}
```

Expected status codes include `400`, `401`, `403`, `404`, `409`, `413`, `422`,
`429`, `502` and `504`. Internal stack traces and filesystem paths are omitted.

## System

- `GET /system/health`
  - `{ "status": "online", "version": "...", "time": "..." }`

## Authentication

- `GET /auth/session`
  - Initializes the anonymous CSRF session when needed.
  - `{ "user": null | User, "csrfToken": "...", "expiresAt": null | "..." }`
- `POST /auth/guest`
  - Starts or returns an isolated short-lived guest session.
- `POST /auth/register`
  - Body: `{ "username": "...", "email": "...", "password": "..." }`
  - Upgrades the current guest when applicable.
- `POST /auth/login`
  - Body: `{ "identifier": "...", "password": "..." }`
- `POST /auth/logout`
- `GET /auth/sessions`
- `DELETE /auth/sessions/{sessionId}`

`User` contains `id`, `username`, `email`, `isGuest`, `createdAt` and no password
or credential material.

## Conversations and chat

- `GET /chat/conversations?limit=20`
- `POST /chat/conversations`
  - Body: `{ "title": "optional" }`
- `GET /chat/conversations/{id}`
- `DELETE /chat/conversations/{id}`
- `GET /chat/conversations/{id}/messages?limit=50`
- `POST /chat/messages`
  - Body: `{ "conversationId": "optional", "message": "...", "requestId": "uuid" }`
  - Idempotent per user and request ID.
- `POST /chat/stream`
  - Same body as `/chat/messages`.
  - Returns `text/event-stream` events: `state`, `conversation`, `delta`, `done`,
    and `error`. The terminal event is always emitted when a stream started.

## Providers

- `GET /providers?kind=ai|stt|tts`
- `POST /providers`
- `GET /providers/{id}`
- `PATCH /providers/{id}`
- `DELETE /providers/{id}`
- `POST /providers/{id}/test`
- `POST /providers/{id}/models`
- `POST /providers/{id}/oauth/openai/start`
  - Returns `{ "authorizationUrl": "https://auth.openai.com/...", "redirectUri": "..." }`.
  - Uses the official Codex OAuth authorization-code + PKCE flow.
- `GET /providers/oauth/openai/callback`
  - Validates the one-time state, exchanges the code, encrypts access/refresh/id tokens,
    and redirects the browser back to Xultron.

Provider write shape:

```json
{
  "name": "OpenAI",
  "kind": "ai",
  "adapter": "openai_compatible",
  "baseUrl": "https://api.openai.com/v1",
  "apiKey": "submitted but never returned",
  "model": "model-id",
  "temperature": 0.3,
  "maxTokens": 800,
  "streaming": true,
  "enabled": true,
  "isDefault": true,
  "config": {}
}
```

Provider read shape replaces `apiKey` with:

```json
"credential": { "configured": true, "masked": "sk-••••••91a2" }
```

Model discovery returns `{ "models": [{ "id": "...", "label": "..." }] }`.
Connection testing returns `{ "ok": true, "latencyMs": 143, "message": "..." }`
or the common safe error envelope.

The Codex OAuth provider uses `https://chatgpt.com/backend-api/codex` only after a
successful user-authorized flow. Passwords, verification codes and raw OAuth
tokens are never accepted from the browser or returned by the API.

## Agent tools

- `GET /tools`

Returns metadata for capabilities available to the authenticated agent. Each
tool includes `name`, descriptions, input/output schemas, required permissions,
availability, side-effect and risk information, reversibility, timeout,
idempotency and verification strategy. Implementation handlers and provider
credentials are never included.

## Voice

- `POST /voice/transcribe`
  - `multipart/form-data` with `audio`, optional `language` and `providerId`.
  - `{ "text": "...", "language": "..." }`
- `POST /voice/synthesize`
  - Body: `{ "text": "...", "providerId": "optional", "voice": "optional" }`
  - Returns bounded audio bytes with a provider media type.

This release never persists raw audio. `saveAudio` is an explicit consent
preference reserved for a future persistence implementation and defaults off.

## Memory

- `GET /memory?query=...&category=personal|preferences|important|temporary`
- `POST /memory`
- `GET /memory/{id}`
- `PATCH /memory/{id}`
- `DELETE /memory/{id}`
- `DELETE /memory` with body `{ "confirm": "CLEAR" }`

Memory write fields are `title`, `content` and `category`.

## Settings

- `GET /settings`
- `PATCH /settings`

Supported settings include `locale`, `lowDataMode`, `memoryEnabled`,
`conversationHistory`, `voiceHistory`, `saveAudio`, `analytics`, `reducedMotion`,
`preferredVoice`, `sttLanguage` and appearance preferences. Analytics defaults off.

## Devices

- `GET /devices`

The first release returns registered device metadata or an empty list. Command and
event service boundaries exist for future Raspberry Pi, ESP32 and Bluetooth work.
