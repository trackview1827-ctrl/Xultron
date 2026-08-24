# Xultron Signal Spine UI System

Status: implementation specification  
Target stack: React, TypeScript, Vite, Tailwind CSS, Framer Motion  
Primary platform: mobile and installable PWA

## 1. Purpose

Xultron must feel like a personal AI operating surface, not a website containing a chatbot. The Signal Spine system organizes the application around one continuous axis that joins system state, the Xultron Core, conversation events, voice activity, and controls.

This document defines the visual language, information architecture, component ownership, motion system, responsive behavior, accessibility requirements, and feature-specific interaction patterns required to implement that interface.

The design has five non-negotiable rules:

1. The Xultron Core is the primary visual and state-bearing element.
2. Content sits on one continuous operating plane rather than inside a collection of cards.
3. Lines, space, opacity, and typography establish hierarchy before fills, shadows, or glow.
4. Motion communicates real application state or causality. Decorative continuous motion is rejected.
5. Every important condition is communicated through visible text and geometry, not color or animation alone.

## 2. Old UI anti-pattern audit

The failed prototype was inspected only to identify patterns that must not be carried forward. No visual element from it should be treated as a foundation for the new application.

### 2.1 Generic chatbot composition

The centered maximum-width column, top bar, hero region, chat list, and sticky composer reproduce a conventional chatbot website. It makes the Core a decorative header above the actual application rather than the operating center of the product.

The replacement must integrate the Core into the conversation and state model. The Core changes placement but remains present as the user moves between console, conversation, voice, and configuration surfaces.

### 2.2 Message bubbles and card behavior

Rounded user and assistant message boxes create a familiar messenger layout. The assistant response becomes another bubble rather than system output.

The replacement uses a chronological Signal Spine. Messages are unboxed timeline events connected to one thin axis. Code, diagnostics, and editable forms may use bounded technical surfaces where containment is functionally necessary, but ordinary content is not wrapped in cards.

### 2.3 Generic glowing orb

A circular radial-gradient orb with intersecting elliptical rings is a generic futuristic assistant motif. Its orbit animation does not communicate application state and visually resembles many existing JARVIS-inspired templates.

The replacement uses an original segmented instrument made of a telemetry crown, incomplete phase rails, curved iris blades, signal threads, and a three-axis aperture. It explicitly avoids atom-like intersecting orbits.

### 2.4 State disconnected from visuals

The prototype Core animates continuously while application state is represented by unrelated text. Listening, thinking, speaking, offline, connecting, and error do not have real visual behavior.

The replacement drives both text and geometry from one guarded Core state machine. Route changes never fabricate Core states.

### 2.5 Excessive template styling

Radial page gradients, cyan and violet glow, rounded controls, and generic dark surfaces create a neon template aesthetic. Glow is used as general decoration rather than information.

The replacement reserves substantial glow for the aperture of the Core. Other surfaces are separated by ruled lines, spacing, and opacity.

### 2.6 Desktop shrinking instead of mobile design

A single narrow breakpoint only changes message width and header padding. It does not address safe areas, mobile keyboard behavior, landscape, touch reach, or tablet and wide-screen composition.

The replacement uses compact, medium, wide, and ultra layouts that reorganize the operating plane instead of merely changing widths.

### 2.7 Weak error and recovery behavior

Errors replace a status string but do not remain associated with the failed transmission. There is no retry object, edit-and-resend action, safe diagnostic detail, or visible reconnection lifecycle.

The replacement preserves failed messages, provides explicit recovery actions, and guarantees that every transient state reaches a terminal success, failure, cancellation, or timeout state.

### 2.8 Incomplete navigation and product structure

The prototype offers no visible information architecture for history, voice, memory, providers, privacy, network, account, or devices. Low-data behavior appears as an arbitrary composer checkbox.

The replacement uses a numbered route index and dedicated feature routes. Low-data mode becomes a coherent network and rendering policy under Settings.

### 2.9 Incomplete accessibility

The prototype does not define visible keyboard focus, route focus behavior, reduced motion, streaming announcements, state labels, or non-color status cues.

The replacement treats accessibility as part of every component contract.

## 3. Visual concept: Signal Spine

The Signal Spine is a one-pixel vertical rule that functions as a spatial and chronological coordinate. On the Core home state it extends downward from the Core. In conversation it becomes the timeline axis. In voice it anchors partial and confirmed transcripts. In settings and memory it becomes a leading ledger rail.

### 3.1 Visual principles

- One continuous field replaces a stack of panels.
- The Core is the only object allowed to cast a substantial cyan glow.
- Thin rules and small notches encode relationships.
- Filled backgrounds indicate true interaction modes such as an input, code block, selected text, or destructive confirmation.
- Default corner radius is 2px. A component may use a larger radius only when the platform interaction benefits from it, such as a thumb control.
- Selected navigation uses a 2px signal line and increased text contrast. It does not use a filled pill.
- Technical metadata is concise and factual. Decorative pseudo-engineering labels are prohibited.
- Empty space is intentional and should not be filled with widgets.

### 3.2 Primary screen hierarchy

```text
SYSTEM MAST
XULTRON  ·  ONLINE                         INDEX

                    CORE FIELD
                    state label
                         │
                         │  SIGNAL SPINE
                         │
                    conversation
                         │

COMMAND DECK
provider/model · input · voice · transmit
safe-area inset
```

On a new console the Core uses approximately 45 percent of the compact viewport height. After the first transmission, the Core contracts into a persistent state instrument above the conversation timeline.

## 4. Information architecture

### 4.1 Public and application routes

