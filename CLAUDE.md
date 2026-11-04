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
3. Be loaded and shown in **`demo/index.html`**.
4. Update `README.md`'s component table.
5. Pass `node scripts/check-catalog.mjs` and a manual run of the demo served over http.

## Releasing
Commit small logical steps to `main`. Cut releases as tags (`v0.x.y`) and update the pinned versions in README, AGENTS.md and `components.json`.
