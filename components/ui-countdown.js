// <ui-countdown> — a countdown timer with optional phases (e.g. focus -> break -> done),
// a built-in start/pause button, a low-time warning state and a "done" slot.
//
// Usage:
//   <script type="module" src="https://cdn.jsdelivr.net/gh/zevaverbach/ui-elements@v0.1.0/components/ui-countdown.js"></script>
//   <ui-countdown seconds="90" label="Start sprint"></ui-countdown>
//   <ui-countdown phases='[{"name":"Focus","seconds":1500},{"name":"Break","seconds":300}]'></ui-countdown>
//   <ui-countdown until="13:00"><span slot="done">Back!</span></ui-countdown>
//
// Attributes / properties:
//   seconds    number    total duration when there are no phases (default 60)
//   phases     JSON      array of {name: string, seconds: number}; runs them in order, then fires ui-done
//   until      string    count down to a clock time instead of a duration: "HH:MM" (or "HH:MM:SS"), local
//                        time today, or tomorrow if that time has already passed; or a full ISO datetime
//                        ("2026-12-01T13:00", "2026-12-01T12:00:00Z"). When set and valid it replaces
//                        `seconds`, `phases` is ignored, it starts automatically, the start/pause button is
//                        hidden, and `remaining` is read from the clock, so a background tab or sleep does
//                        not make it drift. A datetime already in the past is done at once. reset()
//                        resolves the time again (so after an "HH:MM" countdown ends it means tomorrow).
//   running    boolean   counting down while present (reflects; prop: running)
//   autostart  boolean   start as soon as the element is connected
//   label      string    text of the start button before it has been started (default "Start")
//   warn       number    seconds left at which the warning state begins (default 10)
//   (prop) remaining   read-only: whole seconds left in the current phase (from the clock with `until`)
//
// Slots:
//   done       shown instead of the time once the last phase reaches zero
//
// Events (all bubble and are composed; detail shapes):
//   ui-tick    {remaining: number, phase: string, index: number}   once per whole second while running
//   ui-phase   {index: number, name: string}                         a new phase began (not fired for the first)
//   ui-done    {}                                                    the last phase reached zero
//
// Methods: start(), pause(), reset()
//
// Keyboard: the button is a native <button> (Space/Enter).
// Accessibility: the time has role="timer"; phase changes and completion are announced politely.
//
// CSS custom properties (all optional; fall back to the shared --ui-* tokens in tokens.css):
//   --ui-countdown-bg, --ui-countdown-text, --ui-countdown-accent, --ui-countdown-warn
// Parts: time, phase, bar, button

import { emit, define } from './_shared/util.js';
import { sheet } from './_shared/base.js';

const styles = sheet(`
:host { display: block; }
.box {
  display: flex; flex-direction: column; align-items: center; gap: 0.5rem; padding: 1rem;
  background: var(--ui-countdown-bg, var(--_surface));
  color: var(--ui-countdown-text, var(--_text));
  border: 1px solid var(--_border); border-radius: var(--_radius);
  --_c: var(--ui-countdown-accent, var(--_accent));
}
.box[data-state="warn"] { --_c: var(--ui-countdown-warn, var(--_danger)); }
.box[data-state="done"] { --_c: var(--_success); }
.phase { font-size: 0.75rem; letter-spacing: 0.08em; text-transform: uppercase; color: var(--_muted); min-height: 1em; }
.time { font-size: 2.75rem; font-variant-numeric: tabular-nums; font-weight: 600; color: var(--_c); line-height: 1.1; }
.box[data-state="warn"][data-running] .time { animation: pulse 1s ease-in-out infinite; }
@keyframes pulse { 50% { opacity: 0.55; } }
.bar { width: 100%; height: 6px; border-radius: 3px; background: var(--_surface-2); overflow: hidden; }
.fill { height: 100%; width: 0; background: var(--_c); transition: width 0.25s linear; }
.btn {
  padding: 0.45rem 1.1rem; border-radius: var(--_radius); border: 1px solid var(--_c);
  background: var(--_c); color: var(--_on-accent); font-weight: 600; min-height: 2.25rem;
}
.btn[data-secondary] { background: none; color: var(--_c); }
.done-slot { text-align: center; }
`);

const fmt = (s) => {
  const t = Math.max(0, Math.ceil(s));
  const m = Math.floor(t / 60);
  const sec = String(t % 60).padStart(2, '0');
  return m >= 60 ? `${Math.floor(m / 60)}:${String(m % 60).padStart(2, '0')}:${sec}` : `${m}:${sec}`;
};

// "HH:MM[:SS]" -> the next such local time (today, or tomorrow if it has passed); otherwise a full
// ISO datetime. Returns epoch ms, or null when unset or unparseable.
const parseUntil = (v) => {
  v = (v || '').trim();
  if (!v) return null;
  const m = /^(\d{1,2}):(\d{2})(?::(\d{2}))?$/.exec(v);
  if (m) {
    const [h, min, sec] = [Number(m[1]), Number(m[2]), Number(m[3] || 0)];
    if (h > 23 || min > 59 || sec > 59) return null;
    const now = new Date();
    const d = new Date(now.getFullYear(), now.getMonth(), now.getDate(), h, min, sec);
    if (d.getTime() <= now.getTime()) d.setDate(d.getDate() + 1);
    return d.getTime();
  }
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(v)) return null;
  const t = Date.parse(v);
  return Number.isNaN(t) ? null : t;
};

class UiCountdown extends HTMLElement {
  static observedAttributes = ['seconds', 'phases', 'until', 'running', 'label', 'warn'];

