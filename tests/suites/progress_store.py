"""Suite B (4/4, part 2): <ui-progress> bound to a <ui-store> (store, path, where, label placeholders)."""
from registry import test, open_fixture, mount
from helpers import check, eq

C = "ui-progress"
VIEW = {"width": 480, "height": 280}
# tests/media is at its 15 MB budget, so only the core user flow (ticking moves the ring) is recorded.
NO_GIF = {"gif": False}
EVENTS = ("ui-complete", "ui-action")
MAP = """map='{"text":"text","checked":"done"}'"""
TOGGLE = """events='{"ui-toggle":{"action":"toggle","field":"done"}}'"""

def store(name, items, key="items"):
    import json
    return f'<ui-store name="{name}"><script type="application/json">{json.dumps({key: items})}</script></ui-store>'

TODOS = [{"id": "a", "text": "Squat", "done": True}, {"id": "b", "text": "Bench", "done": False}, {"id": "c", "text": "Row", "done": False}]
LIST = f'<ui-each id="todos" store="todos" tag="ui-todo-item" {MAP} {TOGGLE}></ui-each>'

def page(t, html):
    open_fixture(t)
    t.page.wait_for_function("!!customElements.get('ui-progress')")
    t.capture_events(*EVENTS)
    mount(t, f'<div style="display:flex;gap:12px;align-items:flex-start"><div style="width:220px">{html[0]}</div><div style="flex:1;display:grid;gap:6px">{html[1]}</div></div>')
    t.page.wait_for_timeout(50)

def state(p, sel="#ring"):
    """What the ring shows: value/max/percent properties, the label text, done state and aria values."""
    return p.evaluate("""(s) => { const e = document.querySelector(s), r = e.shadowRoot, g = r.querySelector('.graphic');
      return {value: e.value, max: e.max, percent: Math.round(e.percent), label: r.querySelector('.center .label').textContent,
              done: r.querySelector('.card').hasAttribute('data-done'), now: g.getAttribute('aria-valuenow'), aria_max: g.getAttribute('aria-valuemax')}; }""", sel)

def toggle(p, key):
    p.click(f"#todos-{key} .check"); p.wait_for_timeout(60)

@test("progress", "bound-count", desc='With `store` and `where`, value is the number of matching items and max the number of items; the ring fill and aria values follow, and the `value` attribute is ignored.', component=C, viewport=VIEW, **NO_GIF)
def _(t):
    page(t, (store("todos", TODOS) + '<ui-progress id="ring" heading="Sets" store="todos" where=\'{"done":true}\' value="99"></ui-progress>', LIST))
    p = t.page
    t.step("One of three items is done: 1 / 3, 33%", "#ring")
    s = state(p)
    eq((s["value"], s["max"], s["percent"], s["label"]), (1, 3, 33, "33%"))
    eq((s["now"], s["aria_max"]), ("1", "3"), "aria-valuenow / aria-valuemax")
    eq(p.evaluate("document.getElementById('ring').shadowRoot.querySelector('[role=progressbar]').getAttribute('aria-label')"), "Sets", "the heading names the progressbar")
    offset = p.evaluate("parseFloat(document.getElementById('ring').shadowRoot.querySelector('.ring .fill').style.strokeDashoffset)")
    check(abs(offset - 2 * 3.14159265 * 45 * (2 / 3)) < 0.5, f"ring filled a third (offset {offset})")
    t.step("A store change from elsewhere updates it live", "#ring")
    p.evaluate("window.__lib.dispatch('todos', 'add', {item: {id: 'd', text: 'Deadlift', done: true}})"); p.wait_for_timeout(60)
    eq((state(p)["value"], state(p)["max"]), (2, 4))
    t.step("Without `where`, every item counts", "#ring")
    p.evaluate("document.getElementById('ring').removeAttribute('where')"); p.wait_for_timeout(30)
    eq((state(p)["value"], state(p)["max"]), (4, 4))
    t.step("Removing `store` falls back to the static value attribute", "#ring")
    p.evaluate("document.getElementById('ring').removeAttribute('store')"); p.wait_for_timeout(30)
    eq((state(p)["value"], state(p)["max"]), (99, 100))

@test("progress", "toggle-through-ui-each-moves-the-ring", desc='Ticking and unticking to-dos rendered by ui-each (the toggle goes through a ui-action into the store) moves the bound ring up and down.', component=C, viewport=VIEW)
def _(t):
    page(t, (store("todos", TODOS) + '<ui-progress id="ring" store="todos" where=\'{"done":true}\' label="{value} of {max}"></ui-progress>', LIST))
    p = t.page
    eq(state(p)["label"], "1 of 3")
    t.step("Tick Bench: the ring moves to 2 of 3", "#todos-b")
    toggle(p, "b")
    eq(t.events("ui-action")[-1]["detail"]["action"], "toggle", "the tick went through a ui-action")
    eq((state(p)["value"], state(p)["label"]), (2, "2 of 3"))
    t.step("Untick Squat: back to 1 of 3", "#todos-a")
    toggle(p, "a")
    eq((state(p)["value"], state(p)["label"]), (1, "1 of 3"))

