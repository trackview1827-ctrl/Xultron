XULTRON — FROM-SCRATCH PERSONAL AI ASSISTANT

Full-Stack Architecture + Premium Futuristic Mobile UI Specification

Build a completely new application called Xultron from scratch.

Do NOT try to preserve or retrofit the previous Xultron UI.

The previous UI is considered a failed prototype.

Start with a clean architecture and build Xultron as a real personal AI assistant platform with a premium futuristic interface.

The final product must NOT look like:

- a generic SaaS dashboard
- an admin panel
- a ChatGPT clone
- a Discord clone
- a Bootstrap website
- a collection of cards
- a generic glassmorphism template

Xultron should feel like a personal AI operating system / intelligent assistant console.

The visual inspiration may come from futuristic AI interfaces, JARVIS-style assistants and cybernetic systems, but the visual identity must be original and must not copy copyrighted Marvel assets, logos or exact interfaces.

---

1. CORE CONCEPT

Application name:

XULTRON

Xultron is a personal AI assistant that supports:

- Text conversations
- Voice conversations
- AI provider switching
- STT provider switching
- TTS provider switching
- Personal memory
- User accounts
- Guest mode
- Configurable API providers
- Low-data operation
- PWA/mobile usage
- Future Raspberry Pi integration
- Future ESP32 integration
- Future Bluetooth/device integration

The application must be designed so that providers and credentials can be configured from the Xultron Settings interface.

The user should not need to edit source code to change AI/STT/TTS providers.

---

2. TECHNOLOGY STACK

Use a clean modern architecture.

Frontend

Use:

- React
- TypeScript
- Vite
- Tailwind CSS
- Framer Motion

Use a component architecture.

Do not create a giant monolithic React component.

Suggested structure:

frontend/
  src/
    components/
    layouts/
    pages/
    features/
      chat/
      voice/
      core/
      settings/
      memory/
      auth/
    hooks/
    services/
    stores/
    types/
    animations/
    theme/

Use TypeScript strictly.

Avoid unnecessary dependencies.

---

3. BACKEND

Use:

- Python
- Flask
- SQLAlchemy
- SQLite initially
- Flask-Migrate/Alembic-compatible migrations
- REST API
- WebSocket or SSE where appropriate

Suggested structure:

backend/
  app/
    api/
    auth/
    chat/
    memory/
    voice/
    providers/
    models/
    services/
    config/
    security/
    devices/

Keep business logic out of Flask route handlers.

Use service classes/modules.

---

4. PROVIDER SYSTEM

This is one of the most important requirements.

Xultron must NOT hard-code a single AI provider.

Create a provider abstraction.

For example:

AIProvider
STTProvider
TTSProvider

Each provider implements a common interface.

Potential providers may include:

- OpenAI-compatible APIs
- Other OpenAI-compatible providers
- Custom HTTP APIs
- Local AI providers
- Future providers

Do not assume that only one provider will ever exist.

The user should be able to add/configure providers from:

Settings → AI Providers

---

5. API CONFIGURATION FROM SETTINGS

API configuration must be user-configurable.

The Settings UI should allow the user to create a provider.

Example:

Provider Name:
OpenAI

Provider Type:
OpenAI Compatible

Base URL:
https://...

API Key:
••••••••••••

Model:
...

Temperature:
...

Max Tokens:
...

Streaming:
ON

Enabled:
ON

The user can:

- Add provider
- Edit provider
- Delete provider
- Enable/disable provider
- Set default provider
- Test provider connection

The same concept should exist for:

AI

STT

TTS

Future integrations

---

6. SECURITY OF API KEYS

IMPORTANT:

API keys must NEVER be exposed to:

- frontend JavaScript
- HTML
- browser localStorage
- URL parameters
- chat responses
- normal API responses
- logs

The Settings frontend sends credentials securely to the backend.

Backend stores secrets securely.

