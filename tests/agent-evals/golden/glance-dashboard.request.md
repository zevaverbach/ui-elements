# Request: a status row component

## Missing capability

The task asks for a dashboard of rows like "Baby: sleeping", "Package: en route" and "Server: up". Each row has a label, a state (ok, warn or bad) and a detail line, and the rows must follow a `ui-store` live. Nothing in `components.json` renders a labelled status with a state: there is no way to show "ok / warn / bad" as text plus color, bound to store data.

## Why the existing components are not enough

- `ui-todo-item` is a checkbox with a done/not-done state, not a three-way status, and ticking it would let the reader change the data.
- `ui-progress` shows a number against a goal, not a categorical state.
- `ui-store` and `ui-each` hold and repeat data, but `ui-each` needs a tag to render each row, and no existing tag fits.
- `ui-countdown` and `ui-chat-panel` are unrelated.
- Plain HTML can show static text, but it cannot follow the store without inline script, which the stable-shell rules forbid. So this has to be a component.

## Proposed component: `ui-status`

One row showing a label, a state and a detail line.

**Attributes**

- `state` (`ok` | `warn` | `bad` | `unknown`, default `unknown`): reflects; drives the color and the state word.
- `label` (string): what is being watched, e.g. "Server".
- `detail` (string): a short line such as "up for 3 days".
- `store` and `path` (optional): bind to a `ui-store`; `path` points at an object `{state, label, detail}`, so the row updates live when the store changes.

**Slots**

- `icon`: an optional icon before the label.
- `detail`: rich content replacing the `detail` attribute.

**Events** (all bubble and are composed)

- `ui-status-change` with `{state: string, previous: string}` when the state changes.

**CSS custom properties:** `--ui-status-ok`, `--ui-status-warn`, `--ui-status-bad`, `--ui-status-unknown`, each falling back to a shared `--ui-*` token.

**Accessibility:** the state is written as text ("OK", "Warning", "Problem"), never shown by color alone; state changes are announced through a polite live region.

It composes with `ui-each`: `<ui-each store="home" tag="ui-status">` renders one row per item. Until it exists, the page shows the three rows as static text and does not use any script.
