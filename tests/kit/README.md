# tests/kit: record, caption and debug browser tests

A small copy-paste kit for Playwright (Python) tests. It does four things on top of your tests:

1. **Captions**: an on-screen caption for the current step, a cursor dot and a key badge, so a silent GIF is readable.
2. **GIFs**: every passing test becomes a small animated GIF (ffmpeg two-pass palette, ~8 fps, ≤640 px wide, budgeted).
3. **Failure bundles**: a failing test writes `failure.gif`, `filmstrip.png`, `report.json` and `console.log` for people *and* agents.
4. **Console discipline**: uncaught page errors and unexpected console errors fail the test.

It is independent of the ui-elements repo: pure Python stdlib + `playwright` + `ffmpeg`/`ffprobe`. No other files are needed.

## Copy it

```sh
cp -r tests/kit  your-project/tests/kit
pip install playwright && playwright install chromium     # and make sure ffmpeg is on PATH
python3 your-project/tests/kit/sample_test.py              # see it work
python3 your-project/tests/kit/sample_test.py --fail       # see a failure bundle in tests/kit/out/failures/
```

## Files

| File | Purpose |
|---|---|
| `caption.js` | Injected into every page: `window.__caption(text)`, cursor dot, key badge. |
| `video_to_gif.py` | `video_to_gif(src, dst, start, end, max_bytes)`: webm → GIF, shrinks settings until under the byte budget, raises `GifTooLarge` rather than writing an oversized file. Also a CLI. |
| `filmstrip.py` | `filmstrip(src, dst, frames=8)`: a labelled contact sheet of key frames, always including the last frame. Also a CLI. |
| `failure_bundle.py` | `write_failure_bundle(...)` and `snapshot(page, selector)` (a shadow-DOM-aware, trimmed DOM snapshot). |
| `harness.py` | `run_test(browser, name, fn, base_dir, ...)` runs `fn(session)` with video, captions, console capture, then writes the GIF (pass) or the bundle (fail). Also `Skip` and `Pending`. |
| `sample_test.py` | A complete example to copy. |

## The pattern in 12 lines

```python
from harness import run_test
from playwright.sync_api import sync_playwright, expect

def checkout_happy_path(t):                       # t: harness.Session
    t.goto("/cart")
    t.step("Add the first product", "#product-1") # caption + remembers the selector for the failure report
    t.page.click("#product-1 .add")
    t.step("The cart badge shows 1", ".badge")
    expect(t.page.locator(".badge")).to_have_text("1")

with sync_playwright() as p:
    r = run_test(p.chromium.launch(), "checkout-happy-path", checkout_happy_path,
                 base_dir="tests", record_gif=True, base_url="http://localhost:3000")
    print(r.status, r.gif or r.bundle)
```

- On **pass** with `record_gif=True`: `tests/media/checkout-happy-path.gif`. A failing run never touches an existing GIF.
- On **fail**: `tests/failures/checkout-happy-path/` with `failure.gif`, `filmstrip.png`, `report.json`, `console.log`. Keep `tests/failures/` out of git.

## Useful session API

| | |
|---|---|
| `t.page`, `t.context` | the Playwright page and context |
| `t.goto(path)` | relative to `base_url` |
| `t.step(caption, selector=None)` | show a caption (also starts the clock for GIF trimming) |
| `t.capture_events("my-event", ...)`, `t.events(type)` | record CustomEvents (type, detail, target, bubbles, composed, prevented) |
| `t.allow_console(r"regex", ...)` | console errors matching these are expected |
| `run_test(..., catalog_entry=...)` | any JSON you want copied into `report.json` (e.g. the docs for the component under test) |
| `run_test(..., known_issue="why")` | a failure is reported as a known issue instead of failing the run |
| `run_test(..., setup=fn)` | `fn(session)` runs before the test (add routes, cookies, ...) |
| `raise Skip("why")` / `raise Pending("why")` | skipped / not built yet |
| any context option | `viewport`, `has_touch`, `reduced_motion`, `color_scheme`, `locale`, ... |

## Budget

`video_to_gif` defaults to 1.5 MB per GIF. Keep the viewport small (e.g. 640×420), trim idle time (the harness starts the GIF at the first `t.step` and ends shortly after the last), and keep tests short.
