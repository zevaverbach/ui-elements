"""Suite F: agent composition evals. The golden solutions must pass the checker; every kind of bad output must be rejected
with the right reason. No LLM is involved: this proves the checker works, so it can be trusted on real agent output."""
import json, os, subprocess, sys, tempfile
from registry import test, env
from helpers import check, eq

EVALS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "agent-evals")
sys.path.insert(0, EVALS)
import check as ev   # tests/agent-evals/check.py

golden = lambda name, ext=".html": open(os.path.join(EVALS, "golden", name + ext)).read()
IDIO = os.path.join(os.path.dirname(EVALS), ".cache", "idiomorph-0.8.0.esm.js")

def explain(res):
    return "; ".join(f"[{i['code']}] {i['message']}" for i in res["issues"])

def golden_test(task_id, **kw):
    @test("agent-evals", f"golden-{task_id}", needs_idiomorph=True, viewport={"width": 640, "height": 420}, **kw)
    def _(t):
        task = ev.load_task(task_id)
        t.step(f"Task: {task['title']}")
        res = ev.check_output(t, task, html=golden(task_id), idiomorph_path=IDIO)
        t.step("Verdict: " + ("PASS" if res["passed"] else "FAIL " + explain(res)[:90]))
        check(res["passed"], f"golden solution for {task_id} was rejected: {explain(res)}")
    return _

for _id in ("shopping-list", "todo-progress", "chat-left", "kanban"):
    golden_test(_id)

@test("agent-evals", "golden-needs-new-behavior-is-a-request", viewport={"width": 640, "height": 300})
def _(t):
    task = ev.load_task("needs-new-behavior")
    t.step("Task: " + task["title"])
    t.step("Correct output: a written request for a new component, no script")
    res = ev.check_output(t, task, request=golden("needs-new-behavior", ".request.md"))
    check(res["passed"], explain(res))
    t.step("Verdict: PASS (the request names a new tag, attributes, events and why nothing existing fits)")

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

@test("agent-evals", "checker-rejects-bad-output", needs_idiomorph=True, viewport={"width": 640, "height": 420})
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

@test("agent-evals", "checker-rejects-cheating-on-the-impossible-task", viewport={"width": 640, "height": 300})
def _(t):
    task = ev.load_task("needs-new-behavior")
    good = golden("needs-new-behavior", ".request.md")
    cases = [
        ("inline script instead of a request", dict(html="<main id='outlet'><button id='b'>Start timer</button><script>setInterval(()=>{},1000)</script></main>", request=good), "script-in-outlet"),
        ("onclick instead of a request",       dict(html="<main id='outlet'><button onclick=\"start()\">Start timer</button></main>", request=good), "inline-handler"),
        ("no request at all",                  dict(html=None, request=None), "request-incomplete"),
        ("a request that proposes nothing new", dict(request="I added a timer using ui-todo-item and ui-each. It works. " * 8), "request-incomplete"),
        ("too short",                          dict(request="Please add ui-countdown."), "request-incomplete"),
        ("ignores the capability",             dict(request=good.replace("countdown", "widget").replace("seconds", "units")), "request-incomplete"),
    ]
    wrong = []
    for name, kw, code in cases:
        t.step(f"Bad output: {name} -> expect [{code}]")
        res = ev.check_output(t, task, **kw)
        if res["passed"] or code not in {i["code"] for i in res["issues"]}:
            wrong.append(f"{name}: {explain(res) or 'PASS'}")
    check(not wrong, "; ".join(wrong))

@test("agent-evals", "cli-and-aggregate-scoring", needs_idiomorph=True, gif=False, viewport={"width": 640, "height": 300})
def _(t):
    t.step("check.py works as a command")
    out = subprocess.run([sys.executable, os.path.join(EVALS, "check.py"), "--task", "kanban", "--html", os.path.join(EVALS, "golden", "kanban.html")], capture_output=True, text=True)
    check(out.returncode == 0 and out.stdout.startswith("PASS kanban"), out.stdout + out.stderr)
    t.step("run_evals.py scores a folder of outputs and aggregates the metrics")
    d = tempfile.mkdtemp()
    for tid in ("shopping-list", "todo-progress", "chat-left", "kanban"):
        open(os.path.join(d, tid + ".html"), "w").write(golden(tid))
    open(os.path.join(d, "needs-new-behavior.request.md"), "w").write(golden("needs-new-behavior", ".request.md"))
    for tid, it, tin, tout in (("shopping-list", 2, 12000, 3000), ("kanban", 1, 9000, 2500)):
        json.dump({"iterations": it, "tokens_in": tin, "tokens_out": tout}, open(os.path.join(d, tid + ".meta.json"), "w"))
    # break one output: it must show up as a failure and lower the success rate
    open(os.path.join(d, "chat-left.html"), "w").write(golden("chat-left").replace("</body>", "<script>1</script></body>"))
    res_file = os.path.join(d, "results.json")
    run = subprocess.run([sys.executable, os.path.join(EVALS, "run_evals.py"), "--outputs", d, "--out", res_file], capture_output=True, text=True)
    check(run.returncode == 1, "a failing task makes run_evals exit 1")
    r = json.load(open(res_file))["summary"]
    eq((r["tasks"], r["passed"]), (5, 4))
    eq(r["success_rate"], 0.8); eq(r["failures_by_code"], {"inline-script": 1})
    eq(r["mean_iterations_to_pass"], 1.5)
    eq(r["mean_tokens_per_passing_task"], 13250.0)
