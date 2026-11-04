"""Suite G: light/dark screenshots of every demo page, and an axe-core accessibility pass (online only)."""
import os
from registry import test, env
from helpers import check, eq

# (path, themed): the two assertion pages are plain unthemed pages, so only overflow and blank checks apply to them
PAGES = [("/demo/index.html", True), ("/demo/shell.html", True), ("/demo/sanitizer-test.html", False), ("/demo/store-test.html", False)]
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "screenshots")
AXE = "https://cdn.jsdelivr.net/npm/axe-core@4.10.2/axe.min.js"
LUMA = "(() => { const m = getComputedStyle(document.body).backgroundColor.match(/\\d+(\\.\\d+)?/g).map(Number); return (0.2126 * m[0] + 0.7152 * m[1] + 0.0722 * m[2]) / 255; })()"

@test("visual", "demo-pages-light-and-dark", desc='Every demo page renders in both color schemes with no horizontal overflow, no blank screenshot, and a clearly light and a clearly dark background (the recording shows the dark pass).', needs_idiomorph=True, viewport={"width": 640, "height": 420})
def _(t):
    t.allow_console("Failed to load resource", "status of 404")
    os.makedirs(OUT, exist_ok=True)
    p = t.page                                      # recorded, dark
    # The light pass runs in a separate, unrecorded context so the recording stays dark.
    lctx = p.context.browser.new_context(color_scheme="light", viewport={"width": 640, "height": 420})
    lctx.route(lambda url: not url.startswith(("http://127.0.0.1", "data:", "about:", "blob:")), lambda r: r.abort())
    if env.idiomorph:
        body = open(env.idiomorph, "rb").read()
        lctx.route("**/idiomorph*", lambda r: r.fulfill(status=200, body=body, headers={"content-type": "application/javascript", "access-control-allow-origin": "*"}))
    lp = lctx.new_page()
    try:
        for path, themed in PAGES:
            name = path.split("/")[-1][:-5]
            lp.goto(env.base + path); lp.wait_for_timeout(500)
            lum = {"light": lp.evaluate(LUMA)}
            lp.screenshot(path=os.path.join(OUT, f"{name}-light.png"))
            over = lp.evaluate("document.documentElement.scrollWidth - window.innerWidth")
            check(over <= 1, f"{name} (light) overflows horizontally by {over}px")
            t.goto(path); p.wait_for_timeout(500)
            t.step(f"{name}: dark mode")
            lum["dark"] = p.evaluate(LUMA)
            p.screenshot(path=os.path.join(OUT, f"{name}-dark.png"))
            over = p.evaluate("document.documentElement.scrollWidth - window.innerWidth")
            check(over <= 1, f"{name} (dark) overflows horizontally by {over}px")
            if themed:
                check(lum["light"] > 0.8, f"{name}: light page background is too dark ({lum['light']:.2f})")
                check(lum["dark"] < 0.35, f"{name}: dark page background is too light ({lum['dark']:.2f})")
            sizes = [os.path.getsize(os.path.join(OUT, f"{name}-{s}.png")) for s in ("light", "dark")]
            check(min(sizes) > 3000, f"{name}: a screenshot looks blank {sizes}")
            if themed:
                check(sizes[0] != sizes[1], f"{name}: light and dark screenshots are identical")
    finally:
        lctx.close()

@test("visual", "axe-accessibility", desc='Online check: axe-core finds no serious or critical accessibility violations on the demo pages.', online=True, needs_idiomorph=True, viewport={"width": 640, "height": 420})
def _(t):
    t.allow_console("Failed to load resource", "status of 404")
    p = t.page
    for path in ("/demo/index.html", "/demo/shell.html"):
        t.step(f"axe-core on {path}")
        t.goto(path); p.wait_for_timeout(700)
        p.add_script_tag(url=AXE)
        res = p.evaluate("async () => (await axe.run(document, {runOnly: {type: 'tag', values: ['wcag2a', 'wcag2aa']}})).violations.map(v => ({id: v.id, impact: v.impact, help: v.help, nodes: v.nodes.slice(0, 3).map(n => n.target.join(' '))}))")
        serious = [v for v in res if v["impact"] in ("critical", "serious")]
        check(not serious, f"{path}: axe found {len(serious)} serious violation(s): " + "; ".join(f"{v['id']} ({v['impact']}): {v['nodes']}" for v in serious))