If practical, encrypt stored credentials at rest using a server-side encryption key.

At minimum:

- Never return the full API key.
- Display only masked values.
- Never log secrets.
- Never include secrets in exceptions.

Example:

sk-••••••••••••••91a2

The browser should never receive the actual stored secret after initial submission.

---

7. ENVIRONMENT VARIABLES

".env" should contain only application-level secrets/configuration such as:

SECRET_KEY=
DATABASE_URL=
ENCRYPTION_KEY=

Provider API keys should primarily be configurable from the Settings UI.

Do not require the user to modify source code whenever an API provider changes.

The system may optionally support environment-defined bootstrap providers, but database/configured providers must be supported.

---

8. PROVIDER TESTING

Every provider configuration should have:

Test Connection

button.

When pressed:

TESTING CONNECTION...
        ↓
SUCCESS / FAILED

Show useful but safe error information.

For example:

Connection failed
HTTP 401
Authentication rejected by provider

Do NOT expose API keys or internal stack traces.

---

9. MODEL SELECTION

If a provider supports model discovery, allow:

Refresh Models

The user should be able to select:

Provider
↓
Model

Do not assume model names.

Allow manually entering a model ID when discovery is unavailable.

---

10. XULTRON UI — ABSOLUTE PRIORITY

The UI is extremely important.

Spend significant effort on visual quality.

The UI should feel like:

an AI system

not:

a website containing an AI chatbot.

Do not default to:

- sidebar-heavy layouts
- giant cards
- excessive rounded rectangles
- generic dashboard charts
- excessive gradients
- excessive glassmorphism
- stock illustrations
- unnecessary buttons

Use whitespace, hierarchy, subtle lines and controlled glow.

---

11. VISUAL IDENTITY

Create an original Xultron visual language.

Recommended visual direction:

- Near-black background
- Very dark blue/graphite surfaces
- Cyan/blue primary accent
- Small amounts of white
- Optional secondary electric violet
- Thin technical lines
- Subtle glow
- Precise typography
- Minimal icons
- High contrast

Do not overuse neon.

The interface should feel sophisticated rather than like a gaming RGB UI.

---

12. XULTRON CORE

The central UI element is:

XULTRON CORE

It is not just an image.

Create it as an interactive visual component.

Prefer:

- SVG
- CSS
- Canvas
- lightweight WebGL only if genuinely useful

Avoid huge video assets.

The Core represents Xultron's internal state.

States:

BOOTING
OFFLINE
CONNECTING
ONLINE
LISTENING
THINKING
SPEAKING
ERROR

Each state has a different animation.

---

13. CORE BEHAVIOR

BOOTING

Core gradually activates.

Subtle rings appear.

Text:

INITIALIZING XULTRON

Then:

SYSTEM ONLINE

ONLINE

Very subtle pulse.

No distracting animation.

LISTENING

Core reacts to microphone input.

Show audio-reactive rings/waves.

THINKING

Core becomes more active.

Use rotating/flowing energy structures.

SPEAKING

Core reacts to TTS playback.

ERROR

Controlled warning state.

OFFLINE

Core becomes dim and inactive.

---

14. MAIN SCREEN

The main screen should be extremely clean.

Concept:

                 XULTRON

                    ◉
              XULTRON CORE

                  ONLINE


       "How can I assist you?"


        ───────────────────
        Ask Xultron...
        ───────────────────

             🎙        ↑

Do not literally copy this ASCII layout.

Use it as a conceptual hierarchy.

The Core should dominate the screen.

Chat history should appear elegantly without turning the interface into a conventional chat app.

---

15. CHAT MODE

When the user starts chatting, the UI should intelligently transition.

The Core remains visually present.

Messages can appear as a timeline around/below the Core.

Do not use giant rounded message bubbles everywhere.

Xultron responses should feel like system output.

Example:

XULTRON
────────────────────
I found the information you requested.

[response]