| Route | Purpose | Compact behavior | Wide behavior |
| --- | --- | --- | --- |
| `/` | New or most recent console session | Core-focused home | Core observatory and recent activity |
| `/c/:conversationId` | Canonical conversation timeline | Compact Core header and timeline | Sticky Core observatory beside timeline |
| `/history` | Conversation registry | Full route | Ledger beside active conversation when selected |
| `/voice` | Immersive voice interaction | Full-screen voice plane | Centered voice observatory |
| `/memory` | Searchable memory ledger | Full route | Ledger with optional detail plane |
| `/memory/:memoryId` | View or edit one memory | Full route | Adjacent detail plane |
| `/settings` | Settings category index | Full route | Category ledger and current section |
| `/settings/:section` | General, voice, memory, appearance, network, privacy, account, devices | Full route | Split ledger and editor |
| `/settings/providers/:kind` | AI, STT, or TTS provider registry | Provider ledger | Registry plus health context |
| `/settings/providers/:kind/new` | Register provider | Full-screen editor | Editor beside registry |
| `/settings/providers/:kind/:providerId` | Edit provider | Full-screen editor | Editor beside registry |
| `/auth` | Authentication method index | Full-screen | Centered authentication plane |
| `/auth/sign-in` | Sign in | Full-screen | Centered authentication plane |
| `/auth/register` | Create account | Full-screen | Centered authentication plane |
| `/auth/guest` | Guest disclosure and entry | Full-screen | Centered authentication plane |
| `/offline` | Service-worker navigation fallback | Offline shell | Offline shell |

`kind` is one of `ai`, `stt`, or `tts`.

### 4.2 Route Index

The `INDEX` action in the System Mast opens a ruled full-height route sheet:

```text
00  CORE
01  HISTORY
02  VOICE
03  MEMORY
04  CONTROL
05  ACCOUNT
```

Each row contains a two-digit coordinate, concise label, current-state summary, and route link. It is not a hamburger sidebar or grid of menu cards.

On wide screens, the route index becomes a persistent 64px coordinate rail. It shows the coordinate and icon by default and expands its label on focus or pointer intent. It must remain fully usable without expansion.

### 4.3 Settings index

Settings are a ruled system ledger:

```text
GENERAL                     Language · English
AI PROVIDERS                2 configured · 1 online
STT PROVIDERS               Not configured
TTS PROVIDERS               Local Voice · online
VOICE                       Push to speak
MEMORY                      Enabled · 24 records
APPEARANCE                  System
NETWORK                     Low Data off
PRIVACY                     Audio never stored
ACCOUNT                     user@example.com
DEVICES                     No devices
```

The right-hand summary communicates useful status without turning the page into a dashboard.

## 5. Design tokens

### 5.1 Color

```ts
export const colors = {
  void: "#070B10",
  plane: "#0B1118",
  planeRaised: "#101923",
  line: "#22313E",
  lineStrong: "#3B5363",
  text: "#EDF7FA",
  textMuted: "#91A6AF",
  textFaint: "#627780",
  signal: "#47D7E8",
  signalBright: "#A6F5FF",
  phase: "#8C7CFF",
  success: "#61E6A8",
  warning: "#FFB45C",
  danger: "#FF6B6B"
} as const
```

Usage constraints:

- `void` is the application field.
- `plane` identifies working surfaces such as an expanded editor but must not create floating cards.
- `planeRaised` is reserved for input focus, code blocks, dialogs, and destructive confirmations.
- `phase` is used sparingly for secondary Core activity and selected voice or provider detail.
- `danger` is reserved for errors and destructive actions.
- Only the Core may use blurred cyan light.
- Normal text and important controls must meet WCAG 2.2 AA contrast. Target at least 4.5:1 for normal text and 3:1 for large text and graphical controls.

### 5.2 Typography

Bundle local variable WOFF2 font files so the application does not depend on third-party font requests.

- Instrument Sans Variable, weight 400 through 650, for prose, controls, and headings.
- IBM Plex Mono, weight 400 and 500, for states, timestamps, identifiers, and technical metadata.
- Low-data fallback uses `system-ui` and `ui-monospace` when fonts are not already cached.

| Role | Compact specification | Wide specification |
| --- | --- | --- |
| XULTRON wordmark | 15px, weight 650, tracking `0.28em` | same |
| Core state | 11px mono, weight 500, tracking `0.16em` | 12px |
| Route title | 28 to 34px, weight 520 | 36 to 44px |
| Response prose | 16px, line-height 1.65 | 17 to 18px, line-height 1.65 |
| User transmission | 15 to 16px, line-height 1.55 | 16px |
| Technical metadata | 11px mono | 11 to 12px mono |
| Input text | 16px minimum | 16px |

Prose measure is capped near 72 characters. Provider identifiers and code may use a wider technical measure.

### 5.3 Spacing and dimensions

Base spacing uses a 4px scale:

```ts
export const space = {
  1: "4px",
  2: "8px",
  3: "12px",
  4: "16px",
  5: "20px",
  6: "24px",
  8: "32px",
  10: "40px",
  12: "48px",
  16: "64px",
  20: "80px"
} as const
```

- Compact horizontal gutter: 16px.
- Compact gutter below 360px width: 12px.
- Medium gutter: 24px.
- Wide content gap: 32px.
- Minimum touch target: 44 by 44px.
- System Mast minimum height: 52px plus safe-area inset.
- Compact Command Deck minimum height: 64px plus safe-area inset.
- Standard ruled line: 1px.
- Active signal line: 2px.
- Default corner radius: 2px.
- Control corner radius maximum: 6px unless the control is circular by function.

### 5.4 Elevation

Do not define a general card shadow scale.

Allowed elevation effects:

- One static Core field glow.
- One aperture glow inside the Core.
- A narrow top shadow on the Command Deck only when content scrolls beneath it.
- A strong solid backdrop behind modal dialogs.

## 6. Responsive system

Tailwind breakpoints represent structural transitions:

