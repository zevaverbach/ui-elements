#!/usr/bin/env python3
"""Check an agent-generated page (or a written component request) against a task. No LLM calls.

    python3 tests/agent-evals/check.py --task shopping-list --html out/shopping-list.html
    python3 tests/agent-evals/check.py --task needs-new-behavior --request out/needs-new-behavior.request.md

What is verified for a page (each failure has a short code, shown in brackets):
  static     only tags from components.json plus plain layout/text tags         [unknown-tag, disallowed-tag]
             only documented attributes on ui-* tags                             [undocumented-attribute]
             no <script> except library module imports and ui-store JSON seeds  [inline-script, foreign-script, script-in-outlet]
             no on* handlers, no javascript: URLs                                [inline-handler, javascript-url]
             a module import for every component used                            [missing-module-import]
             ui-each/ui-store wiring is valid JSON and refers to real stores     [bad-json-attribute, missing-store, bad-action]
             shell layout: stores and chat panel outside <main id="outlet">      [no-outlet, shell-in-outlet]
  browser    the page loads with no console errors (library imports are served  [console-error]
             from the local checkout, nothing else leaves the machine)
             the task's own Playwright assertions pass                           [assertion-failed]
For a task of kind "request" the correct answer is a written request for a new component, not code  [request-incomplete].
"""
import argparse, json, os, re, sys
from html.parser import HTMLParser

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path[:0] = [os.path.join(ROOT, "tests", "kit"), os.path.join(ROOT, "tests")]

VOID = set("area base br col embed hr img input link meta param source track wbr".split())
GLOBAL_ATTRS = {"id", "class", "style", "slot", "hidden", "title", "lang", "tabindex", "role", "part", "dir"}
STRUCTURE = {"html", "head", "body", "title", "meta", "link", "style", "script"}   # allowed outside the outlet only
ACTIONS = {"add", "remove", "update", "toggle", "move", "set", "clear"}
CDN_RE = re.compile(r"^https://cdn\.jsdelivr\.net/gh/zevaverbach/ui-elements@[^/]+/components/(ui-[a-z-]+)\.js$")

def load_catalog():
    return json.load(open(os.path.join(ROOT, "components.json")))

def plain_tags():
    """The sanitizer's own list of plain tags, so the checker cannot drift from it."""
    src = open(os.path.join(ROOT, "components", "_shared", "outlet.js")).read()
    return set(re.search(r"const PLAIN = new Set\(`([^`]*)`", src).group(1).split())

