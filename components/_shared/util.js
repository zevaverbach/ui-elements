// Shared helpers for ui-* components. Not a component: nothing is registered here.
//
// Exports:
//   emit(el, name, detail?, init?)  dispatch a bubbling, composed CustomEvent; returns the event
//   define(tag, cls)                customElements.define() that is safe to run twice
//   reducedMotion()                 true if the user prefers reduced motion
//   coarsePointer()                 true on touch-first devices
//   uid(prefix?)                    short unique id

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
