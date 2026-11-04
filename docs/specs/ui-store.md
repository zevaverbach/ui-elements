# Spec: ui-store, ui-each and the outlet helper

Status: implemented. This is the spec as built; deviations from the original brief are listed under Decisions.

## Purpose

`<ui-store>` is a non-visual custom element that declares named, observable, optionally persistent JSON state. It lets an agent declare state in HTML the same way it declares UI. `<ui-each>` renders a child component per item of a store's array. A small shared helper swaps the outlet safely. Background: [`../state-and-shell.md`](../state-and-shell.md).

## Files

| File | Role |
|---|---|
| `components/_shared/store-registry.js` | module-level registry and API (no DOM rendering) |
| `components/ui-store.js` | the element |
| `components/ui-each.js` | the repeater |
| `components/_shared/outlet.js` | `swapOutlet()`, `sanitizeHtml()`, `sanitizeFragment()` |
| `components/ui-chat-panel.js` | gained an optional `store` binding |
| `demo/shell.html` | the stable-shell demo |
| `demo/sanitizer-test.html`, `demo/store-test.html` | assertion pages (no framework; open over http, title shows `PASS (n)`) |

## Registry (`store-registry.js`)

- One shared state object (a `Symbol.for` slot on `globalThis`, so two copies of the module still share it). Store record: `{name, data, version, persist, key, dirty, ready}`; subscribers are kept in a separate name-keyed map.
- API: `ensureStore(name, {persist, key, version, seed, src})` creates the record if absent and returns it; if present it returns the existing record and ignores the seed. `getStore(name)`, `get(name, path)`, `set(name, path, value)`, `subscribe(name, fn)` returning an unsubscribe function, `dispatch(name, action, payload)`.
- Subscribing to a store that does not exist yet is allowed; subscribers are notified when it is created.
- Paths are dot paths into the JSON (`"items"`, `"settings.theme"`); empty path = root. Numeric segments index arrays.
- Values are JSON-serializable (they are JSON round-tripped on `set`, which decouples callers from stored objects); `undefined` deletes the key. Updates replace the changed branch (copy-on-write along the path); untouched branches keep their identity. Subscribers run once per microtask batch with `{name, path, paths, data}` (`path` is `""` when several paths changed).
- One document-level `ui-action` listener is installed on first import. A `pagehide`/`visibilitychange` listener flushes pending persistence.

## `<ui-store>`

| Attribute | Meaning |
|---|---|
| `name` (required) | store name; missing → `console.warn`, nothing else happens |
| `persist` | `none` (default), `local`, `session`. Key is `ui-store:<name>` unless `key` is given |
| `version` | default `"1"`; stored value is `{v, data}`; a different stored `v` is ignored and the seed used |
| `src` | URL fetched as JSON seed on first creation; failure is a warning |
| inline seed | child `<script type="application/json">` |

Seed precedence: persisted data, then `src`, then inline seed. A seed is used only when no record with that name exists.

Behavior: hidden (`display: none`), no shadow DOM. `connectedCallback` attaches to the named record, creating it if needed; `disconnectedCallback` never deletes data. Two elements with the same name share one record (the first creates it; a later element asking for a different non-`none` `persist` triggers a warning). Property `data`; methods `get(path)`, `set(path, value)`, `act(action, payload)`. Events on the element while connected (bubble, composed): `ui-store-ready` `{name, data}` once after hydration, and `ui-store-change` `{name, path, data}` after every change. Persistence writes are debounced (~200 ms) and wrapped in try/catch; if storage is unavailable or full, the store continues in memory and warns once.

## Actions

Components request changes with a bubbling, composed `ui-action` event: `detail {store, action, payload}`. The registry's document-level listener routes it **by store name**, so a sender inside the outlet reaches a store in the shell. Actions can also be called with `dispatch()` or `act()`. They operate on the array of objects at `payload.path` (default `"items"`); items are identified by `id`.

