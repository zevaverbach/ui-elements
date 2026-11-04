// Named, observable, optionally persistent JSON state. Not a component: no DOM rendering.
// <ui-store> is the declarative handle for this registry; components that bind to a store
// (ui-each, ...) import it directly. Data lives here, not in elements, so it survives
// elements being removed, re-added or swapped out of the page.
//
// Exports:
//   ensureStore(name, {persist, key, version, seed, src}) -> record   create if absent; if present
//                       return the existing record and ignore the seed
//   getStore(name) -> record | undefined        record = {name, data, version, persist, key, ready}
//   get(name, path?) -> value                   path is a dot path ("items", "settings.theme"); "" = root
//   set(name, path, value)                      replaces the changed branch (never mutates in place);
//                                               value must be JSON-serializable; undefined deletes the key
//   subscribe(name, fn) -> unsubscribe          fn({name, path, paths, data}) once per microtask batch;
//                                               the store may not exist yet (fn fires when it is created)
//   dispatch(name, action, payload) -> boolean  run an action (below); false if unknown store/action
//
// Seed precedence (first hit wins, only when no record exists): persisted data, then `src`
// (fetched JSON), then the inline `seed`. A stored value {v, data} whose v differs from `version`
// is ignored. Persistence is debounced (~200 ms), flushed on pagehide, and never throws: if
// storage is unavailable or full the store continues in memory and warns once.
//
// Actions (also reachable by dispatching a bubbling, composed `ui-action` event with
// detail {store, action, payload} anywhere in the document; routing is by name, not DOM position).
// They operate on the array of objects at payload.path (default "items"); items are identified by `id`.
//   add     {item, index?}        assigns item.id = crypto.randomUUID() if missing
//   remove  {id}
//   update  {id, patch}           shallow-merges patch into the item
//   toggle  {id, field}           flips a boolean field
//   move    {id, toIndex}         item ends up at index toIndex (final position)
//   set     {path, value}         set any path (not array-specific)
//   clear   {}                    empties the array at path

const KEY = Symbol.for('ui-elements.store-registry');
const g = globalThis;
// One shared state object even if this module is loaded twice (e.g. via two different URLs).
const R = (g[KEY] ??= { stores: new Map(), subs: new Map(), queued: new Map(), timers: new Map(), warned: false, listening: false });

const parse = (path) => (path ? String(path).split('.') : []);
const clone = (v) => (v === undefined ? undefined : JSON.parse(JSON.stringify(v)));

function getIn(data, segs) {
  let cur = data;
  for (const s of segs) {
    if (cur == null || typeof cur !== 'object') return undefined;
    cur = cur[s];
  }
  return cur;
}

// Returns a new root with the branch at segs replaced (copy-on-write along the path).
function setIn(data, segs, value) {
  if (!segs.length) return value;
  const [head, ...rest] = segs;
  const base = data != null && typeof data === 'object' ? data : /^\d+$/.test(head) ? [] : {};
  const child = setIn(base[head], rest, value);
  if (Array.isArray(base)) {
    const next = base.slice();
    if (child === undefined) next.splice(Number(head), 1); else next[Number(head)] = child;
    return next;
  }
  const next = { ...base };
  if (child === undefined) delete next[head]; else next[head] = child;
  return next;
}

function warnOnce(msg, err) {
  if (R.warned) return;
  R.warned = true;
  console.warn(msg, err ?? '');
}

function storage(kind) {
  try { return kind === 'session' ? g.sessionStorage : g.localStorage; } catch { return null; }
}

function readPersisted(rec) {
  if (rec.persist === 'none') return undefined;
  try {
    const raw = storage(rec.persist)?.getItem(rec.key);
    if (!raw) return undefined;
    const stored = JSON.parse(raw);
    return stored && stored.v === rec.version ? { data: stored.data } : undefined;
  } catch (err) {
    warnOnce('[ui-store] could not read persisted state; using seed', err);
    return undefined;
  }
}

function writePersisted(rec) {
  if (rec.persist === 'none') return;
  try {
    const s = storage(rec.persist);
    if (!s) throw new Error('storage unavailable');
    s.setItem(rec.key, JSON.stringify({ v: rec.version, data: rec.data }));
  } catch (err) {
    warnOnce(`[ui-store] cannot persist "${rec.name}"; continuing in memory`, err);
  }
}

function schedulePersist(rec) {
  if (rec.persist === 'none') return;
  clearTimeout(R.timers.get(rec.name));
  R.timers.set(rec.name, setTimeout(() => { R.timers.delete(rec.name); writePersisted(rec); }, 200));
}

function flushAll() {
  for (const [name, t] of R.timers) {
    clearTimeout(t);
    R.timers.delete(name);
    const rec = R.stores.get(name);
    if (rec) writePersisted(rec);
  }
}

function listenersFor(name) {
  let set = R.subs.get(name);
  if (!set) R.subs.set(name, (set = new Set()));
  return set;
}

