// Safe, state-preserving swap of a page's outlet. Not a component.
//
// The page shell (stores, chat panel, the outlet element) is never swapped; an agent changes
// the UI by handing swapOutlet() new HTML made of ui-* tags. The HTML is untrusted: it is
// sanitized, then morphed into the outlet with Idiomorph so existing elements (matched by
// stable id) keep focus, caret, scroll and transient state instead of being recreated.
//
// Exports:
//   swapOutlet(html, {outlet = "#outlet", allowedTags}) -> Promise<Element>
//       sanitize + morph the outlet's contents. Throws if the outlet is missing. If Idiomorph cannot
//       be loaded it falls back to replacing the contents (and console.warns): state held in data
//       stores is still safe, transient UI state is not.
//   sanitizeHtml(html, {allowedTags}) -> string
//   sanitizeFragment(html, {allowedTags}) -> DocumentFragment
//       The sanitizer, exported for tests. Removes script/iframe/object/embed/style/link/meta/svg/math/form
//       (with their contents), every on* attribute, and javascript:/vbscript:/data: URLs (data:image/png|gif|jpeg|webp
//       is allowed). Unknown tags are unwrapped (their text/children survive). `allowedTags` is an array/Set of
//       custom-element tags; by default any ui-* tag is allowed. swapOutlet fills it from components.json.
//       One exception to "no script": <script type="application/json"> directly inside <ui-store> is inert
//       data and is kept (its type attribute is the only attribute kept).
//
// What survives a swap: elements with the same id keep their state; <ui-each> keeps its rendered children
// (its attributes are synced and it re-renders from the store); the transient `editing` attribute of
// ui-todo-item is not removed by a morph. Data belongs in <ui-store>, never in swapped markup.
// The only external dependency is Idiomorph, imported on first use from a pinned jsDelivr URL.

const IDIOMORPH_URL = 'https://cdn.jsdelivr.net/npm/idiomorph@0.8.0/dist/idiomorph.esm.js';

const PLAIN = new Set(`a abbr article aside b blockquote br button caption code dd details div dl dt em fieldset
  figcaption figure footer h1 h2 h3 h4 h5 h6 header hr i img input label legend li main mark nav ol optgroup option p pre
  s section select small span strong sub summary sup table tbody td textarea tfoot th thead time tr u ul wbr`.split(/\s+/));
const DROP = new Set('script iframe object embed style link meta base frame frameset applet svg math form template noscript title'.split(' '));
const URL_ATTRS = new Set(['href', 'src', 'action', 'formaction', 'xlink:href', 'data', 'poster', 'background', 'cite', 'srcset', 'src-set']);
const DROP_ATTRS = new Set(['srcdoc', 'is']);
// Attributes that hold transient UI state and must not be removed just because the agent's HTML omits them.
const TRANSIENT_ATTRS = { 'ui-todo-item': ['editing'] };

const badUrl = (v) => {
  const s = String(v).replace(/[\u0000-\u0020\u00ad\u180e\u200b-\u200f\u2028\u2029\ufeff]/g, '').toLowerCase();
  if (/^(javascript|vbscript):/.test(s)) return true;
  return s.startsWith('data:') && !/^data:image\/(png|gif|jpe?g|webp)[;,]/.test(s);
};

function clean(node, allowed) {
  for (const child of [...node.childNodes]) {
    if (child.nodeType === 8) { child.remove(); continue; }          // comments
    if (child.nodeType !== 1) continue;                               // text stays
    const tag = child.localName;
    const isJsonSeed = tag === 'script' && node.localName === 'ui-store' && (child.getAttribute('type') || '').toLowerCase() === 'application/json';
    if (isJsonSeed) {
      for (const a of [...child.attributes]) if (a.name !== 'type') child.removeAttribute(a.name);
      continue;
    }
    if (DROP.has(tag)) { child.remove(); continue; }
    const ok = PLAIN.has(tag) || (tag.includes('-') && (allowed ? allowed.has(tag) : tag.startsWith('ui-')));
    if (!ok) {                                                        // unwrap: keep the children, drop the element
      clean(child, allowed);
      child.replaceWith(...child.childNodes);
      continue;
    }
    for (const a of [...child.attributes]) {
      const n = a.name.toLowerCase();
      if (n.startsWith('on') || DROP_ATTRS.has(n) || (URL_ATTRS.has(n) && badUrl(a.value))) child.removeAttribute(a.name);
    }
    clean(child, allowed);
  }
}

const toSet = (tags) => (tags ? new Set([...tags].map((t) => String(t).toLowerCase())) : null);

export function sanitizeFragment(html, { allowedTags } = {}) {
  const t = document.createElement('template');       // inert: nothing runs or loads while parsing
  t.innerHTML = String(html ?? '');
  clean(t.content, toSet(allowedTags));
  return t.content;
}

export function sanitizeHtml(html, opts = {}) {
  // Two passes so that re-parsing the serialized output cannot produce anything new (mutation XSS).
  const once = (h) => { const t = document.createElement('template'); t.content.append(sanitizeFragment(h, opts)); return t.innerHTML; }; // template keeps it inert (no image loads)
  return once(once(html));
}

let catalog;
function catalogTags() {
  catalog ??= fetch(new URL('../../components.json', import.meta.url))
    .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
    .then((c) => c.components.map((x) => x.tag))
    .catch((err) => { console.warn('[outlet] could not load components.json; allowing any ui-* tag', err); return null; });
  return catalog;
}

let idiomorph;
function loadIdiomorph() {
  idiomorph ??= import(IDIOMORPH_URL).then((m) => m.Idiomorph).catch((err) => {
    console.warn('[outlet] could not load Idiomorph; replacing contents instead of morphing (transient UI state will be lost)', err);
    return null;
  });
  return idiomorph;
}

// <ui-each> children are rendered by the element itself, so the agent's (empty) <ui-each> must not erase them:
// sync its attributes and let it re-render from the store.
function syncAttrs(from, to) {
  for (const a of [...from.attributes]) if (!to.hasAttribute(a.name)) from.removeAttribute(a.name);
  for (const a of to.attributes) if (from.getAttribute(a.name) !== a.value) from.setAttribute(a.name, a.value);
}

export async function swapOutlet(html, { outlet = '#outlet', allowedTags } = {}) {
  const el = typeof outlet === 'string' ? document.querySelector(outlet) : outlet;
  if (!el) throw new Error(`[outlet] no element matches ${outlet}`);
  const frag = sanitizeFragment(html, { allowedTags: allowedTags ?? (await catalogTags()) });
  const Idiomorph = await loadIdiomorph();
  if (!Idiomorph) { el.replaceChildren(frag); return el; }
  Idiomorph.morph(el, [...frag.childNodes], {
    morphStyle: 'innerHTML',
    ignoreActiveValue: true, // keep what the user is typing in the focused field
    callbacks: {
      beforeNodeMorphed(oldNode, newNode) {
        if (oldNode.localName === 'ui-each' && newNode.localName === 'ui-each') { syncAttrs(oldNode, newNode); return false; }
      },
      beforeAttributeUpdated(attr, node, type) {
        if (type === 'remove' && TRANSIENT_ATTRS[node.localName]?.includes(attr)) return false;
      },
    },
  });
  return el;
}
