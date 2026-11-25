"""Suite B (4/4): <ui-progress> in a real browser."""
import math
from registry import test, open_fixture, mount
from helpers import rect, check, eq

C = "ui-progress"
VP = {"width": 400, "height": 300}   # small viewport and one recording per suite (gif=False elsewhere): tests/media has little headroom
CIRC = 2 * math.pi * 45     # the ring's circumference in SVG units (r = 45)
root = lambda i: f"document.getElementById('{i}').shadowRoot"

def aria(p, i):
    return p.evaluate(f"""(() => {{ const g = {root(i)}.querySelector('.graphic');
      return Object.fromEntries(['role', 'aria-valuemin', 'aria-valuemax', 'aria-valuenow', 'aria-valuetext'].map(a => [a, g.getAttribute(a)])); }})()""")

def ring_goal_fraction(p, i):
    """Where the centre of the ring's goal tick sits, as a fraction of the way round from 12 o'clock."""
    dash, off = p.evaluate(f"(() => {{ const g = {root(i)}.querySelector('.ring .goal'); return [parseFloat(g.getAttribute('stroke-dasharray')), parseFloat(g.getAttribute('stroke-dashoffset'))]; }})()")
    return (-off + dash / 2) / CIRC

@test("progress", "ring-and-bar", desc='The default variant is a ring whose fill follows value/max; variant="bar" swaps in a bar of the same percentage, with the label below; heading and meta slot render.', component=C, viewport=VP, gif=False)
def _(t):
    open_fixture(t, '<ui-progress id="r" heading="Ship it" value="3" max="5" label="3 of 5 tasks"><small slot="meta">Friday</small></ui-progress>'
                    '<ui-progress id="b" variant="bar" value="62" label="$62 of $100"></ui-progress>')
    p = t.page
    t.step("Ring: visible, bar hidden, fill at 60%", "#r")
    check(p.locator("#r .ring").is_visible() and p.locator("#r .bar").is_hidden(), "ring shown, bar hidden")
    off = p.evaluate(f"parseFloat({root('r')}.querySelector('.ring .fill').style.strokeDashoffset)")
    check(abs(off - CIRC * 0.4) < 0.01, f"ring dash offset leaves 40% unfilled ({off})")
    eq(p.inner_text("#r .center .label"), "3 of 5 tasks")
    eq(p.inner_text("#r .heading"), "Ship it")
    eq(p.evaluate(f"{root('r')}.querySelector('slot[name=meta]').assignedNodes().length"), 1, "meta slot assigned")
    t.step("Bar: visible, ring hidden, fill width 62%", "#b")
    check(p.locator("#b .bar").is_visible() and p.locator("#b .ring").is_hidden(), "bar shown, ring hidden")
    eq(p.evaluate(f"{root('b')}.querySelector('.bar .fill').style.width"), "62%")
    check(p.locator("#b .barlabel").is_visible(), "bar label shown")
    eq(p.inner_text("#b .barlabel"), "$62 of $100")
    check(p.locator("#b .heading").is_hidden(), "no heading attribute hides the heading")
    t.step("Switching variant at runtime swaps the shape", "#r")
    p.evaluate("document.getElementById('r').setAttribute('variant', 'bar')")
    check(p.locator("#r .bar").is_visible() and p.locator("#r .ring").is_hidden(), "ring -> bar")
    eq(p.evaluate(f"{root('r')}.querySelector('.bar .fill').style.width"), "60%")

@test("progress", "percent", desc='`percent` is value/max as 0-100, clamped at both ends; with no label the percentage is the label; value and max reflect as attributes.', component=C, viewport=VP, gif=False)
def _(t):
    open_fixture(t, '<ui-progress id="a" value="1" max="3"></ui-progress>')
    p = t.page
    pct = lambda: p.evaluate("document.getElementById('a').percent")
    t.step("1 of 3 is 33.3%, shown rounded as the label", "#a")
    check(abs(pct() - 100 / 3) < 1e-9, f"percent {pct()}")
    eq(p.inner_text("#a .center .label"), "33%")
    t.step("Properties reflect to attributes", "#a")
    p.evaluate("const a = document.getElementById('a'); a.max = 8; a.value = 2")
    eq(p.get_attribute("#a", "value"), "2")
    eq(p.get_attribute("#a", "max"), "8")
    eq(pct(), 25)
    eq(p.inner_text("#a .center .label"), "25%")
    t.step("Clamped: over max is 100, negative is 0", "#a")
    p.evaluate("document.getElementById('a').value = 20")
    eq(pct(), 100)
    p.evaluate("document.getElementById('a').value = -4")
    eq(pct(), 0)
    t.step("Defaults: value 0, max 100", "#d")
    mount(t, '<ui-progress id="d"></ui-progress>')
    eq(p.evaluate("[document.getElementById('d').value, document.getElementById('d').max, document.getElementById('d').percent]"), [0, 100, 0])
    eq(p.inner_text("#d .center .label"), "0%")

