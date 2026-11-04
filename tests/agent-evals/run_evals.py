#!/usr/bin/env python3
"""Score a folder of agent outputs against the tasks in tests/agent-evals/tasks/. No LLM calls.

    python3 tests/agent-evals/run_evals.py --outputs out/ [--out results.json]

For each task <id> it looks in the folder for
    <id>.html             the generated page (page tasks)
    <id>.request.md       the written component request (tasks of kind "request")
    <id>.meta.json        optional, what you measured while the agent worked:
                          {"iterations": 2, "tokens_in": 18000, "tokens_out": 4200, "seconds": 95, "model": "..."}
and writes a results file with per-task pass/fail (with the checker's reasons) and the aggregate numbers:
success rate, first-try rate (passed with iterations == 1), mean iterations and mean tokens of the passing runs.
Exit code 1 if any task failed (use --allow-fail to always exit 0).
"""
import argparse, glob, json, os, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import check

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--outputs", required=True); ap.add_argument("--out"); ap.add_argument("--allow-fail", action="store_true")
    ap.add_argument("--only", action="append", help="task id (repeatable)")
    a = ap.parse_args()
    tasks = [json.load(open(f)) for f in sorted(glob.glob(os.path.join(HERE, "tasks", "*.json")))]
    tasks = [t for t in tasks if not a.only or t["id"] in a.only]
    from playwright.sync_api import sync_playwright
    from harness import Session
    rows = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for task in tasks:
            read = lambda ext: open(os.path.join(a.outputs, task["id"] + ext)).read() if os.path.exists(os.path.join(a.outputs, task["id"] + ext)) else None
            html, req = read(".html"), read(".request.md")
            meta = json.loads(read(".meta.json") or "{}")
            s = Session(browser, "eval-" + task["id"], tempfile.mkdtemp(), dwell=0)
            t0 = time.time()
            res = check.check_output(s, task, html, req, idiomorph_path=check.os.path.join(check.ROOT, "tests", ".cache", "idiomorph-0.8.0.esm.js"))
            s.context.close()
            rows.append({"task": task["id"], "passed": res["passed"], "issues": res["issues"], "check_seconds": round(time.time() - t0, 1),
                         "iterations": meta.get("iterations"), "tokens_in": meta.get("tokens_in"), "tokens_out": meta.get("tokens_out"),
                         "seconds": meta.get("seconds"), "model": meta.get("model")})
        browser.close()
    passed = [r for r in rows if r["passed"]]
    num = lambda k, rs: [r[k] for r in rs if isinstance(r.get(k), (int, float))]
    mean = lambda xs: round(sum(xs) / len(xs), 2) if xs else None
    summary = {
        "tasks": len(rows), "passed": len(passed), "success_rate": round(len(passed) / len(rows), 3) if rows else None,
        "first_try_rate": round(sum(1 for r in rows if r["passed"] and r["iterations"] == 1) / len(rows), 3) if rows and any(r["iterations"] for r in rows) else None,
        "mean_iterations_to_pass": mean(num("iterations", passed)),
        "mean_tokens_per_passing_task": mean([r["tokens_in"] + r["tokens_out"] for r in passed if isinstance(r.get("tokens_in"), (int, float)) and isinstance(r.get("tokens_out"), (int, float))]),
        "failures_by_code": {},
    }
    for r in rows:
        for i in r["issues"]:
            summary["failures_by_code"][i["code"]] = summary["failures_by_code"].get(i["code"], 0) + 1
    out = {"summary": summary, "results": rows}
    for r in rows:
        print(("PASS " if r["passed"] else "FAIL ") + r["task"] + ("" if r["passed"] else "  " + "; ".join(f"[{i['code']}] {i['message'][:100]}" for i in r["issues"][:2])))
    print(json.dumps(summary, indent=1))
    if a.out:
        json.dump(out, open(a.out, "w"), indent=2)
    return 0 if (a.allow_fail or len(passed) == len(rows)) else 1

if __name__ == "__main__":
    sys.exit(main())
