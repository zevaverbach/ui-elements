// <ui-status> — one live status row for a glance dashboard ("is everything okay?"): an indicator,
// a label, a one-line detail and a state of ok, warn, bad or unknown, given in text as well as color.
//
// Usage:
//   <script type="module" src="https://cdn.jsdelivr.net/gh/zevaverbach/ui-elements@v0.1.0/components/ui-status.js"></script>
//   <ui-status state="ok" label="Server" detail="Up, 12 days"></ui-status>
//   <ui-store name="home"><script type="application/json">{"baby":{"state":"ok","detail":"Sleeping since 13:10"}}</script></ui-store>
//   <ui-status label="Baby" store="home" path="baby"></ui-status>
//   <ui-each id="checks" store="home" path="checks" tag="ui-status" map='{"state":"state","label":"label","detail":"detail"}'></ui-each>
//
// Attributes / properties:
//   state    "ok" | "warn" | "bad" | "unknown"   the state (default unknown; anything else counts as unknown)
//                                                  (prop: state, the effective state, also when bound)
//   label    string   what is being watched, e.g. "Baby"                          (prop: label)
//   detail   string   the one-line detail, e.g. "Sleeping since 13:10"            (prop: detail)
//
// Store binding (optional; same conventions as ui-progress). Without `store` it works exactly as above.
//   store    string   name of a <ui-store> (it may be declared later). When set, the row re-renders on every
//                     store change from the value at `path`
//   path     string, default "" (the store root)   dot path to an object {state, label, detail}. Each field that
//                     is present there wins over the attribute of the same name, so a page can keep the label
//                     in markup and let the store carry state and detail. A plain string at path is the state.
//   Reading the properties while bound gives the store's values; setting them writes the attributes, which
//   apply again once the store no longer has that field (or `store` is removed).
//
// Slots:
//   icon     replaces the default colored dot (it takes the state color as `color`)
//   detail   rich detail content, shown instead of the detail attribute
//
// Events (all bubble and are composed; detail shapes):
//   ui-status-change   {state: string, previous: string, label: string}   the effective state changed after the
//                      first render, from an attribute, a property or the store. Not fired for detail-only changes.
//
// Accessibility: the state is always written out in a badge ("OK", "Warning", "Problem", "Unknown"), never
// shown by color alone; the dot or icon is decorative. A state change is announced through a live region
// ("Server: Problem, Down since 14:02"), politely, or assertively when the new state is bad, because a glance
// dashboard is often not being watched. Label and detail are set with textContent. No animation.
//
// CSS custom properties (all optional; fall back to the shared --ui-* tokens in tokens.css):
//   --ui-status-ok, --ui-status-warn, --ui-status-bad, --ui-status-unknown   indicator colors per state
//   --ui-status-bg   row background
// Parts: row, label, detail, badge

import { emit, define } from './_shared/util.js';
import { get, subscribe } from './_shared/store-registry.js';
import { sheet } from './_shared/base.js';

const styles = sheet(`
:host { display: block; }
.row {
  --_c: var(--ui-status-unknown, var(--_muted));
  display: grid; grid-template-columns: auto 1fr auto; align-items: center; gap: 0.15rem 0.75rem;
  padding: 0.6rem 0.8rem; background: var(--ui-status-bg, var(--_surface));
  border: 1px solid var(--_border); border-left: 4px solid var(--_c); border-radius: var(--_radius);
}
.row[data-state="ok"] { --_c: var(--ui-status-ok, var(--_success)); }
.row[data-state="warn"] { --_c: var(--ui-status-warn, var(--_warning)); }
.row[data-state="bad"] { --_c: var(--ui-status-bad, var(--_danger)); }
.icon { display: flex; color: var(--_c); }
.dot { display: block; width: 0.75rem; height: 0.75rem; border-radius: 50%; background: var(--_c); }
.text { display: flex; flex-direction: column; min-width: 0; }
.label { font-weight: 600; }
.detail { color: var(--_muted); font-size: 0.9em; overflow-wrap: anywhere; }
.badge {
  font-size: 0.8em; font-weight: 600; white-space: nowrap; padding: 0.1rem 0.55rem; border-radius: 999px;
  border: 1px solid var(--_c); background: color-mix(in srgb, var(--_c) 16%, transparent);
}
`);