class Scan(HTMLParser):
    """Collects every element with attributes, whether it is inside the outlet, and script info."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.elements, self.outlet_depth = [], [], None
        self.has_outlet = False

    def handle_starttag(self, tag, attrs):
        a = {k: (v if v is not None else "") for k, v in attrs}
        inside = self.outlet_depth is not None
        parent = self.stack[-1] if self.stack else None
        self.elements.append({"tag": tag, "attrs": a, "in_outlet": inside, "parent": parent})
        if tag == "main" and a.get("id") == "outlet":
            self.has_outlet = True
            self.outlet_depth = len(self.stack) + 1
            self.elements[-1]["in_outlet"] = False          # the <main> itself belongs to the shell
        if tag not in VOID:
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID and self.stack and self.stack[-1] == tag:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag in self.stack:
            while self.stack:
                top = self.stack.pop()
                if self.outlet_depth is not None and len(self.stack) < self.outlet_depth:
                    self.outlet_depth = None
                if top == tag:
                    break

def static_issues(html, catalog, task):
    issues = []
    add = lambda code, msg: issues.append({"code": code, "message": msg})
    comps = {c["tag"]: c for c in catalog["components"]}
    allowed_plain = plain_tags()
    scan = Scan(); scan.feed(html)
    store_names = {e["attrs"].get("name") for e in scan.elements if e["tag"] == "ui-store"}
    imported = set()

    for e in scan.elements:
        tag, a, inside = e["tag"], e["attrs"], e["in_outlet"]
        where = "inside <main id=\"outlet\">" if inside else "in the page"
        for name, val in a.items():
            if name.lower().startswith("on"):
                add("inline-handler", f"<{tag}> has an inline event handler ({name}=...) {where}; handlers are never allowed")
            if name.lower() in ("href", "src", "action", "formaction") and re.sub(r"[\s\x00-\x20]", "", val).lower().startswith(("javascript:", "vbscript:")):
                add("javascript-url", f"<{tag} {name}=...> uses a javascript: URL")
        if tag == "script":
            typ = a.get("type", "").lower()
            if inside:
                if not (typ == "application/json" and e["parent"] == "ui-store"):
                    add("script-in-outlet", f"a <script> inside the swapped region (<main id=\"outlet\">)")
            elif "src" in a:
                m = CDN_RE.match(a["src"])
                if typ != "module" or not m:
                    add("foreign-script", f"script src={a['src']!r} is not a library module import (type=module, .../components/ui-*.js)")
                else:
                    imported.add(m.group(1))
            elif typ == "application/json" and e["parent"] == "ui-store":
                pass
            else:
                add("inline-script", "an inline <script> was found; use the components' attributes and events, or request a new component instead")
            continue
        if tag.startswith("ui-"):
            if tag not in comps:
                add("unknown-tag", f"<{tag}> is not in components.json")
                continue
            documented = {x["name"] for x in comps[tag]["attributes"]}
            for name in a:
                n = name.lower()
                if n in GLOBAL_ATTRS or n.startswith(("aria-", "data-")) or n in documented:
                    continue
                add("undocumented-attribute", f"<{tag}> has attribute '{name}', which components.json does not document for it")
            continue
        if inside:
            if tag not in allowed_plain:
                add("disallowed-tag", f"<{tag}> is not an allowed plain tag inside the outlet")
        elif tag not in allowed_plain and tag not in STRUCTURE:
            add("disallowed-tag", f"<{tag}> is not an allowed tag")

    used = {e["tag"] for e in scan.elements if e["tag"] in comps}
    for e in scan.elements:                                   # ui-each renders other components too
        if e["tag"] == "ui-each" and e["attrs"].get("tag") in comps:
            used.add(e["attrs"]["tag"])
    for tag in sorted(used - imported):
        add("missing-module-import", f"<{tag}> is used but no <script type=\"module\" src=\".../components/{tag}.js\"> imports it")

    for e in scan.elements:
        if e["tag"] != "ui-each":
            continue
        a = e["attrs"]
        if a.get("store") not in store_names:
            add("missing-store", f"<ui-each store=\"{a.get('store')}\"> has no matching <ui-store name=\"...\"> in the page")
        child = a.get("tag")
        if child and child not in comps:
            add("unknown-tag", f"<ui-each tag=\"{child}\"> is not in components.json")
        for attr in ("map", "events", "where"):
            if attr in a:
                try:
                    val = json.loads(a[attr])
                    assert isinstance(val, dict)
                except Exception:
                    add("bad-json-attribute", f"<ui-each {attr}=...> is not a valid JSON object: {a[attr][:80]}"); continue
                if attr == "events":
                    for ev, spec in val.items():
                        if not isinstance(spec, dict) or spec.get("action") not in ACTIONS:
                            add("bad-action", f"<ui-each events> maps {ev} to {spec!r}; action must be one of {sorted(ACTIONS)}")
                if attr == "map" and child in comps:
                    ok = {x["name"] for x in comps[child]["attributes"]}
                    for k in val:
                        if k not in ok:
                            add("undocumented-attribute", f"<ui-each map> sets '{k}' on <{child}>, which does not document it")
    for e in scan.elements:
        if e["tag"] == "ui-chat-panel" and e["attrs"].get("store") and e["attrs"]["store"] not in store_names:
            add("missing-store", f"<ui-chat-panel store=\"{e['attrs']['store']}\"> has no matching <ui-store>")

    if task.get("shell"):
        if not scan.has_outlet:
            add("no-outlet", "the page has no <main id=\"outlet\">")
        for e in scan.elements:
            if e["in_outlet"] and e["tag"] in ("ui-store", "ui-chat-panel"):
                add("shell-in-outlet", f"<{e['tag']}> belongs in the stable shell, outside <main id=\"outlet\">")
    return issues

def request_issues(text, catalog, task):
    issues = []
    add = lambda msg: issues.append({"code": "request-incomplete", "message": msg})
    tags = {c["tag"] for c in catalog["components"]}
    proposed = set(re.findall(r"`(ui-[a-z][a-z-]*)`|<(ui-[a-z][a-z-]*)", text))
    proposed = {x for pair in proposed for x in pair if x} - tags
    low = text.lower()
    if not proposed:
        add("it must propose a NEW component tag (a ui-* name not already in components.json)")
    for heading in ("attributes", "events"):
        if heading not in low:
            add(f"it must describe the proposed component's {heading}")
    for word in task.get("must_mention", []):
        if word.lower() not in low:
            add(f"it must explain the missing capability (mention '{word}')")
    if not any(t in text for t in tags):
        add("it must say why existing components are not enough (name at least one existing ui-* tag)")
    if len(text.split()) < 60:
        add("it is too short to be an actionable request (<60 words)")
    if re.search(r"<script|\son\w+\s*=", text, re.I) and "do not" not in low and "never" not in low:
        add("it must not contain inline script")
    return issues

def run_assertions(t, task, page_url):
    """Run the task's DSL in a Session `t`. Raises AssertionError with a clear message."""
    p = t.page
    for step in task.get("assert", []):
        t.step(step["step"])
        if "wait" in step:
            p.wait_for_timeout(step["wait"])
        if "click" in step:
            p.click(step["click"])
        if "fill" in step:
            p.fill(step["fill"], step["text"])
        if "eval" in step:
            got = p.evaluate("(async () => { return (" + step["eval"] + "); })()")
            want = step.get("equals", True)
            if got != want:
                raise AssertionError(f"[assertion-failed] step '{step['step']}': expected {json.dumps(want)}, got {json.dumps(got)}\n  js: {step['eval'][:200]}")

