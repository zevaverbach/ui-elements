"""Suite D: the outlet sanitizer, table-driven. Each case is run through sanitizeHtml(), then the result is
inserted into a live page to prove that nothing executes. Payloads set window.__pwned."""
from registry import test, env, open_fixture
from helpers import check, eq

P = "window.__pwned = (window.__pwned || 0) + 1"
NOSP = "window.__pwned=1"        # no spaces: unquoted attribute values end at the first space
TAGS = ["ui-todo-item", "ui-chat-panel", "ui-store", "ui-each"]

# (name, input html, substrings that must NOT appear in the output (lowercase), substrings that must appear)
CASES = [
    # --- script and other dangerous elements
    ("script element",               f"<div>a<script>{P}</script>b</div>",                         ["<script", "__pwned"], ["a", "b"]),
    ("SCRIPT upper case",            f"<DIV>a<SCRIPT>{P}</SCRIPT>b</DIV>",                         ["<script", "__pwned"], ["a", "b"]),
    ("script with attributes",       f'<script type="text/javascript" src="https://evil.test/x.js"></script><p>ok</p>', ["<script", "evil.test"], ["<p>ok</p>"]),
    ("split script tag",             f"<scr<script>ipt>{P}</scr</script>ipt>",                     ["<script"], []),
    ("script in svg",                f"<svg><script>{P}</script></svg><p>ok</p>",                  ["<script", "<svg"], ["<p>ok</p>"]),
    ("iframe",                       '<iframe src="https://evil.test"></iframe><p>ok</p>',        ["<iframe", "evil.test"], ["<p>ok</p>"]),
    ("iframe srcdoc",                f'<iframe srcdoc="<script>{P}</script>"></iframe>',           ["<iframe", "srcdoc"], []),
    ("object",                       '<object data="x.swf"></object><p>ok</p>',                    ["<object", "x.swf"], ["<p>ok</p>"]),
    ("embed",                        '<embed src="x.swf"><p>ok</p>',                               ["<embed"], ["<p>ok</p>"]),
    ("style element",                '<style>body{display:none}</style><p>ok</p>',                  ["<style"], ["<p>ok</p>"]),
    ("link and meta",                '<link rel="stylesheet" href="https://evil.test/x.css"><meta http-equiv="refresh" content="0;url=https://evil.test"><p>ok</p>', ["<link", "<meta", "evil.test"], ["<p>ok</p>"]),
    ("base tag",                     '<base href="https://evil.test/"><p>ok</p>',                   ["<base", "evil.test"], ["<p>ok</p>"]),
    ("form with javascript action",  f'<form action="javascript:{P}"><button>go</button></form>',  ["<form", "javascript:"], []),
    # --- on* attributes
    ("onclick",                      f'<div onclick="{P}">x</div>',                                ["onclick", "__pwned"], ["<div>x</div>"]),
    ("ONCLICK upper case",           f'<div ONCLICK="{P}">x</div>',                                ["onclick", "__pwned"], ["x"]),
    ("onerror on img",               f'<img src="x" onerror="{P}">',                               ["onerror", "__pwned"], ["<img"]),
    ("unquoted handler",             f"<img src=x onerror={NOSP}>",                                ["onerror="], ["<img"]),
    ("slash separators",             f"<img/src=x/onerror={NOSP}>",                                [" onerror"], []),
    ("autofocus + onfocus",          f'<input autofocus onfocus="{P}">',                           ["onfocus", "__pwned"], ["<input"]),
    ("handler on a ui-* tag",        f'<ui-todo-item text="a" onclick="{P}" onmouseover="{P}"></ui-todo-item>', ["onclick", "onmouseover", "__pwned"], ['<ui-todo-item text="a"']),
    ("handler on ui-each",           f'<ui-each store="s" tag="ui-todo-item" onfocus="{P}"></ui-each>', ["onfocus"], ["<ui-each"]),
    ("svg onload",                   f'<svg onload="{P}"></svg><p>ok</p>',                         ["onload", "<svg"], ["<p>ok</p>"]),
    # --- URLs
    ("javascript: href",             f'<a href="javascript:{P}">x</a>',                            ["javascript:"], ["<a>x</a>"]),
    ("JaVaScRiPt: mixed case",       f'<a href="JaVaScRiPt:{P}">x</a>',                            ["javascript:"], ["x"]),
    ("tab/newline inside scheme",    f'<a href="java&#9;script:{P}">x</a>',                        ["script:"], ["x"]),
    ("leading control chars",        f'<a href="&#1;&#32;javascript:{P}">x</a>',                   ["javascript:"], ["x"]),
    ("entity-encoded scheme",        f'<a href="&#106;avascript:{P}">x</a>',                       ["javascript:", "&#106;"], ["x"]),
    ("hex entity scheme",            f'<a href="&#x6A;avascript:{P}">x</a>',                       ["javascript:"], ["x"]),
    ("vbscript:",                    '<a href="vbscript:msgbox(1)">x</a>',                         ["vbscript:"], ["x"]),
    ("data:text/html",               '<a href="data:text/html,<script>1</script>">x</a>',          ["data:text/html"], ["x"]),
    ("javascript: on img src",       f'<img src="javascript:{P}">',                                ["javascript:"], ["<img"]),
    ("formaction",                   f'<button formaction="javascript:{P}">x</button>',            ["javascript:", "formaction"], ["<button"]),
    ("srcdoc and is= attributes",    '<div srcdoc="x" is="evil-el">t</div>',                       ["srcdoc", "is="], ["t"]),
    # --- nested / malformed / parser tricks
    ("unclosed tags",                '<div><ui-todo-item text="a"',                                 ["<script"], []),
    ("unclosed script",              f"<p>a</p><script>{P}",                                       ["<script", "__pwned"], ["<p>a</p>"]),
    ("handler without closing quote", f'<div onclick="{P}>x</div><p>after</p>',                    ["onclick"], []),
    ("comment trick",                f"<!--><script>{P}</script>-->",                              ["<script", "__pwned"], []),
    ("noscript mutation (mXSS)",     f'<noscript><p title="</noscript><img src=x onerror={P}>">',  ["onerror", "<noscript"], []),
    ("math/style mutation (mXSS)",   f"<math><mtext><table><mglyph><style><img src=x onerror={P}>", ["onerror", "<style", "<math"], []),
    ("svg CDATA trick",              f"<svg><desc><![CDATA[</desc><script>{P}</script>]]></svg>",  ["<script", "<svg"], []),
    ("template element",             f"<template><script>{P}</script></template><p>ok</p>",        ["<template", "<script"], ["<p>ok</p>"]),
    ("deeply nested",                "<div>" * 60 + f'<img src=x onerror="{P}">' + "</div>" * 60,  ["onerror"], ["<img"]),
    ("script after ui-* siblings",   f'<ui-todo-item text="a"></ui-todo-item><script>{P}</script><ui-todo-item text="b"></ui-todo-item>', ["<script"], ['text="a"', 'text="b"']),
    # --- things that must survive
    ("ui-* tags and attributes",     '<ui-todo-item id="x" text="Buy milk" checked label="L" progress="50"></ui-todo-item><ui-chat-panel heading="Hi" open></ui-chat-panel>', [], ['<ui-todo-item id="x" text="Buy milk" checked="" label="L" progress="50"', '<ui-chat-panel heading="Hi" open=""']),
    ("ui-each JSON attributes",      '<ui-each id="e" store="s" tag="ui-todo-item" map=\'{"text":"text"}\' events=\'{"ui-toggle":{"action":"toggle","field":"done"}}\' where=\'{"done":false}\'></ui-each>', [], ['<ui-each id="e"', 'map="{&quot;text&quot;:&quot;text&quot;}"']),
    ("layout and text tags",         '<main><section><h1>T</h1><p>a <b>b</b> <i>c</i> <code>d</code></p><ul><li>x</li></ul><table><tbody><tr><td>c</td></tr></tbody></table><button type="button">B</button></section></main>', [], ["<main>", "<h1>T</h1>", "<b>b</b>", "<li>x</li>", "<td>c</td>", "<button"]),
    ("https and relative links",     '<a href="https://example.com/x?y=1">a</a><a href="#top">b</a><a href="/docs">c</a><img src="data:image/png;base64,AAAA" alt="">', [], ['href="https://example.com/x?y=1"', 'href="#top"', 'href="/docs"', "data:image/png"]),
    ("data and aria attributes",     '<div data-role="agent" aria-label="x" slot="meta" style="color:red">t</div>', [], ['data-role="agent"', 'aria-label="x"', 'slot="meta"']),
    ("JSON seed inside ui-store",    '<ui-store name="s"><script type="application/json" onload="x()">{"items":[]}</script></ui-store>', ["onload"], ['<script type="application/json">{"items":[]}</script>']),
    ("JSON script elsewhere dropped", '<div><script type="application/json">{}</script></div>',   ["<script"], []),
    ("JS script inside ui-store",    f'<ui-store name="s"><script>{P}</script></ui-store>',        ["<script", "__pwned"], ["<ui-store"]),
    ("unknown element is unwrapped", "<blink>keep me</blink>",                                      ["<blink"], ["keep me"]),
    ("non-ui custom element dropped", '<x-evil>t</x-evil><ui-todo-item text="a"></ui-todo-item>',  ["x-evil"], ["<ui-todo-item"]),
]