```ts
screens: {
  compact: "0px",
  medium: "600px",
  wide: "960px",
  ultra: "1440px"
}
```

### 6.1 Compact, below 600px

- Four-column grid.
- 16px gutters, reduced to 12px below 360px.
- Application shell uses `100dvh` with `100svh` fallback.
- System Mast is 52px plus top safe area.
- Command Deck occupies the bottom shell row and includes the bottom safe area.
- Home Core size is `clamp(184px, 58vw, 240px)`.
- Conversation Core size is 72 to 88px.
- Provider and memory detail views are independent routes.
- No action depends on hover or swipe.
- Landscape voice mode moves transcript content beside the Core when vertical space is constrained.

### 6.2 Medium, 600px through 959px

- Six-column grid with 24px gutters.
- Conversation and composer are capped at 680px.
- Home Core can grow to 280px.
- Memory and settings remain single-plane unless landscape width exceeds 820px.
- The Command Deck never stretches beyond the readable conversation measure.

### 6.3 Wide, 960px and above

- Twelve-column grid.
- Persistent 64px coordinate rail at the leading edge.
- Conversation Core observatory occupies approximately columns 2 through 5.
- Timeline occupies approximately columns 6 through 11.
- Remaining space stays empty unless a real contextual task requires it.
- The Core observatory is sticky and vertically centered.
- Settings use a 280px category ledger separated from the editor by one vertical rule.
- No boxed sidebar and no dashboard home are allowed.

### 6.4 Ultra, 1440px and above

- Preserve readable measures rather than scaling every element.
- Increase inter-plane whitespace.
- Home Core may grow to 360px.
- Do not introduce additional dashboard columns or widgets.

### 6.5 App shell and keyboard behavior

```css
.app-shell {
  min-height: 100svh;
  height: 100dvh;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
  padding-top: env(safe-area-inset-top);
  overflow: hidden;
}

.command-deck {
  padding-bottom: env(safe-area-inset-bottom);
}
```

The middle row owns scrolling. The body does not independently scroll while the application shell is active. Use `VisualViewport` only as an Android fallback when the browser reports an incorrect dynamic viewport during keyboard display.

The composer grows from one to six rows. The timeline remains reachable when the keyboard opens. Orientation changes preserve the active draft and scroll anchor.

## 7. Xultron Core anatomy

### 7.1 Component contract

```ts
export type CoreState =
  | "booting"
  | "offline"
  | "connecting"
  | "online"
  | "listening"
  | "thinking"
  | "speaking"
  | "error"

export interface CoreVisualInput {
  state: CoreState
  label: string
  inputLevel?: MotionValue<number>
  outputLevel?: MotionValue<number>
  lowData: boolean
  reducedMotion: boolean
}
```

The wrapper is semantic. The detailed SVG is decorative.

```tsx
<motion.figure
  layoutId="xultron-core"
  data-state={state}
  aria-label={`Xultron is ${label}`}
>
  <CoreSvg {...visualInput} aria-hidden="true" />
  <figcaption>{label}</figcaption>
</motion.figure>
```

The SVG uses `viewBox="0 0 320 320"`. All strokes use `vector-effect="non-scaling-stroke"`.

### 7.2 SVG layers

Render layers in this order:

1. **Field glow**  
   One low-opacity radial gradient behind the SVG. It is static. Its opacity may crossfade between states, but blur radius is never animated.

2. **Datum marks**  
   Four groups of short coordinate marks at the cardinal positions. They establish precision without forming a crosshair through the center.

3. **Telemetry crown**  
   Twelve discontinuous arc segments at radius 132. Segments illuminate independently and provide a stepped representation for low-data and reduced-motion audio states.

4. **Outer state notch**  
   A deliberate crown gap around the two o'clock position. Offline widens the gap. Error offsets and sharply angles it. This makes state distinguishable without color.

5. **Phase rails**  
   Two incomplete circular paths at radii 108 and 92. Their gaps are offset. They never intersect as elliptical orbits.

6. **Signal threads**  
   Three asymmetric Bézier paths that join selected crown segments to the iris. Small packets may travel along them only during connecting or thinking.

7. **Iris blades**  
   Six curved shutter paths arranged around the center. Blade opening represents controlled activity or real audio level.

8. **Aperture**  
   A compact three-axis lens made from three concave blades around a bright center slit. It must not resolve into a simple glowing circle.

9. **Diagnostic marker**  
   A small optional marker associated with timeout, provider failure, or reconnect detail. It is visible only when the application has safe diagnostic information.

### 7.3 Performance rules

- Animate only `transform`, `opacity`, `pathLength`, and `strokeDashoffset`.
- Never animate large SVG filters or page-sized gradients.
- Keep one `requestAnimationFrame` loop only while listening or speaking.
- Feed analyser values into Framer Motion values or DOM style properties without causing React rerenders per audio frame.
- Pause all loops when `document.visibilityState !== "visible"`.
- Avoid a continuously active Canvas or WebGL scene.

## 8. Core state animations

### 8.1 Booting

Duration target: 1.8 seconds for a fresh launch. A restored PWA session may use a 350ms abbreviated boot.

Sequence:

1. Datum marks fade from 0 to 0.55 opacity over 220ms.
2. Crown segments draw clockwise using staggered `pathLength` over 1.1 seconds.
3. Phase rails draw from their state-notch gap over 600ms.
4. Iris blades activate inward over 500ms.
5. Aperture illuminates last over 240ms.
6. Visible label starts as `INITIALIZING` and changes only when the state machine reaches connecting, online, offline, or error.

Booting does not loop.

### 8.2 Offline

