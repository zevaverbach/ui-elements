// <ui-each> — renders one child component per item of a store array, and turns the children's
// events into store actions. Children are reconciled by key (reused, updated in place, reordered,
// removed), so focus and transient UI state inside them survive store changes.
//
// Usage:
//   <ui-each id="todos" store="todos" path="items" tag="ui-todo-item"
//            map='{"text":"text","checked":"done"}'
//            events='{"ui-toggle":{"action":"toggle","field":"done"},
//                     "ui-reorder":{"action":"move"},
//                     "ui-delete":{"action":"remove"},
//                     "ui-edit":{"action":"update","patch":{"text":"$detail.text"}}}'></ui-each>
//
// Attributes:
//   store    string (required)   store name (the store may be declared later)
//   path     string, default "items"   dot path to the array in the store
//   tag      string (required)   child tag, e.g. ui-todo-item
//   map      JSON {childAttr: itemField}   item field (dot path ok) -> child attribute. true sets a boolean
//            attribute, false/null/undefined removes it, anything else is String()-ed. Example {"text":"text","checked":"done"}
//   key      string, default "id"   item field used for identity
//   events   JSON {childEvent: {action, ...}}   child event -> ui-action. Entries: `action` (add|remove|update|toggle|move|set|clear),
//            plus optional `field` (toggle), `patch` (update). Any string value starting "$detail." is read from event.detail
//            (e.g. {"done":"$detail.checked"}). Payload `id` is always the item's id. For `move`, `toIndex` defaults to
//            event.detail.to. A cancelable event that someone called preventDefault() on dispatches nothing.
//   where    JSON {field: value}   optional equality filter: render only matching items (path as in map). Reorders
//            inside a filtered list are translated to positions in the full array.
//
// Slots: none. Renders into its own light DOM with display: contents, so layout components work around it.
// Children get id "<ui-each id>-<key>" (give <ui-each> a stable id) and data-each-key.
//
// Events: none of its own. It dispatches bubbling, composed `ui-action` events
//   (detail {store, action, payload}) which the store registry routes by store name.
//
// Child event shapes it understands (see components.json):
//   ui-todo-item: ui-toggle {checked, progress}, ui-edit {text, previousText}, ui-delete {text},
//                 ui-reorder {from, to}, ui-progress {progress}, ui-transcript {text, final, value}
//
// CSS custom properties: none.

import { emit, define, uid } from './_shared/util.js';
import { get, subscribe, dispatch } from './_shared/store-registry.js';

const json = (el, attr) => {
  const raw = el.getAttribute(attr);
  if (!raw) return {};
  try { const v = JSON.parse(raw); return v && typeof v === 'object' ? v : {}; } catch (err) {
    console.warn(`[ui-each] invalid JSON in "${attr}"`, err);
    return {};
  }
};
const field = (item, path) => String(path).split('.').reduce((o, k) => (o == null ? undefined : o[k]), item);
const resolve = (v, detail) => {
  if (typeof v === 'string' && v.startsWith('$detail.')) return field(detail, v.slice(8));
  if (v && typeof v === 'object') return Object.fromEntries(Object.entries(v).map(([k, x]) => [k, resolve(x, detail)]));
  return v;
};

export class UiEach extends HTMLElement {
  static observedAttributes = ['store', 'path', 'tag', 'map', 'key', 'events', 'where', 'id'];

  constructor() {
    super();
    this._onEvent = (e) => this._handle(e);
    this._wired = new Set();
  }

  connectedCallback() {
    this.style.display = 'contents';
    this._subscribe();
    this._wire();
    this._render();
  }
  disconnectedCallback() {
    this._unsub?.(); this._unsub = null;
    for (const n of this._wired) window.removeEventListener(n, this._onEvent);
    this._wired.clear();
  }
  attributeChangedCallback(name, oldV, newV) {
    if (oldV === newV || !this.isConnected) return;
    if (name === 'store') this._subscribe();
    if (name === 'events') this._wire();
    this._render();
  }

  _subscribe() {
    this._unsub?.();
    const store = this.getAttribute('store');
    this._unsub = store ? subscribe(store, () => this._render()) : null;
  }

