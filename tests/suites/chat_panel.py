"""Suite B (2/2): <ui-chat-panel> in a real browser."""
from registry import test, env, open_fixture, mount
from helpers import focused, rect, check, eq

C = "ui-chat-panel"
EVENTS = ("ui-send", "ui-open", "ui-close", "ui-action")
panel = lambda js: f"document.getElementById('c').shadowRoot.querySelector('{js}')"
VW, VH = 640, 420

def settle(t, ms=420):
    t.page.wait_for_timeout(ms)

@test("chat-panel", "open-close", component=C)
def _(t):
    open_fixture(t, '<button id="opener">Open chat</button><ui-chat-panel id="c" heading="Help"></ui-chat-panel>')
    t.capture_events(*EVENTS)
    p = t.page
    t.step("Closed: the panel is off screen, hidden and inert", "#c")
    eq(p.evaluate(f"getComputedStyle({panel('.panel')}).visibility"), "hidden")
    check(p.evaluate(f"{panel('.panel')}.hasAttribute('inert')"), "inert while closed")
    eq(p.evaluate(f"{panel('.panel')}.getAttribute('aria-hidden')"), "true")
    t.step("toggle() opens it and returns the new state", "#c")
    p.focus("#opener")
    eq(p.evaluate("document.getElementById('c').toggle()"), True)
    settle(t)
    check(p.get_attribute("#c", "open") is not None, "open attribute reflects")
    eq(rect(p, "#c .panel")["right"], VW, "panel slid fully on screen")
    eq(t.events("ui-open")[-1]["detail"], {"open": True})
    check(t.events("ui-open")[-1]["bubbles"] and t.events("ui-open")[-1]["composed"], "ui-open bubbles, composed")
    t.step("Opening focuses the composer (non-touch device)", "#c")
    eq(focused(p), ["ui-chat-panel", "textarea.input"])
    t.step("Escape closes it and returns focus to the opener", "#c")
    p.keyboard.press("Escape"); settle(t)
    eq(t.events("ui-close")[-1]["detail"], {"open": False})
    check(p.get_attribute("#c", "open") is None, "open attribute removed")
    eq(focused(p), ["button"], "focus back on the opener")
    t.step("toggle(true)/toggle(false)/show()/hide() work", "#c")
    eq(p.evaluate("(() => { const c = document.getElementById('c'); return [c.toggle(true), c.toggle(true), c.toggle(false), c.show(), c.open, c.hide(), c.open]; })()"), [True, True, False, None, True, None, False])
    t.step("The open attribute can be set directly", "#c")
    p.evaluate("document.getElementById('c').setAttribute('open', '')"); settle(t)
    eq(rect(p, "#c .panel")["right"], VW)
    t.step("The close button closes it", "#c")
    p.click("#c .close"); settle(t)
    check(p.get_attribute("#c", "open") is None, "closed")

@test("chat-panel", "backdrop", component=C)
def _(t):
    open_fixture(t, '<ui-chat-panel id="c" backdrop open></ui-chat-panel>')
    p = t.page; settle(t)
    t.step("`backdrop` shows a scrim while open", "#c")
    check(float(p.evaluate(f"getComputedStyle({panel('.backdrop')}).opacity")) > 0.9, "scrim visible")
    t.step("Clicking the scrim closes the panel", "#c")
    p.mouse.click(20, 200); settle(t)
    check(p.get_attribute("#c", "open") is None, "closed by scrim click")
    check(float(p.evaluate(f"getComputedStyle({panel('.backdrop')}).opacity")) < 0.1, "scrim gone")

@test("chat-panel", "sides", component=C)
def _(t):
    open_fixture(t, '<ui-chat-panel id="r"></ui-chat-panel><ui-chat-panel id="l" side="left"></ui-chat-panel><ui-chat-panel id="b" side="bottom"></ui-chat-panel>')
    p = t.page
    for side, check_fn in (("r", lambda r: abs(r["right"] - VW) < 1 and r["left"] > 0),
                           ("l", lambda r: abs(r["left"]) < 1 and r["right"] < VW),
                           ("b", lambda r: abs(r["bottom"] - VH) < 1 and abs(r["width"] - VW) < 1)):
        name = {"r": "right (default)", "l": "left", "b": "bottom"}[side]
        t.step(f"side: {name}", f"#{side}")
        p.evaluate(f"document.getElementById('{side}').show()"); settle(t)
        r = rect(p, f"#{side} .panel")
        check(check_fn(r), f"{name} panel rect is wrong: {r}")
        p.evaluate(f"document.getElementById('{side}').hide()"); settle(t)