@test("progress", "where-filtering-and-path", desc='`where` counts only matching items (dot paths and non-boolean values work), and `path` points at an array other than "items".', component=C, viewport=VIEW, **NO_GIF)
def _(t):
    items = [{"id": "1", "meta": {"tag": "gym"}, "status": "done"}, {"id": "2", "meta": {"tag": "gym"}, "status": "open"},
             {"id": "3", "meta": {"tag": "home"}, "status": "done"}, {"id": "4", "meta": {"tag": "home"}, "status": "done"}]
    page(t, (store("board", items, key="cards") + '<ui-progress id="ring" store="board" path="cards" where=\'{"status":"done"}\' label="{value}/{max}"></ui-progress>', ""))
    p = t.page
    t.step('`path="cards"`, `where={"status":"done"}`: 3 of 4', "#ring")
    eq(state(p)["label"], "3/4")
    t.step('A dot-path filter: `where={"meta.tag":"gym","status":"done"}`: 1 of 4', "#ring")
    p.evaluate("""document.getElementById('ring').setAttribute('where', '{"meta.tag":"gym","status":"done"}')"""); p.wait_for_timeout(30)
    eq(state(p)["label"], "1/4")
    t.step("Nothing matches: 0", "#ring")
    p.evaluate("""document.getElementById('ring').setAttribute('where', '{"status":"archived"}')"""); p.wait_for_timeout(30)
    eq((state(p)["value"], state(p)["done"]), (0, False))
    t.step("An empty list is 0 of 0 and never complete", "#ring")
    p.evaluate("window.__lib.set('board', 'cards', [])"); p.wait_for_timeout(60)
    s = state(p)
    eq((s["value"], s["max"], s["percent"], s["done"]), (0, 0, 0, False))
    eq(t.events("ui-complete"), [], "no ui-complete for an empty list")

@test("progress", "explicit-max-overrides-the-count", desc='An explicit `max` attribute replaces the item count as the target: 3 of a 5-set goal is not complete even when all three items are done.', component=C, viewport=VIEW, **NO_GIF)
def _(t):
    page(t, (store("todos", TODOS) + '<ui-progress id="ring" store="todos" where=\'{"done":true}\' max="2" label="{value} of {max}"></ui-progress>', LIST))
    p = t.page
    t.step('`max="2"` with one done item: 1 of 2, 50%', "#ring")
    eq((state(p)["label"], state(p)["percent"]), ("1 of 2", 50))
    t.step("Tick a second item: 2 of 2 completes", "#todos-b")
    toggle(p, "b")
    check(state(p)["done"], "complete at the explicit max")
    t.step('Raise `max` to 5: all three done is 3 of 5, not complete', "#ring")
    toggle(p, "c")
    p.evaluate("document.getElementById('ring').max = 5"); p.wait_for_timeout(30)
    s = state(p)
    eq((s["label"], s["percent"], s["done"]), ("3 of 5", 60, False))
    t.step("Remove `max`: back to the item count, 3 of 3", "#ring")
    p.evaluate("document.getElementById('ring').removeAttribute('max')"); p.wait_for_timeout(30)
    eq((state(p)["label"], state(p)["done"]), ("3 of 3", True))

@test("progress", "label-placeholders", desc='`{value}`, `{max}` and `{percent}` in `label` are filled in and stay live, bound or not; text without placeholders is shown as is.', component=C, viewport=VIEW, **NO_GIF)
def _(t):
    page(t, (store("todos", TODOS) + '<ui-progress id="ring" store="todos" where=\'{"done":true}\' label="{value} of {max} sets ({percent}%)"></ui-progress>'
             '<ui-progress id="plain" variant="bar" value="3" max="8" label="{value}/{max} = {percent}%"></ui-progress>', LIST))
    p = t.page
    t.step("Bound: {value} of {max} sets ({percent}%)", "#ring")
    eq(state(p)["label"], "1 of 3 sets (33%)")
    eq(p.evaluate("document.getElementById('ring').shadowRoot.querySelector('.graphic').getAttribute('aria-valuetext')"), "1 of 3 sets (33%)", "aria-valuetext uses the filled label")
    toggle(p, "b")
    eq(state(p)["label"], "2 of 3 sets (67%)")
    t.step("Unbound bar: placeholders work with value/max too", "#plain")
    eq(p.inner_text("#plain .barlabel"), "3/8 = 38%")
    t.step("A label without placeholders is shown as is", "#ring")
    p.evaluate("document.getElementById('ring').setAttribute('label', 'Keep going')"); p.wait_for_timeout(30)
    eq(state(p)["label"], "Keep going")

