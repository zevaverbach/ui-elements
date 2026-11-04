# Using ui-elements from another project

To use this library from another project: read `components.json`, load only the modules you need via the URL pattern, and compose them; do not copy the source.

- Catalog: `https://cdn.jsdelivr.net/gh/zevaverbach/ui-elements@v0.1.0/components.json`
- Component: `<script type="module" src="https://cdn.jsdelivr.net/gh/zevaverbach/ui-elements@v0.1.0/components/<file>.js"></script>`
- Pinned to a tag or commit SHA, not `@main` (cached for hours).
- Pages (only if enabled): `https://zevaverbach.github.io/ui-elements/components/<file>.js`
- Optional theme: `.../tokens.css`. Override `--ui-*` on any ancestor to restyle.

Each entry in the catalog lists attributes, slots, events (all `ui-*`, bubbling and composed, with `detail` shapes), CSS custom properties and `composes-well-with`. Listen for events on the element or any ancestor. Components make no network calls: you wire events to your own backend.

Working on this repo itself? See `CLAUDE.md`.

## Changing the UI at runtime (stable shell)

If the page has a shell (`<ui-store>` elements, `<ui-chat-panel>`, one `<main id="outlet">`), change the UI by calling `swapOutlet(html)` from `components/_shared/outlet.js` with HTML made only of ui-* tags from `components.json` and plain layout/text tags. Read `docs/state-and-shell.md` first. Rules:

- Never swap outside the outlet, and never with ad hoc `innerHTML`.
- Keep data in stores (`<ui-store name=...>`); render lists with `<ui-each>`; keep ids stable across successive outputs (`<ui-each id>`, inputs, anything with focus or an open edit).
- Never put `<script>`, `on*` handlers or `javascript:` URLs in swapped HTML; they are stripped. If you need behavior no component has, stop and propose a new component in this repo.
- Component events become store changes through `ui-action` (`{store, action, payload}`); actions: add, remove, update, toggle, move, set, clear.
- Available from the next tag (suggested `v0.2.0`); until then pin a commit SHA.

## Testing what you build

After building or changing a UI from these components, write or run Playwright tests for the user flow and do not report it done until they pass. Keep the failure bundles; when something fails, read `tests/failures/<test>/report.json` and `filmstrip.png` (and `console.log`), fix, rerun. The pattern and a copy-paste kit (`tests/kit/`): `docs/testing-your-app.md`. What this repo tests and how to run it: `tests/README.md`. To check a generated page against a task: `tests/agent-evals/README.md`.

