// <ui-progress> — a progress ring or bar with an optional goal line and a finish-line state:
// a heading, a meta line (deadline etc.), and an image / "done" content that appears on completion.
//
// Usage:
//   <script type="module" src="https://cdn.jsdelivr.net/gh/zevaverbach/ui-elements@v0.1.0/components/ui-progress.js"></script>
//   <ui-progress heading="Ship the feature" value="3" max="5" label="3 of 5 tasks"></ui-progress>
//   <ui-progress variant="bar" value="62" goal="80" label="$62 of $80"><span slot="done">Under budget!</span></ui-progress>
//   <ui-progress store="todos" where='{"done":true}' label="{value} of {max} done"></ui-progress>
//
// Attributes / properties (all reflect):
//   value     number   current amount (default 0)                      (prop: value)
//   max       number   amount that means "done" (default 100)           (prop: max)
//   variant   "ring" | "bar"   shape (default ring)
//   goal      number   draws a goal line at this amount on the same scale as value/max
//   label     string   text shown with the graphic, e.g. "3 of 5 tasks" (default: the percentage).
//                      Placeholders {value}, {max} and {percent} (rounded) are filled in: "{value} of {max} sets"
//   heading   string   title of the goal, shown above the graphic
//   (prop) percent   read-only: value / max as 0-100
//
// Store binding (optional; same conventions as ui-each). Without `store` it works exactly as above.
//   store     string   name of a <ui-store> (it may be declared later). When set, value and max come from
//                      the store and stay live; the value attribute is ignored and increment() does nothing
//   path      string, default "items"   dot path to the items array in the store
//   where     JSON {field: value}   equality filter (dot paths ok), as on ui-each: value = number of matching items
//   max       when bound: the number of items at path, unless the max attribute is set explicitly.
//             An empty list (max 0) is never complete.
//   ui-complete and the done slot behave as without a store; if the count drops below max, completion re-arms.
//
// Slots:
//   meta     under the graphic: deadline, time left, notes
//   image    always shown beside/below the graphic: the motivating picture of the finished state
//   done     shown in place of the label once value >= max (the finish-line state)
//
// Events (all bubble and are composed; detail shapes):
//   ui-complete   {value: number, max: number}   value reached max (fires once per crossing)
//
// Methods: increment(by?)  adds by (default 1) to value, capped at max
//
// Accessibility: role="progressbar" named by the heading (or the label), with aria-valuenow/min/max
// and the label as its aria-valuetext; completion is announced politely. The fill animates unless
// prefers-reduced-motion.
//
// CSS custom properties (all optional; fall back to the shared --ui-* tokens in tokens.css):
//   --ui-progress-bg, --ui-progress-track, --ui-progress-accent, --ui-progress-done, --ui-progress-goal
// Parts: heading, graphic, label

import { emit, define, json, matches } from './_shared/util.js';
import { get, subscribe } from './_shared/store-registry.js';
import { sheet } from './_shared/base.js';

const styles = sheet(`
:host { display: block; }
.card {
  display: flex; flex-direction: column; align-items: center; gap: 0.6rem; padding: 1rem;
  background: var(--ui-progress-bg, var(--_surface));
  border: 1px solid var(--_border); border-radius: var(--_radius);
  --_fill: var(--ui-progress-accent, var(--_accent));
  --_track: var(--ui-progress-track, var(--_surface-2));
  --_goal: var(--ui-progress-goal, var(--_danger));
}
.card[data-done] { --_fill: var(--ui-progress-done, var(--_success)); }
.heading { font-weight: 600; font-size: 1.05rem; text-align: center; }
.heading:empty { display: none; }
.graphic { position: relative; width: 100%; display: flex; justify-content: center; }
.ring { width: 9rem; height: 9rem; transform: rotate(-90deg); }
.ring circle { fill: none; stroke-width: 10; }
.ring .track { stroke: var(--_track); }
.ring .fill { stroke: var(--_fill); stroke-linecap: round; transition: stroke-dashoffset 0.4s ease; }
.ring .goal { stroke: var(--_goal); stroke-width: 3; stroke-linecap: butt; }
.center {
  position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
  text-align: center; padding: 1.4rem; font-weight: 600; font-variant-numeric: tabular-nums;
}
.bar { position: relative; width: 100%; height: 0.9rem; border-radius: 999px; background: var(--_track); }
.bar .fill { height: 100%; border-radius: inherit; background: var(--_fill); transition: width 0.4s ease; }
.bar .goal { position: absolute; top: -4px; bottom: -4px; width: 3px; background: var(--_goal); border-radius: 2px; }
.barlabel { font-weight: 600; font-variant-numeric: tabular-nums; }
.done-slot { text-align: center; color: var(--_fill); font-weight: 600; }
.meta { color: var(--_muted); font-size: 0.85rem; text-align: center; }
.image ::slotted(img), ::slotted(img) { max-width: 100%; border-radius: var(--_radius); }
[hidden] { display: none !important; }
`);

const NS = 'http://www.w3.org/2000/svg';
const R = 45;
const C = 2 * Math.PI * R;
const pct = (value, max) => (max > 0 ? Math.min(100, Math.max(0, (value / max) * 100)) : 0);

class UiProgress extends HTMLElement {
  static observedAttributes = ['value', 'max', 'variant', 'goal', 'label', 'heading', 'store', 'path', 'where'];

