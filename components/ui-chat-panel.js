// <ui-chat-panel> — a global chat that slides on and off screen. Backend-agnostic: it only
// emits what the user typed; the host page sends it wherever it likes and adds the replies.
//
// Usage:
//   <script type="module" src="https://cdn.jsdelivr.net/gh/zevaverbach/ui-elements@v0.1.0/components/ui-chat-panel.js"></script>
//   <ui-chat-panel heading="Assistant"></ui-chat-panel>
//   panel.addEventListener('ui-send', (e) => reply(e.detail.text));
//   panel.addMessage('agent', 'Hello!');
//
// Attributes / properties:
//   open         boolean  panel is on screen (reflects; set it, or call toggle())
//   side         "right" (default) | "left" | "bottom"   which edge it slides from
//   heading      string   title shown in the header (prop: heading)
//   placeholder  string   composer placeholder, default "Message…"
//   busy         boolean  shows a pending bubble and disables Send (the host sets it while waiting for a reply)
//   busy-text    string   pending bubble text, default "Thinking…"
//   backdrop     boolean  show a scrim behind the panel; clicking it closes the panel
//   no-echo      boolean  do not append the user's message to the log on send (host renders it itself)
//   messages     property array of {role: "user"|"agent"|"error", text: string}; get/set
//   store        string   optional: name of a <ui-store>. Messages are then rendered from the store
//                         (array at `store-path`) and a sent message becomes an `add` ui-action with
//                         {role: "user", text} instead of being echoed locally. Without it nothing changes.
//   store-path   string   dot path of the messages array in the store, default "messages"
//
// Methods: toggle(force?) -> boolean, show(), hide(), addMessage(role, text) -> HTMLElement,
//   clear(), focusInput()
//
// Slots:
//   (default)    messages as light-DOM elements, e.g. <div data-role="agent">Hi</div>
//                (data-role = user | agent | error gets the bubble styling)
//   header       replaces the heading text
//   actions      extra buttons in the header, before the close button
//   footer       content between the log and the composer (suggestions, status)
//
// Events (bubble, composed):
//   ui-action  {store, action: "add", payload: {path, item: {role: "user", text}}}   only when `store` is set;
//                               routed to the store by the store registry (see ui-store)
//   ui-send    {text: string}   user submitted (Enter, or Send; Shift+Enter inserts a newline).
//                               Cancelable: preventDefault() keeps the draft in the box.
//   ui-open    {open: true}     panel finished opening state change
//   ui-close   {open: false}
//
// Keyboard: Enter sends, Shift+Enter newline, Escape closes. Focus returns to the previously
// focused element on close. The composer is not auto-focused on touch devices (the on-screen
// keyboard would cover the log). Slide animation is disabled under prefers-reduced-motion.
//
// CSS custom properties (optional; fall back to the shared --ui-* tokens in tokens.css):
//   --ui-chat-panel-width (default min(28rem, 100vw)), --ui-chat-panel-height (bottom side, default 70dvh),
//   --ui-chat-panel-bg, --ui-chat-panel-border, --ui-chat-panel-user-bg, --ui-chat-panel-user-text,
//   --ui-chat-panel-agent-bg, --ui-chat-panel-z (default 1000), --ui-chat-panel-duration (default 250ms)
// Parts: panel, header, log, message, composer, input, send, backdrop

import { emit, define, coarsePointer } from './_shared/util.js';
import { sheet } from './_shared/base.js';
import { get, subscribe } from './_shared/store-registry.js';