- Stop all rotation, packet travel, and breathing.
- Reduce crown opacity to 22 percent.
- Remove three adjacent crown segments near the state notch.
- Set phase rails to graphite and 35 percent opacity.
- Close the iris to its neutral minimum.
- Remove the bright aperture fill, retaining a faint outline.
- Show `OFFLINE · NETWORK UNAVAILABLE` or a more specific safe label.

Offline must look structurally incomplete rather than merely gray.

### 8.3 Connecting

- Sweep the two phase rails in opposite directions over 1.4 seconds.
- Send one packet from the telemetry crown toward the aperture.
- Illuminate crown segments sequentially with a 70ms stagger.
- Keep the iris partially open at 14 percent.
- Repeat the sweep only while the actual connection attempt is active.
- Stop on explicit success, failure, cancellation, offline event, or timeout.

### 8.4 Online

- Aperture opacity breathes between 0.82 and 1 over 4.8 seconds.
- Scale may vary by at most 1.5 percent when motion is allowed.
- No ring performs a full continuous rotation.
- One crown segment advances every 12 seconds as a restrained heartbeat.
- Datum and phase rail opacity remain stable.

Online should appear alive but almost still.

### 8.5 Listening

- Microphone RMS opens the iris from 8 to 30 percent.
- Smooth analyser input with an exponential moving average around `alpha = 0.18`.
- Nearby crown segments illuminate according to level bands.
- The aperture widens vertically according to real input level.
- A visible recording label and elapsed duration accompany the Core.
- Silence does not cause the interface to appear stopped. The recording label remains authoritative.

Do not add a generic waveform around or below the Core.

### 8.6 Thinking

- Rotate phase rails at 6.4 and 9.6 seconds in opposite directions.
- Send signal packets outward on one thread and inward on another.
- Shift alternating iris blade groups by 2 to 4 degrees.
- Modulate crown segment opacity in a deterministic sequence.
- Keep the response text area ready for streaming without using a fake typewriter effect.
- Stop the animation on complete, cancellation, provider failure, network loss, or timeout.

### 8.7 Speaking

- TTS analyser output controls aperture width.
- Emit thin crown echoes that expand outward and fade.
- Cap echo emission at three per second.
- Use the output analyser when available. If analyser access is unavailable, use word-boundary or playback progress events at a restrained cadence.
- Captions remain visible throughout playback.
- Provide an always-visible stop-output action.

### 8.8 Error

- Widen and angle the state notch.
- Change the active rail and aperture accent to danger.
- Perform two 180ms displacement pulses, then become still.
- Do not flash continuously.
- Display a concise diagnostic below the Core and a direct recovery action.
- Preserve the rest of the application and any user content.

## 9. Core state machine

Core state is owned by application logic. Visual components receive state and never invent it.

```ts
export const allowedTransitions: Record<CoreState, readonly CoreState[]> = {
  booting: ["connecting", "offline", "error"],
  offline: ["connecting"],
  connecting: ["online", "offline", "error"],
  online: ["listening", "thinking", "offline", "error"],
  listening: ["thinking", "online", "offline", "error"],
  thinking: ["speaking", "online", "offline", "error"],
  speaking: ["online", "listening", "offline", "error"],
  error: ["connecting", "online", "offline"]
} as const
```

Event rules:

- `APP_READY` leaves booting and enters connecting or offline based on actual connectivity.
- `CONNECTION_CONFIRMED` enters online from connecting.
- `MIC_GRANTED` may enter listening only from online.
- `TRANSCRIPT_COMMITTED` enters thinking only when confirmed text is non-empty.
- `USER_MESSAGE_SENT` enters thinking only after request dispatch begins.
- `AI_CHUNK_RECEIVED` does not change state.
- `AI_COMPLETE` enters speaking only when TTS is enabled and playable. Otherwise it returns online.
- `TTS_COMPLETE` returns to online.
- `NETWORK_LOST` enters offline from every operational state and cancels state timeouts.
- `RETRY` enters connecting from error or offline.
- `CANCEL` returns to online if connectivity remains available.
- Every asynchronous operation has a timeout that exits its transient state.
- Invalid transitions are logged as safe diagnostic events and are not executed.
- Route changes never modify Core state.

## 10. Core placement transitions

Use one persistent Core host in `AppShell` and Framer Motion shared layout transitions with `layoutId="xultron-core"`.

- Home to conversation: centered 184 to 240px Core becomes a 72 to 88px timeline instrument.
- Conversation to voice: compact Core expands to `min(76vw, 360px)` and moves to the visual center.
- Application route to settings or memory: Core becomes a 28px state glyph in the System Mast on compact screens. It may remain in the wide coordinate rail observatory.
- Any route to offline: Core geometry remains spatially stable while its state changes to offline.
- Route transitions use a 180ms opacity change and at most 12px of movement along the Signal Spine.
- Do not slide entire routes horizontally like a mobile carousel.

## 11. System Mast and navigation

The System Mast is the stable top landmark.

Compact content:

- XULTRON wordmark.
- Core state label and connectivity indicator.
- Optional current provider abbreviation.
- `INDEX` action.

Wide content:

- Coordinate rail controls navigation.
- Mast contains route title, Core state, and current account or guest marker.

The state indicator uses symbol, geometry, and text. Examples:

- `◇ ONLINE`
- `◌ CONNECTING`
- `⌁ LISTENING`
- `× OFFLINE`

Symbols must not replace the visible text.

## 12. Conversation timeline

### 12.1 Structure

The conversation is a chronological signal record.

- A one-pixel Signal Spine runs down the leading edge.
- Every turn connects to the spine with a short horizontal notch.
- User turns use `YOU / timestamp` and a short signal-colored notch.
- Xultron responses use `XULTRON / provider · model`.
- Text sits directly on the operating field.
- Assistant responses receive more vertical space and a faint leading rule.
- Code blocks use bounded technical surfaces because containment and horizontal scrolling are functional requirements.
- Tool activity appears as collapsible operation rows connected to the spine.
- Citations use numbered inline anchors that open a source sheet.