@test("chat-panel", "send-and-messages", component=C)
def _(t):
    open_fixture(t, '<ui-chat-panel id="c" heading="Help" placeholder="Ask…" open><div data-role="agent">Hello from the slot</div></ui-chat-panel>')
    t.capture_events(*EVENTS)
    p = t.page; settle(t)
    t.step("Slotted messages (data-role) are shown", "#c")
    check(p.locator("#c >> text=Hello from the slot").is_visible(), "slotted message visible")
    t.step("Type a message and press Enter", "#c")
    p.fill("#c textarea", "hi there"); p.keyboard.press("Enter")
    eq(t.events("ui-send")[-1]["detail"], {"text": "hi there"})
    check(t.events("ui-send")[-1]["bubbles"] and t.events("ui-send")[-1]["composed"], "ui-send bubbles, composed")
    eq(p.input_value("#c textarea"), "", "composer is cleared")
    eq(p.locator("#c .msg.user").count(), 1, "the user's message is echoed")
    t.step("Shift+Enter inserts a newline instead of sending", "#c")
    p.fill("#c textarea", "line1"); p.keyboard.press("Shift+Enter"); p.keyboard.type("line2")
    eq(len(t.events("ui-send")), 1)
    eq(p.input_value("#c textarea"), "line1\nline2")
    p.keyboard.press("Enter")
    eq(t.events("ui-send")[-1]["detail"]["text"], "line1\nline2")
    t.step("Empty or whitespace-only input sends nothing", "#c")
    p.fill("#c textarea", "   "); p.keyboard.press("Enter")
    eq(len(t.events("ui-send")), 2)
    t.step("addMessage() adds a bubble and returns it", "#c")
    eq(p.evaluate("document.getElementById('c').addMessage('agent', 'Hi!').className"), "msg agent")
    p.evaluate("document.getElementById('c').addMessage('error', 'Boom')")
    check(p.locator("#c .msg.error").is_visible(), "error bubble styled")
    t.step("`messages` property reads and replaces the log", "#c")
    msgs = p.evaluate("document.getElementById('c').messages")
    eq([m["role"] for m in msgs], ["user", "user", "agent", "error"])
    p.evaluate("document.getElementById('c').messages = [{role: 'agent', text: 'fresh'}]")
    eq(p.evaluate("document.getElementById('c').messages"), [{"role": "agent", "text": "fresh"}])
    t.step("clear() empties it", "#c")
    p.evaluate("document.getElementById('c').clear()")
    eq(p.evaluate("document.getElementById('c').messages"), [])
    t.step("A cancelled ui-send keeps the draft and does not echo", "#c")
    p.evaluate("document.getElementById('c').addEventListener('ui-send', (e) => e.preventDefault())")
    p.fill("#c textarea", "keep me"); p.keyboard.press("Enter")
    eq(p.input_value("#c textarea"), "keep me"); eq(p.evaluate("document.getElementById('c').messages.length"), 0)

@test("chat-panel", "busy-and-no-echo", component=C)
def _(t):
    open_fixture(t, '<ui-chat-panel id="c" open no-echo></ui-chat-panel>')
    t.capture_events(*EVENTS)
    p = t.page; settle(t)
    t.step("`no-echo`: sending does not add a user bubble", "#c")
    p.fill("#c textarea", "one"); p.keyboard.press("Enter")
    eq(len(t.events("ui-send")), 1); eq(p.locator("#c .msg.user").count(), 0)
    t.step("`busy` shows a pending bubble and disables Send", "#c")
    p.evaluate("document.getElementById('c').busy = true")
    check(p.locator("#c .pending").is_visible(), "pending bubble")
    eq(p.text_content("#c .pending"), "Thinking…")
    check(p.locator("#c .send").is_disabled(), "send disabled")
    p.fill("#c textarea", "two"); p.keyboard.press("Enter")
    eq(len(t.events("ui-send")), 1, "Enter does not send while busy")
    t.step("`busy-text` customises the pending bubble", "#c")
    p.evaluate("document.getElementById('c').setAttribute('busy-text', 'Working…')")
    eq(p.text_content("#c .pending"), "Working…")
    t.step("Clearing `busy` re-enables Send", "#c")
    p.evaluate("document.getElementById('c').busy = false")
    check(p.locator("#c .send").is_enabled(), "send enabled")

