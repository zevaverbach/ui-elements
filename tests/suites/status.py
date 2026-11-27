"""Suite B: <ui-status> (state/label/detail, badge text, colors, ui-status-change, live region, store binding, ui-each, slots)."""
import json
from registry import test, open_fixture, mount
from helpers import check, eq

C = "ui-status"
VIEW = {"width": 480, "height": 300}
# tests/media is close to its 15 MB budget: only the core flow (the store changes, a row follows) is recorded, cheaply.
NO_GIF = {"gif": False}
CHEAP = {"gif_ladder": [(5, 480, 24), (4, 400, 16)]}

def store(name, data):
    return f'<ui-store name="{name}"><script type="application/json">{json.dumps(data)}</script></ui-store>'

HOME = {"baby": {"state": "ok", "detail": "Sleeping since 13:10"},
        "package": {"state": "warn", "detail": "En route, arriving today"},
        "server": {"state": "ok", "detail": "Up, 12 days"}}
ROWS = ('<ui-status id="baby" label="Baby" store="home" path="baby"></ui-status>'
        '<ui-status id="package" label="Package" store="home" path="package"></ui-status>'
        '<ui-status id="server" label="Server" store="home" path="server"></ui-status>')

def page(t, html):
    open_fixture(t)
    t.capture_events("ui-status-change")
    mount(t, f'<div style="display:grid;gap:8px;max-width:440px">{html}</div>')
    t.page.wait_for_timeout(50)

def row(p, sel):
    """What a row shows: properties, the rendered label/detail/badge text, the state on the row, its color and the live region."""
    return p.evaluate("""(s) => { const e = document.querySelector(s), r = e.shadowRoot, q = (x) => r.querySelector(x);
      return {state: e.state, label: e.label, detail: e.detail, shown_label: q('.label').textContent,
              shown_detail: q('.detail').hidden ? null : q('.detail-text').textContent, badge: q('.badge').textContent,
              data_state: q('.row').dataset.state, color: getComputedStyle(q('.row')).borderLeftColor,
              live: q('[aria-live]').textContent, politeness: q('[aria-live]').getAttribute('aria-live')}; }""", sel)

def store_set(p, path, value):
    p.evaluate("([path, value]) => window.__lib.set('home', path, value)", [path, value]); p.wait_for_timeout(60)

@test("status", "states-in-text-and-color", desc='Each state (ok, warn, bad, unknown) is written out in the badge ("OK", "Warning", "Problem", "Unknown") and drawn in its own color; label and detail are shown; an unknown or missing state counts as unknown; the properties set the attributes.', component=C, viewport=VIEW, **NO_GIF)
def _(t):
    page(t, '<ui-status id="a" state="ok" label="Server" detail="Up, 12 days"></ui-status>'
            '<ui-status id="b" state="warn" label="Package" detail="Late"></ui-status>'
            '<ui-status id="c" state="bad" label="Backups" detail="Failed last night"></ui-status>'
            '<ui-status id="d" label="Garden"></ui-status>')
    p = t.page
    t.step("Four rows: ok, warn, bad and no state", "#a")
    rows = {k: row(p, "#" + k) for k in "abcd"}
    eq([rows[k]["badge"] for k in "abcd"], ["OK", "Warning", "Problem", "Unknown"], "the state is written out")
    eq([rows[k]["state"] for k in "abcd"], ["ok", "warn", "bad", "unknown"])
    eq((rows["a"]["shown_label"], rows["a"]["shown_detail"]), ("Server", "Up, 12 days"))
    eq(rows["d"]["shown_detail"], None, "no detail: the detail line is hidden")
    check(len({rows[k]["color"] for k in "abcd"}) == 4, f"four different state colors: {[rows[k]['color'] for k in 'abcd']}")
    t.step("A value that is not a state counts as unknown", "#d")
    p.evaluate("document.getElementById('d').setAttribute('state', 'sideways')"); p.wait_for_timeout(30)
    eq((row(p, "#d")["state"], row(p, "#d")["badge"]), ("unknown", "Unknown"))
    t.step("Setting the properties updates the attributes and the row", "#d")
    p.evaluate("Object.assign(document.getElementById('d'), {state: 'bad', label: 'Garden hose', detail: 'Leaking'})"); p.wait_for_timeout(30)
    eq(p.evaluate("['state','label','detail'].map(a => document.getElementById('d').getAttribute(a))"), ["bad", "Garden hose", "Leaking"])
    r = row(p, "#d")
    eq((r["badge"], r["shown_label"], r["shown_detail"], r["data_state"]), ("Problem", "Garden hose", "Leaking", "bad"))
    eq(r["color"], rows["c"]["color"], "same color as the other bad row")