@test("progress", "goal-line-position", desc='The goal line sits at goal/max: on the bar its centre is at that fraction of the width, on the ring the tick is centred that far round from 12 o\'clock; no `goal` hides both, and goal is clamped to the track.', component=C, viewport=VP)
def _(t):
    open_fixture(t, '<div style="width:400px"><ui-progress id="b" variant="bar" value="62" goal="80"></ui-progress></div>'
                    '<ui-progress id="r" value="3" max="5" goal="4"></ui-progress>'
                    '<ui-progress id="n" value="3"></ui-progress>')
    p = t.page
    t.step("Bar: the goal line is centred at 80% of the track", "#b")
    bar, goal = rect(p, "#b .bar"), rect(p, "#b .bar .goal")
    centre = (goal["left"] + goal["width"] / 2 - bar["left"]) / bar["width"]
    check(abs(centre - 0.8) < 0.005, f"goal centre at {centre:.3f} of the bar")
    check(goal["height"] > bar["height"], "the goal line stands out above and below the track")
    t.step("Ring: the goal tick is centred 4/5 of the way round", "#r")
    check(p.locator("#r .ring .goal").is_visible(), "ring goal shown")
    f = ring_goal_fraction(p, "r")
    check(abs(f - 0.8) < 0.001, f"tick centre at {f:.4f} of the circle")
    t.step("Changing goal moves it", "#r")
    p.evaluate("document.getElementById('r').setAttribute('goal', '1'); document.getElementById('b').setAttribute('goal', '25')")
    check(abs(ring_goal_fraction(p, "r") - 0.2) < 0.001, "ring tick moved to 20%")
    bar, goal = rect(p, "#b .bar"), rect(p, "#b .bar .goal")
    check(abs((goal["left"] + goal["width"] / 2 - bar["left"]) / bar["width"] - 0.25) < 0.005, "bar line moved to 25%")
    t.step("A goal beyond max is clamped to the end of the track", "#b")
    p.evaluate("document.getElementById('b').setAttribute('goal', '500')")
    bar, goal = rect(p, "#b .bar"), rect(p, "#b .bar .goal")
    check(abs((goal["left"] + goal["width"] / 2 - bar["left"]) / bar["width"] - 1) < 0.005, "clamped to 100%")
    t.step("No goal attribute: no goal line", "#n")
    check(p.locator("#n .ring .goal").is_hidden(), "ring goal hidden")
    p.evaluate("document.getElementById('b').removeAttribute('goal')")
    check(p.locator("#b .bar .goal").is_hidden(), "removing goal hides the bar line")

@test("progress", "complete-fires-once-per-crossing", desc='increment() adds 1 (or `by`) capped at max; ui-complete {value, max} fires once when value reaches max, not again while it stays there, and again after dropping below and crossing back.', component=C, viewport=VP, gif=False)
def _(t):
    open_fixture(t, '<ui-progress id="a" value="3" max="5"></ui-progress>')
    t.capture_events("ui-complete")
    p = t.page
    inc = lambda by="": p.evaluate(f"document.getElementById('a').increment({by})")
    val = lambda: p.evaluate("document.getElementById('a').value")
    t.step("increment() adds one: 3 -> 4, no event yet", "#a")
    inc()
    eq(val(), 4)
    eq(len(t.events("ui-complete")), 0)
    t.step("Reaching max fires ui-complete", "#a")
    inc()
    ev = t.events("ui-complete")
    eq(len(ev), 1, "one ui-complete")
    eq(ev[0]["detail"], {"value": 5, "max": 5})
    check(ev[0]["bubbles"] and ev[0]["composed"], "ui-complete bubbles and is composed")
    eq(ev[0]["target"], "ui-progress#a")
    eq(p.evaluate(f"{root('a')}.querySelector('[aria-live]').textContent"), "Complete", "completion is announced")
    t.step("More increments are capped at max and do not fire again", "#a")
    inc(); inc(10)
    eq(val(), 5, "capped at max")
    eq(len(t.events("ui-complete")), 1, "still one ui-complete")
    t.step("Drop below max, then cross again: a second ui-complete", "#a")
    p.evaluate("document.getElementById('a').value = 2")
    eq(p.evaluate(f"{root('a')}.querySelector('[aria-live]').textContent"), "", "announcement cleared below max")
    inc(2)
    eq(val(), 4, "increment(by) adds by")
    eq(len(t.events("ui-complete")), 1)
    inc(3)
    eq(len(t.events("ui-complete")), 2, "second crossing fires again")
    t.step("Mounting an already-complete element fires once", "#m")
    mount(t, '<ui-progress id="m" value="12" max="12"></ui-progress>')
    eq(len([e for e in t.events("ui-complete") if e["target"] == "ui-progress#m"]), 1)

