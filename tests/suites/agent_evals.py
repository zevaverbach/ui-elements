"""Suite F: agent composition evals. The golden solutions must pass the checker; every kind of bad output must be rejected
with the right reason. No LLM is involved: this proves the checker works, so it can be trusted on real agent output."""
import html as htmllib, json, os, re, subprocess, sys, tempfile
from registry import test, env
from helpers import check, eq
from video_to_gif import TEXT_LADDER

EVALS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "agent-evals")
sys.path.insert(0, EVALS)
import check as ev   # tests/agent-evals/check.py

golden = lambda name, ext=".html": open(os.path.join(EVALS, "golden", name + ext)).read()
IDIO = os.path.join(os.path.dirname(EVALS), ".cache", "idiomorph-0.8.0.esm.js")

def explain(res):
    return "; ".join(f"[{i['code']}] {i['message']}" for i in res["issues"])

GOLDEN_DESC = {
    "shopping-list": "The reference page for the shopping-list task (two filtered views of one store plus a chat panel) passes the checker: only catalog tags, no script, stores and lists wired correctly, and the task's own browser assertions hold.",
    "todo-progress": "The reference page for the release-checklist task (three to-dos with progress steps, no store) passes the checker and its browser assertions.",
    "chat-left": "The reference page for the support-chat task (a chat panel that opens from the left with a placeholder and a first message) passes the checker and its browser assertions.",
    "kanban": "The reference page for the three-column board task (filtered views of one store, with confirm-to-delete) passes the checker and its browser assertions.",
    "timer-60": "The reference page for the 60-second timer task (a ui-countdown with a \"Time's up!\" done slot, no script) passes the checker: it starts on click, counts down, and at zero fires ui-done and shows the done slot.",
    "glance-dashboard": "The reference page for the \"is everything okay?\" dashboard (three ui-status rows bound to one store, no script) passes the checker: the rows show ok, warn and ok in text, and when the store reports the server down that row turns bad live.",
    "sprint": "The reference page for the afternoon-sprint task (five store-backed to-dos, a 2-hour countdown, and a progress ring with heading, standup meta, picture and \"Shipped!\" done slot) passes the checker: ticking the to-dos moves the ring, and ticking all of them fills it and shows the done slot.",
    "workout": "The reference page for the workout task (four headed groups of three sets from one store, a sets-done progress, a 90-second Rest timer and the 45 minutes) passes the checker: the rest timer starts on click and counts down, 7 ticked sets read 7 of 12, and all 12 show the done slot.",
    "errands": "The reference page for the errand-run task (three headed stops whose sub-tasks are filtered views of one store, a store-bound progress bar and a ui-countdown until=\"13:00\") passes the checker: the countdown runs by itself and lands on 1:00 pm, and ticking every sub-task fills the bar and shows the done slot.",
}

def golden_test(task_id, **kw):
    @test("agent-evals", f"golden-{task_id}", desc=GOLDEN_DESC[task_id], needs_idiomorph=True, viewport={"width": 640, "height": 420}, **kw)
    def _(t):
        task = ev.load_task(task_id)
        t.step(f"Task: {task['title']}")
        res = ev.check_output(t, task, html=golden(task_id), idiomorph_path=IDIO)
        t.step("Verdict: " + ("PASS" if res["passed"] else "FAIL " + explain(res)[:90]))
        check(res["passed"], f"golden solution for {task_id} was rejected: {explain(res)}")
    return _

PAGE_TASKS = ("shopping-list", "todo-progress", "chat-left", "kanban", "timer-60", "glance-dashboard")
# tests/media is close to its 15 MB budget: the newest recordings use cheaper GIF settings.
CHEAP = {"gif_ladder": [(4, 480, 48), (3, 400, 32)]}   # enough colors to keep warn and bad apart
for _id in PAGE_TASKS:
    golden_test(_id, **(CHEAP if _id == "glance-dashboard" else {}))
# tests/media is at its 15 MB budget, so the newer goldens are not recorded (the checker's own steps are the evidence).
for _id in ("sprint", "workout", "errands"):
    golden_test(_id, gif=False)