| Action | Payload | Effect |
|---|---|---|
| `add` | `{item, index?}` | assigns `id` via `crypto.randomUUID()` if missing |
| `remove` | `{id}` | |
| `update` | `{id, patch}` | shallow merge |
| `toggle` | `{id, field}` | flips a boolean |
| `move` | `{id, toIndex}` | item ends at `toIndex` |
| `set` | `{path, value}` | set any path |
| `clear` | `{}` | empties the array |

Unknown store or action: warns and returns `false`.

## `<ui-each>`

Attributes: `store`, `path` (default `items`), `tag`, `map` (JSON child attribute → item field), `key` (default `id`), `events` (JSON child event → action), `where` (optional JSON equality filter), `id` (give it a stable one).

- Renders children into its own light DOM with `display: contents`.
- Reconciles by key: reuses existing child elements, updates changed attributes, preserves order (moving only elements that are out of place, because moving drops focus), removes stale children.
- Child ids are `<ui-each id>-<key>`; children also get `data-each-key`.
- `map`: `true` sets a boolean attribute, `false`/`null`/`undefined` removes it, anything else is stringified.
- `events`: `{"<child event>": {"action", "field"?, "patch"?, "toIndex"?}}`. Strings starting `$detail.` are read from `event.detail`. The payload `id` is always the item's id. For `move`, `toIndex` defaults to `event.detail.to` and, in a filtered view, is translated to a position in the full array. Listeners sit on `window` (bubble phase), so a cancelable event that any listener on its path cancelled (for example a vetoed `ui-delete`) dispatches nothing.

Event shapes it relies on (from `ui-todo-item`): `ui-toggle {checked, progress}`, `ui-edit {text, previousText}`, `ui-delete {text}` (cancelable), `ui-reorder {from, to}`, `ui-progress {progress}`, `ui-transcript {text, final, value}`.

## `ui-chat-panel` store binding

Optional `store` (and `store-path`, default `messages`). Messages render from the store; sending dispatches `ui-action` `add` with `{role: "user", text}` instead of echoing locally. `ui-send` still fires first and can still be cancelled. Every new code path is gated on the `store` attribute, so the standalone panel is unchanged.

## `swapOutlet(html, {outlet = "#outlet", allowedTags})`

1. Sanitize into an inert `<template>` fragment (no scripts run, no images load).
2. Snapshot typed text of id'd inputs/textareas and every id'd scroll offset.
3. Morph the outlet's children with Idiomorph (`idiomorph@0.8.0`, dynamic import from jsDelivr; fallback to `replaceChildren` with a warning). `ignoreActiveValue` keeps the focused field's text; Idiomorph restores focus and selection.
4. Restore the snapshot (an input is only restored if the agent did not change its default `value` attribute).

Morph callbacks: an existing `<ui-each>` keeps its rendered children (its attributes are synced from the new markup and it re-renders from the store); the transient `editing` attribute of `ui-todo-item` is never removed by a morph.

Sanitizer (`sanitizeFragment`, `sanitizeHtml`): drops `script iframe object embed style link meta base svg math form template noscript title` with their contents; unwraps other unknown tags (text survives); removes comments; removes all `on*` attributes, `srcdoc`, `is`; removes `javascript:`/`vbscript:`/`data:` URLs (`data:image/png|gif|jpeg|webp` allowed) in `href src action formaction xlink:href data poster background cite srcset`. Custom elements: only tags in `components.json` (`allowedTags`), or any `ui-*` tag when no list is given. Exception: `<script type="application/json">` directly inside `<ui-store>` is kept with only its `type` attribute. `sanitizeHtml` runs two passes so re-parsing its output cannot reveal anything new.

## Acceptance criteria and how they are met

1. `demo/shell.html` has `<ui-store name="todos" persist="local">`, `<ui-chat-panel>` and `<main id="outlet">`; buttons swap single column / two columns / open-only; to-dos, focus, caret and scroll survive; reload keeps data. Verified in headless Chromium (Playwright).
2. Removing and re-adding a `<ui-store>` keeps data: `demo/store-test.html`, and the shell's button.
3. A `ui-action` from inside the outlet reaches a shell store: `demo/store-test.html`.
4. `demo/sanitizer-test.html`: 36 assertions.
5. `components.json` has `ui-store` and `ui-each` (attributes, events, actions, composes-with); `node scripts/check-catalog.mjs` passes.
6. Standalone `ui-todo-item` / `ui-chat-panel` behavior re-checked and unchanged.
7. No build step; the only new external dependency is Idiomorph, imported inside `outlet.js`.

