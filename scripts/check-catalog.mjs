// Dev check (Node >= 18, no dependencies). components.json parses, and every file in
// components/ has a catalog entry whose tag is registered in that file, with a header
// and a mention in a demo page. It then parses each source file and diffs what the code
// actually has (attributes, events, slots, methods, properties, parts, CSS custom
// properties, store actions) against the catalog and against the file-header docs, in both
// directions: documented-but-missing and present-but-undocumented.
// Usage: node scripts/check-catalog.mjs
import { readFileSync, readdirSync } from 'node:fs';
const root = new URL('../', import.meta.url);
const read = (p) => readFileSync(new URL(p, root), 'utf8');
const cat = JSON.parse(read('components.json'));
const demo = readdirSync(new URL('demo/', root)).filter((f) => f.endsWith('.html')).map((f) => read(`demo/${f}`)).join('\n');
const files = readdirSync(new URL('components/', root)).filter((f) => f.endsWith('.js'));
let bad = 0;
const fail = (m) => { console.error('FAIL', m); bad++; };

for (const f of files) {
  const entry = cat.components.find((c) => c.file === `components/${f}`);
  if (!entry) { fail(`${f}: no catalog entry`); continue; }
  const src = read(`components/${f}`);
  if (!src.includes(`define('${entry.tag}'`)) fail(`${f}: does not register ${entry.tag}`);
  if (!src.startsWith(`// <${entry.tag}>`)) fail(`${f}: missing API header`);
  for (const ev of entry.events) if (!src.includes(ev.name)) fail(`${f}: event ${ev.name} not in source`);
  if (!demo.includes(`components/${f}`)) fail(`${f}: demo does not load it`);
  if (!demo.includes(`<${entry.tag}`)) fail(`${f}: demo does not show it`);
}
for (const c of cat.components) if (!files.includes(c.file.replace('components/', ''))) fail(`${c.tag}: file missing`);
for (const s of cat.shared) readFileSync(new URL(s, root));
for (const f of readdirSync(new URL('components/_shared/', root))) if (!cat.shared.includes(`components/_shared/${f}`)) fail(`_shared/${f}: not listed in catalog.shared`);

// ---------------------------------------------------------------------------------------------
// Deep check: source <-> catalog <-> header docs
// ---------------------------------------------------------------------------------------------
const uniq = (a) => [...new Set(a)].sort();
const all = (re, s, g = 1) => [...s.matchAll(re)].map((m) => m[g]);
const tokens = new Set(all(/^\s*(--ui-[a-z0-9-]+)\s*:/gm, read('tokens.css')));

