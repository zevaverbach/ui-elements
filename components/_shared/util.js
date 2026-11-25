// Shared helpers for ui-* components. Not a component: nothing is registered here.
//
// Exports:
//   emit(el, name, detail?, init?)  dispatch a bubbling, composed CustomEvent; returns the event
//   define(tag, cls)                customElements.define() that is safe to run twice
//   reducedMotion()                 true if the user prefers reduced motion
//   coarsePointer()                 true on touch-first devices
//   uid(prefix?)                    short unique id
//   json(el, attr)                  parse a JSON-object attribute; {} when absent or invalid (and warns)
//   field(obj, path)                read a dot path ("a.b") from an object; undefined if missing
//   matches(item, where)            true if every {field: value} in `where` equals field(item, field)

export const emit = (el, name, detail = {}, init = {}) => {
  const ev = new CustomEvent(name, { detail, bubbles: true, composed: true, ...init });
  el.dispatchEvent(ev);
  return ev;
};

export const define = (tag, cls) => {
  if (!customElements.get(tag)) customElements.define(tag, cls);
};

export const reducedMotion = () => matchMedia('(prefers-reduced-motion: reduce)').matches;
export const coarsePointer = () => matchMedia('(pointer: coarse)').matches;

export const uid = (prefix = 'id') => `${prefix}-${Math.random().toString(36).slice(2, 9)}`;

export const json = (el, attr) => {
  const raw = el.getAttribute(attr);
  if (!raw) return {};
  try { const v = JSON.parse(raw); return v && typeof v === 'object' ? v : {}; } catch (err) {
    console.warn(`[${el.localName}] invalid JSON in "${attr}"`, err);
    return {};
  }
};

export const field = (obj, path) => String(path).split('.').reduce((o, k) => (o == null ? undefined : o[k]), obj);

export const matches = (item, where) => Object.entries(where).every(([k, v]) => field(item, k) === v);
