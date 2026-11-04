#!/usr/bin/env python3
"""Run the ui-elements test suites.

    python3 tests/run.py                      everything, headless, offline (online checks skip themselves)
    python3 tests/run.py --suite todo-item    one suite (repeatable)
    python3 tests/run.py -k reorder           tests whose name contains the text
    python3 tests/run.py --gifs               also (re)write tests/media/<suite>-<test>.gif for PASSING tests
    python3 tests/run.py --list               list tests and exit
    python3 tests/run.py --headed --slow      watch it happen

Failures write tests/failures/<suite>-<test>/{failure.gif,filmstrip.png,report.json,console.log}.
A failing test never overwrites its committed GIF. See tests/README.md.
"""
import argparse, glob, importlib, json, os, subprocess, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path[:0] = [HERE, os.path.join(HERE, "kit")]

from playwright.sync_api import sync_playwright
import registry
from registry import env, TESTS
from harness import run_test, Result
from server import serve

IDIO_URL = "https://cdn.jsdelivr.net/npm/idiomorph@0.8.0/dist/idiomorph.esm.js"
IDIO_CACHE = os.path.join(HERE, ".cache", "idiomorph-0.8.0.esm.js")
MEDIA_BUDGET_TOTAL = 15_000_000
ICON = {"passed": "PASS", "failed": "FAIL", "skipped": "SKIP", "pending": "PEND", "known-issue": "KNOWN"}

def online():
    try:
        urllib.request.urlopen("https://cdn.jsdelivr.net/npm/idiomorph@0.8.0/package.json", timeout=4).read(1)
        return True
    except Exception:
        return False

def ensure_idiomorph(is_online):
    """The pinned Idiomorph build is cached under tests/.cache (gitignored) so shell tests run offline."""
    if os.path.exists(IDIO_CACHE):
        return IDIO_CACHE
    if is_online:
        os.makedirs(os.path.dirname(IDIO_CACHE), exist_ok=True)
        with urllib.request.urlopen(IDIO_URL, timeout=15) as r, open(IDIO_CACHE, "wb") as f:
            f.write(r.read())
        return IDIO_CACHE
    return None

def make_setup(spec):
    def setup(t):
        ctx = t.context
        if not spec.online:                                   # offline by default: nothing leaves localhost
            ctx.route(lambda url: not url.startswith(("http://127.0.0.1", "data:", "about:", "blob:")), lambda r: r.abort())
            if env.idiomorph:
                body = open(env.idiomorph, "rb").read()
                ctx.route(IDIO_URL, lambda r: r.fulfill(status=200, body=body, headers={"content-type": "application/javascript", "access-control-allow-origin": "*"}))
    return setup

