// <ui-todo-item> — one to-do item: checkbox, inline edit, delete, speech-to-text mic,
// drag/keyboard/touch reordering among sibling <ui-todo-item>s, optional progress steps.
//
// Usage:
//   <script type="module" src="https://cdn.jsdelivr.net/gh/zevaverbach/ui-elements@v0.1.0/components/ui-todo-item.js"></script>
//   <ui-todo-item text="Buy milk"></ui-todo-item>
//
// Attributes / properties (all reflect):
//   text         string   the item's text                              (prop: text)
//   checked      boolean  done                                         (prop: checked)
//   editing      boolean  inline edit mode                             (prop: editing)
//   label        string   small eyebrow label above the text, e.g. "Small"
//   progress     0-100    if present, shows 4 progress steps (25/50/75/100). Checking sets 100,
//                         unchecking from 100 sets 75 (Day Stack behavior)
//   lang         string   BCP-47 language for dictation (default: document language)
//   no-speech    boolean  never show the mic button
//   no-reorder   boolean  hide the drag handle / disable reordering
//   no-confirm   boolean  delete immediately instead of arm-then-confirm (click twice within 2.6 s)
//
// Slots:
//   meta         extra content under the text (tags, due date, ...)
//
// Events (all bubble and are composed; detail shapes):
//   ui-toggle      {checked: boolean, progress: number|null}
//   ui-edit        {text: string, previousText: string}               after an edit is committed
//   ui-delete      {text: string}  cancelable; if not prevented the element removes itself
//   ui-transcript  {text: string, final: boolean, value: string}     speech-to-text result;
//                  `value` is the edit field's content after a final result is appended
//   ui-progress    {progress: number}
//   ui-reorder     {from: number, to: number}   indices among sibling ui-todo-items, after DOM moved
//
// Methods: focusText(), startEdit(), cancelEdit(), commitEdit()
//
// Keyboard: Space/Enter on the drag handle grabs; Arrow Up/Down move; Space/Enter drops;
//   Escape cancels. In edit mode Enter commits and Escape cancels. Pointer and touch: drag the handle.
//
// CSS custom properties (all optional; fall back to the shared --ui-* tokens in tokens.css):
//   --ui-todo-item-bg, --ui-todo-item-border, --ui-todo-item-radius, --ui-todo-item-padding,
//   --ui-todo-item-text, --ui-todo-item-muted, --ui-todo-item-accent, --ui-todo-item-danger
// Parts: row, handle, text, edit-input, mic, delete

import { emit, define } from './_shared/util.js';
import { sheet } from './_shared/base.js';
import { speechSupported, createDictation } from './_shared/speech.js';
import { Reorder } from './_shared/reorder.js';

const CONFIRM_MS = 2600;

const styles = sheet(`
:host { display: block; }
.row {
  position: relative; display: flex; align-items: center; gap: 0.25rem;
  padding: var(--ui-todo-item-padding, 0.35rem 0.5rem);
  background: var(--ui-todo-item-bg, var(--_surface));
  border: 1px solid var(--ui-todo-item-border, var(--_border));
  border-radius: var(--ui-todo-item-radius, var(--_radius));
  color: var(--ui-todo-item-text, var(--_text));
  overflow: hidden;
}
:host(.reordering) .row { box-shadow: 0 6px 18px rgb(0 0 0 / 0.25); border-color: var(--ui-todo-item-accent, var(--_accent)); }
.handle { cursor: grab; touch-action: none; user-select: none; -webkit-user-select: none; }
.handle[aria-pressed="true"] { color: var(--ui-todo-item-accent, var(--_accent)); border-color: currentColor; }
:host(.reordering) .handle { cursor: grabbing; }
.check { width: 1.15rem; height: 1.15rem; margin: 0 0.35rem; accent-color: var(--ui-todo-item-accent, var(--_accent)); flex: none; }
.main { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 0.1rem; padding: 0.15rem 0; }
.eyebrow { font-size: 0.7rem; letter-spacing: 0.06em; text-transform: uppercase; color: var(--ui-todo-item-muted, var(--_muted)); }
.text { overflow-wrap: anywhere; cursor: text; border-radius: 4px; }
:host([checked]) .text { text-decoration: line-through; color: var(--ui-todo-item-muted, var(--_muted)); }
.edit {
  width: 100%; font: inherit; color: inherit; background: var(--_surface-2);
  border: 1px solid var(--ui-todo-item-border, var(--_border)); border-radius: 4px; padding: 0.3rem 0.45rem;
}
.steps { display: flex; gap: 3px; flex: none; }
.step { width: 0.9rem; height: 1.4rem; padding: 0; background: var(--_surface-2); border: 1px solid var(--ui-todo-item-border, var(--_border)); border-radius: 3px; }
.step.on { background: var(--ui-todo-item-accent, var(--_accent)); border-color: var(--ui-todo-item-accent, var(--_accent)); }
.mic[aria-pressed="true"] { color: var(--ui-todo-item-danger, var(--_danger)); border-color: currentColor; animation: pulse 1.1s ease-in-out infinite; }
@keyframes pulse { 50% { opacity: 0.45; } }
.del.armed { color: var(--ui-todo-item-danger, var(--_danger)); border-color: currentColor; padding: 0 0.4rem; }
`);

