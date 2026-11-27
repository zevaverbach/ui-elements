# Agent composition evals

Measure how well an agent (or a person) composes UIs from these components, **without any LLM calls in this repo**: you produce outputs however you like; the checker scores them.

```
tests/agent-evals/
  tasks/*.json      task definitions: prompt, kind, and Playwright assertions as data
  golden/*          one known-good solution per task (proves the checker works)
  check.py          check one output
  run_evals.py      score a folder of outputs and aggregate the numbers
```

## The tasks

| Task | Kind | What it exercises |
|---|---|---|
| `shopping-list` | page | a store, two filtered `ui-each` views that move items on tick, a store-backed chat panel, stable shell |
| `todo-progress` | page | standalone `ui-todo-item`s with progress steps, no store |
| `chat-left` | page | `ui-chat-panel` `side`, slotted message, placeholder |
| `kanban` | page | three `where` views over one store, two-step delete reaching the store |
| `timer-60` | page | `ui-countdown` `seconds`/`label` and a `done` slot as the reaction at zero, no script |
| `glance-dashboard` | page | not a checklist: an "is everything okay?" dashboard (baby, package, server) of `ui-status` rows bound to one `ui-store`; the rows show ok/warn in text and turn bad live when the store changes. A to-do list dressed up as a dashboard, or static rows, fail |
| `recipe-rating` | **request** | rate recipes 1 to 5 stars, by pointer and keyboard, saved into a `ui-store`. No component is an input that picks a value on a small scale (`ui-progress` is an output, `ui-todo-item` steps are a to-do), so the correct output is a **request for `ui-rating`** (value, max, a change event, store binding, keyboard and slider semantics) |

## What the checker verifies

For a page: only tags from `components.json` plus plain layout/text tags; only documented attributes on `ui-*` tags; no inline `<script>`, `on*` handler or `javascript:` URL (library module imports and `ui-store` JSON seeds are the only scripts allowed); a module import for every component used; valid `map`/`events`/`where` JSON and real store names; stores and chat panel in the shell, content in `<main id="outlet">`; the page loads with **no console errors**; and the task's own assertions pass in a real browser. Each failure has a short code (`inline-script`, `unknown-tag`, `undocumented-attribute`, `missing-module-import`, `shell-in-outlet`, `console-error`, `assertion-failed`, `request-incomplete`, ...). See the header of `check.py`.

The page is loaded with the library served from this checkout under the documented jsDelivr URL shape, with every other request blocked, so evaluation is offline and deterministic.

## Producing outputs

Give the agent the task's `prompt`, plus [`AGENTS.md`](../../AGENTS.md), [`components.json`](../../components.json) and [`docs/state-and-shell.md`](../../docs/state-and-shell.md) (this is the context a real consumer has). Ask for one file per task and save it as:

```
out/<task-id>.html            page tasks; import components from
                              https://cdn.jsdelivr.net/gh/zevaverbach/ui-elements@main/components/<tag>.js
out/<task-id>.request.md      request tasks
out/<task-id>.meta.json       optional measurements (below)
```

## Scoring

```sh
python3 tests/agent-evals/check.py --task shopping-list --html out/shopping-list.html     # one output
python3 tests/agent-evals/check.py --task recipe-rating --request out/recipe-rating.request.md
python3 tests/agent-evals/run_evals.py --outputs out/ --out results.json                  # everything
```

A failing check prints the codes and messages. An agent iterating on its own output should feed these back to itself, then write a new file and rerun; count each cycle as an iteration.

## What to record

Per task, in `<task-id>.meta.json` (all optional, all numbers except `model`):

```json
{"iterations": 2, "tokens_in": 18000, "tokens_out": 4200, "seconds": 95, "model": "your-model-id"}
```

`run_evals.py` aggregates: **success rate** (passed / tasks), **first-try rate** (passed with `iterations == 1`), **mean iterations to pass**, **mean tokens per passing task**, and **failures by code**, which tells you what to improve in the docs or components (for example many `undocumented-attribute` failures mean the catalog is unclear). Compare runs by saving `results.json` per model / prompt version; it records which tasks regressed.

## Adding a task

1. `tasks/<id>.json`: `id`, `title`, `kind` (`page` or `request`), `prompt`, and for pages `shell: true` plus `assert`: a list of steps, each with a caption `step` and one of `eval` (JS expression, with `equals`, default `true`), `click`, `fill`+`text` or `wait`. Assertions must not depend on the agent's ids: find things by text and structure.
2. `golden/<id>.html` that passes (or `golden/<id>.request.md`).
3. Add it to the lists in `tests/suites/agent_evals.py`. `python3 tests/run.py --suite agent-evals` must stay green: the suite proves the golden passes and that 34 kinds of bad output are rejected.

## The request task

The suite must always have one request-kind task whose capability the library really does not have (today `recipe-rating`, whose answer proposes `ui-rating`); the "checker rejects cheating on the impossible task" test points at it (`IMPOSSIBLE` in `tests/suites/agent_evals.py`). When a component ships that makes it solvable, do what was done for `glance-dashboard` when `ui-status` shipped: convert the task to a page task that uses the new component (golden page, browser assertions, cheating cases that are pages), and in the same change add a new request task for something still missing, with its golden `request.md`, and point `IMPOSSIBLE` at it.