# Request-kind checks load no page of their own, so the recording would be a blank screen with captions. They put the
# evidence on screen instead: the answer being judged and the checker's verdict, one table row per check. Rows are added
# in place (no reloads) and text is kept short: dense, changing text makes every video frame differ and blows the GIF budget.
BOARD = """<!doctype html><meta charset="utf-8"><style>
body{margin:0;padding:10px 14px 56px;background:#0f1117;color:#e6e6e6;font:13px/1.35 system-ui,sans-serif}
h1{font-size:14px;margin:0 0 6px;color:#9aa4b2;font-weight:600}
pre{margin:0 0 8px;padding:6px 10px;background:#171a22;border:1px solid #2a2f3a;border-radius:6px;white-space:pre-wrap;
font:12px/1.35 ui-monospace,monospace;color:#c9d1d9}pre:empty{display:none}
table{border-collapse:collapse;width:100%%}th,td{text-align:left;padding:3px 6px;border-bottom:1px solid #2a2f3a;vertical-align:top}
td+td{white-space:nowrap}th{color:#9aa4b2;font-weight:600}code{display:block;font:11px ui-monospace,monospace;color:#8b949e;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:300px}.ok{color:#7ee2a0}.bad{color:#ff9d9d}</style>
<h1>%s</h1><pre id="answer"></pre><table><thead><tr>%s</tr></thead><tbody id="rows"></tbody></table>"""

def board(t, title, *columns):
    page = BOARD % (htmllib.escape(title), "".join(f"<th>{htmllib.escape(c)}</th>" for c in columns))
    t.page.route("http://eval.test/board.html", lambda r: r.fulfill(status=200, body=page, content_type="text/html"))
    t.page.goto("http://eval.test/board.html")

def show(t, answer, chars=240):
    """Show (the start of) the answer being judged."""
    answer = re.sub(r"\n\s*\n", "\n", answer.strip()) if answer else "(nothing submitted)"
    answer = answer if len(answer) <= chars else answer[:chars].rsplit(" ", 1)[0] + " ..."
    t.page.evaluate("(s) => { document.getElementById('answer').textContent = s }", answer)

def row(t, cells, ok, excerpt=None):
    """Append a table row (optionally with an excerpt of the answer under the first cell); the last cell gets a check mark (ok) or a cross."""
    t.page.evaluate("""([cells, ok, excerpt]) => {
      const tr = document.createElement('tr');
      cells.forEach((c, i) => { const td = tr.insertCell(); td.textContent = c; });
      const last = tr.cells[cells.length - 1];
      last.textContent = (ok ? '\u2713 ' : '\u2717 ') + last.textContent; last.className = ok ? 'ok' : 'bad';
      if (excerpt) tr.cells[0].append(Object.assign(document.createElement('code'), {textContent: excerpt}));
      document.getElementById('rows').append(tr);
    }""", [cells, ok, excerpt])

def codes(res):
    return "PASS" if res["passed"] else ", ".join(sorted({i["code"] for i in res["issues"]}))

# The one task no component can do. When a component for it ships, convert this task to a page task and add a new
# request task for something still missing (see tests/agent-evals/README.md, "The request task").
IMPOSSIBLE = "recipe-rating"

@test("agent-evals", "golden-recipe-rating-is-a-request", desc='For a task that needs an input the library does not have (rate recipes 1 to 5 stars, by pointer and keyboard, saved into a store), the correct answer is a written request for a new component (ui-rating), and the checker accepts it (no recording: the control row of the cheating test below shows the same verdict).', gif=False, viewport={"width": 640, "height": 380})
def _(t):
    task = ev.load_task(IMPOSSIBLE)
    good = golden(IMPOSSIBLE, ".request.md")
    board(t, "Request task: " + task["title"], "Submitted", "Checker")
    show(t, "Task prompt: " + task["prompt"], chars=200)
    t.step("Task: a star rating input that no component can do")
    outline = [l for l in good.splitlines() if l.startswith(("#", "**"))]   # headings: what the checker looks for
    show(t, "request.md, outline:\n" + "\n".join(l[:60] for l in outline), chars=400)
    t.step("Correct output: a written request for a new component, no script")
    res = ev.check_output(t, task, request=good)
    row(t, ["request.md (no page, no script)", codes(res)], res["passed"])
    t.step("Verdict: PASS (the request names a new tag, attributes, events and why nothing existing fits)")
    check(res["passed"], explain(res))

