# Request: a status row component

## Missing capability

The task is a glance dashboard ("is everything okay?") with three rows: the baby monitor, a package and the home server. Each row needs a **state** (ok, warn or bad) shown with color and text, a label and a one-line detail, and it has to update live from a `ui-store` named `home` without any script. Nothing in `components.json` renders a labelled status with a state, so the rows cannot be built honestly.

## Why the existing components are not enough

- `ui-todo-item` is a to-do: a checkbox, inline edit, delete and reordering. Using `checked` to mean "ok" would show a checkbox the user can untick, has no warn state, and offers edit and delete on things nobody should edit. It is a to-do list dressed up as a dashboard.
- `ui-progress` shows a value toward a max (a ring or bar). A status is not a quantity: "package en route" has no percentage, and ok/warn/bad are categories, not points on a scale.
- `ui-countdown` counts time down; it has a warn state, but only for low time.
- `ui-store` can hold the values and `ui-each` can render one child per store item, but they need a child component that shows a state; plain `li` or `p` tags cannot take their text or color from the store.
- The remaining option, an inline script that subscribes to the store and rewrites the rows, is forbidden by the stable-shell rules: swapped HTML must not contain script, so this has to be a component.

## Proposed component: `ui-status`

One status row: an indicator (color plus a text badge such as "OK", "Warning", "Problem"), a label and a detail line. Works standalone from attributes, or bound to a store path.

**Attributes**

- `state` (`ok` | `warn` | `bad` | `unknown`, default `unknown`): the state. Reflects; the badge text and color follow it.
- `label` (string): what is being monitored, e.g. "Baby".
- `detail` (string): the one-line detail, e.g. "Sleeping since 13:10".
- `store` (string, optional): a `ui-store` name. When set, `state` and `detail` are read from the store and re-rendered on every change.
- `path` (string, optional): dot path of the object `{state, detail}` in the store, e.g. `baby`.
- `compact` (boolean): one-line layout for small screens.

Store binding is additive: without `store`, the element renders from its attributes exactly as before. It also works as the child of `ui-each` with `map='{"state":"state","label":"label","detail":"detail"}'`.

**Slots**

- `icon`: replaces the default indicator dot.
- `detail`: rich detail content instead of the `detail` attribute.

**Events** (all bubble and are composed)

- `ui-status-change` with `{state: string, previous: string, label: string}` whenever the state changes (from an attribute or the store), so a host can notify on ok -> bad.

**CSS custom properties**

- `--ui-status-ok`, `--ui-status-warn`, `--ui-status-bad`, `--ui-status-unknown` (indicator colors, each falling back to a shared `--ui-*` token).
- `--ui-status-gap`, `--ui-status-radius`.

**Accessibility**

- The state is in text, never color alone (the badge reads "OK", "Warning" or "Problem").
- A change of state is announced through a polite live region (assertive for `bad`), since a glance dashboard is often not being watched.
- Label and detail are set with `textContent`; the indicator respects `prefers-reduced-motion` (no pulsing).

## Usage once it exists

Three `ui-status` elements in the outlet, each with `store="home"` and `path` set to `baby`, `package` and `server`, and the `home` store in the shell seeded with `{state, detail}` per row. No script in the page beyond the library's module imports and the store's JSON seed.

Until it exists, the page shows a static "Dashboard coming soon" paragraph and does not use any script.
