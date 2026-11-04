"""Test registry and shared environment for the suites in tests/suites/.

    from registry import test, env

    @test("todo-item", "toggle", component="ui-todo-item")
    def _(t):            # t is a kit/harness.py Session
        t.goto("/tests/pages/fixture.html")
        ...
"""
from dataclasses import dataclass, field

TESTS = []

@dataclass
class Spec:
    suite: str
    name: str
    fn: object
    component: str | None = None
    online: bool = False
    known_issue: str | None = None
    needs_idiomorph: bool = False
    context: dict = field(default_factory=dict)
    init_scripts: list = field(default_factory=list)

    @property
    def full(self):
        return f"{self.suite}-{self.name}"

def test(suite, name, component=None, online=False, known_issue=None, needs_idiomorph=False, init_scripts=(), **context):
    def deco(fn):
        TESTS.append(Spec(suite, name, fn, component, online, known_issue, needs_idiomorph, context, list(init_scripts)))
        return fn
    return deco

class Env:
    """Filled in by run.py before tests run."""
    base = ""          # http://127.0.0.1:<port>  (repo root)
    cdn = ""           # http://127.0.0.1:<port>  (repo root, jsDelivr layout + CORS)
    root = ""          # repo root on disk
    pages = {}         # path -> html served from memory by the app server
    catalog = {}       # parsed components.json
    online = False
    idiomorph = None   # path to a cached copy of the pinned Idiomorph, or None

env = Env()

# ---- reusable snippets -------------------------------------------------------
FIXTURE = "/tests/pages/fixture.html"

def mount(t, html):
    """Replace the fixture page's #root with `html` (custom elements upgrade immediately)."""
    t.page.evaluate("(h) => { document.getElementById('root').innerHTML = h; }", html)

def open_fixture(t, html=""):
    t.goto(FIXTURE)
    t.page.wait_for_function("customElements.get('ui-todo-item') && customElements.get('ui-chat-panel') && customElements.get('ui-store') && customElements.get('ui-each') && window.__lib")
    if html:
        mount(t, html)

def catalog_entry(tag):
    return next((c for c in env.catalog.get("components", []) if c["tag"] == tag), None)

# Mock Web Speech API: window.__speech.say(text, final) delivers a result to the active recognizer.
SPEECH_MOCK = """
(() => {
  const state = { active: null, started: 0, stopped: 0, lang: null };
  class MockRecognition {
    constructor() { this.interimResults = false; this.continuous = false; this.lang = ''; }
    start() { state.active = this; state.started++; state.lang = this.lang; setTimeout(() => this.onstart && this.onstart(), 0); }
    stop() { state.stopped++; setTimeout(() => { this.onend && this.onend(); if (state.active === this) state.active = null; }, 0); }
  }
  window.SpeechRecognition = MockRecognition; window.webkitSpeechRecognition = MockRecognition;
  window.__speech = { state,
    say(text, final) { const r = state.active; if (!r) return false;
      const res = [{ transcript: text, confidence: 1 }]; res.isFinal = !!final;
      r.onresult && r.onresult({ resultIndex: 0, results: [res] }); return true; },
    fail(code) { const r = state.active; r && r.onerror && r.onerror({ error: code }); } };
})();
"""
NO_SPEECH = "delete window.SpeechRecognition; delete window.webkitSpeechRecognition; window.SpeechRecognition = undefined; window.webkitSpeechRecognition = undefined;"