@test("status", "store-binding-updates-live", desc='Three rows bound to one `<ui-store>` (store + path) show the store\'s state and detail with the label from markup; when the store changes, only the changed row updates, fires ui-status-change {state, previous, label} and announces the change (assertively for bad).', component=C, viewport=VIEW, **CHEAP)
def _(t):
    page(t, store("home", HOME) + ROWS)
    p = t.page
    t.step("Bound rows show the store: baby ok, package warn, server ok", "#server")
    eq([row(p, "#" + k)["state"] for k in ("baby", "package", "server")], ["ok", "warn", "ok"])
    eq(row(p, "#baby")["shown_detail"], "Sleeping since 13:10")
    eq(t.events("ui-status-change"), [], "no event for the first render")
    t.step("The store says the server is down: that row turns bad", "#server")
    store_set(p, "server", {"state": "bad", "detail": "Down since 14:02"})
    r = row(p, "#server")
    eq((r["state"], r["badge"], r["shown_detail"]), ("bad", "Problem", "Down since 14:02"))
    ev = t.events("ui-status-change")
    eq([e["detail"] for e in ev], [{"state": "bad", "previous": "ok", "label": "Server"}], "one event, from the server row only")
    check(ev[0]["bubbles"] and ev[0]["composed"], "bubbles and composed")
    eq((r["live"], r["politeness"]), ("Server: Problem, Down since 14:02", "assertive"), "announced assertively")
    t.step("The package arrives: warn to ok, announced politely", "#package")
    store_set(p, "package.state", "ok")
    r = row(p, "#package")
    eq((r["state"], r["live"], r["politeness"]), ("ok", "Package: OK, En route, arriving today", "polite"))
    t.step("A detail-only change updates the text without an event", "#baby")
    store_set(p, "baby.detail", "Awake, playing")
    eq((row(p, "#baby")["shown_detail"], len(t.events("ui-status-change"))), ("Awake, playing", 2))

@test("status", "binding-rules", desc='Store fields win over attributes only where present (a label in the store replaces the markup label); a plain string at path is the state; a missing path is unknown; removing `store` falls back to the attributes; a store declared after the row binds when it appears; the binding survives the row being removed and re-added.', component=C, viewport=VIEW, **NO_GIF)
def _(t):
    page(t, '<div id="stores"></div><div id="slot"><ui-status id="s" label="Server" state="warn" detail="From markup" store="home" path="server"></ui-status></div>')
    p = t.page
    t.step("No store yet: the attributes show", "#s")
    eq((row(p, "#s")["state"], row(p, "#s")["shown_detail"]), ("warn", "From markup"))
    t.step("The store appears later: its fields win", "#s")
    p.evaluate("(h) => document.getElementById('stores').innerHTML = h", store("home", {**HOME, "flag": "bad"})); p.wait_for_timeout(60)
    r = row(p, "#s")
    eq((r["state"], r["shown_detail"], r["shown_label"]), ("ok", "Up, 12 days", "Server"))
    t.step("A label in the store replaces the markup label", "#s")
    store_set(p, "server.label", "Home server")
    eq(row(p, "#s")["shown_label"], "Home server")
    t.step("A plain string at path is the state", "#s")
    p.evaluate("document.getElementById('s').setAttribute('path', 'flag')"); p.wait_for_timeout(30)
    r = row(p, "#s")
    eq((r["state"], r["shown_label"], r["shown_detail"]), ("bad", "Server", "From markup"))
    t.step("A path that is missing in the store falls back to the attributes", "#s")
    p.evaluate("document.getElementById('s').setAttribute('path', 'nothing.here')"); p.wait_for_timeout(30)
    eq(row(p, "#s")["state"], "warn")
    t.step("Remove the row, change the store, put it back: it catches up", "#s")
    p.evaluate("document.getElementById('s').setAttribute('path', 'server')"); p.wait_for_timeout(30)
    t.clear_events()
    p.evaluate("window.__s = document.getElementById('s'); window.__s.remove()")
    store_set(p, "server.state", "bad")
    eq(t.events("ui-status-change"), [], "nothing fires while detached")
    p.evaluate("document.getElementById('slot').append(window.__s)"); p.wait_for_timeout(30)
    eq(row(p, "#s")["state"], "bad")
    eq([e["detail"]["state"] for e in t.events("ui-status-change")], ["bad"], "the change is reported once on reconnect")
    t.step("Remove `store`: back to the attributes", "#s")
    p.evaluate("document.getElementById('s').removeAttribute('store')"); p.wait_for_timeout(30)
    eq((row(p, "#s")["state"], row(p, "#s")["shown_detail"]), ("warn", "From markup"))
    store_set(p, "server.state", "ok")
    eq(row(p, "#s")["state"], "warn", "no longer follows the store")