function parseSource(src) {
  const attrs = new Set();
  const obs = src.match(/static observedAttributes = \[([^\]]*)\]/);
  if (obs) all(/'([a-z-]+)'/g, obs[1]).forEach((a) => attrs.add(a));
  all(/this\.(?:getAttribute|hasAttribute|toggleAttribute|setAttribute|removeAttribute)\('([a-z-]+)'/g, src).forEach((a) => attrs.add(a));
  all(/json\(this, '([a-z-]+)'\)/g, src).forEach((a) => attrs.add(a));
  for (const host of all(/:host\(([^)]*(?:\)[^{]*?)?)\)/g, src)) all(/\[([a-z-]+)/g, host).forEach((a) => attrs.add(a));

  const events = new Set();
  for (const call of all(/\bemit\(this,\s*([^;]*?)(?:,\s*\{|\))/g, src)) all(/'(ui-[a-z-]+)'/g, call).forEach((e) => events.add(e));

  const slots = new Set();
  for (const m of src.matchAll(/<slot(?:\s+name="([a-z-]+)")?[\s>]/g)) slots.add(m[1] ?? '(default)');

  const methods = new Set();
  const skip = new Set(['constructor', 'connectedCallback', 'disconnectedCallback', 'attributeChangedCallback', 'adoptedCallback', 'if', 'for', 'while', 'switch', 'catch', 'function']);
  for (const m of src.matchAll(/^ {2}(?:async )?([a-zA-Z]\w*)\([^)]*\)\s*\{/gm)) if (!skip.has(m[1])) methods.add(m[1]);

  const props = new Set();
  for (const m of src.matchAll(/^ {2}(?:get|set) ([a-zA-Z]\w*)\(/gm)) props.add(m[1]);

  const parts = new Set([...all(/\bpart="([a-z-]+)"/g, src), ...all(/\.part\s*=\s*'([a-z-]+)'/g, src)]);
  const css = new Set(all(/(--ui-[a-z0-9-]+)/g, src).filter((v) => !tokens.has(v)));
  return { attrs, events, slots, methods, props, parts, css };
}

const nameOf = (s) => String(typeof s === 'string' ? s : s.name).split(/[\s(:]/)[0];
const header = (src) => src.split('\n').filter((l, i, a) => a.slice(0, i + 1).every((x) => x.startsWith('//'))).join('\n');

function diff(label, tag, have, doc, fix) {
  const extra = uniq([...have].filter((x) => !doc.has(x)));
  const missing = uniq([...doc].filter((x) => !have.has(x)));
  if (extra.length) fail(`${tag} ${label}: in the source but not in ${fix}: ${extra.join(', ')}`);
  if (missing.length) fail(`${tag} ${label}: in ${fix} but not in the source: ${missing.join(', ')}`);
}

for (const c of cat.components) {
  const src = read(c.file);
  const have = parseSource(src);
  const docSlots = new Set(c.slots.map((x) => x.name.trim()).filter((n) => n !== '(none)'));
  diff('attributes', c.tag, have.attrs, new Set(c.attributes.map(nameOf)), 'components.json');
  diff('events', c.tag, have.events, new Set(c.events.map(nameOf)), 'components.json');
  diff('slots', c.tag, have.slots, docSlots, 'components.json');
  diff('methods', c.tag, have.methods, new Set((c.methods ?? []).map(nameOf)), 'components.json');
  diff('properties', c.tag, have.props, new Set((c.properties ?? []).map(nameOf)), 'components.json');
  diff('parts', c.tag, have.parts, new Set(c.parts ?? []), 'components.json');
  diff('CSS custom properties', c.tag, have.css, new Set(c.cssCustomProperties ?? []), 'components.json');

  // the file header must mention everything the catalog lists
  const head = header(src);
  const mentioned = (what, names) => { const miss = names.filter((n) => !head.includes(n)); if (miss.length) fail(`${c.tag} header: does not mention ${what}: ${miss.join(', ')}`); };
  mentioned('attributes', c.attributes.map(nameOf));
  mentioned('events', c.events.map(nameOf));
  mentioned('slots', c.slots.map((x) => x.name.trim()).filter((n) => !n.startsWith('(')));
  mentioned('methods', (c.methods ?? []).map(nameOf));
  mentioned('CSS custom properties', c.cssCustomProperties ?? []);
  if (!/Events?\b/.test(head)) fail(`${c.tag} header: has no Events section`);
  if (!/Attributes?\b/.test(head)) fail(`${c.tag} header: has no Attributes section`);

  // README lists every component
  if (!read('README.md').includes(`\`${c.tag}\``)) fail(`${c.tag}: not in README's component table`);
  // events in the catalog have a detail shape
  for (const e of c.events) if (!e.detail) fail(`${c.tag} event ${e.name}: catalog entry has no detail shape`);
}

// store actions: registry switch <-> ui-store catalog
{
  const reg = read('components/_shared/store-registry.js');
  const have = new Set(all(/case '([a-z]+)'/g, reg.slice(reg.indexOf('export function dispatch'))));
  const store = cat.components.find((c) => c.tag === 'ui-store');
  if (store) diff('actions', 'ui-store', have, new Set(store.actions.list.map((a) => a.name)), 'components.json');
}
// shared tokens: tokens.css <-> catalog.tokens
diff('tokens', 'tokens.css', tokens, new Set(cat.tokens.properties), 'components.json');
// every --ui-* token used by _shared/base.js exists
for (const v of all(/var\((--ui-[a-z0-9-]+)/g, read('components/_shared/base.js'))) if (!tokens.has(v)) fail(`_shared/base.js reads ${v}, which tokens.css does not define`);

console.log(bad ? `${bad} problem(s)` : `ok: ${files.length} components in sync`);
process.exit(bad ? 1 : 0);