  constructor() {
    super();
    this._wasDone = false;
    const root = this.attachShadow({ mode: 'open' });
    root.adoptedStyleSheets = [styles];
    root.innerHTML = `
      <div class="card" part="card">
        <div class="heading" part="heading"></div>
        <div class="graphic" part="graphic" role="progressbar" aria-valuemin="0">
          <svg class="ring" viewBox="0 0 100 100" aria-hidden="true">
            <circle class="track" cx="50" cy="50" r="${R}"></circle>
            <circle class="fill" cx="50" cy="50" r="${R}" stroke-dasharray="${C}" stroke-dashoffset="${C}"></circle>
            <circle class="goal" cx="50" cy="50" r="${R}" hidden></circle>
          </svg>
          <div class="center"><span class="label" part="label"></span><span class="done-slot" hidden><slot name="done"></slot></span></div>
          <div class="bar" hidden><div class="fill"></div><div class="goal" hidden></div></div>
        </div>
        <div class="barlabel" part="label" hidden></div>
        <slot name="image"></slot>
        <div class="meta"><slot name="meta"></slot></div>
        <div class="sr-only" aria-live="polite"></div>
      </div>`;
    const q = (s) => root.querySelector(s);
    this._card = q('.card');
    this._head = q('.heading');
    this._graphic = q('.graphic');
    this._ring = q('.ring');
    this._ringFill = q('.ring .fill');
    this._ringGoal = q('.ring .goal');
    this._center = q('.center');
    this._label = q('.center .label');
    this._doneSlot = q('.done-slot');
    this._bar = q('.bar');
    this._barFill = q('.bar .fill');
    this._barGoal = q('.bar .goal');
    this._barLabel = q('.barlabel');
    this._live = q('[aria-live]');
  }

  connectedCallback() {
    this._subscribe();
    this._render();
  }

  disconnectedCallback() { this._unsub?.(); this._unsub = null; }

  // Before connection there is nothing to render for (and a ui-complete would reach no listener).
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

  // {value, max} from the attributes, or from the store when bound.
  _amounts() {
    const store = this.getAttribute('store');
    const maxAttr = this.getAttribute('max');
    const explicitMax = Number(maxAttr) || 100;
    if (!store) return { value: Number(this.getAttribute('value')) || 0, max: explicitMax };
    const arr = get(store, this.getAttribute('path') || 'items');
    const items = Array.isArray(arr) ? arr : [];
    const where = json(this, 'where');
    const value = items.filter((it) => it != null && typeof it === 'object' && matches(it, where)).length;
    return { value, max: maxAttr === null ? items.length : explicitMax };
  }

  get value() { return this._amounts().value; }
  set value(v) { this.setAttribute('value', String(v)); }
  get max() { return this._amounts().max; }
  set max(v) { this.setAttribute('max', String(v)); }
  get percent() { const { value, max } = this._amounts(); return pct(value, max); }

  increment(by = 1) { if (!this.hasAttribute('store')) this.value = Math.min(this.max, this.value + by); }

  _render() {
    const { value, max } = this._amounts();
    const ring = this.getAttribute('variant') !== 'bar';
    const percent = pct(value, max);
    const done = max > 0 && value >= max;
    const hasDone = this.querySelector('[slot="done"]') !== null;
    const fill = { value, max, percent: Math.round(percent) };
    const tpl = this.getAttribute('label');
    const label = tpl ? tpl.replace(/\{(value|max|percent)\}/g, (_, k) => String(fill[k])) : `${fill.percent}%`;
    const goalAttr = this.getAttribute('goal');
    const goalPct = goalAttr === null ? null : pct(Number(goalAttr), max);

    this._card.toggleAttribute('data-done', done);
    this._head.textContent = this.getAttribute('heading') || '';
    this._graphic.setAttribute('aria-valuemax', String(max));
    this._graphic.setAttribute('aria-valuenow', String(Math.min(value, max)));
    this._graphic.setAttribute('aria-valuetext', label);
    this._graphic.setAttribute('aria-label', this.getAttribute('heading') || label);

    // SVG elements have no `hidden` property, so toggle the attribute
    this._ring.toggleAttribute('hidden', !ring);
    this._center.hidden = !ring;
    this._bar.hidden = ring;
    this._barLabel.hidden = ring;

    const showDone = done && hasDone;
    this._label.hidden = showDone;
    this._doneSlot.hidden = !showDone;
    this._label.textContent = label;
    this._barLabel.textContent = showDone ? '' : label;
    if (showDone && !ring) this._barLabel.append(this._doneSlot);
    else if (this._doneSlot.parentNode !== this._center) this._center.append(this._doneSlot);

    this._ringFill.style.strokeDashoffset = String(C * (1 - percent / 100));
    this._barFill.style.width = `${percent}%`;

    this._ringGoal.toggleAttribute('hidden', goalPct === null);
    if (goalPct !== null) {
      // a short tick on the ring: a dash of 1.5% of the circumference, offset to the goal angle
      this._ringGoal.setAttribute('stroke-dasharray', `${C * 0.015} ${C}`);
      this._ringGoal.setAttribute('stroke-dashoffset', String(-C * (goalPct / 100) + C * 0.0075));
    }
    this._barGoal.hidden = goalPct === null;
    if (goalPct !== null) this._barGoal.style.left = `calc(${goalPct}% - 1.5px)`;

    if (done && !this._wasDone) {
      this._live.textContent = 'Complete';
      emit(this, 'ui-complete', { value, max });
    }
    if (!done) this._live.textContent = '';
    this._wasDone = done;
  }
}

define('ui-progress', UiProgress);
