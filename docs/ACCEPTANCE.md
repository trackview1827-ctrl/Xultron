# Acceptance and validation matrix

This matrix turns the product specification into observable checks. A feature is
not complete until its applicable checks have been executed and recorded.

## Priority 0: release blockers

| Area | Acceptance behavior | Primary check |
| --- | --- | --- |
| Startup | Backend and frontend start from documented clean setup | install, migration, build and smoke commands |
| CLI install | GitHub-hosted npm package exposes `xultron`, clones only the expected repository and fails closed on dirty, unrelated or non-main updates | Node tests, packed-package consumer install and public `npx` check |
| Authentication | Register, login, logout and guest mode work | backend API tests plus frontend flow test |
| Session invalidation | A logged-out or expired session cannot be reused | backend integration test |
| Isolation | User B and Guest cannot read or mutate User A resources | direct API IDOR matrix |
| Secrets | Submitted provider keys never appear in JSON, HTML, storage, JS or logs | sentinel secret scan and API tests |
| Encryption | Database does not contain the submitted provider key in plaintext | database inspection test |
| Providers | AI, STT and TTS configurations support CRUD, default, enable, test and safe failure | mocked provider integration tests |
| Chat | Unicode text, emoji and idempotent request IDs work | API and UI tests |
| Recovery | Failed or interrupted chat returns Core to a stable state | state-machine and UI recovery tests |
| Memory | View, search, create, edit, delete and clear are user-scoped | API and component tests |
| Voice | Permission, empty/large audio, STT and TTS success/failure have recoverable UX | API tests plus browser/manual checks |
| PWA | Manifest, service worker, offline shell and standalone metadata are valid | build artifact checks plus browser/manual checks |
| Mobile | Small phone layout, safe areas, keyboard and touch targets work | responsive browser/manual checks |

## CLI installation and updates

- `xultron doctor` requires supported Git, Node.js, npm and Python versions.
- The default install location is `~/.xultron/app`; `--dir` selects an explicit path.
- Install never overwrites a non-empty directory that is not the expected Xultron checkout.
- The repository remote must match the canonical Xultron GitHub repository.
- Update requires the `main` branch, a clean worktree and a fast-forward-only merge.
- The npm package contains only the CLI, package metadata and public README.
- The installed binary runs on Termux and standard Node.js environments.
- A packed-package consumer test and the public GitHub `npx` command must both pass.

## Authentication edge cases

- Empty registration and login fields return validation errors.
- Wrong password returns a generic authentication error.
- Duplicate username or email returns conflict without exposing an account secret.
- Logout revokes the server-side session immediately.
- An expired or manually revoked session returns `401`.
- Concurrent logout is idempotent.
- Guest registration upgrades only the current guest and preserves only its data.
- Session management can revoke another session owned by the same user.
- Session IDs belonging to another user are not addressable.

## Chat and provider edge cases

- Empty and whitespace-only messages are rejected.
- Messages over the configured character limit return `413` or `422`.
- Unicode, right-to-left text and emoji round-trip safely.
- Reusing a request ID returns the original result and creates no duplicate records.
- Provider `401`, `429`, `500`, timeout, malformed JSON and empty output map to safe errors.
- Invalid base URLs stop loading and do not break other application surfaces.
- Network failure always exits `THINKING`.
- Model discovery supports empty lists and manual model IDs.
- Removing or disabling a default provider leaves a valid no-provider state.
- Provider errors never include authorization headers, keys or stack traces.

## Voice edge cases

- Microphone denial returns the Core to `ONLINE` with actionable copy.
- Empty, unsupported, corrupted and oversized audio are rejected safely.
- STT timeout and provider failures are recoverable.
- TTS failures do not discard the assistant text response.
- Playback completion and interruption return the Core to `ONLINE`.
- Audio is not stored when `saveAudio` is false.
- The browser never receives the configured STT or TTS credential.

## Database and authorization

Create User A resources for conversations, messages, memory, providers, settings
and device metadata. Authenticate as User B and then Guest. For every resource,
attempt read, update, delete and nested access with User A identifiers. Every
operation must return `404` or `403`, and no User A field may appear in the body.

Also validate:

- Foreign keys are enabled in SQLite.
- Duplicate records covered by unique constraints fail cleanly.
- Service transactions roll back on provider or validation failures.
- An empty database can be initialized through migrations.
- A locked or unavailable database produces a safe service error.

## Frontend and Core

- Every allowed Core transition is tested.
- Impossible transitions such as `OFFLINE -> SPEAKING` are rejected.
- Browser offline events override transient states.
- Reduced Motion and Low Data Mode suppress continuous decorative animation.
- The main hierarchy remains Core, conversation, voice and system state.
- Chat messages render as semantic timeline output rather than generic bubbles.
- Settings remain usable at 320 CSS pixels and on tablet/desktop widths.
- Focus is visible, dialogs are labelled and touch targets are at least 44 pixels.
- Error copy is useful and does not render raw backend content as HTML.

## PWA and network

- The production build includes a valid manifest and service worker.
- Static shell requests can be served from cache after first load.
- API requests are not falsely satisfied as working AI while offline.
- Offline mode is explicit and the reconnect path returns to `ONLINE`.
- No polling runs continuously in Low Data Mode.
- Network byte estimates are local and analytics remain off by default.

## Evidence record

Final delivery must list:

1. Commands executed.
2. Passed test counts.
3. Failed checks and the fixes applied.
4. Browser or device checks completed.
5. Checks blocked by the execution environment.
6. Known product limitations that remain after validation.
