"""The framework-free assertion pages under demo/ (sanitizer-test.html, store-test.html) run as tests.
Each page sets document.title to PASS (n) or FAIL (n) and fills window.__results."""
from registry import test, env
from helpers import check, eq

def run_page(t, path, allow=()):
    for a in allow:
        t.allow_console(a)
    t.step(f"Open {path}")
    t.goto(path)
    t.page.wait_for_function("document.title.startsWith('PASS') || document.title.startsWith('FAIL')", timeout=15000)
    res = t.page.evaluate("window.__results")
    t.step(f"{len(res)} assertions run: {t.page.title()}")
    failed = [r["name"] for r in res if not r["ok"]]
    check(not failed, f"failing assertions: {failed}")
    check(len(res) >= 30, f"expected at least 30 assertions, saw {len(res)}")
    return res

@test("demo-pages", "sanitizer-assertions", viewport={"width": 640, "height": 420})
def _(t):
    t.allow_console("Failed to load resource")
    run_page(t, "/demo/sanitizer-test.html")

@test("demo-pages", "store-assertions", needs_idiomorph=True, viewport={"width": 640, "height": 420})
def _(t):
    t.allow_console("status of 404")          # the page deliberately fetches a missing src
    run_page(t, "/demo/store-test.html")