const icon = (d) => `<svg viewBox="0 0 24 24" aria-hidden="true">${d}</svg>`;
const ICONS = {
  grip: icon('<circle cx="9" cy="6" r="1"/><circle cx="15" cy="6" r="1"/><circle cx="9" cy="12" r="1"/><circle cx="15" cy="12" r="1"/><circle cx="9" cy="18" r="1"/><circle cx="15" cy="18" r="1"/>'),
  mic: icon('<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/>'),
  edit: icon('<path d="M4 20h4L19 9l-4-4L4 16z"/>'),
  del: icon('<path d="M5 5l14 14M19 5L5 19"/>'),
};

export class UiTodoItem extends HTMLElement {
  static observedAttributes = ['text', 'checked', 'editing', 'label', 'progress', 'no-speech', 'no-reorder'];

  constructor() {
    super();
    this.attachShadow({ mode: 'open' }).adoptedStyleSheets = [styles];
    this._armed = false;
    this._reorder = new Reorder(this);
    this._dict = createDictation({
      lang: () => this.getAttribute('lang'),
      onResult: (text, final) => this._onTranscript(text, final),
      onState: (on) => this._mic?.setAttribute('aria-pressed', String(on)),
    });
    this._build();
  }

  connectedCallback() { this._sync(); }
  disconnectedCallback() { this._dict.stop(); }
  attributeChangedCallback(name, oldV, newV) {
    if (oldV === newV) return;
    this._sync();
    if (name === 'editing') newV === null ? this._dict.stop() : this._focusEdit();
  }

  // ---- properties ----
  get text() { return this.getAttribute('text') ?? ''; }
  set text(v) { this.setAttribute('text', v ?? ''); }
  get checked() { return this.hasAttribute('checked'); }
  set checked(v) { this.toggleAttribute('checked', !!v); }
  get editing() { return this.hasAttribute('editing'); }
  set editing(v) { this.toggleAttribute('editing', !!v); }
  get progress() { return this.hasAttribute('progress') ? Number(this.getAttribute('progress')) || 0 : null; }
  set progress(v) { v == null ? this.removeAttribute('progress') : this.setAttribute('progress', String(v)); }

