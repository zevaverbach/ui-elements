#!/usr/bin/env python3
"""A complete, self-contained example of the pattern. Copy this file and edit it for your own app.

    python3 sample_test.py              run the sample (writes out/media/*.gif for passing tests)
    python3 sample_test.py --fail       make one test fail on purpose to see the failure bundle in out/failures/

It serves a tiny page from a temp folder, so it needs nothing but Python, Playwright and ffmpeg.
Replace PAGE and the test bodies with your app's URL and user flows.
"""
import http.server, os, sys, tempfile, threading, functools

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from playwright.sync_api import sync_playwright, expect
from harness import run_test

PAGE = """<!doctype html><title>Counter</title>
<h1 id="count">0</h1><button id="inc">Add one</button>
<script>document.getElementById('inc').onclick = () => { const c = document.getElementById('count'); c.textContent = +c.textContent + 1; }</script>"""

def test_counter_increments(t):                      # t is a harness.Session
    t.goto("/")
    t.step("The counter starts at 0", "#count")
    expect(t.page.locator("#count")).to_have_text("0")
    t.step("Click the button three times", "#inc")
    for _ in range(3):
        t.page.click("#inc")
    t.step("The counter shows 3", "#count")
    expect(t.page.locator("#count")).to_have_text("3")

def test_counter_never_negative(t, fail=False):
    t.goto("/")
    t.step("Click once", "#inc")
    t.page.click("#inc")
    t.step("The counter is not negative" + (" (this one is wrong on purpose)" if fail else ""), "#count")
    expect(t.page.locator("#count")).to_have_text("-1" if fail else "1", timeout=1500)

def main():
    root = tempfile.mkdtemp()
    open(os.path.join(root, "index.html"), "w").write(PAGE)
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    handler = functools.partial(Quiet, directory=root)
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
    fail = "--fail" in sys.argv
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for name, fn in (("counter-increments", test_counter_increments),
                         ("counter-never-negative", lambda t: test_counter_never_negative(t, fail))):
            r = run_test(browser, name, fn, base_dir=out, record_gif=True, base_url=base,
                         catalog_entry=None, dwell=0.5)             # catalog_entry: put your component docs here
            results.append(r)
            print(f"{r.status.upper():7} {name}  {r.gif or r.bundle or ''}")
        browser.close()
    httpd.shutdown()
    return 1 if any(r.status == "failed" for r in results) else 0

if __name__ == "__main__":
    sys.exit(main())
