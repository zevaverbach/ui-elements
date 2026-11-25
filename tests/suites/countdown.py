"""Suite B (3/4): <ui-countdown> in a real browser. Phases are 1-3 s so the suite stays fast."""
from registry import test, open_fixture, mount
from helpers import check, eq

C = "ui-countdown"
VP = {"width": 400, "height": 300}   # small viewport and one recording per suite (gif=False elsewhere): tests/media has little headroom
EVENTS = ("ui-tick", "ui-phase", "ui-done")
TWO = '[{"name":"Focus","seconds":1},{"name":"Break","seconds":2}]'
el = "document.getElementById('c')"
prop = lambda name: f"{el}.{name}"

def state(p):
    """What the user sees: time text, phase line, button text, box state, running."""
    return p.evaluate(f"""(() => {{ const c = {el}, r = c.shadowRoot, b = r.querySelector('.box');
      return {{ time: r.querySelector('.time').textContent, phase: r.querySelector('.phase').textContent,
        button: r.querySelector('.btn').textContent, state: b.dataset.state, running: c.running,
        remaining: c.remaining, live: r.querySelector('[aria-live]').textContent }}; }})()""")

@test("countdown", "ticks", desc='Start counts down once per second: the time text, `remaining` and a ui-tick per whole second (bubbling, composed), the bar fills, and the button reads Start, then Pause.', component=C, viewport=VP, gif=False)
def _(t):
    open_fixture(t, '<ui-countdown id="c" seconds="3" label="Go"></ui-countdown>')
    t.capture_events(*EVENTS)
    p = t.page
    t.step("Before starting: full time, the custom label, nothing running", "#c")
    eq(state(p)["time"], "0:03")
    eq(state(p)["button"], "Go", "`label` names the start button")
    eq(p.evaluate(prop("remaining")), 3)
    check(not p.evaluate(prop("running")), "not running")
    eq(p.get_attribute("#c .time", "role"), "timer")
    t.step("Click Start: it runs and the button becomes Pause", "#c")
    p.click("#c .btn")
    check(p.get_attribute("#c", "running") is not None, "`running` attribute reflects")
    eq(state(p)["button"], "Pause")
    t.step("One ui-tick per whole second, counting down", "#c")
    p.wait_for_function(f"{el}.remaining === 1", timeout=4000)
    eq(state(p)["time"], "0:01")
    ticks = t.events("ui-tick")
    eq([e["detail"] for e in ticks], [{"remaining": 3, "phase": "", "index": 0}, {"remaining": 2, "phase": "", "index": 0}, {"remaining": 1, "phase": "", "index": 0}])
    check(all(e["bubbles"] and e["composed"] for e in ticks), "ui-tick bubbles and is composed")
    eq(ticks[0]["target"], "ui-countdown#c")
    width = p.evaluate(f"parseFloat({el}.shadowRoot.querySelector('.fill').style.width)")
    check(55 < width < 100, f"the bar is about two thirds full ({width}%)")
    t.step("It reaches 0:00 and stops", "#c")
    p.wait_for_function(f"!{el}.running", timeout=3000)
    eq(state(p)["time"], "0:00")
    eq(len(t.events("ui-done")), 1, "one ui-done")

@test("countdown", "pause-holds-time", desc='Pause stops the clock: the time and `remaining` hold, no ticks arrive while paused, the button reads Resume, and resuming continues from where it stopped.', component=C, viewport=VP, gif=False)
def _(t):
    open_fixture(t, '<ui-countdown id="c" seconds="5"></ui-countdown>')
    t.capture_events(*EVENTS)
    p = t.page
    t.step("Start, let it run about a second", "#c")
    p.click("#c .btn")
    p.wait_for_function(f"{el}.remaining <= 4", timeout=3000)
    t.step("Pause: the button reads Resume", "#c")
    p.click("#c .btn")
    before = state(p)
    eq(before["button"], "Resume")
    check(not before["running"], "not running")
    check(p.get_attribute("#c", "running") is None, "`running` attribute removed")
    ticks = len(t.events("ui-tick"))
    t.step("1.5 s later the time has not moved", "#c")
    p.wait_for_timeout(1500)
    after = state(p)
    eq(after["time"], before["time"], "time holds while paused")
    eq(after["remaining"], before["remaining"], "remaining holds while paused")
    eq(len(t.events("ui-tick")), ticks, "no ticks while paused")
    t.step("Resume continues from the paused time, not from the start", "#c")
    p.click("#c .btn")
    eq(state(p)["button"], "Pause")
    p.wait_for_function(f"{el}.remaining === {before['remaining'] - 1}", timeout=3000)
    eq(t.events("ui-tick")[-1]["detail"]["remaining"], before["remaining"] - 1)
    t.step("pause() and the `running` property do the same", "#c")
    p.evaluate(f"{el}.pause()")
    check(not p.evaluate(prop("running")), "pause() stops it")
    p.evaluate(f"{el}.running = true")
    check(p.get_attribute("#c", "running") is not None, "running = true starts it")