  // Listen on window (bubble phase) so every listener between the child and window, including page code that
  // calls preventDefault(), has run before we decide whether to dispatch the action.
  _wire() {
    const want = new Set(Object.keys(json(this, 'events')));
    for (const n of this._wired) if (!want.has(n)) { window.removeEventListener(n, this._onEvent); this._wired.delete(n); }
    for (const n of want) if (!this._wired.has(n)) { window.addEventListener(n, this._onEvent); this._wired.add(n); }
  }

  _items() {
    const arr = get(this.getAttribute('store'), this.getAttribute('path') || 'items');
    return Array.isArray(arr) ? arr : [];
  }
  _visible(items) {
    const where = json(this, 'where');
    const entries = Object.entries(where);
    return entries.length ? items.filter((it) => entries.every(([k, v]) => field(it, k) === v)) : items;
  }
  get _keyField() { return this.getAttribute('key') || 'id'; }

  _render() {
    const tag = this.getAttribute('tag');
    const store = this.getAttribute('store');
    if (!tag || !store) return;
    if (!this.id) this.id = uid('each');
    const map = json(this, 'map');
    const kf = this._keyField;
    const items = this._visible(this._items());

    const existing = new Map();
    for (const el of this.children) if (el.dataset.eachKey !== undefined && el.localName === tag) existing.set(el.dataset.eachKey, el);

    const wanted = [];
    const seen = new Set();
    for (const item of items) {
      const k = field(item, kf);
      if (k == null || seen.has(String(k))) continue; // skip items without a usable unique key
      seen.add(String(k));
      let el = existing.get(String(k));
      if (!el) { el = document.createElement(tag); el.dataset.eachKey = String(k); }
      el.id = `${this.id}-${k}`;
      for (const [attr, f] of Object.entries(map)) {
        const v = field(item, f);
        if (v === true) { if (el.getAttribute(attr) !== '') el.setAttribute(attr, ''); }
        else if (v === false || v == null) el.removeAttribute(attr);
        else if (el.getAttribute(attr) !== String(v)) el.setAttribute(attr, String(v));
      }
      wanted.push(el);
    }
    // Remove stale children (anything of ours not wanted any more).
    for (const el of [...this.children]) if (!wanted.includes(el)) el.remove();
    // Order: only move elements that are out of place (moving drops focus).
    let cursor = this.firstElementChild;
    for (const el of wanted) {
      if (el === cursor) cursor = cursor.nextElementSibling;
      else this.insertBefore(el, cursor);
    }
  }

  _handle(e) {
    const path = e.composedPath();
    const child = path.find((n) => n.parentNode === this && n.dataset?.eachKey !== undefined);
    if (!child || !this.isConnected) return;
    if (e.cancelable && e.defaultPrevented) return;
    const spec = json(this, 'events')[e.type];
    if (!spec?.action) return;
    const store = this.getAttribute('store');
    const arrPath = this.getAttribute('path') || 'items';
    const id = child.dataset.eachKey;
    const payload = { path: arrPath, id: this._itemId(child.dataset.eachKey) ?? id };
    if (spec.field) payload.field = spec.field;
    if (spec.patch) payload.patch = resolve(spec.patch, e.detail ?? {});
    if (spec.action === 'move') {
      const to = spec.toIndex !== undefined ? resolve(spec.toIndex, e.detail ?? {}) : e.detail?.to;
      payload.toIndex = this._fullIndex(to);
      if (payload.toIndex == null) return;
    }
    if (spec.action === 'set') { payload.path = spec.path ?? arrPath; payload.value = resolve(spec.value, e.detail ?? {}); }
    emit(this, 'ui-action', { store, action: spec.action, payload });
  }

  // Item id as stored (keeps its original type) for the child with this key.
  _itemId(key) {
    const it = this._items().find((x) => String(field(x, this._keyField)) === key);
    return it?.id;
  }

  // Translate a position in the visible (possibly filtered) list to a position in the full array.
  _fullIndex(to) {
    if (!Number.isInteger(to)) return null;
    const all = this._items();
    const vis = this._visible(all);
    if (vis.length === all.length) return to;
    const target = vis[Math.max(0, Math.min(vis.length - 1, to))];
    return target ? all.indexOf(target) : null;
  }
}

define('ui-each', UiEach);