@test("status", "change-event-and-announcement", desc='Attribute changes fire ui-status-change once per real change (not on the first render, not when the state stays the same, not for label or detail changes) and write the change into the live region.', component=C, viewport=VIEW, **NO_GIF)
def _(t):
    page(t, '<ui-status id="s" state="ok" label="Wi-Fi" detail="Fast"></ui-status>')
    p = t.page
    set_state = lambda v: (p.evaluate("(v) => document.getElementById('s').setAttribute('state', v)", v), p.wait_for_timeout(20))
    eq(t.events("ui-status-change"), [])
    t.step("ok -> warn -> warn -> bad -> ok", "#s")
    for v in ("warn", "warn", "bad", "ok"):
        set_state(v)
    eq([(e["detail"]["previous"], e["detail"]["state"]) for e in t.events("ui-status-change")], [("ok", "warn"), ("warn", "bad"), ("bad", "ok")])
    eq((row(p, "#s")["live"], row(p, "#s")["politeness"]), ("Wi-Fi: OK, Fast", "polite"))
    t.step("Label and detail changes fire nothing", "#s")
    p.evaluate("Object.assign(document.getElementById('s'), {label: 'WLAN', detail: 'Slow'})"); p.wait_for_timeout(20)
    eq(len(t.events("ui-status-change")), 3)
    t.step("Upper case and spaces are accepted; an invalid value means unknown", "#s")
    set_state(" WARN ")
    eq(row(p, "#s")["state"], "warn")
    set_state("broken")
    eq(t.events("ui-status-change")[-1]["detail"], {"state": "unknown", "previous": "warn", "label": "WLAN"})

@test("status", "ui-each-and-slots", desc='`<ui-each tag="ui-status">` renders one row per store item and follows changes; the `detail` slot replaces the detail text (and is what gets announced), the `icon` slot replaces the dot, and `--ui-status-*` properties restyle the state colors.', component=C, viewport=VIEW, **NO_GIF)
def _(t):
    items = [{"id": "w", "label": "Washer", "state": "ok", "detail": "Done"}, {"id": "d", "label": "Dryer", "state": "warn", "detail": "Filter full"}]
    page(t, store("rooms", {"items": items}) +
         '<ui-each id="m" store="rooms" tag="ui-status" map=\'{"state":"state","label":"label","detail":"detail"}\'></ui-each>'
         '<ui-status id="rich" state="ok" label="Car"><span slot="icon">🚗</span><span slot="detail">Parked at <b>home</b></span></ui-status>'
         '<ui-status id="themed" state="ok" label="Themed" style="--ui-status-ok: rgb(255, 0, 255)"></ui-status>')
    p = t.page
    t.step("ui-each renders a row per item", "#m-w")
    eq([(row(p, f"#m-{k}")["shown_label"], row(p, f"#m-{k}")["badge"]) for k in "wd"], [("Washer", "OK"), ("Dryer", "Warning")])
    p.evaluate("window.__lib.dispatch('rooms', 'update', {id: 'd', patch: {state: 'bad', detail: 'Overheating'}})"); p.wait_for_timeout(60)
    eq((row(p, "#m-d")["state"], row(p, "#m-d")["shown_detail"]), ("bad", "Overheating"))
    eq(t.events("ui-status-change")[-1]["detail"], {"state": "bad", "previous": "warn", "label": "Dryer"})
    t.step("Slots: an icon instead of the dot and rich detail", "#rich")
    eq(p.evaluate("document.getElementById('rich').shadowRoot.querySelector('slot[name=icon]').assignedElements()[0].textContent"), "🚗")
    check(p.evaluate("!document.getElementById('rich').shadowRoot.querySelector('.detail').hidden"), "the detail line shows for slotted detail")
    p.evaluate("document.getElementById('rich').state = 'warn'"); p.wait_for_timeout(20)
    eq(row(p, "#rich")["live"], "Car: Warning, Parked at home")
    t.step("--ui-status-ok restyles the ok color", "#themed")
    eq(row(p, "#themed")["color"], "rgb(255, 0, 255)")