# (name, task, mutate(html) -> html, expected issue code)
SHOP = "shopping-list"
def ins_before(marker, text): return lambda h: h.replace(marker, text + marker, 1)
MUTATIONS = [
    ("inline script in the outlet",        SHOP, ins_before("</main>", "<script>document.title = 'x'</script>"), "script-in-outlet"),
    ("inline script in the page",          SHOP, ins_before("</body>", "<script>document.title = 'x'</script>"), "inline-script"),
    ("onclick handler",                    SHOP, lambda h: h.replace("<h1>Shopping list</h1>", "<h1 onclick=\"alert(1)\">Shopping list</h1>"), "inline-handler"),
    ("javascript: URL",                    SHOP, ins_before("</main>", "<a href=\"javascript:alert(1)\">x</a>"), "javascript-url"),
    ("invented component",                 SHOP, lambda h: h.replace("<h2>To buy</h2>", "<ui-fancy-title>To buy</ui-fancy-title>"), "unknown-tag"),
    ("undocumented attribute",             SHOP, lambda h: h.replace('<ui-chat-panel id="chat"', '<ui-chat-panel sparkle="yes" id="chat"'), "undocumented-attribute"),
    ("component used but not imported",    SHOP, lambda h: "\n".join(l for l in h.split("\n") if "ui-each.js" not in l), "missing-module-import"),
    ("ui-each points at a missing store",  SHOP, lambda h: h.replace('store="shopping" tag', 'store="nope" tag', 1), "missing-store"),
    ("invalid JSON in where=",              SHOP, lambda h: h.replace("where='{\"done\":false}'", "where='{done:false}'"), "bad-json-attribute"),
    ("unknown store action",               SHOP, lambda h: h.replace('"action":"toggle"', '"action":"explode"', 1), "bad-action"),
    ("chat panel inside the outlet",       SHOP, lambda h: h.replace('<main id="outlet">', '<main id="outlet">\n<ui-chat-panel id="x" heading="x" open></ui-chat-panel>'), "shell-in-outlet"),
    ("no outlet at all",                   SHOP, lambda h: h.replace('<main id="outlet">', "<main>"), "no-outlet"),
    ("script from another origin",         SHOP, ins_before("</head>", '<script type="module" src="https://evil.test/x.js"></script>'), "foreign-script"),
    ("tag that is not allowed",            SHOP, ins_before("</main>", "<marquee>hi</marquee>"), "disallowed-tag"),
    ("page logs a console error",          SHOP, ins_before("</main>", '<img alt="" src="https://cdn.jsdelivr.net/gh/zevaverbach/ui-elements@main/nope.png">'), "console-error"),
    ("task assertions fail (item missing)", SHOP, lambda h: h.replace('{"id":"2","text":"Eggs","done":false},', ""), "assertion-failed"),
    ("wrong view (no done filter)",        SHOP, lambda h: h.replace("where='{\"done\":true}'", ""), "assertion-failed"),
]

@test("agent-evals", "checker-rejects-bad-output", desc='Each of a set of deliberately broken pages (unknown tags, script, on* handlers, broken wiring, missing ids and so on) is rejected by the checker with the right reason.', needs_idiomorph=True, viewport={"width": 640, "height": 420})
def _(t):
    t.allow_console("Failed to load resource", "net::ERR")
    task = ev.load_task(SHOP)
    base = golden(SHOP)
    check(ev.check_output(t, task, html=base, idiomorph_path=IDIO)["passed"], "the unmodified golden must pass first")
    wrong = []
    for i, (name, tid, mutate, code) in enumerate(MUTATIONS, 1):
        t.dwell = 0.0 if i % 3 else 0.1
        if i % 3 == 0 or i == len(MUTATIONS):
            t.step(f"[{i}/{len(MUTATIONS)}] bad output: {name} -> expect [{code}]")
        mutated = mutate(base)
        check(mutated != base, f"mutation '{name}' did not change the page")
        res = ev.check_output(t, task, html=mutated, idiomorph_path=IDIO)
        codes = {x["code"] for x in res["issues"]}
        if res["passed"] or code not in codes:
            wrong.append(f"{name}: expected [{code}], checker said {sorted(codes) or 'PASS'}")
    t.step("Result: " + ("every bad output was rejected for the right reason" if not wrong else f"{len(wrong)} wrong verdicts"))
    check(not wrong, "checker verdicts were wrong:\n  " + "\n  ".join(wrong))

