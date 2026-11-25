"""<ui-countdown> until= (count down to a clock time), on a fake clock: nothing waits in real time.

Every test runs in Europe/Zurich with Date and timers faked by Playwright's clock, starting at
2026-06-15 12:00:00 local time (10:00:00 UTC), so "13:00" is exactly an hour away.
"""
from datetime import datetime, timedelta, timezone
from registry import test, open_fixture, mount
from helpers import check, eq

C = "ui-countdown"
EVENTS = ("ui-tick", "ui-done", "ui-phase")
NOW = datetime(2026, 6, 15, 10, 0, 0, tzinfo=timezone.utc)   # 12:00 in Zurich (CEST)
TZ = dict(timezone_id="Europe/Zurich")
el = "document.getElementById('c')"
shadow = lambda sel: f"{el}.shadowRoot.querySelector('{sel}')"

def start(t, html):
    t.page.clock.install(time=NOW - timedelta(minutes=1))
    open_fixture(t)
    t.page.wait_for_function("!!customElements.get('ui-countdown')")
    t.page.clock.pause_at(NOW)          # from here on, time only moves when a test says so
    t.capture_events(*EVENTS)
    mount(t, html)

def remaining(t):
    return t.page.evaluate(f"{el}.remaining")

def shown(t):
    return t.page.evaluate(f"{shadow('.time')}.textContent")

@test("countdown", "until-hh-mm", desc='until="13:00" at 12:00 counts down an hour from the clock: it starts by itself, hides the start button, ignores seconds and phases, and stays right after the clock jumps (sleep, background tab).', component=C, gif=False, **TZ)
def _(t):
    start(t, '<ui-countdown id="c" until="13:00" seconds="5" phases=\'[{"name":"Focus","seconds":3}]\'></ui-countdown>')
    p = t.page
    t.step('until="13:00" at 12:00: one hour left, running without a click', "#c")
    eq(remaining(t), 3600, "remaining")
    eq(shown(t), "1:00:00", "time shown")
    check(p.get_attribute("#c", "running") is not None, "started automatically")
    check(p.evaluate(f"{shadow('.btn')}.hidden"), "start/pause button hidden")
    eq(p.evaluate(f"{shadow('.phase')}.textContent"), "", "phases ignored")
    t.step("Ten seconds later it shows 59:50 and has ticked", "#c")
    p.clock.run_for(10_000)
    eq(remaining(t), 3590)
    eq(shown(t), "59:50")
    tick = t.events("ui-tick")[-1]
    eq(tick["detail"], {"remaining": 3590, "phase": "", "index": 0})
    check(tick["bubbles"] and tick["composed"], "ui-tick bubbles, composed")
    t.step("The clock jumps 30 minutes (sleep): remaining follows the clock, no drift", "#c")
    p.clock.fast_forward("30:00")
    eq(remaining(t), 1790)
    p.clock.run_for(300)
    eq(shown(t), "29:50")
    t.step("Changing until re-targets it", "#c")
    p.evaluate(f"{el}.setAttribute('until', '12:00:30')")
    eq(remaining(t), 23 * 3600 + 30 * 60 + 20, "12:00:30 has passed at 12:30:10, so it means tomorrow")
    p.evaluate(f"{el}.setAttribute('until', '12:45')")
    eq(remaining(t), 14 * 60 + 50)
    t.step("Removing until goes back to a duration that waits for Start", "#c")
    p.evaluate(f"{el}.removeAttribute('until')")
    check(p.get_attribute("#c", "running") is None, "stopped")
    check(not p.evaluate(f"{shadow('.btn')}.hidden"), "start button back")
    eq(p.evaluate(f"{shadow('.phase')}.textContent"), "Focus", "phases apply again")
    eq(remaining(t), 3)

