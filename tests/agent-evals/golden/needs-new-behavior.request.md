# Request: a countdown component

## Missing capability

The task asks for a "Start timer" button that counts down from 60 seconds, shows the remaining time and signals when it reaches zero. A countdown needs a clock that ticks, state that changes every second, and an event at zero. No component in `components.json` does any of that.

## Why the existing components are not enough

- `ui-todo-item` has a `progress` attribute, but it is set by clicks on four fixed steps, not by time.
- `ui-store` and `ui-each` hold and render data; they do not change it on a schedule.
- `ui-chat-panel` has no timer behavior.
- The only remaining option would be an inline `<script>` with `setInterval` or an `onclick` handler. The stable-shell rules forbid both: swapped HTML must not contain script, so this has to be a component.

## Proposed component: `ui-countdown`

A small element that shows the time left and counts down, started and stopped by attributes and methods.

**Attributes**

- `seconds` (number, default 60): the duration.
- `running` (boolean): counting down while present. Reflects state.
- `autostart` (boolean): start counting as soon as it is connected.
- `label` (string): text of the built-in start/pause button, default "Start timer".

**Slots**

- `done` (shown instead of the time when it reaches zero).

**Events** (all bubble and are composed)

- `ui-tick` with `{remaining: number}` once per second.
- `ui-done` with `{}` when it reaches zero.

**Methods:** `start()`, `pause()`, `reset()`.

**CSS custom properties:** `--ui-countdown-bg`, `--ui-countdown-text`, `--ui-countdown-accent`.

**Accessibility:** the time is announced politely (`role="timer"`), the button is a native `<button>`, and the countdown respects `prefers-reduced-motion`.

Until it exists, the page shows a static "Timer coming soon" paragraph and does not use any script.
