// Dev check (Node >= 18, no dependencies): components.json parses, and every file in
// components/ has a catalog entry whose tag is registered in that file, with a header
// and a mention in a demo page. Usage: node scripts/check-catalog.mjs
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
console.log(bad ? `${bad} problem(s)` : `ok: ${files.length} components in sync`);
process.exit(bad ? 1 : 0);