@test("sanitizer", "table-driven", desc='A table of 51 markup cases: dangerous markup is removed, ui-* and layout tags are kept, and each case also inserted into a live page runs nothing.', init_scripts=[], viewport={"width": 640, "height": 420})
def _(t):
    t.allow_console("Failed to load resource")   # surviving <img src="x"> / blocked external URLs are inserted for real
    open_fixture(t)
    p = t.page
    t.step(f"{len(CASES)} cases: dangerous markup removed, ui-* and layout tags kept")
    failures = []
    for i, (name, html, forbid, keep) in enumerate(CASES, 1):
        t.dwell = 0.0 if i % 4 else 0.12                                  # keep the recording short; show every 4th case
        if i % 4 == 0 or i == len(CASES):
            t.step(f"[{i}/{len(CASES)}] {name}")
        out = p.evaluate("([h, tags]) => window.__lib.sanitizeHtml(h, {allowedTags: tags})", [html, TAGS])
        low = out.lower()
        bad = [f for f in forbid if f.lower() in low]
        missing = [k for k in keep if k not in out]
        # now run it for real: insert the sanitized output into the page and look for side effects
        p.evaluate("(h) => { window.__pwned = 0; document.getElementById('root').innerHTML = h; }", out)
        p.wait_for_timeout(40)
        pwned = p.evaluate("window.__pwned")
        # idempotent: sanitizing the output again changes nothing
        again = p.evaluate("([h, tags]) => window.__lib.sanitizeHtml(h, {allowedTags: tags})", [out, TAGS])
        if bad or missing or pwned or again != out:
            failures.append(f"{name}: " + "; ".join(filter(None, [f"output still contains {bad}" if bad else "", f"output lacks {missing}" if missing else "", "CODE EXECUTED" if pwned else "", "not idempotent" if again != out else ""])) + f"\n      input:  {html[:120]}\n      output: {out[:160]}")
    p.evaluate("document.getElementById('root').innerHTML = ''")
    t.step("Result: " + ("all cases pass" if not failures else f"{len(failures)} failing"))
    check(not failures, f"{len(failures)} sanitizer case(s) failed:\n  " + "\n  ".join(failures))

@test("sanitizer", "allowlist-comes-from-the-catalog", desc='swapOutlet allows only the tags listed in components.json, and rejects a missing outlet with a clear error.')
def _(t):
    open_fixture(t)
    p = t.page
    t.step("swapOutlet only allows tags listed in components.json")
    p.evaluate("document.getElementById('root').innerHTML = '<main id=\"outlet\"></main>'")
    p.evaluate("window.__lib.swapOutlet('<ui-todo-item id=\"ok\" text=\"a\"></ui-todo-item><ui-not-in-catalog id=\"bad\"></ui-not-in-catalog><p>kept</p>')")
    p.wait_for_timeout(300)
    check(p.locator("#ok").count() == 1, "catalog tag kept")
    check(p.locator("#bad").count() == 0, "tag missing from the catalog removed")
    check(p.locator("#outlet >> text=kept").count() == 1, "plain tags kept")
    t.step("swapOutlet rejects a missing outlet with a clear error")
    err = p.evaluate("window.__lib.swapOutlet('<p>x</p>', {outlet: '#nope'}).then(() => 'resolved', (e) => e.message)")
    check("no element matches" in err, err)
