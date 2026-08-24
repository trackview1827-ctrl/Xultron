# Xultron security model

Xultron handles account data, conversation history and third-party provider
credentials. Security-sensitive behavior is part of the product contract rather
than an optional deployment add-on.

## Trust boundaries

- The browser is untrusted and never receives a stored provider secret.
- The Flask API is the only component allowed to call configured providers.
- The SQLite database may contain personal data and encrypted credentials.
- `SECRET_KEY` and `ENCRYPTION_KEY` are server-only application secrets.
- Third-party provider responses are untrusted input and are normalized before
  they become API responses or UI content.

## Implemented controls expected by the architecture

- Passwords use Werkzeug's adaptive password hashing.
- Authentication is backed by revocable, expiring database sessions.
- Session cookies are HttpOnly and SameSite, with Secure enabled in production.
- Cookie-authenticated mutations require a session-bound CSRF token.
- User-owned records are queried by both resource ID and current user ID.
- Provider credentials use authenticated encryption at rest.
- API responses contain a stored masked hint, never decrypted credentials.
- Request bodies, messages and audio have explicit size limits.
- Authentication and expensive provider operations are rate limited.
- Errors use stable safe codes and omit stack traces, paths and headers.
- Logs pass through secret redaction and never record request bodies containing
  credentials or authorization headers.
- Analytics are disabled by default and audio persistence requires consent.

## Secret configuration

Development can use generated secrets in the ignored backend instance directory.
Production must provide strong independent values:

```dotenv
SECRET_KEY=<at least 32 random bytes>
ENCRYPTION_KEY=<Fernet-compatible key>
DATABASE_URL=sqlite:////absolute/path/xultron.sqlite3
```

Rotate an encryption key only through a migration that decrypts and re-encrypts
all provider credentials. Replacing it directly makes existing credentials
unreadable. Never commit `.env`, database files, logs or generated instance data.

## Production checklist

1. Run behind HTTPS with a trusted reverse proxy.
2. Set the production environment and explicit application secrets.
3. Restrict allowed origins and proxy host headers.
4. Keep the database and instance directory readable only by the service user.
5. Back up encrypted data and application keys through separate secure channels.
6. Review provider base URLs before enabling private-network access.
7. Run all automated tests and the direct API isolation matrix.
8. Search the production frontend and sampled responses for a sentinel API key.
9. Confirm analytics and audio persistence remain off unless explicitly enabled.
10. Monitor safe error codes and rate-limit events without logging user content.

## Reporting a vulnerability

Do not include real API keys, passwords, private conversations or database copies
in a report. Provide a minimal reproduction, affected endpoint, expected behavior
and observed safe-to-share output. Revoke any credential that may have been exposed.