  constructor() {
    super();
    this._timer = 0;
    this._started = false;
    this._lastWhole = -1;
    const root = this.attachShadow({ mode: 'open' });
    root.adoptedStyleSheets = [styles];
    root.innerHTML = `
      <div class="box" part="box">
        <div class="phase" part="phase"></div>
        <div class="time" part="time" role="timer"></div>
        <div class="done-slot" hidden><slot name="done"></slot></div>
        <div class="bar" part="bar" aria-hidden="true"><div class="fill"></div></div>
        <button class="btn" part="button" type="button"></button>
        <div class="sr-only" aria-live="polite"></div>
      </div>`;
    this._box = root.querySelector('.box');
    this._phaseEl = root.querySelector('.phase');
    this._timeEl = root.querySelector('.time');
    this._doneEl = root.querySelector('.done-slot');
    this._fill = root.querySelector('.fill');
    this._btn = root.querySelector('.btn');
    this._live = root.querySelector('[aria-live]');
    this._btn.addEventListener('click', () => {
      if (this._done) { this.reset(); this.start(); } else if (this.running) this.pause(); else this.start();
    });
    this._load();
  }

  connectedCallback() {
    this._render();
    if ((this._target !== null || this.hasAttribute('autostart')) && !this._started) this.start();
    else if (this.hasAttribute('running')) this._begin();
  }

  disconnectedCallback() { this._halt(); }

  attributeChangedCallback(name) {
    if (name === 'running') { if (this.hasAttribute('running')) this._begin(); else this._halt(); return; }
    if (name === 'until') { this.removeAttribute('running'); this._halt(); this._started = false; this._load(); if (this.isConnected && this._target !== null) this.start(); }
    else if (name === 'seconds' || name === 'phases') { if (!this._started) this._load(); }
    this._render();
  }

  get running() { return this.hasAttribute('running'); }
  set running(v) { this.toggleAttribute('running', !!v); }
  get remaining() {
    if (this._target !== null && !this._done) return Math.max(0, Math.ceil((this._target - Date.now()) / 1000));
    return Math.ceil(this._left);
  }

  start() {
    if (this._done) this.reset();
    this._started = true;
    this.setAttribute('running', '');
  }

  pause() { this.removeAttribute('running'); }

  reset() {
    this.removeAttribute('running');
    this._halt();
    this._started = false;
    this._load();
    this._render();
    if (this._target !== null && this.isConnected) this.start();
  }

  _load() {
    this._target = parseUntil(this.getAttribute('until'));
    let phases = null;
    try { phases = JSON.parse(this.getAttribute('phases') || 'null'); } catch { phases = null; }
    if (!Array.isArray(phases) || !phases.length) phases = [{ name: '', seconds: Number(this.getAttribute('seconds')) || 60 }];
    this._phases = phases.map((p) => ({ name: String(p.name ?? ''), seconds: Math.max(1, Number(p.seconds) || 1) }));
    // until replaces seconds and phases; the single phase's length is the time left now (for the bar)
    if (this._target !== null) this._phases = [{ name: '', seconds: Math.max(0, (this._target - Date.now()) / 1000) }];
    this._i = 0;
    this._left = this._phases[0].seconds;
    this._done = false;
    this._lastWhole = -1;
  }

  _begin() {
    if (this._timer || this._done) return;
    this._started = true;
    this._end = this._target ?? Date.now() + this._left * 1000;
    this._timer = setInterval(() => this._step(), 200);
    this._step();
  }

  _halt() {
    if (!this._timer) return;
    clearInterval(this._timer);
    this._timer = 0;
    this._left = Math.max(0, (this._end - Date.now()) / 1000);
    this._render();
  }

  _step() {
    const now = Date.now();
    this._left = (this._end - now) / 1000;
    while (this._left <= 0) {
      if (this._i + 1 < this._phases.length) {
        this._i += 1;
        this._end += this._phases[this._i].seconds * 1000;
        this._left = (this._end - now) / 1000;
        this._lastWhole = -1;
        this._say(this._phases[this._i].name);
        emit(this, 'ui-phase', { index: this._i, name: this._phases[this._i].name });
      } else {
        this._left = 0;
        this._done = true;
        clearInterval(this._timer);
        this._timer = 0;
        this.removeAttribute('running');
        this._render();
        this._say('Done');
        emit(this, 'ui-done', {});
        return;
      }
    }
    const whole = Math.ceil(this._left);
    if (whole !== this._lastWhole) {
      this._lastWhole = whole;
      emit(this, 'ui-tick', { remaining: whole, phase: this._phases[this._i].name, index: this._i });
    }
    this._render();
  }

  _say(text) { this._live.textContent = text; }

  _render() {
    const p = this._phases[this._i];
    const warn = Number(this.getAttribute('warn') ?? 10);
    const state = this._done ? 'done' : this._left <= warn && this._phases.length === 1 + this._i && this._started ? 'warn' : '';
    this._box.dataset.state = state;
    this._box.toggleAttribute('data-running', this.running);
    this._timeEl.hidden = this._done && this.querySelector('[slot="done"]') !== null;
    this._doneEl.hidden = !(this._done && this.querySelector('[slot="done"]'));
    this._timeEl.textContent = fmt(this._left);
    this._phaseEl.textContent = this._phases.length > 1 ? `${p.name || 'Phase'} · ${this._i + 1} of ${this._phases.length}` : p.name;
    this._fill.style.width = `${p.seconds > 0 ? Math.min(100, Math.max(0, (1 - this._left / p.seconds) * 100)) : 100}%`;
    this._btn.hidden = this._target !== null;
    this._btn.textContent = this.running ? 'Pause' : this._done ? 'Restart' : this._started ? 'Resume' : this.getAttribute('label') || 'Start';
    if (this._btn.textContent === 'Pause') this._btn.dataset.secondary = ''; else delete this._btn.dataset.secondary;
  }
}

define('ui-countdown', UiCountdown);
