# Tests

A real-browser test suite for the components, the state/shell features, the sanitizer, the CDN consumption path and agent-composed pages. Every browser test is **recorded as an animated GIF with on-screen step captions**; every failure writes a **failure bundle** that people and agents can read.

Dev-only: nothing here is loaded by consumers, and the library itself stays build-free. The tooling is Python + Playwright + ffmpeg (the same stack as `scripts/capture-media.py`); Node (>= 18, no packages) runs the catalog check. There is no `package.json` and no npm install.

## Run

```sh
pip install playwright && playwright install chromium     # once; ffmpeg and node must be on PATH
python3 tests/run.py                                       # everything, headless  (about 80 s)
```

| Command | What it does |
|---|---|
| `python3 tests/run.py --suite todo-item` | one suite (repeatable) |
| `python3 tests/run.py -k reorder` | tests whose name contains the text |
| `python3 tests/run.py --list` | list tests (`[online]` marks the ones that need the internet) |
| `python3 tests/run.py --gifs` | also (re)write `tests/media/<suite>-<test>.gif` for **passing** tests |
| `python3 tests/run.py --headed --slow` | watch the browser |
| `python3 tests/run.py --no-online` | skip the checks that need the internet |
| `python3 tests/run.py --table` | print the recordings table below (paste into this README) |
| `node scripts/check-catalog.mjs` | suite A alone (no browser) |
| `python3 tests/agent-evals/run_evals.py --outputs DIR` | score a folder of agent outputs ([details](agent-evals/README.md)) |