@test("progress", "bound-complete-fires-once-per-crossing", desc='Ticking the last item fires ui-complete once and shows the done slot; further store changes while complete fire nothing; unticking re-arms it and the next crossing fires again.', component=C, viewport=VIEW, **NO_GIF)
def _(t):
    page(t, (store("todos", TODOS) + '<ui-progress id="ring" store="todos" where=\'{"done":true}\' label="{value} of {max}"><span slot="done">All done!</span></ui-progress>', LIST))
    p = t.page
    done_slot = lambda: p.evaluate("!document.getElementById('ring').shadowRoot.querySelector('.done-slot').hidden")
    t.step("Tick the remaining two items", "#todos-c")
    toggle(p, "b")
    eq(t.events("ui-complete"), [], "not yet complete")
    toggle(p, "c")
    ev = t.events("ui-complete")
    eq(len(ev), 1, "one ui-complete")
    eq(ev[0]["detail"], {"value": 3, "max": 3})
    check(ev[0]["bubbles"] and ev[0]["composed"], "bubbles and composed")
    check(done_slot(), "done slot shown")
    t.step("A store change that stays complete fires nothing more", "#ring")
    p.evaluate("window.__lib.dispatch('todos', 'update', {id: 'a', patch: {text: 'Front squat'}})"); p.wait_for_timeout(60)
    eq(len(t.events("ui-complete")), 1)
    t.step("Untick one: the label comes back and completion re-arms", "#todos-a")
    toggle(p, "a")
    check(not done_slot() and state(p)["label"] == "2 of 3", "label back")
    t.step("Tick it again: ui-complete fires a second time", "#todos-a")
    toggle(p, "a")
    eq(len(t.events("ui-complete")), 2)
    t.step("Adding an open item drops below max, and ticking it crosses again", "#ring")
    p.evaluate("window.__lib.dispatch('todos', 'add', {item: {id: 'd', text: 'Plank', done: false}})"); p.wait_for_timeout(60)
    eq((state(p)["label"], state(p)["done"]), ("3 of 4", False))
    toggle(p, "d")
    eq([e["detail"] for e in t.events("ui-complete")][-1], {"value": 4, "max": 4})
    eq(len(t.events("ui-complete")), 3)

@test("progress", "store-swapped-out-and-back", desc='The binding survives the ring being removed and re-added, the `<ui-store>` element being removed and re-added, a store declared after the ring, and `store` pointing elsewhere and back, without duplicate ui-complete events.', component=C, viewport=VIEW, **NO_GIF)
def _(t):
    page(t, ('<div id="slot"><ui-progress id="ring" store="todos" where=\'{"done":true}\' label="{value} of {max}"></ui-progress></div>', '<div id="stores"></div>' + LIST))
    p = t.page
    t.step("The store is declared after the ring: it binds when it appears", "#ring")
    eq(state(p)["label"], "0 of 0")
    p.evaluate("(h) => document.getElementById('stores').innerHTML = h", store("todos", TODOS)); p.wait_for_timeout(60)
    eq(state(p)["label"], "1 of 3")
    t.step("Remove the ring and put it back: still bound and live", "#ring")
    p.evaluate("window.__ring = document.getElementById('ring'); window.__ring.remove()")
    toggle(p, "b")
    p.evaluate("document.getElementById('slot').append(window.__ring)"); p.wait_for_timeout(30)
    eq(state(p)["label"], "2 of 3", "caught up after re-adding")
    toggle(p, "c")
    eq(len(t.events("ui-complete")), 1, "completes once")
    t.step("Remove the <ui-store> element and re-add it: data and binding kept", "#ring")
    p.evaluate("window.__st = document.querySelector('ui-store[name=todos]'); window.__st.remove()"); p.wait_for_timeout(30)
    eq(state(p)["label"], "3 of 3")
    p.evaluate("document.getElementById('stores').append(window.__st)"); p.wait_for_timeout(60)
    eq(state(p)["label"], "3 of 3")
    toggle(p, "a")
    eq(state(p)["label"], "2 of 3", "still live after the store element came back")
    t.step("Point `store` at another store, then back", "#ring")
    p.evaluate("(h) => document.getElementById('stores').insertAdjacentHTML('beforeend', h)", store("other", [{"id": "x", "done": True}]))
    p.evaluate("document.getElementById('ring').setAttribute('store', 'other')"); p.wait_for_timeout(60)
    eq(state(p)["label"], "1 of 1")
    eq(len(t.events("ui-complete")), 2, "the other store is complete: one crossing")
    toggle(p, "a")
    eq(state(p)["label"], "1 of 1", "no longer follows the first store")
    p.evaluate("document.getElementById('ring').setAttribute('store', 'todos')"); p.wait_for_timeout(60)
    eq(state(p)["label"], "3 of 3")
    eq(len(t.events("ui-complete")), 2, "already complete: no duplicate event when switching back")