  // ---- DOM ----
  _build() {
    const r = this.shadowRoot;
    r.innerHTML = `
      <div class="row" part="row">
        <button class="icon-btn handle" part="handle" type="button" aria-pressed="false">${ICONS.grip}</button>
        <input class="check" type="checkbox">
        <div class="main">
          <span class="eyebrow" hidden></span>
          <span class="text" part="text"></span>
          <input class="edit" part="edit-input" type="text" hidden autocomplete="off" enterkeyhint="done">
          <slot name="meta"></slot>
        </div>
        <div class="steps" role="group" aria-label="Progress" hidden>
          ${[25, 50, 75, 100].map((v) => `<button class="step" type="button" data-v="${v}"></button>`).join('')}
        </div>
        <button class="icon-btn mic" part="mic" type="button" aria-pressed="false" hidden>${ICONS.mic}</button>
        <button class="icon-btn editbtn" type="button">${ICONS.edit}</button>
        <button class="icon-btn del" part="delete" type="button"><span class="x">${ICONS.del}</span></button>
      </div>
      <div class="sr-only" role="status" aria-live="assertive"></div>`;
    const $ = (s) => r.querySelector(s);
    Object.assign(this, {
      _handle: $('.handle'), _check: $('.check'), _eyebrow: $('.eyebrow'), _text: $('.text'), _edit: $('.edit'),
      _steps: $('.steps'), _mic: $('.mic'), _editBtn: $('.editbtn'), _del: $('.del'), _live: $('[role=status]'),
    });

    this._check.addEventListener('change', () => this._setChecked(this._check.checked));
    this._text.addEventListener('dblclick', () => this.startEdit());
    this._editBtn.addEventListener('click', () => (this.editing ? this.commitEdit() : this.startEdit()));
    this._del.addEventListener('click', () => this._onDelete());
    for (const b of [this._mic, this._editBtn]) b.addEventListener('pointerdown', (e) => e.preventDefault()); // keep focus in the edit field
    this._mic.addEventListener('click', () => this._onMic());
    this._steps.addEventListener('click', (e) => {
      const b = e.target.closest('.step');
      if (b) this._onStep(Number(b.dataset.v));
    });
    this._edit.addEventListener('keydown', (e) => {
      if (e.isComposing) return;
      if (e.key === 'Enter') { e.preventDefault(); this.commitEdit(); }
      else if (e.key === 'Escape') { e.preventDefault(); this.cancelEdit(); }
    });
    this._edit.addEventListener('focusout', (e) => {
      if (e.relatedTarget === this._mic) return;
      if (this.editing) this.commitEdit();
    });
    this._wireReorder();
  }

  _sync() {
    if (!this._text) return;
    const text = this.text;
    this._text.textContent = text;
    this._check.checked = this.checked;
    this._check.setAttribute('aria-label', text || 'Done');
    const label = this.getAttribute('label');
    this._eyebrow.hidden = !label;
    this._eyebrow.textContent = label ?? '';
    const p = this.progress;
    this._steps.hidden = p === null;
    this._steps.querySelectorAll('.step').forEach((b) => {
      const v = Number(b.dataset.v);
      b.classList.toggle('on', p !== null && p >= v);
      b.setAttribute('aria-label', `Set ${v} percent`);
      b.setAttribute('aria-pressed', String(p !== null && p >= v));
    });
    const editing = this.editing;
    this._text.hidden = editing;
    this._edit.hidden = !editing;
    this._editBtn.setAttribute('aria-label', editing ? 'Save' : `Edit ${text}`);
    this._editBtn.title = editing ? 'Save' : 'Edit';
    const canSpeak = speechSupported() && !this.hasAttribute('no-speech');
    this._mic.hidden = !canSpeak;
    this._mic.setAttribute('aria-label', 'Dictate text');
    this._mic.title = 'Dictate';
    const canReorder = !this.hasAttribute('no-reorder');
    this._handle.hidden = !canReorder;
    this._handle.setAttribute('aria-label', `Reorder ${text}. Press space to grab, arrow keys to move.`);
    this._setArmed(this._armed);
  }

  focusText() { (this.editing ? this._edit : this._check).focus(); }

  // ---- behavior ----
  _setChecked(checked) {
    this.checked = checked;
    if (this.progress !== null) {
      if (checked) this.progress = 100;
      else if (this.progress === 100) this.progress = 75;
    }
    emit(this, 'ui-toggle', { checked, progress: this.progress });
  }

  _onStep(v) {
    if (v >= 100) { this._setChecked(true); return; }
    const next = this.progress === v ? v - 25 : v; // clicking the active step steps back one
    this.progress = next;
    if (this.checked) this.checked = false;
    emit(this, 'ui-progress', { progress: next });
  }

