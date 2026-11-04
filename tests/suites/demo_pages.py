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

@test("demo-pages", "sanitizer-assertions", desc='Opens demo/sanitizer-test.html and requires all 36 of its in-page sanitizer assertions to pass with no console errors.', viewport={"width": 640, "height": 420})
def _(t):
    t.allow_console("Failed to load resource")
    run_page(t, "/demo/sanitizer-test.html")

@test("demo-pages", "store-assertions", desc='Opens demo/store-test.html and requires all 42 of its in-page store assertions to pass.', needs_idiomorph=True, viewport={"width": 640, "height": 420})
def _(t):
    t.allow_console("status of 404")          # the page deliberately fetches a missing src
    run_page(t, "/demo/store-test.html")

IDX = "/demo/index.html"
LIVE_COUNT = "(document.querySelector('#live-data').textContent.match(/\"id\"/g) || []).length"

@test("demo-pages", "reset-data-restores-the-seed", desc='Regression test: "Reset data" on the live editor puts back exactly the four seed to-dos (it used to drop one), whether or not anything was changed.', needs_idiomorph=True, viewport={"width": 640, "height": 420})
def _(t):
    t.goto(IDX); p = t.page
    p.wait_for_function("document.querySelector('#live-data').textContent.includes('\"items\"')")
    t.step("Untouched demo: four to-dos in the store", "#live-data")
    eq(p.evaluate(LIVE_COUNT), 4)
    t.step("Reset data without changing anything: still the same four", "#live-reset")
    p.click("#live-reset"); p.wait_for_timeout(250)
    eq(p.evaluate(LIVE_COUNT), 4, "reset must not drop an entry")
    t.step("Delete one and add another through the store, then reset", "#live-reset")
    p.evaluate("(async () => { const r = await import('/components/_shared/store-registry.js'); r.dispatch('demo', 'remove', {id: 'a'}); r.dispatch('demo', 'add', {item: {text: 'extra', done: false}}); })()")
    p.wait_for_timeout(250)
    p.click("#live-reset"); p.wait_for_timeout(250)
    eq(p.evaluate(LIVE_COUNT), 4)
    check("extra" not in p.inner_text("#live-data") and '"a"' in p.inner_text("#live-data"), "reset did not restore the seed data")

@test("demo-pages", "injection-example-shows-what-was-removed", desc='The "Try to inject script" example lists exactly what the sanitizer removed (script, onclick, onerror, javascript: URL), the preview really is clean, and the ui-* component survives.', needs_idiomorph=True, viewport={"width": 640, "height": 420})
def _(t):
    t.goto(IDX); p = t.page
    t.step("Pick the injection example", "#live-preset")
    p.select_option("#live-preset", "Try to inject script (it is stripped)"); p.wait_for_timeout(500)
    t.step("The report names each removal", "#live-report")
    rep = p.inner_text("#live-report")
    for needle in ("4 dangerous things", "<script>", "onclick", "onerror", "javascript:", "verified clean: yes"):
        check(needle in rep, f"report lacks {needle!r}: {rep}")
    t.step("Nothing dangerous is left in the preview; the component stays", "#live-outlet")
    check(p.evaluate("!document.querySelector('#live-outlet script') && ![...document.querySelectorAll('#live-outlet *')].some(e => [...e.attributes].some(a => /^on/i.test(a.name) || /^javascript:/i.test(a.value)))"), "dangerous markup survived")
    eq(p.evaluate("document.querySelectorAll('#live-outlet ui-todo-item').length"), 1)
    t.step("A harmless preset reports nothing", "#live-report")
    p.select_option("#live-preset", "Standalone items (no store)"); p.wait_for_timeout(400)
    check(p.evaluate("document.querySelector('#live-report').hidden"), "report should be hidden when nothing was removed")

@test("demo-pages", "layouts-use-the-width-on-tablets", desc='On iPad-sized screens the demo pages fill the width (no narrow centered column), the two-column to-do layout is used only when wide enough to read, and stacks on iPad portrait.', needs_idiomorph=True, viewport={"width": 1180, "height": 560})
def _(t):
    p = t.page
    for w, h, cols in ((820, 560, False), (1180, 560, True)):
        p.set_viewport_size({"width": w, "height": h})
        t.goto("/demo/index.html"); p.wait_for_timeout(300)
        t.step(f"{w}px wide: the live editor page uses the full width", "main")
        mw = p.evaluate("document.querySelector('main').getBoundingClientRect().width")
        check(mw >= w - 2, f"index.html main is {mw}px of {w}px")
        t.goto("/demo/shell.html"); p.wait_for_timeout(300)
        p.click("[data-layout=columns]"); p.wait_for_timeout(400)
        t.step(f"{w}px wide: Open and Done are " + ("side by side" if cols else "stacked"), "#outlet")
        x = p.evaluate("(() => { const a = document.querySelector('#open ui-todo-item').getBoundingClientRect(), b = document.querySelector('#done ui-todo-item').getBoundingClientRect(); return {side: Math.abs(a.top - b.top) < 40 || b.left > a.right - 1, wopen: a.width}; })()")
        check(x["side"] == cols, f"{w}px: expected {'two columns' if cols else 'one column'}, got {x}")
        check(x["wopen"] >= 300, f"{w}px: the open column is squashed ({x['wopen']}px)")