const STATES = ['ok', 'warn', 'bad', 'unknown'];
const WORDS = { ok: 'OK', warn: 'Warning', bad: 'Problem', unknown: 'Unknown' };
const norm = (s) => (STATES.includes(String(s ?? '').trim().toLowerCase()) ? String(s).trim().toLowerCase() : 'unknown');

class UiStatus extends HTMLElement {
  static observedAttributes = ['state', 'label', 'detail', 'store', 'path'];

  constructor() {
    super();
    this._last = undefined;   // effective state at the last render; undefined until the first one
    const root = this.attachShadow({ mode: 'open' });
    root.adoptedStyleSheets = [styles];
    root.innerHTML = `
      <div class="row" part="row" data-state="unknown">
        <span class="icon" aria-hidden="true"><slot name="icon"><span class="dot"></span></slot></span>
        <span class="text">
          <span class="label" part="label"></span>
          <span class="detail" part="detail"><slot name="detail"><span class="detail-text"></span></slot></span>
        </span>
        <span class="badge" part="badge"></span>
        <span class="sr-only" aria-live="polite"></span>
      </div>`;
    const q = (s) => root.querySelector(s);
    this._row = q('.row');
    this._label = q('.label');
    this._detail = q('.detail');
    this._detailText = q('.detail-text');
    this._detailSlot = q('slot[name="detail"]');
    this._badge = q('.badge');
    this._live = q('[aria-live]');
    this._detailSlot.addEventListener('slotchange', () => this._render());
  }

  connectedCallback() {
    this._subscribe();
    this._render();
  }

  disconnectedCallback() { this._unsub?.(); this._unsub = null; }

  attributeChangedCallback(name) {
    if (!this.isConnected) return;
    if (name === 'store') this._subscribe();
    this._render();
  }

  _subscribe() {
    this._unsub?.();
    const store = this.getAttribute('store');
    this._unsub = store ? subscribe(store, () => this._render()) : null;
  }

  // {state, label, detail} from the attributes, with the bound store's fields winning where present.
  _values() {
    const v = { state: this.getAttribute('state'), label: this.getAttribute('label') ?? '', detail: this.getAttribute('detail') ?? '' };
    const store = this.getAttribute('store');
    if (store) {
      const at = get(store, this.getAttribute('path') || '');
      if (typeof at === 'string') v.state = at;
      else if (at && typeof at === 'object') for (const k of Object.keys(v)) if (at[k] != null) v[k] = String(at[k]);
    }
    v.state = norm(v.state);
    return v;
  }

  get state() { return this._values().state; }
  set state(v) { this.setAttribute('state', String(v)); }
  get label() { return this._values().label; }
  set label(v) { this.setAttribute('label', String(v)); }
  get detail() { return this._values().detail; }
  set detail(v) { this.setAttribute('detail', String(v)); }

  _render() {
    const { state, label, detail } = this._values();
    const slotted = this._detailSlot.assignedNodes().length > 0;
    this._row.dataset.state = state;
    this._label.textContent = label;
    this._detailText.textContent = detail;
    this._detail.hidden = !detail && !slotted;
    this._badge.textContent = WORDS[state];

    const previous = this._last;
    this._last = state;
    if (previous === undefined || previous === state) return;
    const said = slotted ? this._detailSlot.assignedNodes().map((n) => n.textContent).join(' ').trim() : detail;
    this._live.setAttribute('aria-live', state === 'bad' ? 'assertive' : 'polite');
    this._live.textContent = `${label ? `${label}: ` : ''}${WORDS[state]}${said ? `, ${said}` : ''}`;
    emit(this, 'ui-status-change', { state, previous, label });
  }
}

define('ui-status', UiStatus);
