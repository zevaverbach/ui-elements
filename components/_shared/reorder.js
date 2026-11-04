// Reorder engine for sibling elements of the same tag. Not a component.
//
// Works with pointer (mouse, pen, touch) and keyboard through one code path: during a
// move the dragged element and its siblings are shifted visually with CSS transforms
// (so focus and pointer capture are never lost to DOM churn), and the DOM is changed once,
// on commit. Siblings animate out of the way unless the user prefers reduced motion.
//
// Exports:
//   class Reorder
//     new Reorder(hostElement)
//     begin()          -> boolean   snapshot siblings; false if there is nothing to reorder
//     dragTo(dy)                    pointer: dragged element is dy px from its start position
//     moveBy(n)                     keyboard: move n places (negative = up), clamped
//     end(commit)      -> {from, to} | null   finish; commit=false restores. Result only if the order changed
//     index, count                  current target index and number of siblings

import { reducedMotion } from './util.js';

export class Reorder {
  constructor(host) { this.host = host; this.active = false; }

  begin() {
    const parent = this.host.parentElement;
    if (!parent) return false;
    this.parent = parent;
    this.items = [...parent.children].filter((c) => c.localName === this.host.localName);
    if (this.items.length < 2) return false;
    this.from = this.index = this.items.indexOf(this.host);
    this.rects = this.items.map((i) => i.getBoundingClientRect());
    const r = this.rects[this.from];
    const next = this.rects[this.from + 1];
    const prev = this.rects[this.from - 1];
    const gap = next ? next.top - r.bottom : prev ? r.top - prev.bottom : 0;
    this.h = r.height;
    this.stride = this.h + Math.max(0, gap);
    const anim = reducedMotion() ? 'none' : 'transform 150ms ease';
    for (const it of this.items) {
      it.style.transition = it === this.host ? 'none' : anim;
      it.style.willChange = 'transform';
    }
    this.host.style.position = 'relative';
    this.host.style.zIndex = '10';
    this.active = true;
    return true;
  }

  get count() { return this.items?.length ?? 0; }

  _shift(idx) {
    this.items.forEach((it, i) => {
      if (it === this.host) return;
      let s = 0;
      if (idx > this.from && i > this.from && i <= idx) s = -this.stride;
      else if (idx < this.from && i < this.from && i >= idx) s = this.stride;
      it.style.transform = s ? `translateY(${s}px)` : '';
    });
    this.index = idx;
  }

  dragTo(dy) {
    if (!this.active) return;
    const center = this.rects[this.from].top + dy + this.h / 2;
    let idx = this.from;
    this.rects.forEach((r, i) => {
      const mid = r.top + r.height / 2;
      if (i < this.from && center < mid) idx = Math.min(idx, i);
      if (i > this.from && center > mid) idx = Math.max(idx, i);
    });
    this.host.style.transform = `translateY(${dy}px)`;
    this._shift(idx);
  }

  moveBy(n) {
    if (!this.active) return;
    const idx = Math.max(0, Math.min(this.items.length - 1, this.index + n));
    const start = this.rects[this.from];
    let offset = 0;
    if (idx > this.from) offset = this.rects[idx].bottom - this.h - start.top;
    else if (idx < this.from) offset = this.rects[idx].top - start.top;
    this.host.style.transform = offset ? `translateY(${offset}px)` : '';
    this._shift(idx);
  }

  end(commit) {
    if (!this.active) return null;
    this.active = false;
    for (const it of this.items) {
      it.style.transform = it.style.transition = it.style.willChange = '';
    }
    this.host.style.position = this.host.style.zIndex = '';
    if (!commit || this.index === this.from) return null;
    const ref = this.index > this.from ? this.items[this.index].nextSibling : this.items[this.index];
    this.parent.insertBefore(this.host, ref);
    return { from: this.from, to: this.index };
  }
}
