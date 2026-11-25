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
    gif: bool = True
    desc: str = ""
    context: dict = field(default_factory=dict)
    init_scripts: list = field(default_factory=list)

    @property
    def full(self):
        return f"{self.suite}-{self.name}"

def test(suite, name, component=None, online=False, known_issue=None, needs_idiomorph=False, init_scripts=(), gif=True, desc="", **context):
    def deco(fn):
        TESTS.append(Spec(suite, name, fn, component, online, known_issue, needs_idiomorph, gif, desc, context, list(init_scripts)))
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
    t.page.wait_for_function("customElements.get('ui-todo-item') && customElements.get('ui-chat-panel') && customElements.get('ui-store') && customElements.get('ui-each') && customElements.get('ui-countdown') && customElements.get('ui-progress') && window.__lib")
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

# Mock getUserMedia + MediaRecorder for the backend (transcriber) path.
#   window.__rec.state      {gum, started, stopped, denied, tracksStopped}
#   window.__rec.deny(name) make the next getUserMedia reject with a DOMException of that name
#   window.__rec.calls      [{size, mime, lang}] seen by the stub transcriber
#   window.__rec.install(text|Error)  register a stub transcriber (global) returning text or rejecting
BACKEND_MOCK = """
(() => {
  const state = { gum: 0, started: 0, stopped: 0, deny: null, tracksStopped: 0 };
  const calls = [];
  navigator.mediaDevices.getUserMedia = async () => {
    state.gum++;
    if (state.deny) { const n = state.deny; state.deny = null; throw new DOMException('denied', n); }
    return { getTracks: () => [{ stop: () => { state.tracksStopped++; } }] };
  };
  class MockRecorder {
    static isTypeSupported(m) { return m === 'audio/webm;codecs=opus'; }
    constructor(stream, opts) { this.mimeType = (opts && opts.mimeType) || 'audio/webm'; this.state = 'inactive'; }
    start() { state.started++; this.state = 'recording'; }
    stop() { state.stopped++; this.state = 'inactive';
      setTimeout(() => { this.ondataavailable && this.ondataavailable({ data: new Blob(['abc'], { type: this.mimeType }) });
        this.onstop && this.onstop(); }, 0); }
  }
  window.MediaRecorder = MockRecorder;
  window.__rec = { state, calls, deny(n) { state.deny = n; },
    install(result) { window.__lib.speech.setTranscriber(async (blob, o) => {
      calls.push({ size: blob.size, mime: o.mime, lang: o.lang });
      if (result === 'reject') throw new Error('boom');
      return result; }); } };
})();
"""