### 12.2 Timeline turn states

User transmission states:

- `draft`
- `queued`
- `sending`
- `accepted`
- `failed`

Assistant output states:

- `waiting`
- `streaming`
- `complete`
- `cancelled`
- `failed`

Failed transmissions retain the original content and expose:

- `RETRY`
- `EDIT AND RETRANSMIT`
- safe failure detail

A duplicate request response should annotate the existing turn instead of appending another assistant event.

### 12.3 Streaming behavior

- Append chunks without character-by-character animation.
- Show one signal cursor at the end of the active response.
- Announce completed messages rather than individual chunks.
- Do not force-scroll when the user has moved away from the bottom.
- Show a `1 NEW SIGNAL` marker connected to the spine.
- Restore automatic following when the marker is activated or the user returns to the bottom.
- Copy, retry, read-aloud, and feedback actions remain visible on touch devices.
- Preserve the current timeline and draft during provider errors or reconnection.

### 12.4 Long content

- Markdown headings participate in the response hierarchy but cannot exceed the route heading level.
- Tables scroll horizontally inside a ruled technical surface.
- Code has copy and language controls.
- Very long operation traces are collapsed by default.
- Large messages may be virtually rendered only after measurement proves it necessary. Do not add virtualization prematurely.

## 13. Command Deck

The composer is an edge-to-edge working deck separated from the timeline by one top rule.

Compact anatomy:

- Index action at the leading edge.
- Auto-growing textarea in the center.
- Microphone action.
- Transmit action.
- Metadata row for active provider, model, low-data status, and attachment state.

Rules:

- Do not wrap the composer in a rounded pill.
- Use a flat field with a focused leading rail and bottom border.
- Grow from one to six text rows.
- Keep input text at 16px minimum.
- On touch keyboards, Enter inserts a newline and the explicit transmit control sends.
- Hardware keyboard users may enable Enter-to-send.
- Drafts survive route changes during the current session.
- Voice permission and missing providers are explained before activation.
- Empty submission is disabled without presenting an error.
- Network loss preserves the draft and changes the transmit action to an offline state.

## 14. Voice mode

Voice is a dedicated route rather than a microphone overlay on chat.

### 14.1 Layout

- Large Core in the upper-middle region.
- Visible state text directly below the Core.
- Partial transcript in a restrained text band attached to the Signal Spine.
- Latest confirmed transcript remains visible during thinking.
- Spoken output includes synchronized text captions.
- Bottom controls expose cancel, microphone state, and stop output.

### 14.2 Voice lifecycle

1. **Permission preflight**  
   Explain microphone access, current STT provider, whether audio is stored, and how to change privacy settings. Audio persistence is off by default.

2. **Listening**  
   Core responds to real microphone RMS. Show `LISTENING`, elapsed duration, and an explicit stop control.

3. **Transcribing**  
   Keep the last audio geometry briefly, then display partial and confirmed text with clear distinction.

4. **Thinking**  
   Freeze the confirmed transcript. Provide cancel and timeout recovery.

5. **Speaking**  
   Core responds to output audio. Display captions and a stop-output action.

6. **Return**  
   Core settles to online while the new turn remains in the active conversation.

### 14.3 Voice failures

Provide specific recovery for:

- Microphone permission denied.
- No microphone available.
- Empty audio.
- Audio size limit reached.
- Missing STT provider.
- STT timeout or malformed response.
- Missing TTS provider.
- TTS failure after a valid text answer.
- Bluetooth or audio output disconnect.
- Network interruption.

When TTS fails, retain and display the textual answer. Never discard a valid answer because playback failed.

### 14.4 Interruption

If barge-in is supported, it must be explicit in Voice settings. The user can interrupt playback with the microphone control or stop-output action. A gesture may be offered as an enhancement but cannot be the only path.

## 15. Settings system

Settings remain a first-class operating surface.

### 15.1 Settings sections

- General
- AI Providers
- STT Providers
- TTS Providers
- Voice
- Memory
- Appearance
- Network
- Privacy
- Account
- Devices

Every settings page uses a heading, concise explanation, and ruled field groups. It does not use cards for each option.

### 15.2 Field behavior

- Labels remain visible above controls.
- Descriptions explain consequences rather than restating labels.
- Validation appears next to the field and in an error summary after submission.
- Toggle controls include explicit current-state text for screen readers.
- Dirty forms show `UNSAVED` in the System Mast.
- Route changes with unsaved values require confirmation.
- Saving preserves scroll and focus context.

## 16. Provider registry

Each provider is one ledger row containing:

- Status symbol and text.
- Provider name.
- Provider type.
- Safe endpoint hostname.
- Active model, language, or voice.
- `DEFAULT` marker where applicable.
- Last test result and timestamp.
- Accessible overflow action.

The registration action is the final ledger row labeled `+ REGISTER PROVIDER`.

Provider health states:

- Untested.
- Testing.
- Online.
- Degraded.
- Failed.
- Disabled.

Status is never indicated by a colored dot alone.

## 17. Provider editor

On compact screens, the editor is a full route. On wide screens, it opens beside the provider registry.

### 17.1 Common sections

1. **Identity**
   - Provider name.
   - Provider kind.
   - Provider type.
   - Enabled.
   - Set as default.

2. **Connection**
   - Base URL.
   - API key or credential.
   - Timeout.
   - Optional custom headers where supported.

3. **Capability**
   - Model, language, or voice.
   - Model or voice discovery.
   - Manual identifier entry.
   - Streaming.
   - Supported formats.

4. **Generation or recognition**
   - AI temperature and maximum output.
   - STT language and audio format.
   - TTS speed, pitch, language, and output format.