@test("progress", "done-slot", desc='Once value >= max the done slot replaces the label (ring and bar, also after switching variant) and the fill switches to the done color; below max the label is back.', component=C, viewport=VP, gif=False)
def _(t):
    open_fixture(t, '<ui-progress id="r" value="11" max="12" label="11 of 12 sets"><span slot="done">Done!</span></ui-progress>'
                    '<ui-progress id="b" variant="bar" value="9" max="10" label="9 of 10"><span slot="done">Under budget!</span></ui-progress>'
                    '<ui-progress id="n" value="1" max="1" label="1 of 1"></ui-progress>')
    p = t.page
    fill = lambda i, sel, propname: p.evaluate(f"getComputedStyle({root(i)}.querySelector('{sel}')).{propname}")
    t.step("Below max: the label shows, the done slot is hidden", "#r")
    check(p.locator("#r .center .label").is_visible() and p.locator("#r .done-slot").is_hidden(), "label, not done")
    before = fill("r", ".ring .fill", "stroke")
    t.step("Ring at max: the done slot replaces the label, the fill turns the done color", "#r")
    p.evaluate("document.getElementById('r').increment()")
    check(p.locator("#r .done-slot").is_visible(), "done slot shown")
    check(p.locator("#r .center .label").is_hidden(), "label hidden")
    eq(p.inner_text("#r [slot=done]"), "Done!")
    check(fill("r", ".ring .fill", "stroke") != before, "fill color changes on completion")
    t.step("Bar at max: the done slot shows in the label's place", "#b")
    p.evaluate("document.getElementById('b').increment()")
    check(p.locator("#b .barlabel .done-slot").is_visible(), "done slot shown under the bar")
    check(p.locator("#b [slot=done]").is_visible(), "slotted content visible")
    check(p.locator("#b .center").is_hidden(), "the ring's centre stays hidden")
    t.step("Switching the finished bar to a ring moves the done slot into the ring", "#b")
    p.evaluate("document.getElementById('b').removeAttribute('variant')")
    check(p.locator("#b .center .done-slot").is_visible() and p.locator("#b [slot=done]").is_visible(), "done slot inside the ring")
    t.step("Without a done slot the label stays", "#n")
    check(p.locator("#n .center .label").is_visible(), "label shown")
    eq(p.inner_text("#n .center .label"), "1 of 1")
    t.step("Back below max: the label returns", "#r")
    p.evaluate("document.getElementById('r').value = 5")
    check(p.locator("#r .center .label").is_visible() and p.locator("#r .done-slot").is_hidden(), "label back")

@test("progress", "aria-values", desc='The graphic is role="progressbar" with aria-valuemin 0, aria-valuemax = max, aria-valuenow = value capped at max, aria-valuetext = the label (or the percentage), and an accessible name from the heading or label.', component=C, viewport=VP, gif=False)
def _(t):
    open_fixture(t, '<ui-progress id="a" value="3" max="5" label="3 of 5 tasks"></ui-progress><ui-progress id="p" variant="bar" value="40"></ui-progress>')
    p = t.page
    t.step("Ring with a label", "#a")
    eq(aria(p, "a"), {"role": "progressbar", "aria-valuemin": "0", "aria-valuemax": "5", "aria-valuenow": "3", "aria-valuetext": "3 of 5 tasks"})
    t.step("Values follow changes; valuenow is capped at max", "#a")
    p.evaluate("const a = document.getElementById('a'); a.value = 9; a.setAttribute('label', 'all done')")
    eq(aria(p, "a")["aria-valuenow"], "5")
    eq(aria(p, "a")["aria-valuetext"], "all done")
    t.step("Bar without a label: valuetext is the percentage", "#p")
    eq(aria(p, "p"), {"role": "progressbar", "aria-valuemin": "0", "aria-valuemax": "100", "aria-valuenow": "40", "aria-valuetext": "40%"})
    t.step("The progressbar is named by the heading, or else by the label", "#a")
    eq(p.evaluate(f"{root('a')}.querySelector('.graphic').getAttribute('aria-label')"), "all done")
    p.evaluate("document.getElementById('a').setAttribute('heading', 'Sprint')")
    eq(p.evaluate(f"{root('a')}.querySelector('.graphic').getAttribute('aria-label')"), "Sprint")
    eq(p.evaluate(f"{root('p')}.querySelector('.graphic').getAttribute('aria-label')"), "40%")
    t.step("The accessibility tree exposes a progressbar with that value", "#p")
    loc = p.get_by_role("progressbar").nth(1)
    eq(loc.get_attribute("aria-valuetext"), "40%")
    check(p.locator("#p .ring").get_attribute("aria-hidden") == "true", "the decorative svg is hidden from assistive tech")
