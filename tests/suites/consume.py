"""Suite E: consuming the library the way another project does, by URL.

A blank page on one origin imports components from a second origin that mimics the jsDelivr layout
(/gh/<user>/<repo>@<ref>/<path>, CORS enabled). That proves relative imports such as ./_shared/util.js
resolve correctly from a CDN-style path. One optional check hits the real jsDelivr."""
import json, os, urllib.error, urllib.request
from registry import test, env
from helpers import check, eq
from kit_skip import Skip

REF = "v0.1.0"

def consumer_page(cdn, ref, modules, extra=""):
    base = f"{cdn}/gh/zevaverbach/ui-elements@{ref}"
    mods = "\n".join(f'<script type="module" src="{base}/components/{m}.js"></script>' for m in modules)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>consumer</title>
<link rel="stylesheet" href="{base}/tokens.css"></head>
<body><main id="root"><ui-todo-item id="a" text="Loaded by URL"></ui-todo-item>
<ui-chat-panel id="c" heading="Hi"></ui-chat-panel></main>
{mods}{extra}</body></html>"""

def serve_page(t, html, path="/consumer.html"):
    env.pages[path] = html          # served by the real test server, so it is a normal loopback page
    t.goto(path)

def track(t):
    t.reqs = []
    t.page.on("response", lambda r: t.reqs.append((r.url, r.status)))

@test("consume", "cdn-layout-and-relative-imports", desc='A blank page imports components from a jsDelivr-shaped URL: both elements define and render, the relative ./_shared imports resolve from the same path, and the component works.', viewport={"width": 640, "height": 300})
def _(t):
    track(t)
    t.step("Blank page imports components by a jsDelivr-shaped URL")
    serve_page(t, consumer_page(env.cdn, REF, ["ui-todo-item", "ui-chat-panel"]))
    p = t.page
    p.wait_for_function("!!(customElements.get('ui-todo-item') && customElements.get('ui-chat-panel'))")
    t.step("Both elements are defined and rendered")
    check(p.locator("#a .check").is_visible(), "ui-todo-item rendered its shadow DOM")
    t.step("The relative imports (./_shared/*.js) were fetched from the same CDN-style path")
    cdn_prefix = f"{env.cdn}/gh/zevaverbach/ui-elements@{REF}/components/_shared/"
    got = {u.replace(cdn_prefix, ""): s for u, s in t.reqs if u.startswith(cdn_prefix)}
    for mod in ("util.js", "base.js", "speech.js", "reorder.js", "store-registry.js"):
        if mod == "store-registry.js":
            continue          # only imported by ui-chat-panel's optional store binding and ui-each/ui-store
        eq(got.get(mod), 200, f"_shared/{mod} status")
    check(all(s == 200 for u, s in t.reqs if env.cdn in u), f"every CDN request succeeded: {[x for x in t.reqs if x[1] != 200]}")
    t.step("The component works: tick the box, get a ui-toggle event")
    t.capture_events("ui-toggle")
    p.click("#a .check")
    eq(t.events("ui-toggle")[-1]["detail"], {"checked": True, "progress": None})
    t.step("tokens.css loaded from the same path themes the page")
    eq(p.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--ui-radius').trim()"), "8px")

@test("consume", "catalog-matches-loaded-modules", desc='components.json fetched from the CDN-style path lists modules that all load, and every catalog tag ends up defined.', viewport={"width": 640, "height": 300})
def _(t):
    t.step("Fetch components.json from the CDN path and load every module it lists")
    cat = json.load(urllib.request.urlopen(f"{env.cdn}/gh/zevaverbach/ui-elements@{REF}/components.json"))
    tags = [c["tag"] for c in cat["components"]]
    serve_page(t, consumer_page(env.cdn, REF, [c["file"].split("/")[-1][:-3] for c in cat["components"]]))
    t.page.wait_for_function("(tags) => tags.every((t) => customElements.get(t))", arg=tags)
    t.step(f"All {len(tags)} catalog tags are defined: " + ", ".join(tags))
    eq(t.page.evaluate("(tags) => tags.filter((t) => !customElements.get(t))", tags), [])

@test("consume", "swap-outlet-from-the-cdn-path", desc='swapOutlet imported from the CDN-style path swaps an outlet correctly.', needs_idiomorph=True, viewport={"width": 640, "height": 300})
def _(t):
    track(t)
    t.step("Import swapOutlet from the CDN-style path and swap an outlet")
    extra = f"""<script type="module">
      import {{ swapOutlet }} from '{env.cdn}/gh/zevaverbach/ui-elements@{REF}/components/_shared/outlet.js';
      window.__swap = swapOutlet;
    </script>"""
    serve_page(t, consumer_page(env.cdn, REF, ["ui-todo-item"], extra).replace('<main id="root">', '<main id="outlet">'))
    p = t.page
    p.wait_for_function("window.__swap")
    p.evaluate("window.__swap('<ui-todo-item id=\"n\" text=\"swapped in\"></ui-todo-item><ui-bogus id=\"x\"></ui-bogus>')")
    p.wait_for_timeout(400)
    check(p.locator("#n").count() == 1, "swapped markup arrived")
    check(p.locator("#x").count() == 0, "tag missing from the catalog was removed: the catalog was fetched relative to outlet.js")
    check(any(u.endswith("/components.json") and u.startswith(env.cdn) for u, s in t.reqs), "components.json fetched from the CDN path")

@test("consume", "online-real-jsdelivr", desc='Online check against the real jsDelivr: the pinned tag serves the module and its _shared imports.', online=True, viewport={"width": 640, "height": 300})
def _(t):
    ref = os.environ.get("UI_ELEMENTS_TAG", REF)
    url = f"https://cdn.jsdelivr.net/gh/zevaverbach/ui-elements@{ref}/components/ui-todo-item.js"
    t.step(f"HEAD {url.replace('https://cdn.jsdelivr.net/gh/', '')}")
    try:
        urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=10)
    except urllib.error.HTTPError as e:
        raise Skip(f"tag {ref} does not exist on jsDelivr yet (HTTP {e.code})")
    except Exception as e:
        raise Skip(f"jsDelivr unreachable: {e}")
    t.step("The real CDN serves the module and its _shared imports")
    track(t)
    serve_page(t, consumer_page("https://cdn.jsdelivr.net", ref, ["ui-todo-item"]).replace('<ui-chat-panel id="c" heading="Hi"></ui-chat-panel>', ""))
    t.page.wait_for_function("!!customElements.get('ui-todo-item')", timeout=20000)
    check(t.page.locator("#a .check").is_visible(), "rendered from jsDelivr")
    check(any("/_shared/util.js" in u and s == 200 for u, s in t.reqs), "relative import _shared/util.js loaded from jsDelivr")