// Collect changes; notify once per microtask batch.
function changed(rec, path, persist = true) {
  let q = R.queued.get(rec.name);
  if (!q) {
    q = new Set();
    R.queued.set(rec.name, q);
    queueMicrotask(() => {
      R.queued.delete(rec.name);
      const paths = [...q];
      const detail = { name: rec.name, path: paths.length === 1 ? paths[0] : '', paths, data: rec.data };
      for (const fn of [...listenersFor(rec.name)]) {
        try { fn(detail); } catch (err) { console.error('[ui-store] subscriber threw', err); }
      }
    });
  }
  q.add(path);
  if (persist) schedulePersist(rec);
}

export function getStore(name) { return R.stores.get(name); }

export function ensureStore(name, { persist = 'none', key, version = '1', seed, src } = {}) {
  const existing = R.stores.get(name);
  if (existing) {
    if (persist !== existing.persist && persist !== 'none') {
      console.warn(`[ui-store] "${name}" already exists with persist="${existing.persist}"; ignoring persist="${persist}"`);
    }
    return existing;
  }
  if (!['none', 'local', 'session'].includes(persist)) {
    console.warn(`[ui-store] unknown persist="${persist}" for "${name}"; using "none"`);
    persist = 'none';
  }
  const rec = { name, data: undefined, version: String(version), persist, key: key || `ui-store:${name}`, dirty: false, ready: null };
  const stored = readPersisted(rec);
  rec.data = stored ? stored.data : clone(seed ?? {});
  R.stores.set(name, rec);

  const hydrate = async () => {
    if (!stored && src) {
      try {
        const res = await fetch(src);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const fetched = await res.json();
        // Only adopt the fetched seed if nothing has changed the store in the meantime.
        if (!rec.dirty) { rec.data = clone(fetched); changed(rec, '', false); }
      } catch (err) {
        console.warn(`[ui-store] "${name}": could not load src ${src}; using inline seed`, err);
      }
    }
  };
  rec.ready = hydrate().then(() => rec);
  // Subscribers that connected before the store existed learn about it now.
  if (listenersFor(name).size) changed(rec, '', false);
  return rec;
}

export function get(name, path = '') {
  const rec = R.stores.get(name);
  return rec ? getIn(rec.data, parse(path)) : undefined;
}

export function set(name, path, value) {
  const rec = R.stores.get(name);
  if (!rec) { console.warn(`[ui-store] set: no store "${name}"`); return false; }
  const segs = parse(path);
  rec.data = setIn(rec.data, segs, clone(value));
  rec.dirty = true;
  changed(rec, segs.join('.'));
  return true;
}

export function subscribe(name, fn) {
  const set = listenersFor(name);
  set.add(fn);
  return () => set.delete(fn);
}

function list(rec, path) {
  const arr = getIn(rec.data, parse(path));
  return Array.isArray(arr) ? arr : [];
}

export function dispatch(name, action, payload = {}) {
  const rec = R.stores.get(name);
  if (!rec) { console.warn(`[ui-store] action "${action}": no store "${name}"`); return false; }
  const path = payload.path ?? 'items';
  const put = (arr) => set(name, path, arr);
  const arr = list(rec, path);
  const at = () => arr.findIndex((it) => it && String(it.id) === String(payload.id));
  switch (action) {
    case 'add': {
      const item = { ...clone(payload.item) };
      if (item.id == null) item.id = crypto.randomUUID();
      const next = arr.slice();
      const i = Number.isInteger(payload.index) ? Math.max(0, Math.min(arr.length, payload.index)) : arr.length;
      next.splice(i, 0, item);
      return put(next);
    }
    case 'remove': { const i = at(); return i < 0 ? false : put(arr.filter((_, j) => j !== i)); }
    case 'update': { const i = at(); return i < 0 ? false : put(arr.map((it, j) => (j === i ? { ...it, ...clone(payload.patch) } : it))); }
    case 'toggle': { const i = at(); return i < 0 || !payload.field ? false : put(arr.map((it, j) => (j === i ? { ...it, [payload.field]: !it[payload.field] } : it))); }
    case 'move': {
      const i = at();
      if (i < 0 || !Number.isInteger(payload.toIndex)) return false;
      const next = arr.slice();
      const [it] = next.splice(i, 1);
      next.splice(Math.max(0, Math.min(next.length, payload.toIndex)), 0, it);
      return put(next);
    }
    case 'set': return set(name, payload.path ?? '', payload.value);
    case 'clear': return put([]);
    default: console.warn(`[ui-store] unknown action "${action}"`); return false;
  }
}

if (!R.listening && typeof document !== 'undefined') {
  R.listening = true;
  document.addEventListener('ui-action', (e) => {
    const { store, action, payload } = e.detail ?? {};
    if (store && action) dispatch(store, action, payload ?? {});
  });
  g.addEventListener('pagehide', flushAll);
  document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'hidden') flushAll(); });
}