def run_catalog():
    t0 = time.monotonic()
    p = subprocess.run(["node", os.path.join(ROOT, "scripts", "check-catalog.mjs")], capture_output=True, text=True, cwd=ROOT)
    out = (p.stdout + p.stderr).strip()
    return Result("catalog-integrity", "passed" if p.returncode == 0 else "failed", round(time.monotonic() - t0, 2), out[-1500:])

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--suite", action="append", help="run only this suite (repeatable)")
    ap.add_argument("-k", dest="keyword", help="run tests whose full name contains this text")
    ap.add_argument("--gifs", action="store_true", help="write tests/media GIFs for passing tests")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--table", action="store_true", help="print the markdown table of browser tests and their GIFs (for tests/README.md)")
    ap.add_argument("--headed", action="store_true")
    ap.add_argument("--slow", action="store_true", help="longer on-screen dwell per step (default with --gifs)")
    ap.add_argument("--no-online", action="store_true", help="skip tests that need the internet")
    a = ap.parse_args()

    for f in sorted(glob.glob(os.path.join(HERE, "suites", "*.py"))):
        sys.path.insert(0, os.path.join(HERE, "suites"))
        importlib.import_module(os.path.basename(f)[:-3])
    specs = [s for s in TESTS if (not a.suite or s.suite in a.suite) and (not a.keyword or a.keyword in s.full)]
    run_cat = (not a.suite or "catalog" in a.suite) and (not a.keyword or a.keyword in "catalog-integrity")
    if a.table:
        import inspect, re as _re
        by_suite = {}
        for s in specs:
            by_suite.setdefault(s.suite, []).append(s)
        for suite, items in by_suite.items():
            print(f"#### {suite}\n\n<details><summary>{len(items)} recorded tests</summary>\n\n| Test | What the recording shows | Recording |\n|---|---|---|")
            for s in items:
                steps = _re.findall(r't\.step\(f?"([^"]*)"', inspect.getsource(s.fn))
                what = " → ".join(_re.sub(r"\{[^}]*\}", "…", x).replace("|", "/") for x in steps[:4]) + (" → …" if len(steps) > 4 else "")
                cell = f"![{s.full}](media/{s.full}.gif)" if s.gif else "(no GIF)"
                print(f"| `{s.name}`{' (online)' if s.online else ''} | {what} | {cell} |")
            print("\n</details>\n")
        return 0
    if a.list:
        print("catalog-integrity")
        for s in specs:
            print(s.full + ("  [online]" if s.online else ""))
        return 0

    app, cdn = serve(ROOT), serve(ROOT, cdn_layout=True)
    env.base, env.cdn, env.root, env.pages = app.url, cdn.url, ROOT, app.pages
    env.catalog = json.load(open(os.path.join(ROOT, "components.json")))
    reachable = online()
    env.online = reachable and not a.no_online          # --no-online skips the online *checks*...
    env.idiomorph = ensure_idiomorph(reachable)         # ...but a one-time fetch of the pinned Idiomorph is still fine
    dwell = 0.55 if (a.gifs or a.slow) else 0.05
    results = []
    try:
        if run_cat:
            results.append(run_catalog())
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=not a.headed)
            for spec in specs:
                if spec.online and not env.online:
                    results.append(Result(spec.full, "skipped", message="needs internet (offline or --no-online)")); continue
                if spec.needs_idiomorph and not env.idiomorph:
                    results.append(Result(spec.full, "skipped", message="Idiomorph not cached; run once online to cache it")); continue
                entry = registry.catalog_entry(spec.component) if spec.component else None
                r = run_test(browser, spec.full, lambda t, f=spec.fn: f(t), base_dir=HERE, record_gif=a.gifs and spec.gif,
                             base_url=env.base, catalog_entry=entry, init_scripts=spec.init_scripts, dwell=dwell,
                             known_issue=spec.known_issue, setup=make_setup(spec), **spec.context)
                results.append(r)
                print(f"{ICON[r.status]:5} {r.name:46} {r.seconds:5.1f}s" + (f"  {r.gif_bytes // 1024} KB gif" if r.gif else "")
                      + (f"  {r.message.splitlines()[0][:110]}" if r.message and r.status != "passed" else ""), flush=True)
            browser.close()
    finally:
        app.close(); cdn.close()

    counts = {}
    for r in results:
        counts[r.status] = counts.get(r.status, 0) + 1
    media = sum(os.path.getsize(f) for f in glob.glob(os.path.join(HERE, "media", "*.gif")))
    print("\n" + ", ".join(f"{v} {k}" for k, v in sorted(counts.items())) + f"  | tests/media: {media / 1e6:.1f} MB in {len(glob.glob(os.path.join(HERE, 'media', '*.gif')))} GIFs")
    for r in results:
        if r.status == "failed":
            print(f"\nFAILED {r.name}: {r.message}\n  bundle: {r.bundle}" if r.bundle else f"\nFAILED {r.name}:\n{r.message}")
    if media > MEDIA_BUDGET_TOTAL:
        print(f"ERROR: tests/media is {media / 1e6:.1f} MB, over the {MEDIA_BUDGET_TOTAL / 1e6:.0f} MB budget"); return 1
    return 1 if counts.get("failed") else 0

if __name__ == "__main__":
    sys.exit(main())