@test("countdown", "phases-in-order", desc='Phases run in order: ui-tick for each second of each phase, ui-phase when the second phase begins (not for the first), then a single ui-done; the phase line and the live region follow along.', component=C, viewport=VP)
def _(t):
    open_fixture(t, f"<ui-countdown id=\"c\" phases='{TWO}'></ui-countdown>")
    t.capture_events(*EVENTS)
    p = t.page
    t.step("Two phases: the phase line names the first", "#c")
    eq(state(p)["phase"], "Focus · 1 of 2")
    eq(state(p)["time"], "0:01")
    t.step("Start: Focus runs, then Break", "#c")
    p.click("#c .btn")
    p.wait_for_function(f"{el}.shadowRoot.querySelector('.phase').textContent.startsWith('Break')", timeout=3000)
    eq(state(p)["phase"], "Break · 2 of 2")
    eq(state(p)["live"], "Break", "the new phase is announced")
    t.step("After the last phase: ui-done", "#c")
    p.wait_for_function(f"!{el}.running", timeout=4000)
    seq = [(e["type"], e["detail"]) for e in t.events()]
    eq(seq, [("ui-tick", {"remaining": 1, "phase": "Focus", "index": 0}),
             ("ui-phase", {"index": 1, "name": "Break"}),
             ("ui-tick", {"remaining": 2, "phase": "Break", "index": 1}),
             ("ui-tick", {"remaining": 1, "phase": "Break", "index": 1}),
             ("ui-done", {})], "event order")
    check(all(e["bubbles"] and e["composed"] for e in t.events()), "every event bubbles and is composed")
    eq(state(p)["live"], "Done", "completion is announced")
    eq(state(p)["state"], "done")

@test("countdown", "done-slot-and-restart", desc='At zero the done slot replaces the time (without a done slot the time shows 0:00), the button reads Restart, and Restart runs the countdown again from the first phase.', component=C, viewport=VP, gif=False)
def _(t):
    open_fixture(t, f"<ui-countdown id=\"c\" phases='{TWO}'><span slot=\"done\">Nice work!</span></ui-countdown><ui-countdown id=\"plain\" seconds=\"1\"></ui-countdown>")
    t.capture_events(*EVENTS)
    p = t.page
    t.step("While counting, the done slot is hidden", "#c")
    check(p.locator("#c .done-slot").is_hidden(), "done slot hidden before the end")
    p.click("#c .btn"); p.click("#plain .btn")
    t.step("At zero the done slot replaces the time", "#c")
    p.wait_for_function(f"!{el}.running", timeout=4500)
    check(p.locator("#c .done-slot").is_visible(), "done slot shown")
    check(p.locator("#c .time").is_hidden(), "time hidden")
    eq(p.inner_text("#c [slot=done]"), "Nice work!")
    eq(state(p)["button"], "Restart")
    t.step("Without a done slot the time stays, at 0:00", "#plain")
    check(p.locator("#plain .time").is_visible(), "time shown")
    eq(p.inner_text("#plain .time"), "0:00")
    t.step("Restart runs it again from the first phase", "#c")
    t.clear_events()
    p.click("#c .btn")
    s = state(p)
    check(s["running"], "running again")
    eq(s["phase"], "Focus · 1 of 2")
    eq(s["button"], "Pause")
    check(p.locator("#c .time").is_visible() and p.locator("#c .done-slot").is_hidden(), "time back, done slot hidden")
    p.wait_for_function(f"{el}.shadowRoot.querySelector('.phase').textContent.startsWith('Break')", timeout=3000)
    eq(t.events("ui-phase")[0]["detail"], {"index": 1, "name": "Break"})

@test("countdown", "warn-state", desc='The warning state starts when the last phase reaches `warn` seconds left (default 10), only once started, and pulses only while running; `--ui-countdown-warn` colors it.', component=C, viewport=VP, gif=False)
def _(t):
    open_fixture(t, '<ui-countdown id="c" seconds="3" warn="1" style="--ui-countdown-warn: rgb(255, 0, 255)"></ui-countdown><ui-countdown id="d" seconds="3"></ui-countdown>')
    p = t.page
    t.step("Not started: no warning even with the default warn of 10", "#d")
    eq(p.evaluate("document.getElementById('d').shadowRoot.querySelector('.box').dataset.state"), "")
    t.step("warn=1: no warning while more than a second is left", "#c")
    p.click("#c .btn")
    eq(state(p)["state"], "")
    t.step("At 1 s left the warning state begins and pulses", "#c")
    p.wait_for_function(f"{el}.shadowRoot.querySelector('.box').dataset.state === 'warn'", timeout=4000)
    check(p.evaluate(prop("remaining")) <= 1, "warning only at the last second")
    eq(p.evaluate(f"getComputedStyle({el}.shadowRoot.querySelector('.time')).color"), "rgb(255, 0, 255)", "--ui-countdown-warn colors the time")
    check(p.evaluate(f"getComputedStyle({el}.shadowRoot.querySelector('.time')).animationName") == "pulse", "pulses while running")
    t.step("Default warn (10): a 3 s countdown warns as soon as it starts", "#d")
    p.click("#d .btn")
    eq(p.evaluate("document.getElementById('d').shadowRoot.querySelector('.box').dataset.state"), "warn")
    t.step("Paused in the warning state: no pulse", "#d")
    p.click("#d .btn")
    eq(p.evaluate("getComputedStyle(document.getElementById('d').shadowRoot.querySelector('.time')).animationName"), "none")