User messages can remain visually distinct but minimal.

---

16. VOICE MODE

Voice interaction should feel like activating an AI system.

User presses microphone.

UI:

LISTENING

Core activates.

Audio visualization appears.

Speech is converted to text.

Then:

THINKING

Then:

SPEAKING

Finally:

ONLINE

The transition between states must be smooth.

---

17. SETTINGS UI

Settings should be a first-class part of the application.

Categories:

GENERAL

AI PROVIDERS

STT PROVIDERS

TTS PROVIDERS

VOICE

MEMORY

APPEARANCE

NETWORK

PRIVACY

ACCOUNT

DEVICES

---

18. AI PROVIDER SETTINGS

Example UI:

AI PROVIDERS

OpenAI
● Enabled
Model: ...

Anthropic
○ Disabled
Model: ...

Local AI
○ Disabled

+ Add Provider

Clicking provider:

Provider Name
Provider Type
Base URL
API Key
Model
Temperature
Max Output
Streaming
Enabled

Buttons:

TEST CONNECTION
SAVE
DELETE

---

19. STT PROVIDER SETTINGS

Same architecture.

Example:

STT PROVIDERS

Provider:
...

API endpoint:
...

API key:
••••••••

Language:
Auto Detect

Model:
...

Test Connection

---

20. TTS PROVIDER SETTINGS

Example:

TTS PROVIDERS

Provider:
...

Voice:
...

Language:
...

Speed:
...

Pitch:
...

Test Voice

Allow the user to change TTS provider without changing application code.

---

21. MEMORY UI

Xultron should have a Memory section.

Display:

XULTRON MEMORY

Personal
Preferences
Important
Temporary

Allow:

- View memory
- Search
- Edit
- Delete
- Clear all

The user must have complete control over stored memory.

---

22. PRIVACY

Privacy settings:

Memory:
ON/OFF

Conversation history:
ON/OFF

Voice history:
ON/OFF

Save audio:
ON/OFF

Analytics:
OFF by default

Never silently store audio.

If audio persistence is implemented, make it explicitly configurable.

---

23. LOW DATA MODE

Settings:

LOW DATA MODE
ON

When enabled:

- Reduce network requests
- Reduce animation complexity
- Compress audio appropriately
- Avoid unnecessary polling
- Cache static assets
- Avoid repeatedly downloading conversation history
- Prefer streaming where it reduces perceived latency
- Send only required context

Display optional network statistics:

SESSION DATA
↓ 1.8 MB
↑ 0.7 MB

---

24. RESPONSIVE DESIGN

Mobile is the primary platform.

Must work correctly on:

- Small Android phones
- Large Android phones
- Tablets
- Desktop

Do not simply shrink the desktop UI.

Design mobile-first.

Touch targets must be comfortable.

Keyboard must not cover chat input.

Safe-area support should be implemented for modern phones.

---

25. PWA

Make Xultron installable as a PWA.

Support:

- manifest
- icons
- service worker
- caching
- offline shell
- app-like standalone mode

Do not pretend AI works offline if it does not.

Offline should mean the UI still opens and clearly displays connection state.

---

26. BACKEND API

Use:

/api/v1/auth
/api/v1/chat
/api/v1/voice
/api/v1/memory
/api/v1/providers
/api/v1/settings
/api/v1/devices

Provider management API should support:

GET providers
POST providers
PATCH providers/{id}
DELETE providers/{id}
POST providers/{id}/test
POST providers/{id}/models

Never return secrets.

---

27. AUTHENTICATION

Support:

- User registration
- Login
- Logout
- Session management
- Guest mode
- Password hashing
- Rate limiting
- Session expiration

Every user's data must be isolated.

---

28. GUEST MODE

Guest users can:

- Open Xultron
- Chat
- Test voice if configured
- Experience the UI

Guest users cannot access another user's:

- conversations
- memory
- settings
- providers
- API keys
- contacts