const styles = sheet(`
:host { position: fixed; inset: 0; z-index: var(--ui-chat-panel-z, 1000); pointer-events: none; --_dur: var(--ui-chat-panel-duration, 250ms); }
.backdrop { position: absolute; inset: 0; background: rgb(0 0 0 / 0.45); opacity: 0; visibility: hidden; pointer-events: none;
  transition: opacity var(--_dur) ease, visibility 0s var(--_dur); }
:host([open][backdrop]) .backdrop { opacity: 1; visibility: visible; pointer-events: auto; transition: opacity var(--_dur) ease; }
.panel {
  position: absolute; top: 0; bottom: 0; right: 0; width: var(--ui-chat-panel-width, min(28rem, 100vw));
  display: flex; flex-direction: column; pointer-events: auto;
  background: var(--ui-chat-panel-bg, var(--_bg)); color: var(--_text);
  border-left: 1px solid var(--ui-chat-panel-border, var(--_border));
  box-shadow: -8px 0 24px rgb(0 0 0 / 0.2);
  transform: translateX(100%); visibility: hidden;
  transition: transform var(--_dur) ease, visibility 0s var(--_dur);
}
:host([side="left"]) .panel { right: auto; left: 0; border-left: 0; border-right: 1px solid var(--ui-chat-panel-border, var(--_border)); box-shadow: 8px 0 24px rgb(0 0 0 / 0.2); transform: translateX(-100%); }
:host([side="bottom"]) .panel { top: auto; left: 0; right: 0; width: auto; height: var(--ui-chat-panel-height, 70dvh);
  border-left: 0; border-top: 1px solid var(--ui-chat-panel-border, var(--_border)); box-shadow: 0 -8px 24px rgb(0 0 0 / 0.2); transform: translateY(100%); }
:host([open]) .panel { transform: none; visibility: visible; transition: transform var(--_dur) ease; }
header { display: flex; align-items: center; gap: 0.5rem; padding: 0.6rem 0.75rem; border-bottom: 1px solid var(--ui-chat-panel-border, var(--_border)); }
.heading { flex: 1; min-width: 0; margin: 0; font-size: 1.05em; font-weight: 600; color: var(--_accent); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.log { flex: 1; overflow-y: auto; padding: 1rem; display: flex; flex-direction: column; gap: 0.7rem; overscroll-behavior: contain; }
.msg, ::slotted([data-role]) { max-width: 85%; padding: 0.6rem 0.85rem; border-radius: var(--_radius); white-space: pre-wrap; overflow-wrap: anywhere; line-height: 1.5;
  background: var(--ui-chat-panel-agent-bg, var(--_surface-2)); border: 1px solid var(--_border); align-self: flex-start; }
.msg.user, ::slotted([data-role="user"]) { background: var(--ui-chat-panel-user-bg, var(--_accent)); color: var(--ui-chat-panel-user-text, var(--_on-accent)); border-color: transparent; align-self: flex-end; }
.msg.error, ::slotted([data-role="error"]) { background: color-mix(in srgb, var(--_danger) 14%, var(--_bg)); border-color: var(--_danger); color: var(--_danger); }
.msg.pending { color: var(--_muted); font-style: italic; }
.composer { display: flex; gap: 0.5rem; padding: 0.7rem 0.75rem calc(0.7rem + env(safe-area-inset-bottom)); border-top: 1px solid var(--ui-chat-panel-border, var(--_border)); }
textarea { flex: 1; min-width: 0; max-height: 9rem; resize: none; font: inherit; font-size: max(16px, 1em); /* >=16px stops iOS zooming on focus */
  color: var(--_text); background: var(--_surface); border: 1px solid var(--_border); border-radius: var(--_radius); padding: 0.55rem 0.7rem; }
.send { padding: 0 1.1rem; border: 0; border-radius: var(--_radius); background: var(--_accent); color: var(--_on-accent); font-weight: 600; }
.send:disabled { background: var(--_border); color: var(--_muted); cursor: default; }
`);

export class UiChatPanel extends HTMLElement {
  static observedAttributes = ['open', 'heading', 'placeholder', 'busy', 'busy-text', 'store', 'store-path'];