## Follow-ups

- A declarative action trigger (for example `<ui-action-button store action payload>`), so swapped HTML can say "add an item from this input" without shell script.
- Restrict `ui-store src` to same-origin or an allowlist when the HTML is agent-generated.
- Server sync for `persist` (hook already exists: `ui-store-change`).
- Optional `ui-chat-panel` message ids so replies can update a message in place.
- Cross-browser runs (Firefox, WebKit/iOS) of `demo/*-test.html` and the shell scenario.

## Decisions

1. **Repo conventions beat the spec; no conflicts found.** All files follow the existing ES-module, self-registering, header-comment, catalog conventions.
2. **Allowlist from the catalog.** `swapOutlet` fetches `components.json` (relative to `outlet.js`, so it works from jsDelivr) and allows only the listed tags; if the fetch fails it allows any `ui-*` tag. Consequence found during testing: a new component must be in `components.json` before an agent can use it in swapped HTML. `check-catalog.mjs` already enforces catalog completeness.
3. **JSON seed exception.** The brief says to strip `<script>`, but a `<ui-store>` seed is a script element. Only `type="application/json"` directly inside `ui-store` is kept (inert, non-executing, only `type` attribute kept).
4. **Stricter sanitizer than listed.** Also drops `style link meta base svg math form template noscript title`, `srcdoc` and `is`, and non-image `data:` URLs. Unknown plain tags are unwrapped rather than deleted. DOM clobbering via `id`/`name` is not handled.
5. **Morph input is DOM nodes, not a string,** so sanitized markup is never re-serialized and re-parsed (mutation XSS). `sanitizeHtml` (string) does two passes for the same reason.
6. **Idiomorph 0.8.0** (the latest on jsDelivr when written; ESM at `dist/idiomorph.esm.js`, `export {Idiomorph}`, API checked against the source).
7. **`<ui-each>` special case in the morph.** The agent's `<ui-each>` is empty; without the special case the morph would delete its rendered children. Its attributes are synced instead and it re-renders from the store.
8. **Snapshot/restore around the morph** (typed text of id'd unfocused inputs, id'd scroll offsets). Added because testing showed Idiomorph resets unfocused inputs to the new HTML's value and that scroll can be lost when elements are briefly detached.
9. **`editing` is protected** on `ui-todo-item`, so a swap does not cancel an open edit.
10. **Additions to `ui-each` beyond the brief:** `where` (needed for a real "filtered view" and a two-column open/done layout) and `$detail.` templating in `events` (needed to map `ui-edit` to an `update` patch). Reorders in a filtered view are translated to full-array positions.
11. **`ui-each` listens on `window`** so page-level `preventDefault()` on `ui-delete` is honored before the action is dispatched.
12. **Registry record has no `listeners` field.** Subscribers live in a separate name-keyed map so they can exist before the store does. The record carries `dirty` (changed since creation, so a late `src` fetch does not clobber edits) and `ready` (hydration promise).
13. **Notification timing.** Subscribers that connected before a store existed are notified at creation; a `src` seed that replaces data notifies as a change; neither schedules a persistence write.
14. **Persist conflict warning** is raised only when a later element asks for a different persist mode other than the default `none`, so plain handles for an existing store stay quiet.
15. **`ui-chat-panel` store binding was implemented** (judged low-risk: every branch is gated on the attribute). It re-renders the whole message list on each change.
16. **The demo's "add" field is wired in the shell script,** because swapped HTML may not contain script. This is a real level-1 limitation, recorded as a follow-up.
17. **`check-catalog.mjs` extended:** scans every `demo/*.html` for component loads/usages and requires every `_shared` file to be listed in `catalog.shared`.
18. **Version.** `components.json` says `0.2.0-dev`; no tag was created. Existing pinned `v0.1.0` URLs in the docs stay valid for the two original components.