@test("countdown", "until-past-means-tomorrow", desc='An HH:MM that has already passed today (11:30 at 12:00) means tomorrow; a time equal to now also means tomorrow, and 24-hour times and HH:MM:SS work.', component=C, gif=False, **TZ)
def _(t):
    start(t, '<ui-countdown id="c" until="11:30"></ui-countdown><ui-countdown id="d" until="12:00"></ui-countdown><ui-countdown id="e" until="23:59:59"></ui-countdown><ui-countdown id="f" until="7:05"></ui-countdown>')
    p = t.page
    t.step('until="11:30" at 12:00 is tomorrow: 23.5 hours left', "#c")
    eq(remaining(t), 23 * 3600 + 30 * 60)
    eq(shown(t), "23:30:00")
    t.step('until="12:00" at 12:00 (exactly now) is tomorrow too, not done', "#d")
    eq(p.evaluate("document.getElementById('d').remaining"), 86400)
    eq(t.events("ui-done"), [], "nothing finished")
    t.step('"23:59:59" and a one-digit hour "7:05" parse', "#e")
    eq(p.evaluate("document.getElementById('e').remaining"), 11 * 3600 + 59 * 60 + 59)
    eq(p.evaluate("document.getElementById('f').remaining"), 19 * 3600 + 5 * 60)

@test("countdown", "until-iso", desc='until takes a full ISO datetime, with an offset or in local time; one already past is done at once; an unparseable value falls back to seconds.', component=C, gif=False, **TZ)
def _(t):
    start(t, '<ui-countdown id="c" until="2026-06-15T10:30:00Z"></ui-countdown><ui-countdown id="d" until="2026-06-16T12:00"></ui-countdown>')
    p = t.page
    t.step('"2026-06-15T10:30:00Z" (12:30 local) is 30 minutes away', "#c")
    eq(remaining(t), 1800)
    eq(shown(t), "30:00")
    t.step('A local ISO datetime "2026-06-16T12:00" is a day away (no rollover for dates)', "#d")
    eq(p.evaluate("document.getElementById('d').remaining"), 86400)
    t.step("An ISO datetime in the past is done at once", "#c")
    p.evaluate(f"{el}.setAttribute('until', '2026-06-15T09:00:00Z')")
    p.clock.run_for(50)
    eq(remaining(t), 0)
    eq(len(t.events("ui-done")), 1, "ui-done fired")
    eq(p.evaluate(f"{shadow('.box')}.dataset.state"), "done")
    t.step("Garbage in until is ignored: back to seconds, waiting for Start", "#c")
    p.evaluate(f"{el}.setAttribute('seconds', '42'); {el}.setAttribute('until', 'lunchtime')")
    eq(remaining(t), 42)
    check(p.get_attribute("#c", "running") is None, "not started")
    check(not p.evaluate(f"{shadow('.btn')}.hidden"), "start button shown")
    p.evaluate(f"{el}.setAttribute('until', '25:00')")
    eq(remaining(t), 42, "25:00 is not a time")

@test("countdown", "until-done-and-warn", desc='A countdown to a time a few seconds away ticks every second, enters the warning state, then fires ui-done once and shows the done slot.', component=C, **TZ)
def _(t):
    start(t, '<ui-countdown id="c" until="12:00:05" warn="3"><span slot="done">Back!</span></ui-countdown>')
    p = t.page
    t.step('until="12:00:05": five seconds left, not yet warning', "#c")
    eq(remaining(t), 5)
    eq(p.evaluate(f"{shadow('.box')}.dataset.state"), "")
    t.step("At three seconds left it is in the warning state", "#c")
    p.clock.run_for(2_100)
    eq(remaining(t), 3)
    eq(p.evaluate(f"{shadow('.box')}.dataset.state"), "warn")
    t.step("At 12:00:05 ui-done fires once and the done slot shows", "#c")
    p.clock.run_for(3_000)
    done = t.events("ui-done")
    eq(len(done), 1, "ui-done count")
    eq(done[0]["detail"], {})
    check(done[0]["bubbles"] and done[0]["composed"], "ui-done bubbles, composed")
    eq([e["detail"]["remaining"] for e in t.events("ui-tick")], [5, 4, 3, 2, 1])
    eq(remaining(t), 0)
    eq(p.evaluate(f"{shadow('.box')}.dataset.state"), "done")
    check(p.get_attribute("#c", "running") is None, "stopped")
    check(p.locator("#c >> text=Back!").is_visible(), "done slot visible")
    eq(p.evaluate(f"{shadow('[aria-live]')}.textContent"), "Done", "completion announced")
    t.step("reset() resolves the time again: 12:00:05 has passed, so it is tomorrow", "#c")
    p.evaluate(f"{el}.reset()")
    check(p.get_attribute("#c", "running") is not None, "running again")
    eq(remaining(t), 86400)
    p.clock.run_for(5_000)
    eq(len(t.events("ui-done")), 1, "no second ui-done")
