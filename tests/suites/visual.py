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

# Where the goal marks of the demo's ui-progress cards are drawn (page pixels), and the colours that should be there.
GOAL_MARKS_JS = """() => {
  const ring = document.querySelector('ui-progress[goal]:not([variant])'), bar = document.querySelector('ui-progress[variant=bar][goal]');
  const r = ring.shadowRoot, b = bar.shadowRoot, g = r.querySelector('.ring .goal');
  const svg = r.querySelector('.ring').getBoundingClientRect();
  const dash = parseFloat(g.getAttribute('stroke-dasharray')), off = parseFloat(g.getAttribute('stroke-dashoffset'));
  const frac = (-off + dash / 2) / (2 * Math.PI * 45), a = 2 * Math.PI * frac, rad = svg.width * 0.45;
  const line = b.querySelector('.bar .goal').getBoundingClientRect(), track = b.querySelector('.bar').getBoundingClientRect();
  return {
    tick: {x: svg.left + svg.width / 2 + rad * Math.sin(a), y: svg.top + svg.height / 2 - rad * Math.cos(a), color: getComputedStyle(g).stroke, frac},
    line: {x: line.left + line.width / 2, y: line.top + 2, color: getComputedStyle(b.querySelector('.bar .goal')).backgroundColor,
           frac: (line.left + line.width / 2 - track.left) / track.width, goal: +bar.getAttribute('goal') / bar.max},
    ringFill: getComputedStyle(r.querySelector('.ring .fill')).stroke,
    barHasRing: getComputedStyle(b.querySelector('.ring')).display !== 'none',
  };
}"""

def _rgb(css):
    return tuple(int(float(v)) for v in css[css.index("(") + 1:css.index(")")].split(",")[:3])

def _near(a, b, tol=60):
    return sum(abs(x - y) for x, y in zip(a, b)) <= tol

@test("visual", "countdown-and-progress-light-and-dark", desc='The ui-countdown and ui-progress demo sections in both color schemes: the ring goal tick and the bar goal line are drawn at the goal in the goal color (sampled from the screenshot), the bar card shows no ring, and nothing is blank.', viewport={"width": 640, "height": 900}, gif=False)
def _(t):
    from PIL import Image
    os.makedirs(OUT, exist_ok=True)
    p = t.page                                      # recorded, dark
    lctx = p.context.browser.new_context(color_scheme="light", viewport={"width": 640, "height": 900})
    lctx.route(lambda url: not url.startswith(("http://127.0.0.1", "data:", "about:", "blob:")), lambda r: r.abort())
    lp = lctx.new_page()
    try:
        for scheme, page in (("light", lp), ("dark", p)):
            if page is p:
                t.goto("/demo/index.html")
            else:
                page.goto(env.base + "/demo/index.html")
            page.wait_for_function("!!(customElements.get('ui-progress') && customElements.get('ui-countdown'))")
            page.locator("ui-progress").first.scroll_into_view_if_needed()
            page.wait_for_timeout(600)                  # let the 0.4 s fill transitions finish
            if page is p:
                t.step("dark mode: the ui-countdown and ui-progress demo sections", "ui-progress[goal]")
            for name, sel in (("countdown", "ui-countdown"), ("progress", "ui-progress")):
                path = os.path.join(OUT, f"index-{name}-{scheme}.png")
                page.locator(sel).first.locator("xpath=..").screenshot(path=path)
                check(os.path.getsize(path) > 3000, f"{name} ({scheme}) screenshot looks blank")
            m = page.evaluate(GOAL_MARKS_JS)
            check(not m["barHasRing"], f"{scheme}: the bar variant also draws a ring")
            check(abs(m["tick"]["frac"] - 0.8) < 0.001, f"{scheme}: ring goal tick at {m['tick']['frac']:.3f}, expected 0.8")
            check(abs(m["line"]["frac"] - m["line"]["goal"]) < 0.01, f"{scheme}: bar goal line at {m['line']['frac']:.3f}, expected {m['line']['goal']}")
            full = os.path.join(OUT, f"index-goals-{scheme}.png")
            page.screenshot(path=full)
            img = Image.open(full).convert("RGB")
            for mark in ("tick", "line"):
                want, got = _rgb(m[mark]["color"]), img.getpixel((round(m[mark]["x"]), round(m[mark]["y"])))
                check(_near(got, want), f"{scheme}: {mark} pixel {got} is not the goal color {want}")
            check(not _near(_rgb(m["tick"]["color"]), _rgb(m["ringFill"]), 90), f"{scheme}: goal color too close to the ring fill")
    finally:
        lctx.close()
