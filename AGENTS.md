# Using ui-elements from another project

To use this library from another project: read `components.json`, load only the modules you need via the URL pattern, and compose them; do not copy the source.

- Catalog: `https://cdn.jsdelivr.net/gh/zevaverbach/ui-elements@v0.1.0/components.json`
- Component: `<script type="module" src="https://cdn.jsdelivr.net/gh/zevaverbach/ui-elements@v0.1.0/components/<file>.js"></script>`
- Pinned to a tag or commit SHA, not `@main` (cached for hours).
- Pages (only if enabled): `https://zevaverbach.github.io/ui-elements/components/<file>.js`
- Optional theme: `.../tokens.css`. Override `--ui-*` on any ancestor to restyle.

Each entry in the catalog lists attributes, slots, events (all `ui-*`, bubbling and composed, with `detail` shapes), CSS custom properties and `composes-well-with`. Listen for events on the element or any ancestor. Components make no network calls: you wire events to your own backend.

Working on this repo itself? See `CLAUDE.md`.
