# Request: a star rating input component

## Missing capability

The task is a recipe list where each recipe gets a **rating** from 1 to 5 stars: set by clicking a star, changed with the keyboard (arrow keys), read out to screen readers as "3 of 5 stars", and saved into the recipe's `rating` field in a `ui-store` named `recipes` so it survives an outlet swap, without any script. Nothing in `components.json` is an input that picks one value out of a small scale and reports it, so the page cannot be built honestly.

## Why the existing components are not enough

- `ui-progress` is an output, not an input: it shows a value toward a max and cannot be clicked or focused. A bar at 60% is not "3 of 5 stars", and its completion event means a goal was reached, which a rating never does.
- `ui-todo-item` has clickable progress steps, but they are fixed at 0, 25, 50, 75 and 100 percent of a task, come with a checkbox, inline edit and delete, and 100 checks the item off. Five steps that mean "stars" would be a to-do item dressed up as a rating, and screen readers would hear "75% done".
- `ui-status` shows a state (ok, warn, bad); it is read-only and has no scale.
- `ui-each` can render one child per recipe and turn a child's event into a store `update`, but it needs a child component that emits the chosen rating; plain `input type="radio"` or `select` tags emit no `ui-*` event, so nothing would reach the store.
- An inline script that listens to clicks and writes the store is forbidden by the stable-shell rules: swapped HTML must not contain script, so this has to be a component.

## Proposed component: `ui-rating`

A row of stars (or another symbol) that is a single focusable slider-like control. Works standalone from attributes, or inside `ui-each` with its `ui-rating-change` mapped to a store update.

**Attributes**

- `value` (number, 0 to `max`, default 0): the current rating; 0 means not rated. Reflects (prop: `value`).
- `max` (number, default 5): number of stars.
- `label` (string): accessible name, e.g. "Rating for Lentil soup".
- `readonly` (boolean): show the rating without letting it change.
- `allow-clear` (boolean): clicking the current star again (or pressing 0 / Delete) clears to 0.
- `store` (string, optional) and `path` (string, optional): read the value from a `ui-store` path and keep it live; changes are still sent as events, never written directly. Store binding is additive.

**Slots**

- `symbol`: replaces the default star glyph (e.g. hearts).
- `caption`: text after the stars, e.g. "(12 ratings)".

**Events** (all bubble and are composed)

- `ui-rating-change` with `{value: number, previous: number, max: number}` when the user picks a new value by pointer or keyboard. Cancelable, so a host can veto. In `ui-each`: `events='{"ui-rating-change":{"action":"update","patch":{"rating":"$detail.value"}}}'` and `map='{"value":"rating","label":"title"}'`.

**CSS custom properties**

- `--ui-rating-color` (filled star, falls back to `--ui-color-accent`), `--ui-rating-empty` (falls back to `--ui-color-border`), `--ui-rating-size`, `--ui-rating-gap`.

**Accessibility and keyboard**

- `role="slider"` with `aria-valuemin="0"`, `aria-valuemax` = `max`, `aria-valuenow` and `aria-valuetext` "3 of 5 stars", named by `label`.
- Keyboard: Arrow Right/Up +1, Arrow Left/Down -1, Home = 1, End = `max`, digits 1 to `max` set directly; visible `:focus-visible` outline.
- Hover preview is not the only cue: the value is in text for assistive technology; respects `prefers-reduced-motion` (no star pop animation).

## Usage once it exists

A `<ui-store name="recipes">` in the shell with the three recipes, and in the outlet a `ui-each` over it with `tag="ui-rating"`, the map and events above, and the recipe title as a heading or label. No script in the page beyond the library's module imports and the store's JSON seed.

Until it exists, the page lists the three recipe titles as plain text and does not use any script.
