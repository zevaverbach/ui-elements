# ui-elements

A basket of small, composable, vanilla-JS custom elements that AI agents (and people) can discover and compose into generative UIs quickly.

- **No build step.** Plain ES modules, one component per file, no bundler, no npm install.
- **Themeable.** Shadow DOM plus CSS custom properties (`tokens.css`), light and dark.
- **Discoverable.** [`components.json`](components.json) is a machine-readable catalog of every tag, attribute, slot, event and CSS property.

## Use

```html
<script type="module" src="https://cdn.jsdelivr.net/gh/zevaverbach/ui-elements@v0.1.0/components/ui-todo-item.js"></script>
<ui-todo-item text="Buy milk"></ui-todo-item>
```

Optional theme tokens (components work without them):

```html
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/zevaverbach/ui-elements@v0.1.0/tokens.css">
```

## Components

| Tag | What it is |
|---|---|
| `ui-todo-item` | To-do item: check, inline edit, confirm-delete, progress steps, speech-to-text mic (Web Speech API), drag/keyboard/touch reorder |
| `ui-chat-panel` | Slide-in chat panel with `ui-send` event; no backend assumed |

Full API for each is in the file header and in `components.json`. Design provenance: [`docs/inventory.md`](docs/inventory.md).

## URLs

| What | URL |
|---|---|
| Component (pinned, preferred) | `https://cdn.jsdelivr.net/gh/zevaverbach/ui-elements@v0.1.0/components/ui-todo-item.js` (or `@<commit SHA>`) |
| Catalog | `https://cdn.jsdelivr.net/gh/zevaverbach/ui-elements@v0.1.0/components.json` |
| Tokens | `https://cdn.jsdelivr.net/gh/zevaverbach/ui-elements@v0.1.0/tokens.css` |
| GitHub Pages (only if enabled) | `https://zevaverbach.github.io/ui-elements/components/ui-todo-item.js`, live demo at `https://zevaverbach.github.io/ui-elements/demo/` |

`@main` URLs are cached by jsDelivr for hours; use a tag or a commit SHA for stability. Relative imports inside components (`./_shared/*.js`) resolve correctly when served from jsDelivr.

## Try the demo locally

ES modules do not load from `file://`; serve the repo root:

```sh
python3 -m http.server   # then open http://localhost:8000/demo/
```

## Check the catalog

```sh
node scripts/check-catalog.mjs   # dev-only; the library itself needs no Node
```