@test("countdown", "warn-only-in-last-phase", desc='With phases, an early phase that is under `warn` seconds does not warn; only the last phase does.', component=C, viewport=VP, gif=False)
def _(t):
    open_fixture(t, f"<ui-countdown id=\"c\" warn=\"5\" phases='{TWO}'></ui-countdown>")
    p = t.page
    t.step("Focus (1 s, under warn=5) does not warn", "#c")
    p.click("#c .btn")
    eq(state(p)["state"], "")
    t.step("Break, the last phase, warns", "#c")
    p.wait_for_function(f"{el}.shadowRoot.querySelector('.phase').textContent.startsWith('Break')", timeout=3000)
    eq(state(p)["state"], "warn")

@test("countdown", "autostart", desc='`autostart` starts counting as soon as the element is connected, with no click; without it nothing runs.', component=C, viewport=VP, gif=False)
def _(t):
    open_fixture(t)
    t.capture_events(*EVENTS)
    p = t.page
    t.step("Mount one with autostart and one without", "#c")
    mount(t, '<ui-countdown id="c" seconds="2" autostart></ui-countdown><ui-countdown id="d" seconds="2"></ui-countdown>')
    check(p.evaluate(prop("running")), "autostart: running on connect")
    check(not p.evaluate("document.getElementById('d').running"), "no autostart: idle")
    eq(state(p)["button"], "Pause")
    t.step("It ticks without a click", "#c")
    p.wait_for_function(f"{el}.remaining === 1", timeout=3000)
    check(all(e["target"] == "ui-countdown#c" for e in t.events("ui-tick")), "only the autostarted one ticks")
    t.step("A `running` attribute in markup also starts it", "#r")
    mount(t, '<ui-countdown id="r" seconds="2" running></ui-countdown>')
    p.wait_for_function("document.getElementById('r').remaining === 1", timeout=3000)

@test("countdown", "reset", desc='reset() stops the clock and returns to the first phase at full time with the original button label, from running, paused or done; `seconds` changes apply after a reset.', component=C, viewport=VP, gif=False)
def _(t):
    open_fixture(t, f"<ui-countdown id=\"c\" label=\"Begin\" phases='{TWO}'></ui-countdown>")
    t.capture_events(*EVENTS)
    p = t.page
    t.step("Run into the second phase", "#c")
    p.click("#c .btn")
    p.wait_for_function(f"{el}.shadowRoot.querySelector('.phase').textContent.startsWith('Break')", timeout=3000)
    t.step("reset() while running: back to Focus at full time, stopped", "#c")
    p.evaluate(f"{el}.reset()")
    s = state(p)
    eq((s["phase"], s["time"], s["button"], s["running"], s["state"]), ("Focus · 1 of 2", "0:01", "Begin", False, ""))
    n = len(t.events())
    p.wait_for_timeout(600)
    eq(len(t.events()), n, "no events after reset")
    t.step("reset() after done clears the done state", "#c")
    p.click("#c .btn")
    p.wait_for_function(f"{el}.shadowRoot.querySelector('.box').dataset.state === 'done'", timeout=4500)
    p.evaluate(f"{el}.reset()")
    eq(state(p)["state"], "")
    eq(state(p)["button"], "Begin")
    t.step("`seconds` set on a fresh element applies; while started it waits for reset()", "#d")
    mount(t, '<ui-countdown id="d" seconds="5"></ui-countdown>')
    p.evaluate("document.getElementById('d').setAttribute('seconds', '7')")
    eq(p.evaluate("document.getElementById('d').remaining"), 7)
    p.evaluate("const d = document.getElementById('d'); d.start(); d.pause(); d.setAttribute('seconds', '9')")
    check(p.evaluate("document.getElementById('d').remaining") <= 7, "a started countdown keeps its time")
    p.evaluate("document.getElementById('d').reset()")
    eq(p.evaluate("document.getElementById('d').remaining"), 9)
