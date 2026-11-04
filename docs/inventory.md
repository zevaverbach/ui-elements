# Inventory of existing UIs

Source material found on this machine (read-only references; nothing was modified, no secrets, keys or backend URLs were copied). Searched: `~/repos` and every subdirectory, `~` (one level up) and its subdirectories (`media-ext`, `srv`, `git`, …).

| UI | Location | Kind |
|---|---|---|
| Beelink Chat | `home-server-migration/media-server/chat-server.py` (HTML/CSS/JS embedded in the `PAGE` string) | chat |
| Day Stack | `daystack/day-stack.html` | task list ("blocks" with progress) |
| STT bench / live dictation | `stt/index.html`, `stt/client/live-dictation.js` | speech-to-text (server-side Deepgram, not Web Speech) |

Other UIs found (`bbq/ui`, `health/web`, `learnharness`) are app-specific and have neither a task list nor a chat to extract.

## Honest gap

Neither the Day Stack nor the STT code uses drag-and-drop or the Web Speech API (`grep` for `draggable`, `dragstart`, `SpeechRecognition` finds nothing outside unrelated vendored code). The required drag-and-drop reordering and Web Speech microphone are therefore **new behavior specified by the brief**, not extracted behavior. They are built to the source UIs' conventions (see below), and marked "new" in the tables.

## 1. Beelink Chat

| Pattern | What the source does | Extract? |
|---|---|---|
| Message roles | `.msg.user` right-aligned accent bubble, `.msg.agent` left surface bubble with border, `.msg.error` red-tinted bubble; `white-space: pre-wrap`; 80% max width (90% on phones) | **Yes** → `ui-chat-panel` bubble styles, roles `user` / `agent` / `error` |
| Composer | `<textarea rows=1>` + Send button; **Enter sends, Shift+Enter inserts newline** | **Yes** (also ignore Enter during IME composition) |
| Send disabled while busy | Send button disabled while a job runs for the viewed chat | **Yes** → `busy` attribute disables Send |
| Pending indicator | A "Thinking..." bubble (`.msg.pending`, grey italic) shown while the agent works | **Yes** → `busy` shows a pending bubble (`busy-text`) |
| Auto-scroll | `log.scrollTop = log.scrollHeight` after each message | **Yes** |
| Slide-in sidebar | On phones the sidebar is `position: fixed`, `transform: translateX(-100%)` → `translateX(0)` with `transition .2s`; `#overlay` scrim closes it on tap; `toggleSidebar(force)` | **Yes** → `open` attribute, `toggle(force)`, optional `backdrop` scrim |
| Composer focus rule | `focusComposer()` focuses the box on open **except** on `(pointer: coarse)` so the on-screen keyboard doesn't cover the log | **Yes** → focus input on open unless coarse pointer |
| Safe-area padding | `env(safe-area-inset-bottom)` in the input row | **Yes** |
| Per-chat drafts, session list, archive, job polling, spend footer, push links | Backend- and app-specific | No (the panel must not assume a backend; the host app owns sessions) |
| Escaping | `escapeHtml` before `innerHTML` | Replaced by `textContent` everywhere; no HTML injection path |
| Dark GitHub-like palette | `#0f1117`, `#161b22`, `#30363d`, `#1f6feb` | **Yes** → default values in `tokens.css` |

## 2. Day Stack (task list)

| Pattern | What the source does | Extract? |
|---|---|---|
| Task model | `{id, text, size, progress, done}`; `done` also stamps `doneAt` | **Yes** → `text`, `checked`, `progress` attributes |
| Complete / restore | Completing sets `progress = 100`; restoring a cleared task sets `progress = 75`, not 0 | **Yes** → checking sets progress 100, unchecking from 100 sets 75 (only when `progress` is in use) |
| Progress steps | Four step buttons set 25 / 50 / 75 %; the 100 % step completes; clicking the active step steps back one (`i*25`); each button has `aria-label="Set N percent"` | **Yes** → optional `progress` attribute renders the steps |
| Armed (two-step) delete | First click on ✕ arms it ("✕?", reverts after 2.6 s); second click deletes; `aria-label="Delete <text>"` | **Yes** → delete needs confirm unless `no-confirm` |
| Size eyebrow | Small caps label above the text (`Small`, `Medium`, …) | **Yes**, generalised to a free-form `label` attribute |
| Enter submits, Escape closes | Sheet inputs submit on Enter | **Yes** → edit commits on Enter/blur, cancels on Escape |
| `prefers-reduced-motion` | `matchMedia('(prefers-reduced-motion: reduce)')` plus a CSS override that zeroes durations | **Yes** → shared `reducedMotion()`; all transitions respect it |
| `aria-label`s on icon buttons | "Delete …", "Clear …", "Toggle sound" | **Yes** |
| FLIP animation on re-order/remove | Capture rects, render, animate delta | **Idea reused** for the reorder animation (siblings slide to make room), implemented with transforms |
| Optimistic store + queue, KV sync, streak, sound effects, outcome pill, idle check-in, 2D tile packing | App-specific | No |
| Colourful "Bungee"/grape theme, Google Fonts | Brand-specific | No (neutral tokens instead; no web-font dependency) |

## 3. STT bench

| Pattern | What the source does | Extract? |
|---|---|---|
| Mic button → transcript text | Press mic, receive cleaned text, put it in the field | **Pattern only.** Source streams audio to a paid backend through `MediaRecorder` + a token endpoint. The brief requires the browser's Web Speech API and no backend, so only the interaction shape (mic toggle → transcript → event) is reused. `getUserMedia`/token code is **not** copied. |

## Extraction plan

| Component | Source patterns | New (from the brief) |
|---|---|---|
| `ui-todo-item` | task model, complete/restore, progress steps, armed delete, eyebrow label, Enter/Escape, reduced motion, aria-labels | Web Speech mic (feature-detected, hidden if unsupported), pointer/touch/keyboard drag-reorder, inline edit |
| `ui-chat-panel` | roles, composer keys, busy/pending, autoscroll, slide + scrim, coarse-pointer focus rule, safe-area padding | `ui-send` event, `messages` property, slots, no backend |

Shared modules (`components/_shared/`), each needed by more than one component or too large to inline:

- `util.js`: `emit` (bubbling, composed `CustomEvent`), `define`, `reducedMotion`, `coarsePointer`, `uid`
- `base.js`: the token-reading base stylesheet (`--_*` internal variables with fallbacks) and a `sheet()` helper
- `speech.js`: Web Speech wrapper (`speechSupported`, `createDictation`)
- `reorder.js`: pointer/touch/keyboard reorder engine used by `ui-todo-item`

No third component is needed: the mic, delete, edit and handle controls are small native `<button>`s inside the item's shadow root, and a plain `<div>`/`<ul>` is a sufficient list container.