5. **Diagnostics**
   - Test connection.
   - Test voice where relevant.
   - Last safe diagnostic.
   - Response latency.

6. **Danger zone**
   - Disable.
   - Delete with explicit confirmation.

### 17.2 Credential behavior

- Existing credentials display `STORED ·••••91A2` or equivalent masked metadata.
- The frontend never receives the complete stored credential.
- A blank credential submission retains the existing secret.
- `REPLACE SECRET` creates an empty password field for a new value.
- Stored credentials cannot be copied or revealed.
- Diagnostics never display request headers, stack traces, secrets, or internal paths.
- Browser autofill behavior should be tested and controlled with appropriate autocomplete attributes.

### 17.3 Testing lifecycle

The sticky action rail contains `DISCARD`, `TEST`, and `SAVE`.

Testing moves through:

```text
UNTESTED → TESTING → SUCCESS
                   → FAILED
                   → TIMEOUT
                   → CANCELLED
```

Every test reaches a terminal state. A safe failure may include HTTP status, category, and a plain-language recommendation. It must never include secret material.

### 17.4 Model discovery

- `REFRESH MODELS` runs only on explicit activation.
- Loading does not block editing unrelated fields.
- Discovered models are searchable.
- Manual model ID entry remains available when discovery is unavailable.
- Changing the provider type clears only fields that are incompatible, and only after confirmation if values would be lost.

## 18. Memory system

Memory is presented as a searchable Memory Ledger.

### 18.1 Categories

- Personal
- Preferences
- Important
- Temporary

Search and category filters use an underlined text index rather than filled pills.

### 18.2 Memory row

Each row includes:

- Content preview.
- Category.
- Source.
- Created or updated timestamp.
- Optional last-used timestamp.
- Inferred or user-created marker.

Selecting a row opens the memory detail route or adjacent wide-screen detail plane.

### 18.3 Detail and control

- Edit content and category.
- Inspect source and reason for storage.
- Inspect whether Xultron has used it recently.
- Set retention for temporary memories.
- Delete one item.
- Bulk select and delete.
- Clear all with explicit confirmation and re-authentication where appropriate.

Automatically inferred memories show `INFERRED FROM CONVERSATION` and can be rejected. Guest mode clearly states that persistent memory is unavailable.

Disabling memory explains what stops being recorded and does not silently delete existing memory. Deletion is a separate explicit action.

## 19. Authentication and guest mode

The authentication plane uses a quiet, partially active Core and one central Signal Spine.

### 19.1 Layout

- No hard-coded personal greeting.
- Sign in, registration, and guest entry are explicit routes.
- Forms are unboxed and capped at 420px.
- Labels remain visible above fields.
- Primary and secondary actions are visually distinct without using large cards.

### 19.2 Behavior

- Errors appear beside the relevant field and in a summary.
- Password reveal is a labeled control.
- Loading retains button dimensions and visible action context.
- Rate-limit states include safe retry guidance.
- Session expiration preserves an unsent draft in session memory, then requests sign-in.
- Logout is available from Account and the route index rather than as a dominant header button.

### 19.3 Guest mode

Before entry, explain:

- Guest data lifetime.
- Whether conversation history persists.
- Memory limitations.
- Provider and credential restrictions.
- How to convert to an account.

Guest-to-account conversion asks whether the current conversation should be imported. It never merges data silently.

## 20. Offline and reconnect behavior

### 20.1 Offline shell

When cached shell assets are available:

- Application shell opens.
- Core enters the true offline state.
- System Mast shows `OFFLINE · LAST CONNECTED 13:04` or equivalent.
- Composer remains available for drafting.
- Transmit is disabled and drafts are labeled `UNSENT`.
- Xultron never claims AI, STT, or TTS functionality works offline when it does not.
- Reconnection enters connecting before online.
- Unsent content is not transmitted automatically without user consent.

### 20.2 Failed in-flight request

Network loss during a message request must:

1. Leave thinking.
2. Mark the associated transmission as failed or interrupted.
3. Preserve user content.
4. Enter offline.
5. Offer retry after reconnection.
6. Never remain permanently stuck in a transient state.

### 20.3 PWA caching policy

Precache:

- Application shell.
- Local fonts.
- Icons.
- Core SVG and static visual assets.
- Offline route.

Do not cache by default:

- Provider responses.
- Credentials.
- Authentication API responses.
- Memory API responses.
- Chat API responses.
- Audio.

Conversation caching is opt-in under Privacy. Cached private data is cleared on logout. An unavailable or expired session hides cached private content behind the authentication boundary.

### 20.4 Install and update

- PWA install is offered under General settings rather than through an intrusive launch prompt.
- An available update produces a small `UPDATE READY` system notice.
- Applying an update requires user activation when a draft or active voice session exists.
- Standalone mode respects all safe-area insets and uses the same route history semantics.

## 21. Error UX

Errors are designed states rather than dumped server messages.

Every error presentation includes:

- What failed.
- Whether user data was preserved.
- What can be done next.
- Safe optional detail.

Examples:

```text
PROVIDER UNAVAILABLE
Your message is preserved.
Retry the transmission or inspect the active AI provider.

RETRY     OPEN PROVIDER
```

```text
MICROPHONE ACCESS DENIED
Voice input cannot start without microphone permission.
Use device settings to allow access or continue with text.
```

Raw stack traces, API keys, internal filesystem paths, request headers, and uncontrolled provider response bodies never appear.

## 22. Accessibility

Accessibility is part of each component's acceptance criteria.

### 22.1 Semantics and focus

- Use `header`, `nav`, `main`, `section`, `form`, and `footer` landmarks.
- Provide skip links to the active conversation and Command Deck.
- Route changes move focus to the route heading.
- Dialogs trap focus and return it to the originating control.
- All actions work by keyboard without gesture requirements.
- Focus uses a 2px signal outline and 3px dark offset.
- Do not remove browser focus unless an equally visible replacement is active.

