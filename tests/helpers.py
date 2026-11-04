"""Small helpers shared by the suites."""
import json

FOCUSED_JS = """() => { let e = document.activeElement; const path = [];
  while (e) { path.push(e.localName + (e.className && typeof e.className === 'string' ? '.' + e.className.split(' ')[0] : ''));
    e = e.shadowRoot && e.shadowRoot.activeElement; } return path; }"""

def focused(page):
    """Path to the focused element through shadow roots, e.g. ['ui-todo-item', 'button.handle']."""
    return page.evaluate(FOCUSED_JS)

def texts(page, selector="ui-todo-item"):
    return page.evaluate("(s) => [...document.querySelectorAll(s)].map(i => i.text)", selector)

def rect(page, selector):
    """Bounding rect of an element; the selector may reach into open shadow roots."""
    return page.locator(selector).first.evaluate("e => { const r = e.getBoundingClientRect(); return {left: r.left, right: r.right, top: r.top, bottom: r.bottom, width: r.width, height: r.height}; }")

def check(cond, msg):
    if not cond:
        raise AssertionError(msg)

def eq(actual, expected, what=""):
    if actual != expected:
        raise AssertionError(f"{what + ': ' if what else ''}expected {json.dumps(expected)}, got {json.dumps(actual)}")

def touch_drag(t, x0, y0, x1, y1, steps=10):
    """Drag with real touch events (CDP). The context must be created with has_touch=True."""
    cdp = t.context.new_cdp_session(t.page)
    send = lambda typ, pts: cdp.send("Input.dispatchTouchEvent", {"type": typ, "touchPoints": pts})
    send("touchStart", [{"x": x0, "y": y0, "id": 1}])
    for i in range(1, steps + 1):
        send("touchMove", [{"x": x0 + (x1 - x0) * i / steps, "y": y0 + (y1 - y0) * i / steps, "id": 1}])
        t.page.wait_for_timeout(20)
    send("touchEnd", [])