  startEdit() {
    this._edit.value = this.text;
    this.editing = true;
  }
  _focusEdit() {
    this._edit.value = this._edit.value || this.text;
    const focus = () => { this._edit.focus(); this._edit.setSelectionRange(this._edit.value.length, this._edit.value.length); };
    focus();                                                             // now, so keys typed straight after the click are not lost
    if (this.shadowRoot.activeElement !== this._edit) requestAnimationFrame(focus);   // not rendered yet (e.g. element not connected)
  }
  commitEdit() {
    if (!this.editing) return;
    const next = this._edit.value.trim();
    const previousText = this.text;
    this.editing = false;
    if (next && next !== previousText) {
      this.text = next;
      emit(this, 'ui-edit', { text: next, previousText });
    }
  }
  cancelEdit() { this.editing = false; }

  _onMic() {
    if (!this.editing) this.startEdit();
    this._dict.toggle();
  }
  _onTranscript(text, final) {
    if (!text) return;
    if (final) {
      this._edit.value = `${this._edit.value} ${text}`.trim();
      this._edit.focus();
    }
    emit(this, 'ui-transcript', { text, final, value: this._edit.value });
  }

  _setArmed(on) {
    this._armed = on;
    this._del.classList.toggle('armed', on);
    this._del.setAttribute('aria-label', on ? `Confirm delete ${this.text}` : `Delete ${this.text}`);
    this._del.querySelector('.x').innerHTML = on ? '?' : ICONS.del;
  }
  _onDelete() {
    if (!this.hasAttribute('no-confirm') && !this._armed) {
      this._setArmed(true);
      this._say('Press delete again to confirm');
      clearTimeout(this._armTimer);
      this._armTimer = setTimeout(() => this._setArmed(false), CONFIRM_MS);
      return;
    }
    clearTimeout(this._armTimer);
    this._setArmed(false);
    const ev = emit(this, 'ui-delete', { text: this.text }, { cancelable: true });
    if (!ev.defaultPrevented) this.remove();
  }

  _say(msg) {
    this._live.textContent = '';
    requestAnimationFrame(() => { this._live.textContent = msg; });
  }

  // ---- reordering ----
  _wireReorder() {
    const h = this._handle;
    const R = this._reorder;
    let startY = 0;
    let mode = null; // 'pointer' | 'key'
    const finish = (commit) => {
      mode = null;
      this.classList.remove('reordering');
      h.setAttribute('aria-pressed', 'false');
      const res = R.end(commit);
      if (res) {
        this._say(`Moved to position ${res.to + 1} of ${R.count}`);
        h.focus();
        emit(this, 'ui-reorder', res);
      } else if (!commit) this._say('Reorder cancelled');
    };

    h.addEventListener('pointerdown', (e) => {
      if (e.button !== 0 || mode || !R.begin()) return;
      mode = 'pointer';
      startY = e.clientY;
      h.setPointerCapture(e.pointerId);
      this.classList.add('reordering');
    });
    h.addEventListener('pointermove', (e) => { if (mode === 'pointer') R.dragTo(e.clientY - startY); });
    h.addEventListener('pointerup', () => { if (mode === 'pointer') finish(true); });
    h.addEventListener('pointercancel', () => { if (mode === 'pointer') finish(false); });

    h.addEventListener('keydown', (e) => {
      if (mode === null) {
        if ((e.key === ' ' || e.key === 'Enter') && R.begin()) {
          e.preventDefault();
          mode = 'key';
          h.setAttribute('aria-pressed', 'true');
          this.classList.add('reordering');
          this._say(`Grabbed. Position ${R.index + 1} of ${R.count}. Use arrow keys to move, space to drop, escape to cancel.`);
        }
        return;
      }
      if (mode !== 'key') return;
      if (e.key === 'ArrowUp' || e.key === 'ArrowDown') {
        e.preventDefault();
        R.moveBy(e.key === 'ArrowUp' ? -1 : 1);
        this._say(`Position ${R.index + 1} of ${R.count}`);
      } else if (e.key === ' ' || e.key === 'Enter') { e.preventDefault(); finish(true); }
      else if (e.key === 'Escape') { e.preventDefault(); finish(false); }
    });
    h.addEventListener('blur', () => { if (mode === 'key') finish(false); });
  }
}

define('ui-todo-item', UiTodoItem);