### 22.2 Core and system status

- Detailed Core SVG layers are `aria-hidden`.
- The Core wrapper exposes a concise current-state label.
- Core state changes use a polite live region.
- Disconnection or a failure requiring immediate attention may use an assertive announcement once.
- Animation and color are never the only state cues.

### 22.3 Conversation

- Timeline uses `role="log"` and `aria-relevant="additions"`.
- Streaming content is announced once when complete, not on each chunk.
- User and Xultron identities are present in accessible names.
- Code copy actions identify the code language or block context.
- New-message markers receive keyboard focus and explain the number of unread events.

### 22.4 Forms

- Fields use visible labels.
- Descriptions and errors are connected with `aria-describedby`.
- Submission errors are summarized at the top and linked to fields.
- Required fields are programmatically indicated.
- Secret replacement state is explicit.
- Toggle controls announce name and current state.

### 22.5 Voice

- Captions are mandatory during TTS playback.
- A visible label indicates active recording even when audio level is zero.
- Stop recording and stop output controls remain keyboard and screen-reader accessible.
- Elapsed time is not announced every second. Announce meaningful milestones or rely on user query.

## 23. Reduced motion

Respect both `prefers-reduced-motion` and the in-app motion preference.

When reduced motion is active:

- No Core rotation.
- No packet travel.
- No scale breathing.
- No expanding speaking echoes.
- No page translation.
- State changes use immediate geometry and color changes.
- Route changes use a 100ms opacity change or no transition.
- Listening and speaking use stepped crown illumination at no more than eight updates per second.
- Error state changes geometry and label without displacement pulses.
- All features and status information remain available.

Reduced motion is not identical to low-data mode. Users may enable either independently.

## 24. Low-data mode

Low-data mode changes network and rendering policy. It is not a composer checkbox.

### 24.1 Network behavior

- Do not preload conversation history, models, voices, or inactive settings sections.
- Run model discovery only when requested.
- Stop background provider polling.
- Refresh health on focus or explicit activation.
- Send only required conversation context.
- Avoid repeatedly downloading unchanged history.
- Compress supported audio before upload.
- Prefer streaming when it improves perceived latency without increasing total transfer significantly.
- Display session upload and download totals under Network.

### 24.2 Rendering behavior

- Use system fonts unless bundled fonts are already cached.
- Disable optional background glow and signal packet effects.
- Update voice visualization at 12Hz rather than every animation frame.
- Use stepped crown segments instead of continuous analyser interpolation.
- Crossfade Core state over 100 to 120ms without rotation.
- Do not load decorative images or large media.

### 24.3 Data controls

Network settings show:

- Low Data mode on or off.
- Session download total.
- Session upload total.
- Audio compression policy.
- Background refresh policy.
- Last provider health check.

## 25. Framer Motion implementation

### 25.1 Motion tokens

```ts
export const motion = {
  fast: 0.12,
  route: 0.18,
  state: 0.24,
  settle: 0.42,
  onlineBreath: 4.8,
  connectingSweep: 1.4,
  thinkingRailA: 6.4,
  thinkingRailB: 9.6
} as const
```

Use easing intentionally:

- State activation: `[0.22, 1, 0.36, 1]`.
- Route movement: `[0.4, 0, 0.2, 1]`.
- Linear only for continuous analyser-independent rotation.

### 25.2 AnimatePresence

- Use `initial={false}` for route and transient state surfaces after hydration.
- Exit animations never delay navigation by more than 180ms.
- Do not animate height for large streaming content regions.
- Preserve layout around the Command Deck while the keyboard is active.

### 25.3 Audio values

Use `useMotionValue` for raw and smoothed levels. Update SVG transforms and opacity without storing each audio frame in React state. React state receives only lifecycle changes such as started, stopped, permission denied, or device changed.

## 26. React and TypeScript component map

```text
frontend/src/
  app/
    App.tsx
    router.tsx
    AppShell.tsx
    AuthShell.tsx
    providers.tsx

  components/
    actions/
      ActionKey.tsx
      IconAction.tsx
    fields/
      Field.tsx
      SecretField.tsx
      SwitchField.tsx
      SelectField.tsx
      RangeField.tsx
    feedback/
      DiagnosticNotice.tsx
      InlineError.tsx
      ProgressRail.tsx
      StateLabel.tsx
    navigation/
      SystemMast.tsx
      RouteIndex.tsx
      CoordinateRail.tsx
    surfaces/
      Ledger.tsx
      LedgerRow.tsx
      Rule.tsx
      TechnicalSurface.tsx

  features/
    core/
      XultronCore.tsx
      CoreSvg.tsx
      CoreHost.tsx
      coreMachine.ts
      coreVariants.ts
      useAudioLevel.ts
      core.types.ts

    chat/
      ConversationPage.tsx
      SignalTimeline.tsx
      TimelineTurn.tsx
      AssistantOutput.tsx
      UserTransmission.tsx
      OperationTrace.tsx
      StreamingCursor.tsx
      CommandDeck.tsx
      conversation.api.ts
      conversation.types.ts

    voice/
      VoicePage.tsx
      VoiceTranscript.tsx
      VoiceControls.tsx
      PermissionPreflight.tsx
      voiceMachine.ts
      voice.api.ts
      voice.types.ts

    providers/
      ProviderRegistryPage.tsx
      ProviderLedger.tsx
      ProviderEditorPage.tsx
      ProviderForm.tsx
      ProviderDiagnostics.tsx
      ModelDiscovery.tsx
      provider.schemas.ts
      provider.api.ts
      provider.types.ts

    settings/
      SettingsIndexPage.tsx
      SettingsSectionPage.tsx
      GeneralSettings.tsx
      VoiceSettings.tsx
      NetworkSettings.tsx
      PrivacySettings.tsx
      AccountSettings.tsx
      DevicesSettings.tsx
      settings.routes.ts

    memory/
      MemoryPage.tsx
      MemoryLedger.tsx
      MemoryRow.tsx
      MemoryEditor.tsx
      MemoryBulkActions.tsx
      memory.api.ts
      memory.types.ts

    auth/
      AuthIndexPage.tsx
      SignInPage.tsx
      RegisterPage.tsx
      GuestPage.tsx
      SessionExpired.tsx
      auth.api.ts

    connectivity/
      ConnectivityProvider.tsx
      OfflinePage.tsx
      ReconnectNotice.tsx
      connectivityMachine.ts

  hooks/
    useReducedMotionMode.ts
    useLowDataMode.ts
    useVisualViewport.ts
    useOnlineState.ts
    useRouteFocus.ts

  services/
    apiClient.ts
    eventStream.ts
    serviceWorker.ts
    secureDrafts.ts

  state/
    sessionReducer.ts
    uiPreferencesReducer.ts

  theme/
    tokens.ts
    globals.css
    typography.css

  types/
    api.ts
    entities.ts
```