Guest data should have controlled lifetime.

---

29. DATABASE

Use SQLite initially.

Models:

User
Session
Conversation
Message
Memory
Provider
ProviderCredential
UserSettings
Device

Use migrations.

Do not store API secrets in plaintext if secure encryption-at-rest can be implemented.

---

30. FUTURE DEVICES

Do not implement Raspberry Pi/ESP32/Bluetooth now.

But reserve architecture:

Device
DeviceType
DeviceStatus
DeviceCommand
DeviceEvent

Future:

Phone
  ↓
Xultron Backend
  ↓
Raspberry Pi
  ↓
ESP32
  ↓
Bluetooth / Sensors / Actuators

The current architecture must not prevent this.

---

31. SECURITY

Implement:

- password hashing
- secure sessions
- CSRF protection where applicable
- input validation
- rate limiting
- request size limits
- audio size limits
- authentication checks
- authorization checks
- user data isolation
- secure cookies
- CORS restrictions
- secret encryption
- safe logging

Never expose:

- API keys
- passwords
- encryption keys
- stack traces
- internal filesystem paths

to the frontend/user.

---

32. ERROR UX

Errors should be designed as part of the UI.

Never dump:

500 Internal Server Error
Traceback...

into the UI.

Instead:

XULTRON

Connection unavailable.

Please check your network or provider configuration.

[Retry]

Different errors should have appropriate messages.

---

33. EDGE CASE TESTING

Before declaring the project complete, deliberately test:

Authentication

- Wrong password
- Empty credentials
- Invalid session
- Expired session
- Logout then reuse session
- Concurrent login/logout
- Guest → user transition

Chat

- Empty message
- Huge message
- Unicode
- Emoji
- Rapid messages
- Duplicate request
- Network loss during request
- AI timeout
- AI 401
- AI 429
- AI 500
- Malformed provider response
- Empty provider response

Voice

- Microphone denied
- Empty audio
- Corrupted audio
- Huge audio
- Network interruption
- STT timeout
- STT failure
- TTS failure
- Bluetooth audio disconnect

Database

- Empty database
- Database locked
- Database unavailable
- Duplicate records
- Failed transaction
- Restart during write

Security

- SQL injection
- XSS
- CSRF
- IDOR
- User ID manipulation
- Conversation ID manipulation
- Memory ID manipulation
- Provider ID manipulation
- API key exposure
- Rate limit bypass

UI

- Small screen
- Large screen
- Keyboard open
- Keyboard closed
- Orientation change
- App background
- App resume
- Refresh
- Offline
- Slow network

---

34. USER DATA ISOLATION TEST

This test is mandatory.

Create:

USER A

with:

- conversation
- message
- memory
- provider
- settings

Then login as:

USER B

Attempt to access every User A resource using direct API requests.

Expected:

403 Forbidden

or:

404 Not Found

Never return User A data.

Repeat with Guest mode.

---

35. PROVIDER FAILURE TEST

Configure an intentionally invalid provider.

Example:

Base URL: invalid
API Key: invalid

Click:

TEST CONNECTION

Xultron must:

1. Detect failure.
2. Stop loading.
3. Display a useful error.
4. Never expose the secret.
5. Keep the rest of the application functional.

---

36. API KEY SECURITY TEST

After adding an API key:

Search frontend/network responses/source for the actual key.

The actual secret must not appear.

Check:

- HTML
- JavaScript
- localStorage
- sessionStorage
- URL
- API response
- console logs
- server logs

---

37. NETWORK RECOVERY TEST

Test:

ONLINE
↓
SEND MESSAGE
↓
NETWORK OFF
↓
REQUEST FAILS
↓
UI RECOVERS
↓
NETWORK ON
↓
RECONNECT
↓
ONLINE

Xultron must never remain permanently stuck in:

THINKING...

---

38. CORE STATE MACHINE

