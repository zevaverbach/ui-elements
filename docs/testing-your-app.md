# Testing an application built from these components

For people and agents who build pages and apps with `ui-*` components. This repo tests the components themselves (see [`tests/README.md`](../tests/README.md)); this guide teaches the same pattern for **your** application's user flows. A ready-to-copy kit lives in [`tests/kit/`](../tests/kit/).

The pattern in one sentence: *write a Playwright test for each user flow, record it with step captions, keep a GIF of every passing flow, write a failure bundle when one fails, and loop: run, read the bundle, fix, rerun.*

## Why test the UI you generated

Components are tested in isolation here, but your page is a composition: the wiring (`store`, `map`, `events`, `where`, ids), the layout swaps and the content are yours. They fail in ways no component test can see: a `ui-each` pointing at a store that is not declared, a swapped layout that loses an id, an action that never reaches the store. A test of the *flow* a user cares about ("tick Milk and it moves to the basket") catches all of those at once.

## The loop

```
write/change UI  →  run tests  →  pass? keep the GIFs, done
                                  fail? read tests/failures/<test>/report.json and filmstrip.png
                                        fix the page (or the test, if the test was wrong)
                                        rerun  ↺
```

For an agent, that is: run the command, and on a non-zero exit open **`report.json`** first (text, exact), then **`filmstrip.png`** (what the screen looked like at key moments), then `console.log` if the report says the console had errors. Do not try to interpret `failure.gif`; it is for humans.

### Why the bundle has both a GIF and text/image forms

| File | For | Why |
|---|---|---|
| `failure.gif` | people | An animation shows *what happened over time* at a glance, and can be attached to a bug report or PR. |
| `filmstrip.png` | agents (and people skimming) | Agents can usually read an image but cannot watch an animation. A contact sheet of ~8 labelled frames, including the last one, is the same story as a still image. |
| `report.json` | agents | Exact, machine-readable facts: test name, **failing step**, error message, page URL, console errors, the **catalog entry** of the component under test (so the expected API is right there) and a trimmed **DOM snapshot** around the failing element (including shadow roots). |
| `console.log` | both | Every console message and page error with timestamps; most "nothing happens" bugs are visible here. |

## Step by step

### 1. Copy the kit and install the tools

```sh
cp -r path/to/ui-elements/tests/kit  your-app/tests/kit
pip install playwright && playwright install chromium      # ffmpeg must be on PATH
python3 your-app/tests/kit/sample_test.py                  # a working example
```

The kit is pure Python (stdlib + Playwright) plus ffmpeg, and does not depend on this repo.

### 2. Write one test per user flow

```python
# your-app/tests/flows.py
from playwright.sync_api import sync_playwright, expect
from kit.harness import run_test          # or add tests/kit to sys.path and `from harness import run_test`

def tick_moves_item_to_basket(t):
    t.goto("/")
    t.step("Milk starts in 'To buy'", "#to-buy")
    expect(t.page.locator("#to-buy ui-todo-item", has_text="Milk")).to_have_count(1)
    t.step("Tick Milk", "#to-buy")
    t.page.locator("#to-buy ui-todo-item", has_text="Milk").locator(".check").click()   # CSS pierces open shadow DOM
    t.step("Milk is now in 'In basket'", "#in-basket")
    expect(t.page.locator("#in-basket ui-todo-item", has_text="Milk")).to_have_count(1)
```

Rules of thumb:

- **One flow, 3 to 8 steps.** Every `t.step("caption", selector)` appears on screen in the GIF and is recorded as the *failing step* in the report. Write captions a stranger can read.
- **Pass the selector** of the element the step is about; the report's DOM snapshot is taken around the last selector.
- Use Playwright's `expect(...)` (auto-retrying) instead of sleeping. Locators pierce open shadow roots, so `.check`, `.handle`, `.panel` etc. are reachable; see each component's header for its parts and internals.
- Assert the **store**, not just the pixels, for state: `page.evaluate("document.querySelector('ui-store').data")`.
- Record events with `t.capture_events("ui-toggle", ...)` and assert their `detail` against the shapes in [`components.json`](../components.json).
- Mock browser APIs in an init script (for example `SpeechRecognition`; see `tests/registry.py` in this repo) instead of depending on hardware.
- Keep tests offline and deterministic: seed stores inline, route or block external requests, no real clocks where you can avoid them.

### 3. Run them and keep the artifacts

```python
with sync_playwright() as p:
    browser = p.chromium.launch()
    for name, fn in FLOWS.items():
        r = run_test(browser, name, fn, base_dir="tests", record_gif=True, base_url="http://localhost:8000")
        print(r.status, r.gif or r.bundle)
```

- A **passing** flow writes `tests/media/<name>.gif`. Commit these: they document what your app does, render in a README or PR, and show a reviewer the behavior without running anything. A failing run never overwrites an existing GIF.
- A **failing** flow writes `tests/failures/<name>/`. Put `tests/failures/` in `.gitignore` and upload it as a CI artifact.
- Keep GIFs small (default budget 1.5 MB each): small viewport (640×420), short flows. The kit shrinks fps, size and colors automatically and refuses to write an oversized file.

### 4. Testing swapped UIs (the stable-shell pattern)

If your page swaps its outlet at runtime (see [`state-and-shell.md`](state-and-shell.md)), test what must survive a swap:

```python
t.step("Type half a sentence in the stable-id input", "#new-todo")
t.page.click("#new-todo"); t.page.keyboard.type("hello")
t.step("Swap the outlet", "#outlet")
t.page.evaluate("window.swapOutlet(newHtml)")
t.step("Focus, text and data survived", "#new-todo")
expect(t.page.locator("#new-todo")).to_be_focused()
expect(t.page.locator("#new-todo")).to_have_value("hello")
```

Also assert that hostile or sloppy HTML does not execute (no `window.__pwned`), and that your swapped markup uses only documented tags and attributes. This repo's checker does the latter for you: [`tests/agent-evals/check.py`](../tests/agent-evals/check.py) takes a generated HTML file and verifies tags, attributes, script rules, wiring and task assertions. Copy it, or point it at your files.

### 5. Put it in CI

Run the same command headless on every push and upload `tests/failures/` on failure. The workflow in this repo, [`tests/ci/tests.yml`](../tests/ci/tests.yml) (copy it to `.github/workflows/`), is a template: install Python, `pip install playwright`, `playwright install --with-deps chromium`, install ffmpeg, run the tests, `actions/upload-artifact` for the failures folder.

## Checklist for an agent that just built or changed a UI

1. Write or update a Playwright test for the user flow you changed.
2. Run it. Do not report the work as done until it passes.
3. On failure: read `tests/failures/<test>/report.json`, then `filmstrip.png`, then `console.log`. Fix, rerun.
4. Keep the failure bundle until the test passes (it is gitignored), and keep the new GIF.
5. If the fix needs behavior no component has, do not add inline script: write a request for a new component (see [`state-and-shell.md`](state-and-shell.md)).

## Measuring how well an agent composes UIs

[`tests/agent-evals/`](../tests/agent-evals/README.md) turns this into a repeatable measurement without any LLM calls in the repo: task definitions, a checker, golden solutions and a scoring script that reports success rate, first-try rate, iterations and tokens.