Exit code is 1 if any test fails. Tests are headless and offline: all requests that leave localhost are blocked, except the two clearly marked online checks (`consume-online-real-jsdelivr`, `visual-axe-accessibility`), which skip themselves when offline. The pinned [Idiomorph](https://github.com/bigskysoftware/idiomorph) build that `swapOutlet` imports is fetched once into `tests/.cache/` (gitignored) and served to the pages from there; without the cache and without internet the shell tests report "skipped" with that reason.

## Suites

| Suite | Checks | Why |
|---|---|---|
| **A. catalog** (`catalog-integrity`) | `components.json` parses; every component file has an entry, a header and a demo; every attribute, event, slot, method, property, part, CSS custom property and store action in the **source** matches the catalog and the file header, in both directions, with a diff when they disagree | agents trust the catalog instead of reading source; drift makes them write wrong HTML |
| **B. `todo-item`, `chat-panel`** | attributes and properties, event names and `detail` shapes (and that they bubble and are composed), keyboard behavior, roles/labels/focus order. todo-item: toggle, progress steps, inline edit, confirm-delete including a vetoed cancelable `ui-delete`, mouse drag, keyboard and **touch** reorder, speech-to-text with a **mocked SpeechRecognition** (and the mic hidden when the API is missing). chat-panel: open/close, focus return, backdrop, all three sides, `ui-send` (cancelable, Shift+Enter), `addMessage`/`messages`, busy, `prefers-reduced-motion`, store binding | the contract of each element, in a real browser |
| **C. `state`** | on `demo/shell.html`: swapping the outlet keeps the to-do items, **focus and caret** in an input with a stable id, typed text, scroll position and an open inline edit; removing and re-adding `<ui-store>` keeps data; `persist="local"` survives reload (and a schema version bump re-seeds); a `ui-action` from inside the outlet reaches a store in the shell; filtered views; chat history | the point of the stable shell |
| **D. `sanitizer`** | 51 table-driven cases (script/iframe/object/embed, `on*` in every spelling, `javascript:` URLs with case/whitespace/entity tricks, nested and malformed markup, mXSS patterns) run through `sanitizeHtml`, then **inserted into a live page** to prove nothing executes; `ui-*` and layout tags survive; output is idempotent | swapped HTML is untrusted |
| **E. `consume`** | a blank page on one origin imports components from a second origin that mimics the jsDelivr layout (`/gh/<user>/<repo>@<ref>/<path>`, CORS): relative `./_shared/*.js` imports work, every catalog module loads, `swapOutlet` finds `components.json` relative to itself; plus one online check against real jsDelivr (skips when offline or the tag does not exist) | proves the no-build, CDN-only promise |
| **F. `agent-evals`** | tasks, golden solutions and a checker (tags, attributes, script rules, wiring, console errors, task assertions). The goldens must pass; 23 kinds of bad output must be rejected with the right code, including inline script on the one task no component can do, where the right answer is a written request for a new component | lets you measure agents without an LLM in the repo; see [agent-evals/README.md](agent-evals/README.md) |
| **G. `visual`, `demo-pages`** | light/dark screenshots of every demo page (background luminance, no horizontal overflow, non-blank, light != dark), an axe-core pass (online), and the framework-free assertion pages `demo/sanitizer-test.html` and `demo/store-test.html` | catches theming and accessibility regressions |

## Recordings

Each recording is the test's own run: the caption at the bottom is the current step, the red dot is the pointer, the badge in the corner is the key being pressed. Only **passing** runs are kept.

#### agent-evals

<details><summary>8 recorded tests</summary>

| Test | What the recording shows | Recording |
|---|---|---|
| `golden-shopping-list` | Task: … → Verdict:  | ![agent-evals-golden-shopping-list](media/agent-evals-golden-shopping-list.gif) |
| `golden-todo-progress` | Task: … → Verdict:  | ![agent-evals-golden-todo-progress](media/agent-evals-golden-todo-progress.gif) |
| `golden-chat-left` | Task: … → Verdict:  | ![agent-evals-golden-chat-left](media/agent-evals-golden-chat-left.gif) |
| `golden-kanban` | Task: … → Verdict:  | ![agent-evals-golden-kanban](media/agent-evals-golden-kanban.gif) |
| `golden-needs-new-behavior-is-a-request` | Task:  → Correct output: a written request for a new component, no script → Verdict: PASS (the request names a new tag, attributes, events and why nothing existing fits) | ![agent-evals-golden-needs-new-behavior-is-a-request](media/agent-evals-golden-needs-new-behavior-is-a-request.gif) |
| `checker-rejects-bad-output` | […/…] bad output: … -> expect […] → Result:  | ![agent-evals-checker-rejects-bad-output](media/agent-evals-checker-rejects-bad-output.gif) |
| `checker-rejects-cheating-on-the-impossible-task` | Bad output: … -> expect […] | ![agent-evals-checker-rejects-cheating-on-the-impossible-task](media/agent-evals-checker-rejects-cheating-on-the-impossible-task.gif) |
| `cli-and-aggregate-scoring` | check.py works as a command → run_evals.py scores a folder of outputs and aggregates the metrics | (no GIF) |

</details>

#### chat-panel

<details><summary>9 recorded tests</summary>

| Test | What the recording shows | Recording |
|---|---|---|
| `open-close` | Closed: the panel is off screen, hidden and inert → toggle() opens it and returns the new state → Opening focuses the composer (non-touch device) → Escape closes it and returns focus to the opener → … | ![chat-panel-open-close](media/chat-panel-open-close.gif) |
| `backdrop` | `backdrop` shows a scrim while open → Clicking the scrim closes the panel | ![chat-panel-backdrop](media/chat-panel-backdrop.gif) |
| `sides` | side: … | ![chat-panel-sides](media/chat-panel-sides.gif) |
| `send-and-messages` | Slotted messages (data-role) are shown → Type a message and press Enter → Shift+Enter inserts a newline instead of sending → Empty or whitespace-only input sends nothing → … | ![chat-panel-send-and-messages](media/chat-panel-send-and-messages.gif) |
| `busy-and-no-echo` | `no-echo`: sending does not add a user bubble → `busy` shows a pending bubble and disables Send → `busy-text` customises the pending bubble → Clearing `busy` re-enables Send | ![chat-panel-busy-and-no-echo](media/chat-panel-busy-and-no-echo.gif) |
| `reduced-motion` | prefers-reduced-motion: reduce, so the slide has no real duration → The panel is fully on screen immediately after opening | ![chat-panel-reduced-motion](media/chat-panel-reduced-motion.gif) |
| `slide-animation` | Without a reduced-motion preference the panel animates (~250ms) → --ui-chat-panel-duration changes the speed | ![chat-panel-slide-animation](media/chat-panel-slide-animation.gif) |
| `accessibility` | Roles and labels → While closed, Tab skips the panel entirely → Open: Tab order is close, log, composer, send | ![chat-panel-accessibility](media/chat-panel-accessibility.gif) |
| `store-binding` | With `store`, messages render from the store → Sending dispatches a ui-action add instead of echoing → A store change from elsewhere shows up in the panel | ![chat-panel-store-binding](media/chat-panel-store-binding.gif) |

</details>

#### consume

<details><summary>4 recorded tests</summary>

| Test | What the recording shows | Recording |
|---|---|---|
| `cdn-layout-and-relative-imports` | Blank page imports components by a jsDelivr-shaped URL → Both elements are defined and rendered → The relative imports (./_shared/*.js) were fetched from the same CDN-style path → The component works: tick the box, get a ui-toggle event → … | ![consume-cdn-layout-and-relative-imports](media/consume-cdn-layout-and-relative-imports.gif) |
| `catalog-matches-loaded-modules` | Fetch components.json from the CDN path and load every module it lists → All … catalog tags are defined:  | ![consume-catalog-matches-loaded-modules](media/consume-catalog-matches-loaded-modules.gif) |
| `swap-outlet-from-the-cdn-path` | Import swapOutlet from the CDN-style path and swap an outlet | ![consume-swap-outlet-from-the-cdn-path](media/consume-swap-outlet-from-the-cdn-path.gif) |
| `online-real-jsdelivr` (online) | HEAD … → The real CDN serves the module and its _shared imports | ![consume-online-real-jsdelivr](media/consume-online-real-jsdelivr.gif) |

</details>

#### demo-pages

<details><summary>2 recorded tests</summary>

| Test | What the recording shows | Recording |
|---|---|---|
| `sanitizer-assertions` |  | ![demo-pages-sanitizer-assertions](media/demo-pages-sanitizer-assertions.gif) |
| `store-assertions` |  | ![demo-pages-store-assertions](media/demo-pages-store-assertions.gif) |

</details>

#### sanitizer

<details><summary>2 recorded tests</summary>

| Test | What the recording shows | Recording |
|---|---|---|
| `table-driven` | … cases: dangerous markup removed, ui-* and layout tags kept → […/…] … → Result:  | ![sanitizer-table-driven](media/sanitizer-table-driven.gif) |
| `allowlist-comes-from-the-catalog` | swapOutlet only allows tags listed in components.json → swapOutlet rejects a missing outlet with a clear error | ![sanitizer-allowlist-comes-from-the-catalog](media/sanitizer-allowlist-comes-from-the-catalog.gif) |

</details>

#### state

<details><summary>10 recorded tests</summary>

| Test | What the recording shows | Recording |
|---|---|---|
| `swap-keeps-focus-caret-and-text` | Type half a sentence in the stable-id input → Swap the outlet to: … → Nothing was lost: still 10 to-dos in the store | ![state-swap-keeps-focus-caret-and-text](media/state-swap-keeps-focus-caret-and-text.gif) |
| `swap-keeps-scroll-position` | Scroll the outlet → Swap in new markup (adds a paragraph above the list) | ![state-swap-keeps-scroll-position](media/state-swap-keeps-scroll-position.gif) |
| `swap-keeps-component-instances` | Open an inline edit in one row → Swap layouts: same element instance, edit still open → Finish the edit: it lands in the store | ![state-swap-keeps-component-instances](media/state-swap-keeps-component-instances.gif) |
| `filtered-view-and-two-columns` | Open-only view shows just the open to-dos → Two columns: open on the left, done on the right → Tick an open item: it moves to the done column | ![state-filtered-view-and-two-columns](media/state-filtered-view-and-two-columns.gif) |
| `action-from-outlet-reaches-shell-store` | The store lives in the shell, outside #outlet → Tick a row inside the outlet → Rename and delete go through actions too | ![state-action-from-outlet-reaches-shell-store](media/state-action-from-outlet-reaches-shell-store.gif) |
| `add-and-reorder-update-the-store` | Add a to-do through the shell's input → Reorder with the keyboard: the store follows | ![state-add-and-reorder-update-the-store](media/state-add-and-reorder-update-the-store.gif) |
| `store-element-remove-and-readd` | Remove the <ui-store> element from the page → The data is still there (and still rendered) → Change data while the element is gone, then re-add it | ![state-store-element-remove-and-readd](media/state-store-element-remove-and-readd.gif) |
| `persist-local-survives-reload` | Change the data: tick one, add one → Reload the page → Everything is back: items, order, ticked state → A different schema version ignores stored data and re-seeds | ![state-persist-local-survives-reload](media/state-persist-local-survives-reload.gif) |
| `chat-panel-in-the-shell` | Open the shell's chat panel (it persists across swaps) → Swap the outlet: the conversation is untouched → Reload: the chat history persists too | ![state-chat-panel-in-the-shell](media/state-chat-panel-in-the-shell.gif) |
| `outlet-never-swaps-the-shell` | Hostile markup is swapped in → The shell (chat panel, store element) is untouched | ![state-outlet-never-swaps-the-shell](media/state-outlet-never-swaps-the-shell.gif) |

</details>

#### todo-item

<details><summary>13 recorded tests</summary>

| Test | What the recording shows | Recording |
|---|---|---|
| `attributes-and-properties` | Attribute `text` renders, property `text` reflects → `checked` attribute and property → `label` shows an eyebrow, `progress` shows steps → `editing` attribute opens the edit field → … | ![todo-item-attributes-and-properties](media/todo-item-attributes-and-properties.gif) |
| `toggle` | Tick the checkbox → The text is struck through → Untick it | ![todo-item-toggle](media/todo-item-toggle.gif) |
| `progress-steps` | Click the 50% step → Click the active step again: steps back one → Click 100%: the item completes → Untick: progress restores to 75, not 0 | ![todo-item-progress-steps](media/todo-item-progress-steps.gif) |
| `inline-edit` | Double-click the text to edit → Type a new value and press Enter → Escape cancels an edit → An empty value is not saved → … | ![todo-item-inline-edit](media/todo-item-inline-edit.gif) |
| `edit-field-is-focused-immediately` | startEdit() focuses the edit field in the same task (no keystroke can be lost) → Typing straight after the click lands in the field → Same when `editing` is set as an attribute | ![todo-item-edit-field-is-focused-immediately](media/todo-item-edit-field-is-focused-immediately.gif) |
| `confirm-delete` | First click arms the delete button (nothing is deleted) → The armed state expires on its own → A vetoed (preventDefault) ui-delete keeps the item → Click twice to delete for real → … | ![todo-item-confirm-delete](media/todo-item-confirm-delete.gif) |
| `drag-reorder` | Drag Alpha's grip below Charlie with the mouse → Drag it back to the top | ![todo-item-drag-reorder](media/todo-item-drag-reorder.gif) |
| `keyboard-reorder` | Focus Alpha's grip and press Space to grab → ArrowDown twice moves it → Space drops it → Escape cancels a grab → … | ![todo-item-keyboard-reorder](media/todo-item-keyboard-reorder.gif) |
| `touch-reorder` | Touch-drag Alpha's grip down past Bravo → The grip opts out of touch scrolling (touch-action: none) | ![todo-item-touch-reorder](media/todo-item-touch-reorder.gif) |
| `speech-to-text` | The mic button is visible when SpeechRecognition exists → Click the mic: edit mode opens and listening starts → An interim result emits ui-transcript but does not change the field → A final result is appended to the field → … | ![todo-item-speech-to-text](media/todo-item-speech-to-text.gif) |
| `speech-unsupported` | Without the Web Speech API the mic button is hidden → The rest of the item still works | ![todo-item-speech-unsupported](media/todo-item-speech-unsupported.gif) |
| `speech-opt-out` | `no-speech` hides the mic even when the API exists | ![todo-item-speech-opt-out](media/todo-item-speech-opt-out.gif) |
| `accessibility` | Every control has an accessible name → Tab order: grip, checkbox, steps, mic, edit, delete | ![todo-item-accessibility](media/todo-item-accessibility.gif) |

</details>

#### visual

<details><summary>2 recorded tests</summary>

| Test | What the recording shows | Recording |
|---|---|---|
| `demo-pages-light-and-dark` | …: … mode | ![visual-demo-pages-light-and-dark](media/visual-demo-pages-light-and-dark.gif) |
| `axe-accessibility` (online) | axe-core on … | ![visual-axe-accessibility](media/visual-axe-accessibility.gif) |

</details>

Regenerate: `python3 tests/run.py --gifs` (about 5 minutes), then `python3 tests/run.py --table` and paste. A failing test never overwrites its committed GIF. GIFs are produced with ffmpeg's two-pass `palettegen`/`paletteuse`, about 8 fps (the ladder steps down from there), at most 640 px wide, from the first caption to just after the last (idle time trimmed, 18 s cap).

**Media budget:** each GIF under 1.5 MB and `tests/media/` under 15 MB in total. `kit/video_to_gif.py` steps down fps, width and palette size until a GIF fits and refuses to write one that does not; `run.py` fails the run if the folder goes over 15 MB. Currently: 12.3 MB in 49 GIFs, largest 1208 KB.

## Failure bundles

A failing test writes `tests/failures/<suite>-<test>/` (gitignored; CI uploads it as an artifact):

| File | For | Contents |
|---|---|---|
| `failure.gif` | people | the run as an animation |
| `filmstrip.png` | agents | contact sheet of ~8 labelled key frames, including the last |
| `report.json` | agents | test name, **failing step**, error + traceback, console errors, page URL, the **catalog entry** of the component under test, a trimmed shadow-DOM-aware **DOM snapshot** around the failing element, all steps |
| `console.log` | both | every console message and page error with timestamps |

Uncaught page errors and unexpected `console.error`s fail a test (a test can declare expected ones with `t.allow_console(...)`). The loop for a person or an agent: run, read `report.json` and `filmstrip.png`, fix, rerun. More in [docs/testing-your-app.md](../docs/testing-your-app.md).

## Reuse the pattern in your own project

[`tests/kit/`](kit/README.md) is a copy-paste kit (caption helper, video-to-GIF, filmstrip, failure-bundle writer, harness, a sample test) that depends on nothing in this repo. This repo's runner is built on it, so it is exercised on every run. [docs/testing-your-app.md](../docs/testing-your-app.md) explains the pattern. [`ci/tests.yml`](ci/tests.yml) is a GitHub Actions workflow to copy.

## Layout

```
tests/
  run.py            runner (servers, discovery, recording, summary)
  registry.py       @test decorator, shared env, mocks (SpeechRecognition), fixture helpers
  helpers.py        focus path, rects, touch drag
  server.py         tiny static server (+ jsDelivr-style layout and in-memory pages)
  pages/fixture.html  blank page that loads every component
  suites/           the suites above
  agent-evals/      tasks, golden solutions, checker, scoring
  kit/              the reusable pieces
  ci/tests.yml      CI workflow template
  media/            committed GIFs (budgeted)     failures/ .cache/ screenshots/  (gitignored)
```

## Known issues and pending

No failing or pending tests. Bugs the suite found while it was being written, each fixed in its own commit with the test that exposed it:

1. **Sanitizer** (`outlet.js`): the parser's internal *is value* survived `removeAttribute('is')`, so `<div is="x">` was still serialized with `is="x"`. Elements carrying `is` are now rebuilt without it. Test: `sanitizer-table-driven`.
2. **Shell demo**: the playground `<textarea>` had `width: 100%` without `box-sizing: border-box` and overflowed the page by 10 px. Test: `visual-demo-pages-light-and-dark`.
3. **Demo page**: the scrollable store-data `<pre>` was not keyboard-focusable (axe `scrollable-region-focusable`, serious). Test: `visual-axe-accessibility`.
4. **`ui-todo-item`**: `startEdit()` focused the edit field in a `requestAnimationFrame`, so keys typed right after clicking Edit could be lost. Test: `todo-item-edit-field-is-focused-immediately`.

Not covered: browsers other than Chromium, real touch hardware and real speech recognition (mocked), and screen-reader output (only roles, labels, focus order and axe).

## Decisions

1. **Tooling: Python Playwright and a stdlib runner, no npm.** The repo already uses Python Playwright and ffmpeg (`scripts/capture-media.py`), both are installed, and they work offline. `@playwright/test` would have meant a `tests/package.json` plus a network install, so it was not added. Node is only used for the existing, dependency-free `scripts/check-catalog.mjs`. There is no pytest either: `run.py` is about 150 lines.
2. **The runner is built on the kit.** `tests/kit/` (caption, GIF, filmstrip, failure bundle, harness) is what `run.py` calls, so the copy-paste kit is exercised on every run. It imports nothing from this repo.
3. **Suite A extends `scripts/check-catalog.mjs`** instead of adding a sibling: the same script now also parses the source (attributes, events, slots, methods, properties, parts, CSS custom properties, store actions) and diffs it against the catalog and the file headers in both directions. Verified by mutation (added an attribute and an event to source, a phantom attribute to the catalog: all reported). `run.py` runs it as `catalog-integrity`.
4. **Offline by default.** Every request that leaves localhost is aborted by a Playwright route. Idiomorph (loaded from jsDelivr by `outlet.js`) is fetched once into `tests/.cache/` and served from there; with neither cache nor internet the shell tests are *skipped with a reason*, not failed. `--no-online` only skips the online checks; it does not stop that one-time fetch.
5. **Two online checks, both auto-skipping.** `consume-online-real-jsdelivr` (tag from `UI_ELEMENTS_TAG`, default `v0.1.0`; skips on HTTP 404 so it does not fail before a tag exists) and `visual-axe-accessibility`. The brief asks for axe-core to be loaded from a CDN, which makes it online too; it is clearly marked and skips offline.
6. **GIFs only with `--gifs`.** Videos are always recorded (a failure needs them) but GIFs are not rewritten on every run: it is slower (a readable on-screen dwell per step) and would churn committed binaries. A failing test never touches its committed GIF; a GIF that cannot fit the budget fails the test instead of being written.
7. **Budget.** Per-GIF limit 1.5 MB, total 15 MB, enforced by `video_to_gif` (steps down fps, width and palette) and by `run.py`. Viewports are small (640x420 to 640x480); GIFs start at the first caption and end just after the last.
8. **Sanitizer is one recorded test with 51 table rows**, not 51 GIFs. Each row is also inserted into a live page to prove nothing executes (payloads set `window.__pwned`), and checked for idempotence.
9. **Consumption uses two servers.** The consumer page is on one port; the library comes from a second port that answers `/gh/<user>/<repo>@<ref>/<path>` with CORS, like jsDelivr. The page is served by the real server, not by a Playwright route: Chromium's private-network-access check blocks a route-fulfilled page from reaching a second loopback origin.
10. **Touch reorder uses Chrome DevTools Protocol touch events** (`Input.dispatchTouchEvent`); Playwright's own touchscreen API only taps.
11. **Visual checks have no pixel baselines.** Baselines are brittle across fonts and OSes. Instead: background luminance for light/dark on the themed pages, no horizontal overflow, non-blank, light differs from dark. Screenshots go to `tests/screenshots/` (gitignored). The two assertion pages are plain unthemed pages, so they only get the overflow and blank checks.
12. **Console errors fail tests.** Uncaught page errors and `console.error` fail the test unless the test lists them with `t.allow_console(...)` (for example the deliberate 404 in the store test).
13. **Agent evals are stricter than the sanitizer.** The checker rejects any inline `<script>` anywhere in a generated page (not just in the outlet), allows `<style>` only outside the outlet, and requires the shell layout (`<main id="outlet">`, stores and chat outside it) for shell tasks. Goldens import from `@main` jsDelivr URLs; the checker serves them from the local checkout. The "needs new behavior" task is a `request` task: the correct output is a markdown request for a new `ui-*` component, checked for a new tag, attributes, events, the missing capability and why existing components are not enough.
14. **CI workflow is a template in `tests/ci/tests.yml`**, not in `.github/workflows/`: the available token has no `workflow` scope, so pushing a workflow file would be rejected.
15. **Failure bundles live in `tests/failures/<suite>-<test>/`** and are gitignored; `report.json` embeds the catalog entry of the component under test (`@test(..., component="ui-todo-item")`) and a DOM snapshot that pierces shadow roots.