@test("chat-panel", "reduced-motion", component=C, reduced_motion="reduce")
def _(t):
    open_fixture(t, '<ui-chat-panel id="c"></ui-chat-panel>')
    p = t.page
    t.step("prefers-reduced-motion: reduce, so the slide has no real duration", "#c")
    dur = p.evaluate(f"parseFloat(getComputedStyle({panel('.panel')}).transitionDuration)")
    check(dur < 0.001, f"transition duration should be ~0, got {dur}s")
    t.step("The panel is fully on screen immediately after opening", "#c")
    p.evaluate("document.getElementById('c').show()"); p.wait_for_timeout(60)
    eq(rect(p, "#c .panel")["right"], VW)

@test("chat-panel", "slide-animation", component=C)
def _(t):
    open_fixture(t, '<ui-chat-panel id="c"></ui-chat-panel>')
    p = t.page
    t.step("Without a reduced-motion preference the panel animates (~250ms)", "#c")
    dur = p.evaluate(f"parseFloat(getComputedStyle({panel('.panel')}).transitionDuration)")
    check(0.2 <= dur <= 0.3, f"expected ~0.25s, got {dur}s")
    p.evaluate("document.getElementById('c').show()"); p.wait_for_timeout(50)
    check(rect(p, "#c .panel")["right"] > VW + 20, "still sliding in 50ms after opening")
    settle(t)
    eq(rect(p, "#c .panel")["right"], VW)
    t.step("--ui-chat-panel-duration changes the speed", "#c")
    p.evaluate("document.getElementById('c').hide(); document.getElementById('c').style.setProperty('--ui-chat-panel-duration', '600ms')")
    eq(p.evaluate(f"parseFloat(getComputedStyle({panel('.panel')}).transitionDuration)"), 0.6)

@test("chat-panel", "accessibility", component=C)
def _(t):
    open_fixture(t, '<button id="before">before</button><ui-chat-panel id="c" heading="Support" placeholder="Ask support"></ui-chat-panel>')
    p = t.page
    t.step("Roles and labels", "#c")
    eq(p.get_attribute("#c .panel", "role"), "complementary")
    eq(p.get_attribute("#c .panel", "aria-label"), "Support")
    eq(p.get_attribute("#c .log", "role"), "log"); eq(p.get_attribute("#c .log", "aria-live"), "polite")
    eq(p.get_attribute("#c textarea", "aria-label"), "Ask support")
    eq(p.get_attribute("#c .close", "aria-label"), "Close chat")
    t.step("While closed, Tab skips the panel entirely", "#c")
    p.focus("#before"); p.keyboard.press("Tab")
    check(focused(p)[0] != "ui-chat-panel", f"closed panel took focus: {focused(p)}")
    t.step("Open: Tab order is close, log, composer, send", "#c")
    p.evaluate("document.getElementById('c').show()"); settle(t)
    p.evaluate(f"{panel('.close')}.focus()")
    seq = [focused(p)[-1]]
    for _ in range(3):
        p.keyboard.press("Tab"); seq.append(focused(p)[-1])
    check([s.split(".")[-1].replace("icon-btn", "close") for s in seq] == ["close", "log", "input", "send"], f"unexpected tab order {seq}")

@test("chat-panel", "store-binding", component=C)
def _(t):
    open_fixture(t, '<ui-store name="chat1"><script type="application/json">{"messages":[{"role":"agent","text":"seeded"}]}</script></ui-store><ui-chat-panel id="c" store="chat1" open></ui-chat-panel>')
    t.capture_events(*EVENTS)
    p = t.page; settle(t)
    t.step("With `store`, messages render from the store", "#c")
    eq(p.evaluate("document.getElementById('c').messages"), [{"role": "agent", "text": "seeded"}])
    t.step("Sending dispatches a ui-action add instead of echoing", "#c")
    p.fill("#c textarea", "hello store"); p.keyboard.press("Enter"); p.wait_for_timeout(100)
    a = t.events("ui-action")[-1]["detail"]
    eq(a["store"], "chat1"); eq(a["action"], "add"); eq(a["payload"]["item"], {"role": "user", "text": "hello store"}); eq(a["payload"]["path"], "messages")
    eq([m["text"] for m in p.evaluate("window.__lib.get('chat1', 'messages')")], ["seeded", "hello store"])
    eq([m["text"] for m in p.evaluate("document.getElementById('c').messages")], ["seeded", "hello store"], "panel re-rendered from the store")
    t.step("A store change from elsewhere shows up in the panel", "#c")
    p.evaluate("window.__lib.dispatch('chat1', 'add', {path: 'messages', item: {role: 'agent', text: 'pushed'}})"); p.wait_for_timeout(100)
    check(p.locator("#c .msg", has_text="pushed").is_visible(), "pushed message rendered")
