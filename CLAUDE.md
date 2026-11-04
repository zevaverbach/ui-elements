# Conventions for agents working in this repo

## Hard constraints
- Vanilla JavaScript custom elements only. No build step, bundler, TypeScript, or npm install needed to *use* a component.
- One component per file in `components/`, as an ES module that registers itself with `define()` (from `_shared/util.js`, a safe `customElements.define`).
- Third-party dependencies load from a CDN (`cdn.jsdelivr.net` or `esm.sh`) with a pinned version. Never vendor them.
- Style with Shadow DOM plus CSS custom properties. Read tokens through `_shared/base.js` (`--_*` variables with fallbacks) so components render without `tokens.css` and theme without edits.
- Shared logic lives in `components/_shared/`; do not duplicate it between components. Use relative imports (`./_shared/x.js`) so files work from jsDelivr.
- Never commit secrets, keys or backend URLs. Components make no network calls.

## Naming
- Tags: `ui-` prefix, kebab-case (`ui-todo-item`). File name equals tag name.
- Events: `ui-` prefix, kebab-case, always `bubbles: true, composed: true` (use `emit()`). `detail` is a plain object; make cancelable only when the host should be able to veto.
- Attributes: kebab-case; boolean attributes are presence-only; reflect state attributes (`open`, `checked`) with matching properties.
- CSS custom properties: `--ui-<tag-without-ui->-<thing>` (e.g. `--ui-chat-panel-width`), each falling back to a shared `--ui-*` token.

## Accessibility baseline
- Roles and accessible names on every control (icon buttons need `aria-label`); prefer native elements (`button`, `input`, `textarea`).
- Everything operable by keyboard, including drag operations (see `reorder.js`); visible `:focus-visible` outline.
- Announce state changes through a polite/assertive live region where there is no visible change.
- Respect `prefers-reduced-motion`; use `textContent`, never `innerHTML`, for user-supplied strings.
- Feature-detect browser APIs (e.g. Web Speech) and hide the affordance when unsupported.

## Every new or changed component must
1. Document its API in the **file header** (attributes/properties, slots, events with `detail` shapes, CSS custom properties, keyboard behavior). The header starts with `// <tag>`.
2. Update **`components.json`** (tag, file, description, attributes, slots, events, cssCustomProperties, `composes-well-with`) and keep it valid JSON.
3. Be loaded and shown in **`demo/index.html`** (add an example to the live editor presets when it fits).
4. Update `README.md`'s component table, and re-run `scripts/capture-media.py` if the look changed.
5. Pass `node scripts/check-catalog.mjs` and a manual run of the demo served over http.

## State and swappable UIs
Read `docs/state-and-shell.md` (guidance) and `docs/specs/ui-store.md` (spec) before touching `ui-store`, `ui-each`, `_shared/store-registry.js`, `_shared/outlet.js`, or adding a store-bound component.
- Never swap outside the outlet; only `swapOutlet()` replaces page UI at runtime.
- Keep data in stores (`<ui-store>`), not in element fields. A store-bound component renders from the store and sends changes as `ui-action` events (`{store, action, payload}`).
- Store binding is additive: a component must still work standalone, exactly as before, when `store` is not set.
- Never put inline script, `on*` handlers or `javascript:` URLs in swapped HTML; the sanitizer strips them. Behavior that needs script means a new component in this repo.
- A new component must be in `components.json` before agents can use it in swapped HTML (the sanitizer allowlist is read from it).
- Give anything with transient state a stable `id`; `ui-each` children get `<ui-each id>-<key>`.
- Run `demo/sanitizer-test.html` and `demo/store-test.html` (over http) after touching the sanitizer, registry or `ui-each`.

## Testing
Read `tests/README.md` (what is tested, how to run it) and `docs/testing-your-app.md` (the pattern, for your own apps).
- After building or changing a UI from these components, write or run Playwright tests for the user flow; do not call the work done until they pass.
- Keep failure bundles (`tests/failures/<test>/`, gitignored). When something fails, read `report.json` first, then `filmstrip.png`, then `console.log`; fix and rerun. `failure.gif` is for humans.
- `python3 tests/run.py` runs everything (headless, offline). A new or changed component needs tests in `tests/suites/`, an entry in `components.json` that `node scripts/check-catalog.mjs` accepts (it diffs source against catalog both ways), and, for browser tests, a refreshed GIF via `python3 tests/run.py --gifs --suite <suite>`. Keep `tests/media/` under 15 MB.

## Releasing
Commit small logical steps to `main`. Cut releases as tags (`v0.x.y`) and update the pinned versions in README, AGENTS.md and `components.json`.