Implement a real state machine.

Valid states:

BOOTING
OFFLINE
CONNECTING
ONLINE
LISTENING
THINKING
SPEAKING
ERROR

Prevent impossible transitions.

For example:

OFFLINE → SPEAKING

must not occur.

The Core's visual state must reflect actual application state.

---

39. PERFORMANCE

The interface should remain smooth on mid-range Android devices.

Avoid:

- unnecessary rerenders
- massive DOM trees
- huge images
- heavy 3D scenes
- continuous expensive animation
- memory leaks

Animations should be disabled/reduced when:

Low Data Mode

or:

Reduced Motion

is enabled.

---

40. TESTING REQUIREMENT

Do not simply write tests.

Actually execute them.

Use appropriate automated tests for:

- backend services
- API endpoints
- authentication
- database
- provider abstraction
- authorization
- frontend critical components

Also perform manual browser/mobile tests for:

- UI
- voice
- responsive behavior
- PWA
- reconnect
- Core states

Do not mark a feature complete merely because the code compiles.

---

41. DEVELOPMENT ORDER

Follow this order:

PHASE 1

Architecture.

Inspect the empty/new project structure and establish:

- frontend
- backend
- database
- configuration
- API structure

Do not build the entire application in one giant step.

PHASE 2

Build the visual foundation first.

Implement:

- Theme
- Typography
- Xultron Core
- Main screen
- Navigation
- Animation system
- Responsive layout

The UI must be reviewed internally before adding large amounts of backend functionality.

PHASE 3

Authentication + database.

PHASE 4

Provider management.

PHASE 5

Text chat.

PHASE 6

Voice/STT/TTS.

PHASE 7

Memory.

PHASE 8

Low Data Mode + PWA.

PHASE 9

Security hardening.

PHASE 10

Full automated + manual testing.

---

42. IMPORTANT UI RULE

If a design decision makes Xultron look like a generic dashboard, reject it.

If a design decision makes Xultron look like a generic chatbot, reject it.

If a component exists only because "modern websites usually have cards", do not automatically use it.

Every UI component should have a purpose.

The interface should prioritize:

XULTRON CORE → CONVERSATION → VOICE → SYSTEM STATE

rather than:

sidebar → cards → tables → dashboard widgets.

---

43. DO NOT ASK FOR API KEYS DURING DEVELOPMENT

The application must be usable without configured providers.

If no AI provider exists:

NO AI PROVIDER CONFIGURED

Go to Settings → AI Providers

[Configure Provider]

This should be a normal application state, not a crash.

The same applies to STT/TTS.

---

44. FINAL ACCEPTANCE CRITERIA

Xultron is complete only when:

- UI looks intentionally designed, not generated from a generic template.
- Xultron Core is visually polished.
- Main screen works on mobile.
- Chat works.
- Authentication works.
- Guest mode works.
- AI providers can be added from Settings.
- STT providers can be added from Settings.
- TTS providers can be added from Settings.
- Provider credentials are securely stored.
- API keys never reach frontend.
- Provider connection testing works.
- Model selection works where supported.
- Memory works.
- User isolation works.
- Voice works.
- Low Data Mode works.
- Offline/reconnect works.
- PWA works.
- Error states are polished.
- Core state machine works.
- Security tests pass.
- Edge-case tests pass.
- Regression tests pass.

---

45. FINAL AGENT BEHAVIOR

Do not rush.

Before modifying code:

Inspect → Architect → Implement → Run → Test → Debug → Retest

When a test fails, investigate the root cause.

Do not hide failures.

Do not claim a feature is complete without testing it.

When the implementation is complete, provide a final report containing:

Architecture
Implemented Features
UI Components
API Providers
Security
Tests
Passed
Failed
Fixed
Known Limitations
Performance
Remaining TODO

Most importantly:

Xultron must feel like a real personal AI system, not a website with an AI API attached to it.
