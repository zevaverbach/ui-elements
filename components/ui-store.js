// <ui-store> — non-visual element that declares named, observable, optionally persistent JSON state.
// The element is only a handle: the data lives in a module-level registry (_shared/store-registry.js),
// so removing the element (or swapping it out of the page and back) never loses data.
//
// Usage:
//   <ui-store name="todos" persist="local">
//     <script type="application/json">{"items":[{"id":"1","text":"Buy milk","done":false}]}</script>
//   </ui-store>
//
// Attributes:
//   name      string (required)   store name; without it the element warns and does nothing
//   persist   "none" (default) | "local" | "session"   storage key is "ui-store:<name>" unless `key` is given
//   key       string              override the storage key
//   version   string, default "1" stored value is {v, data}; a different stored v is ignored (seed is used)
//   src       URL                 fetch JSON as the seed on first creation (failure is non-fatal)
//   Seed precedence (only when no store with this name exists yet): persisted data, src, inline JSON script.
//   Two elements with the same name share one store; the first to create it wins (a conflicting
//   `persist` logs a warning).
//
// Properties / methods:
//   data                get/set the root value (must be JSON-serializable)
//   get(path)           read a dot path ("items", "settings.theme"); "" is the root
//   set(path, value)    replace a branch; subscribers are notified once per microtask batch
//   act(action, payload)  run an action (see below)
//
// Slots: none (a child <script type="application/json"> is the inline seed).
//
// Events (dispatched on the element while connected; bubble, composed):
//   ui-store-ready   {name, data}          once, after hydration (persisted / src / seed)
//   ui-store-change  {name, path, data}    after every change; `path` is "" when several paths changed in one
//                                          batch. This is the hook for server sync (page code listens and POSTs).
//
// Actions: components request changes with a bubbling, composed `ui-action` event,
//   detail {store, action, payload}; it is routed by store name to the store, wherever the
//   sender is in the DOM. Actions work on the array of objects at payload.path (default "items"), items identified by `id`:
//   add {item, index?} · remove {id} · update {id, patch} · toggle {id, field} · move {id, toIndex} · set {path, value} · clear {}
//
// CSS custom properties: none (display: none).

import { emit, define } from './_shared/util.js';
import { ensureStore, getStore, get, set, subscribe, dispatch } from './_shared/store-registry.js';

export class UiStore extends HTMLElement {
  static observedAttributes = ['name'];

  connectedCallback() {
    const name = this.getAttribute('name');
    this.style.display = 'none';
    if (!name) { console.warn('[ui-store] missing required "name" attribute; element ignored', this); return; }
    this._name = name;
    const existing = getStore(name);
    const rec = ensureStore(name, {
      persist: this.getAttribute('persist') ?? 'none',
      key: this.getAttribute('key') ?? undefined,
      version: this.getAttribute('version') ?? '1',
      src: this.getAttribute('src') ?? undefined,
      seed: existing ? undefined : this._inlineSeed(),
    });
    this._unsub?.();
    this._unsub = subscribe(name, ({ path, data }) => emit(this, 'ui-store-change', { name, path, data }));
    const token = (this._token = Symbol());
    rec.ready.then(() => {
      if (this._token === token && this.isConnected) emit(this, 'ui-store-ready', { name, data: rec.data });
    });
  }

  // Data is deliberately NOT deleted here.
  disconnectedCallback() { this._unsub?.(); this._unsub = null; this._token = null; }

  attributeChangedCallback(attr, oldV, newV) {
    if (attr === 'name' && this.isConnected && oldV !== null && oldV !== newV) { this.disconnectedCallback(); this.connectedCallback(); }
  }

  _inlineSeed() {
    const el = this.querySelector(':scope > script[type="application/json"]');
    if (!el) return undefined;
    try { return JSON.parse(el.textContent); } catch (err) { console.warn(`[ui-store] "${this._name}": inline seed is not valid JSON`, err); return undefined; }
  }

  get data() { return get(this._name, ''); }
  set data(v) { if (this._name) set(this._name, '', v); }
  get(path = '') { return get(this._name, path); }
  set(path, value) { return set(this._name, path, value); }
  act(action, payload) { return dispatch(this._name, action, payload); }
}

define('ui-store', UiStore);