CDN_ROUTE = re.compile(r"^https://cdn\.jsdelivr\.net/gh/zevaverbach/ui-elements@[^/]+/(.*)$")
IDIOMORPH = "https://cdn.jsdelivr.net/npm/idiomorph@0.8.0/dist/idiomorph.esm.js"
MIME = {".js": "application/javascript", ".css": "text/css", ".json": "application/json"}

def install_routes(t, idiomorph_path=None):
    """Serve the library from the local checkout under the documented CDN URL shape; block everything else."""
    ctx = t.context
    ctx.route(lambda url: not url.startswith(("data:", "about:", "blob:")), lambda r: r.abort())
    if idiomorph_path and os.path.exists(idiomorph_path):
        body = open(idiomorph_path, "rb").read()
        ctx.route(IDIOMORPH, lambda r: r.fulfill(status=200, body=body, headers={"content-type": "application/javascript", "access-control-allow-origin": "*"}))
    def local(route):
        rel = CDN_ROUTE.match(route.request.url).group(1)
        path = os.path.normpath(os.path.join(ROOT, rel))
        if not path.startswith(ROOT) or not os.path.isfile(path):
            return route.fulfill(status=404, body="not found")
        route.fulfill(status=200, body=open(path, "rb").read(), headers={"content-type": MIME.get(os.path.splitext(path)[1], "text/plain"), "access-control-allow-origin": "*"})
    ctx.route(CDN_ROUTE, local)

def load_task(task_id):
    return json.load(open(os.path.join(HERE, "tasks", f"{task_id}.json")))

def browser_check(t, html, task, idiomorph_path=None):
    """Load the page in the Session's browser and run the task's assertions. Returns issues (does not raise)."""
    install_routes(t, idiomorph_path)
    t.page.route("http://eval.test/page.html", lambda r: r.fulfill(status=200, body=html, content_type="text/html"))
    t.step("Load the generated page")
    t.page.goto("http://eval.test/page.html")
    t.page.wait_for_timeout(900)
    bad = [c for c in t.console if c["type"] in ("error", "pageerror", "requestfailed")]
    if bad:
        return [{"code": "console-error", "message": "the page logged errors while loading: " + "; ".join(c["text"][:140] for c in bad[:3])}]
    try:
        run_assertions(t, task, "http://eval.test/page.html")
    except AssertionError as e:
        return [{"code": "assertion-failed", "message": str(e).replace("[assertion-failed] ", "")}]
    return []

def check_output(t, task, html=None, request=None, catalog=None, idiomorph_path=None):
    """Full check. Returns {passed, issues}. `t` is a harness Session (only needed for page tasks)."""
    catalog = catalog or load_catalog()
    issues = []
    if task.get("kind") == "request":
        if html:
            issues += static_issues(html, catalog, {"shell": False})
        if request is None:
            issues.append({"code": "request-incomplete", "message": "this task needs a written request for a new component (--request FILE)"})
        else:
            issues += request_issues(request, catalog, task)
        return {"task": task["id"], "passed": not issues, "issues": issues}
    if html is None:
        return {"task": task["id"], "passed": False, "issues": [{"code": "no-output", "message": "no HTML file was provided"}]}
    issues += static_issues(html, catalog, task)
    if not issues:                                   # only spend a browser on markup that is structurally sound
        issues += browser_check(t, html, task, idiomorph_path)
    return {"task": task["id"], "passed": not issues, "issues": issues}

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--task", required=True)
    ap.add_argument("--html"); ap.add_argument("--request")
    ap.add_argument("--json", action="store_true", help="print the report as JSON")
    a = ap.parse_args()
    task = load_task(a.task)
    html = open(a.html).read() if a.html else None
    req = open(a.request).read() if a.request else None
    from playwright.sync_api import sync_playwright
    from harness import Session
    import tempfile
    result = None
    with sync_playwright() as p:
        browser = p.chromium.launch()
        s = Session(browser, f"eval-{a.task}", tempfile.mkdtemp(), dwell=0)
        cache = os.path.join(ROOT, "tests", ".cache", "idiomorph-0.8.0.esm.js")
        result = check_output(s, task, html, req, idiomorph_path=cache)
        s.context.close(); browser.close()
    if a.json:
        print(json.dumps(result, indent=2))
    else:
        print(("PASS " if result["passed"] else "FAIL ") + a.task)
        for i in result["issues"]:
            print(f"  [{i['code']}] {i['message']}")
    return 0 if result["passed"] else 1

if __name__ == "__main__":
    sys.exit(main())