@test("agent-evals", "checker-rejects-cheating-on-the-impossible-task", desc='Answering the impossible task (star ratings) with inline script, an onclick handler, to-do progress steps dressed up as stars, or a request that proposes nothing new, only an existing tag, or ignores the rating, the store or the keyboard is rejected; only a proper component request passes.', gif_ladder=[(4, 560, 8), (3, 480, 8)], viewport={"width": 640, "height": 420})
def _(t):
    task = ev.load_task(IMPOSSIBLE)
    good = golden(IMPOSSIBLE, ".request.md")
    stars = ("<main id='outlet'><ui-todo-item text='Lentil soup' progress='75'></ui-todo-item>"
             "<ui-todo-item text='Shakshuka' progress='50'></ui-todo-item></main>")
    cases = [
        ("inline script instead of a request",  dict(html="<main id='outlet'><p id='stars'>*****</p><script>stars.onclick=()=>{}</script></main>", request=good), "script-in-outlet"),
        ("onclick instead of a request",        dict(html="<main id='outlet'><button onclick=\"rate(3)\">3 stars</button></main>", request=good), "inline-handler"),
        ("to-do steps dressed up as stars",     dict(html=stars, request=None), "request-incomplete"),
        ("no request at all",                   dict(html=None, request=None), "request-incomplete"),
        ("a request that proposes nothing new", dict(request="I rated the recipes with ui-todo-item progress steps and ui-each over a store. It works. " * 8), "request-incomplete"),
        ("proposes an existing tag only",       dict(request=good.replace("`ui-rating-change`", "a change event").replace("ui-rating", "ui-progress")), "request-incomplete"),
        ("too short",                           dict(request="Please add ui-rating."), "request-incomplete"),
        ("ignores the capability",              dict(request=re.sub("rating", "score", good, flags=re.I)), "request-incomplete"),
        ("ignores the store",                   dict(request=re.sub("store", "source", good, flags=re.I)), "request-incomplete"),
        ("ignores the keyboard",                dict(request=re.sub("keyboard", "input", good, flags=re.I)), "request-incomplete"),
    ]
    board(t, "Bad answers to the impossible task (" + task["id"] + ")", "Bad output", "Expected", "Checker said")
    t.dwell = min(t.dwell, 0.3)                      # many screens of text: keep the GIF inside the media budget
    wrong = []
    for name, kw, code in cases:
        res = ev.check_output(t, task, **kw)
        right = not res["passed"] and code in {i["code"] for i in res["issues"]}
        others = len({i["code"] for i in res["issues"]}) - 1
        said = f"{code} (+{others} more)" if right and others else codes(res)
        # One line per row so the whole table fits: only submitted pages get an excerpt; the request variants are named.
        row(t, [name, code, said], right, re.sub(r"\s+", " ", kw["html"])[:60] if kw.get("html") else None)
        t.step(f"Bad output: {name} -> expect [{code}]")
        if not right:
            wrong.append(f"{name}: {explain(res) or 'PASS'}")
    res = ev.check_output(t, task, request=good)
    row(t, ["control: the proper request", "PASS", codes(res)], res["passed"])
    t.step("Control: the proper request still passes")
    check(res["passed"], "the golden request must pass: " + explain(res))
    check(not wrong, "; ".join(wrong))

# Bad answers to the dashboard task, now that ui-status exists: each is a page (or no page) and must be rejected.
DASH = "glance-dashboard"
STATIC_ROWS = """<ui-status id="baby" label="Baby monitor" state="ok" detail="Sleeping since 13:10"></ui-status>
  <ui-status id="package" label="Package" state="warn" detail="En route, arriving today"></ui-status>
  <ui-status id="server" label="Home server" state="ok" detail="Up, 12 days"></ui-status>"""
def rows_of(h):
    return h[h.index('  <ui-status id="baby"'):h.index("</main>")]
