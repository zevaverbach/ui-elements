"""Suite H: the Cloudflare Pages site that scripts/publish.py builds.

The site is built into a temp dir (main at the root, HEAD also published as a fake tag v9.9.9) and served on a
second origin by a small server that applies the generated `_headers` file the way Cloudflare Pages does
(`*` splats, later rules add headers, `! Name` detaches one). A blank page on the test origin then imports
components from both roots, exactly as another project would from https://ui-elements.pages.dev."""
import functools, http.server, importlib.util, os, re, shutil, tempfile, threading, urllib.request
from registry import test, env
from helpers import check, eq

# Loaded by path: this suite is itself a module named "publish".
_spec = importlib.util.spec_from_file_location("publish_script", os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "publish.py"))
publish = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(publish)

VER = "v9.9.9"


def parse_headers(text):
    rules, cur = [], None
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line[0].isspace():
            cur = (re.compile("^" + re.escape(line.strip()).replace(r"\*", ".*") + "$"), [])
            rules.append(cur)
        elif line.strip().startswith("!"):
            cur[1].append((line.strip()[1:].strip(), None))
        else:
            k, v = line.strip().split(":", 1)
            cur[1].append((k.strip(), v.strip()))
    return rules


def headers_for(rules, path):
    out = {}
    for pat, items in rules:
        if pat.match(path):
            for k, v in items:
                if v is None:
                    out.pop(k.lower(), None)
                else:
                    out[k.lower()] = (k, v)
    return dict(out.values())


class PagesSite:
    def __init__(self):
        self.dir = tempfile.mkdtemp(prefix="ui-pages-")
        self.versions = publish.build(self.dir, {VER: "HEAD"})
        rules = parse_headers(open(os.path.join(self.dir, "_headers")).read())

        class H(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def end_headers(self):
                for k, v in headers_for(rules, self.path.split("?")[0]).items():
                    self.send_header(k, v)
                super().end_headers()

        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(H, directory=self.dir))
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown(); self.httpd.server_close(); shutil.rmtree(self.dir, ignore_errors=True)


def consumer(base):
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>consumer of Pages</title>
<link rel="stylesheet" href="{base}/tokens.css"></head>
<body style="padding:16px"><p id="src" style="font:14px system-ui">Loaded from {base}</p>
<main id="outlet"><ui-todo-item id="a" text="Loaded from Cloudflare Pages"></ui-todo-item></main>
<script type="module" src="{base}/components/ui-todo-item.js"></script>
<script type="module">import {{ swapOutlet }} from '{base}/components/_shared/outlet.js'; window.__swap = swapOutlet;</script>
</body></html>"""


@test("publish", "pages-site-layout-and-headers", gif=False, desc='scripts/publish.py builds the Pages site: main at the root, each tag under /<tag>/ with the same files, test/script folders left out, and a _headers file that allows cross-origin imports everywhere and marks only tag paths immutable.', viewport={"width": 640, "height": 300})
def _(t):
    site = PagesSite()
    try:
        t.step("Build the site: main at the root, HEAD as tag " + VER)
        eq(site.versions, [VER])
        for root in ("", VER + "/"):
            for f in ("components/ui-todo-item.js", "components/_shared/util.js", "components.json", "tokens.css", "demo/index.html"):
                check(os.path.isfile(os.path.join(site.dir, root + f)), f"{root}{f} published")
        for f in ("tests", "scripts", "docs/media", VER + "/tests", VER + "/docs/media"):
            check(not os.path.exists(os.path.join(site.dir, f)), f"{f} left out")
        t.step("Headers: CORS everywhere, immutable only under the tag")
        root = urllib.request.urlopen(site.url + "/components/ui-todo-item.js").headers
        tag = urllib.request.urlopen(f"{site.url}/{VER}/components/ui-todo-item.js").headers
        eq(root["Access-Control-Allow-Origin"], "*", "root CORS")
        eq(tag["Access-Control-Allow-Origin"], "*", "tag CORS")
        eq(root["Cache-Control"], "public, max-age=300", "root follows main")
        eq(tag["Cache-Control"], "public, max-age=31536000, immutable", "tag paths never change")
        check("javascript" in tag["Content-Type"], f"module MIME type: {tag['Content-Type']}")
    finally:
        site.close()


@test("publish", "import-from-the-pages-site", gif=False, desc='A blank page on another origin imports a component, tokens.css and swapOutlet from the built Pages site, from the pinned tag path and from the root: the element renders and works, ./_shared imports resolve, and swapOutlet finds components.json next to components/.', needs_idiomorph=True, viewport={"width": 640, "height": 300})
def _(t):
    site = PagesSite()
    try:
        for base in (f"{site.url}/{VER}", site.url):
            reqs = []
            t.page.on("response", lambda r, reqs=reqs: reqs.append((r.url, r.status)))
            t.step(f"Import from {base.replace(site.url, '<pages>') or '<pages>/'}")
            env.pages["/pages-consumer.html"] = consumer(base)
            t.goto("/pages-consumer.html")
            p = t.page
            p.wait_for_function("!!customElements.get('ui-todo-item') && !!window.__swap")
            check(p.locator("#a .check").is_visible(), "ui-todo-item rendered")
            check(any(u == f"{base}/components/_shared/util.js" and s == 200 for u, s in reqs), "./_shared/util.js resolved under the same root")
            eq(p.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--ui-radius').trim()"), "8px", "tokens.css applied")
            t.capture_events("ui-toggle")
            p.click("#a .check")
            eq(t.events("ui-toggle")[-1]["detail"], {"checked": True, "progress": None})
            p.evaluate("window.__swap('<ui-todo-item id=\"n\" text=\"swapped\"></ui-todo-item><ui-bogus id=\"x\"></ui-bogus>')")
            p.wait_for_timeout(400)
            check(p.locator("#n").count() == 1 and p.locator("#x").count() == 0, "swapOutlet used the catalog from the same root")
            check(any(u == f"{base}/components.json" for u, s in reqs), "components.json fetched from the Pages root")
            check(all(s == 200 for u, s in reqs if u.startswith(site.url)), f"every Pages request succeeded: {[x for x in reqs if x[1] != 200]}")
    finally:
        site.close()
