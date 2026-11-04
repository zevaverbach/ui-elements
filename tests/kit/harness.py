"""Run one Playwright (Python, sync) test with video, captions, console capture, GIF and failure bundle.

    from harness import run_test

    def my_test(t):                       # t is a Session
        t.goto("http://localhost:8000/")
        t.step("Click the button", selector="#go")
        t.page.click("#go")
        assert t.page.inner_text("#out") == "done"

    result = run_test(browser, "checkout-happy-path", my_test, base_dir="out",
                      record_gif=True, base_url="http://localhost:8000")

On pass: writes <base_dir>/media/<name>.gif when record_gif is true (never touches an existing GIF
when the test fails). On fail: writes <base_dir>/failures/<name>/{failure.gif, filmstrip.png,
report.json, console.log}. Uncaught page errors and unexpected console errors fail the test
(use t.allow_console(r"regex") for expected ones).

Stdlib + playwright + ffmpeg only. Not tied to any particular site or library.
"""
import os, re, shutil, tempfile, time, traceback
from dataclasses import dataclass, field

import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from failure_bundle import write_failure_bundle, snapshot, slug
from video_to_gif import video_to_gif, GifTooLarge

HERE = os.path.dirname(os.path.abspath(__file__))
CAPTION_JS = open(os.path.join(HERE, "caption.js")).read()

class Skip(Exception):
    """Raise inside a test to skip it (reported as skipped, not failed)."""

class Pending(Exception):
    """Raise inside a test for something not built yet (reported as pending, not failed)."""

@dataclass
class Result:
    name: str
    status: str                      # passed | failed | skipped | pending | known-issue
    seconds: float = 0.0
    message: str = ""
    gif: str | None = None
    gif_bytes: int = 0
    bundle: str | None = None
    steps: list = field(default_factory=list)

class Session:
    def __init__(self, browser, name, work_dir, base_url="", init_scripts=(), dwell=0.5, **context_opts):
        self.name, self.base_url, self.dwell = name, base_url.rstrip("/"), dwell
        self.console, self.steps, self._allowed = [], [], []
        self.last_selector = None
        vp = context_opts.setdefault("viewport", {"width": 640, "height": 420})
        video_dir = os.path.join(work_dir, "video")
        self.context = browser.new_context(record_video_dir=video_dir, record_video_size=vp, **context_opts)
        self.context.add_init_script(CAPTION_JS)
        for s in init_scripts:
            self.context.add_init_script(s)
        self.page = self.context.new_page()
        self.t0 = time.monotonic()
        self.page.on("console", lambda m: self._log(m.type, m.text))
        self.page.on("pageerror", lambda e: self._log("pageerror", str(e)))
        self.page.on("requestfailed", lambda r: self._log("requestfailed", f"{r.method} {r.url} {r.failure}"))

    # ---- helpers for tests
    def now(self):
        return time.monotonic() - self.t0

    def _log(self, kind, text):
        self.console.append({"t": self.now(), "type": kind, "text": text})

    def allow_console(self, *patterns):
        """Console errors matching any regex are not treated as failures."""
        self._allowed += [re.compile(p) for p in patterns]

    def goto(self, url, **kw):
        self.page.goto(url if url.startswith("http") else self.base_url + url, **kw)

    def step(self, caption, selector=None):
        """Show `caption` on screen (it appears in the GIF) and remember it as the current step."""
        self.steps.append({"t": round(self.now(), 2), "caption": caption, "selector": selector})
        self.last_selector = selector or self.last_selector
        try:
            self.page.evaluate("(t) => window.__caption && window.__caption(t)", f"{len(self.steps)}. {caption}")
        except Exception:
            pass
        if self.dwell:
            time.sleep(self.dwell)

    def capture_events(self, *names):
        """Record CustomEvents on document: type, JSON detail, target tag/id, defaultPrevented."""
        self.page.evaluate("""(names) => {
          window.__events = window.__events || [];
          for (const n of names) document.addEventListener(n, (e) => {
            let d; try { d = JSON.parse(JSON.stringify(e.detail ?? null)); } catch { d = String(e.detail); }
            const t = e.composedPath()[0];
            window.__events.push({type: e.type, detail: d, target: (t.localName || '') + (t.id ? '#' + t.id : ''), prevented: e.defaultPrevented, bubbles: e.bubbles, composed: e.composed});
          });
        }""", list(names))

    def events(self, type=None):
        ev = self.page.evaluate("window.__events || []")
        return [e for e in ev if type is None or e["type"] == type]

    def clear_events(self):
        self.page.evaluate("window.__events = []")

    def unexpected_console_errors(self):
        out = []
        for c in self.console:
            if c["type"] in ("error", "pageerror") and not any(p.search(c["text"]) for p in self._allowed):
                out.append(c)
        return out

def run_test(browser, name, fn, base_dir, record_gif=False, base_url="", catalog_entry=None, init_scripts=(),
             dwell=0.5, max_gif_bytes=1_500_000, known_issue=None, setup=None, **context_opts):
    """Run fn(session). Returns a Result. Never raises for test failures."""
    work = tempfile.mkdtemp(prefix="pwtest-")
    started = time.monotonic()
    s = Session(browser, name, work, base_url=base_url, init_scripts=init_scripts, dwell=dwell, **context_opts)
    status, error = "passed", None
    try:
        if setup:
            setup(s)
        fn(s)
        bad = s.unexpected_console_errors()
        if bad:
            raise AssertionError("unexpected console errors: " + "; ".join(c["text"][:160] for c in bad[:3]))
    except Skip as e:
        status, error = "skipped", e
    except Pending as e:
        status, error = "pending", e
    except BaseException as e:               # AssertionError, playwright errors, anything
        status, error = "failed", e
        s._snap = snapshot(s.page, s.last_selector)   # must happen before the context closes
    elapsed = time.monotonic() - started
    video_path = None
    try:
        s.context.close()                    # finalizes the video
        video_path = s.page.video.path() if s.page.video else None
    except Exception:
        pass
    first = s.steps[0]["t"] if s.steps else 0.0
    last = s.steps[-1]["t"] if s.steps else elapsed
    v_start, v_end = max(0.0, first - 0.4), last + 1.4 + (s.dwell or 0)
    res = Result(name=name, status=status, seconds=round(elapsed, 2), steps=[x["caption"] for x in s.steps],
                 message=str(error) if error else "")
    if status == "failed" and known_issue:
        res.status, res.message = "known-issue", f"{known_issue} | {error}"
    if status == "passed" and record_gif and video_path:
        dst = os.path.join(base_dir, "media", slug(name) + ".gif")
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        try:
            res.gif_bytes = video_to_gif(video_path, dst, start=v_start, end=v_end, max_bytes=max_gif_bytes)
            res.gif = dst
        except GifTooLarge as e:
            res.status, res.message = "failed", f"GIF over budget: {e}"
    if status == "failed" and res.status != "known-issue":
        try:
            url = s.page.url
        except Exception:
            url = ""
        snap = snapshot_after_close(s)
        res.bundle = write_failure_bundle(os.path.join(base_dir, "failures"), name, video_path, error,
                                          s.steps[-1]["caption"] if s.steps else "(before first step)", s.console, url,
                                          catalog_entry, snap, v_start, v_end, extra={"steps": s.steps})
    shutil.rmtree(work, ignore_errors=True)
    return res

def snapshot_after_close(s):
    return getattr(s, "_snap", "<page closed before snapshot>")