DASH_CASES = [
    ("to-do items dressed up as a dashboard", lambda h: h.replace(rows_of(h), '<ui-todo-item text="Baby: sleeping" checked></ui-todo-item>\n  <ui-todo-item text="Package: en route"></ui-todo-item>\n  <ui-todo-item text="Server: up" checked></ui-todo-item>\n').replace("components/ui-status.js", "components/ui-todo-item.js"), "assertion-failed"),
    ("rows not bound to the store (never update)", lambda h: h.replace(rows_of(h), STATIC_ROWS + "\n"), "assertion-failed"),
    ("inline script that rewrites the rows",  lambda h: h.replace("</main>", "<script>setInterval(() => {}, 1000)</script>\n</main>"), "script-in-outlet"),
    ("onclick refresh button",                lambda h: h.replace("</main>", '<button onclick="location.reload()">Refresh</button>\n</main>'), "inline-handler"),
    ("state by color only (invented attribute)", lambda h: h.replace('path="package"', 'path="package" color="orange"'), "undocumented-attribute"),
    ("ui-status used but not imported",       lambda h: "\n".join(l for l in h.split("\n") if "ui-status.js" not in l), "missing-module-import"),
    ("a component request instead of the page", None, "no-output"),
]

@test("agent-evals", "checker-rejects-cheating-on-the-dashboard", desc='Now that ui-status exists, the dashboard task wants a page: a to-do list dressed up as a dashboard, rows that are not bound to the store, inline script, an onclick handler, an invented color attribute, a missing import or a component request instead of the page are all rejected.', gif=False, viewport={"width": 640, "height": 360})
def _(t):
    task = ev.load_task(DASH)
    base = golden(DASH)
    wrong = []
    for name, mutate, code in DASH_CASES:
        t.step(f"Bad output: {name} -> expect [{code}]")
        if mutate is None:
            res = ev.check_output(t, task, html=None, request=golden(IMPOSSIBLE, ".request.md").replace("ui-rating", "ui-status-board"))
        else:
            html = mutate(base)
            check(html != base, f"case '{name}' did not change the page")
            res = ev.check_output(t, task, html=html)
        if res["passed"] or code not in {i["code"] for i in res["issues"]}:
            wrong.append(f"{name}: expected [{code}], checker said {explain(res) or 'PASS'}")
    t.step("Result: " + ("every bad answer was rejected for the right reason" if not wrong else f"{len(wrong)} wrong verdicts"))
    check(not wrong, "; ".join(wrong))

@test("agent-evals", "cli-and-aggregate-scoring", desc='check.py works as a command-line tool, and run_evals.py scores a folder of outputs and aggregates success rate and iterations.', needs_idiomorph=True, gif=False, viewport={"width": 640, "height": 300})
def _(t):
    t.step("check.py works as a command")
    out = subprocess.run([sys.executable, os.path.join(EVALS, "check.py"), "--task", "kanban", "--html", os.path.join(EVALS, "golden", "kanban.html")], capture_output=True, text=True)
    check(out.returncode == 0 and out.stdout.startswith("PASS kanban"), out.stdout + out.stderr)
    t.step("run_evals.py scores a folder of outputs and aggregates the metrics")
    d = tempfile.mkdtemp()
    for tid in PAGE_TASKS + ("sprint", "workout", "errands",):
        open(os.path.join(d, tid + ".html"), "w").write(golden(tid))
    open(os.path.join(d, IMPOSSIBLE + ".request.md"), "w").write(golden(IMPOSSIBLE, ".request.md"))
    for tid, it, tin, tout in (("shopping-list", 2, 12000, 3000), ("kanban", 1, 9000, 2500)):
        json.dump({"iterations": it, "tokens_in": tin, "tokens_out": tout}, open(os.path.join(d, tid + ".meta.json"), "w"))
    # break one output: it must show up as a failure and lower the success rate
    open(os.path.join(d, "chat-left.html"), "w").write(golden("chat-left").replace("</body>", "<script>1</script></body>"))
    res_file = os.path.join(d, "results.json")
    run = subprocess.run([sys.executable, os.path.join(EVALS, "run_evals.py"), "--outputs", d, "--out", res_file], capture_output=True, text=True)
    check(run.returncode == 1, "a failing task makes run_evals exit 1")
    r = json.load(open(res_file))["summary"]
    eq((r["tasks"], r["passed"]), (10, 9))
    eq(r["success_rate"], 0.9); eq(r["failures_by_code"], {"inline-script": 1})
    eq(r["mean_iterations_to_pass"], 1.5)
    eq(r["mean_tokens_per_passing_task"], 13250.0)