### 26.1 State ownership

- React Router owns route and selected-resource identity.
- TanStack Query owns server data and mutations.
- A Core reducer or small finite-state implementation owns guarded Core transitions.
- A dedicated voice machine owns microphone, STT, thinking, and playback lifecycle.
- Connectivity provider owns browser and backend reachability.
- UI preference reducer owns low-data, reduced-motion override, theme, and keyboard behavior.
- Do not add another global state library unless real cross-feature complexity demonstrates the need.

### 26.2 Component boundaries

- `XultronCore` renders visuals only from its input contract.
- `CoreHost` maps application state into Core placement and labels.
- `SignalTimeline` owns scroll following and unread markers.
- `TimelineTurn` owns one chronological event and its accessible label.
- `CommandDeck` owns draft editing but not request transport.
- `ProviderForm` handles fields and client validation. The page handles queries, mutations, unsaved-route protection, and diagnostics.
- `Ledger` and `LedgerRow` are structural primitives, not card abstractions.

## 27. Tailwind implementation guidance

Extend Tailwind with semantic names rather than using raw colors in components:

```ts
extend: {
  colors: {
    void: "#070B10",
    plane: "#0B1118",
    "plane-raised": "#101923",
    line: "#22313E",
    "line-strong": "#3B5363",
    ink: "#EDF7FA",
    muted: "#91A6AF",
    faint: "#627780",
    signal: "#47D7E8",
    "signal-bright": "#A6F5FF",
    phase: "#8C7CFF",
    success: "#61E6A8",
    warning: "#FFB45C",
    danger: "#FF6B6B"
  },
  screens: {
    medium: "600px",
    wide: "960px",
    ultra: "1440px"
  }
}
```

Create only a small number of component classes in `globals.css`:

- `.focus-signal`
- `.ruled-row`
- `.technical-surface`
- `.safe-top`
- `.safe-bottom`

Do not hide a generic component library aesthetic behind utility classes.

## 28. Practical implementation sequence

1. Define tokens, local fonts, global operating plane, and ruled structural primitives.
2. Build static Core SVG anatomy with isolated fixtures for all eight states.
3. Implement the guarded Core state machine and reduced-motion variants.
4. Implement responsive AppShell, System Mast, Route Index, and Coordinate Rail.
5. Implement home console and Command Deck.
6. Implement Signal Timeline, streaming output, failures, retry, and scroll behavior.
7. Implement settings ledger and provider registry/editor.
8. Implement authentication, session expiration, and guest disclosure.
9. Implement voice route using real analyser input and explicit failure states.
10. Implement Memory Ledger and user control flows.
11. Implement PWA shell, offline fallback, reconnect lifecycle, and update handling.
12. Perform low-data, accessibility, keyboard viewport, performance, and device passes.

## 29. Required UI verification

Before visual foundation approval, verify:

- 320px Android viewport.
- 360px and 412px common Android viewports.
- Mobile portrait and landscape.
- Tablet portrait and landscape.
- 960px and large desktop layouts.
- Software keyboard open and closed.
- Safe-area behavior in standalone PWA mode.
- Route navigation by keyboard and screen reader.
- Reduced-motion system preference.
- Low-data mode independent of reduced motion.
- Core fixtures for booting, offline, connecting, online, listening, thinking, speaking, and error.
- Invalid Core transitions are rejected.
- Network loss from listening, thinking, and speaking.
- Provider test success, failure, cancellation, and timeout.
- Missing AI, STT, and TTS provider states.
- Streaming with the user scrolled away from the bottom.
- Large messages, Unicode, emoji, code, and long unbroken identifiers.
- Microphone permission denial and audio output interruption.
- Guest-to-account conversion.
- Session expiration with an unsent draft.
- Offline shell without pretending AI is available.

## 30. Definition of visual success

The Signal Spine system is successful only when:

- The Core appears to be a real state instrument rather than a decorative orb.
- The Core, conversation, voice, and system state form one coherent hierarchy.
- The main screen is recognizable without using familiar chatbot bubbles or dashboard cards.
- Settings and provider management remain dense enough for real configuration while still belonging to the same visual language.
- Mobile operation feels native to the available space and is not a scaled desktop page.
- Every transient state terminates safely.
- Reduced-motion and low-data experiences remain complete, legible, and intentional.
- Accessibility is apparent in actual keyboard, screen-reader, contrast, caption, and focus testing.
- Empty space, restrained glow, and ruled structure produce a precise intelligent-console identity without copying existing fictional interfaces.