  constructor() {
    super();
    this._messages = [];
    this._wasOpen = false;
    this.attachShadow({ mode: 'open' }).adoptedStyleSheets = [styles];
    this.shadowRoot.innerHTML = `
      <div class="backdrop" part="backdrop"></div>
      <section class="panel" part="panel" role="complementary" inert>
        <header part="header">
          <slot name="header"><h2 class="heading"></h2></slot>
          <slot name="actions"></slot>
          <button class="icon-btn close" type="button" aria-label="Close chat"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 5l14 14M19 5L5 19"/></svg></button>
        </header>
        <div class="log" part="log" role="log" aria-live="polite" tabindex="0">
          <slot></slot>
          <div class="rendered" style="display:contents"></div>
          <div class="msg agent pending" part="message" hidden></div>
        </div>
        <slot name="footer"></slot>
        <form class="composer" part="composer">
          <textarea class="input" part="input" rows="1" enterkeyhint="send"></textarea>
          <button class="send" part="send" type="submit">Send</button>
        </form>
      </section>`;
    const $ = (s) => this.shadowRoot.querySelector(s);
    Object.assign(this, {
      _panel: $('.panel'), _heading: $('.heading'), _log: $('.log'), _rendered: $('.rendered'),
      _pending: $('.pending'), _input: $('.input'), _send: $('.send'),
    });
    $('.close').addEventListener('click', () => this.hide());
    $('.backdrop').addEventListener('click', () => this.hide());
    $('.composer').addEventListener('submit', (e) => { e.preventDefault(); this._submit(); });
    this._input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); this._submit(); }
    });
    this._input.addEventListener('input', () => this._autosize());
    this._panel.addEventListener('keydown', (e) => { if (e.key === 'Escape' && this.open) { e.stopPropagation(); this.hide(); } });
    this.shadowRoot.querySelector('slot:not([name])').addEventListener('slotchange', () => this._scroll());
  }

  connectedCallback() { this._sync(); this._bindStore(); }
  disconnectedCallback() { this._unsub?.(); this._unsub = null; this._bound = null; }
  attributeChangedCallback(name) {
    this._sync();
    if (name === 'store' || name === 'store-path') this._bindStore();
  }

  // ---- properties ----
  get open() { return this.hasAttribute('open'); }
  set open(v) { this.toggleAttribute('open', !!v); }
  get heading() { return this.getAttribute('heading') ?? ''; }
  set heading(v) { this.setAttribute('heading', v ?? ''); }
  get busy() { return this.hasAttribute('busy'); }
  set busy(v) { this.toggleAttribute('busy', !!v); }
  get messages() { return this._messages.map((m) => ({ ...m })); }
  set messages(list) {
    this._messages = [];
    this._rendered.replaceChildren();
    for (const m of list ?? []) this.addMessage(m.role, m.text);
  }

  // ---- public methods ----
  toggle(force) {
    this.open = force === undefined ? !this.open : !!force;
    return this.open;
  }
  show() { this.toggle(true); }
  hide() { this.toggle(false); }
  focusInput() { this._input.focus(); }
  clear() { this.messages = []; }
  addMessage(role, text) {
    const el = document.createElement('div');
    el.className = `msg ${role === 'user' || role === 'error' ? role : 'agent'}`;
    el.part = 'message';
    el.textContent = text;
    this._rendered.append(el);
    this._messages.push({ role, text });
    this._scroll();
    return el;
  }

  // ---- internals ----
  _sync() {
    if (!this._panel) return;
    this._heading.textContent = this.heading;
    this._input.placeholder = this.getAttribute('placeholder') ?? 'Message…';
    this._input.setAttribute('aria-label', this._input.placeholder);
    this._panel.setAttribute('aria-label', this.heading || 'Chat');
    this._pending.textContent = this.getAttribute('busy-text') ?? 'Thinking…';
    this._pending.hidden = !this.busy;
    this._send.disabled = this.busy;
    if (this.busy) this._scroll();

    const open = this.open;
    const hadFocus = !!this.shadowRoot.activeElement;
    this._panel.toggleAttribute('inert', !open);
    this._panel.setAttribute('aria-hidden', String(!open));
    if (open === this._wasOpen) return;
    this._wasOpen = open;
    if (open) {
      this._returnFocus = document.activeElement;
      if (!coarsePointer()) requestAnimationFrame(() => this._input.focus());
    } else {
      const prev = this._returnFocus;
      this._returnFocus = null;
      if (prev?.isConnected && hadFocus) prev.focus?.();
    }
    emit(this, open ? 'ui-open' : 'ui-close', { open });
  }

  // Optional store binding: render messages from the store. Inert unless the `store` attribute is set.
  _bindStore() {
    if (!this.isConnected) return;
    const store = this.getAttribute('store');
    const path = this.getAttribute('store-path') || 'messages';
    const bound = store ? `${store}\u0000${path}` : null;
    if (bound === this._bound) return;
    this._unsub?.(); this._unsub = null; this._bound = bound;
    if (!store) return;
    const render = () => {
      const list = get(store, path);
      this.messages = Array.isArray(list) ? list : [];
    };
    this._unsub = subscribe(store, render);
    render();
  }

  _submit() {
    const text = this._input.value.trim();
    if (!text || this.busy) return;
    const ev = emit(this, 'ui-send', { text }, { cancelable: true });
    if (ev.defaultPrevented) return;
    const store = this.getAttribute('store');
    if (store) {
      emit(this, 'ui-action', { store, action: 'add', payload: { path: this.getAttribute('store-path') || 'messages', item: { role: 'user', text } } });
    } else if (!this.hasAttribute('no-echo')) this.addMessage('user', text);
    this._input.value = '';
    this._autosize();
  }

  _autosize() {
    this._input.style.height = 'auto';
    this._input.style.height = `${Math.min(this._input.scrollHeight + 2, 144)}px`;
  }

  _scroll() {
    requestAnimationFrame(() => { this._log.scrollTop = this._log.scrollHeight; });
  }
}

define('ui-chat-panel', UiChatPanel);
