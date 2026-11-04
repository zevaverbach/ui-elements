"""Suite C: shared state and the stable shell, driven through demo/shell.html."""
from registry import test, env, open_fixture, mount
from helpers import focused, texts, check, eq

SHELL = "/demo/shell.html"
VIEW = {"width": 640, "height": 480}
items = lambda p: p.evaluate("document.querySelectorAll('#outlet ui-todo-item').length")
status = lambda p: p.inner_text("#status")

def reg(p, expr):
    """Evaluate `expr` with the store registry module (the same instance the shell uses) as `r`."""
    return p.evaluate("async () => { const r = await import('/components/_shared/store-registry.js'); return (" + expr + "); }")

def load(t):
    t.goto(SHELL)
    t.page.wait_for_function("document.querySelectorAll('#outlet ui-todo-item').length > 0")

def swap(p, layout):
    p.evaluate(f"document.querySelector('[data-layout={layout}]').click()")
    p.wait_for_timeout(450)

@test("state", "swap-keeps-focus-caret-and-text", desc='Swapping the outlet keeps focus, the caret and half-typed text in a stable-id input, and no to-dos are lost.', needs_idiomorph=True, viewport=VIEW)
def _(t):
    load(t); p = t.page
    eq(items(p), 10, "ten seeded items")
    t.step("Type half a sentence in the stable-id input", "#new-todo")
    p.click("#new-todo"); p.keyboard.type("hello world")
    p.evaluate("document.getElementById('new-todo').setSelectionRange(5, 5)")
    for layout, label in (("open", "Open only"), ("columns", "Two columns"), ("single", "Single column")):
        t.step(f"Swap the outlet to: {label}", "#new-todo")
        swap(p, layout)
        st = p.evaluate("({id: document.activeElement && document.activeElement.id, v: document.getElementById('new-todo').value, s: document.getElementById('new-todo').selectionStart})")
        eq(st, {"id": "new-todo", "v": "hello world", "s": 5}, f"after swap to {layout}")
    t.step("Nothing was lost: still 10 to-dos in the store", "#status")
    check("10 items" in status(p), status(p))

@test("state", "swap-keeps-scroll-position", desc='Swapping the outlet keeps its scroll position, even when new markup is added above the list.', needs_idiomorph=True, viewport=VIEW)
def _(t):
    load(t); p = t.page
    t.step("Scroll the outlet", "#outlet")
    p.evaluate("document.getElementById('outlet').scrollTop = 150")
    eq(p.evaluate("document.getElementById('outlet').scrollTop"), 150)
    t.step("Swap in new markup (adds a paragraph above the list)", "#outlet")
    p.evaluate("const pg = document.getElementById('playground'); pg.value = pg.value.replace('<div id=\"layout\">', '<div id=\"layout\"><p>extra note</p>')")
    p.click("#swap-playground"); p.wait_for_timeout(450)
    check(p.locator("#outlet p", has_text="extra note").count() == 1, "the new markup arrived")
    check(abs(p.evaluate("document.getElementById('outlet').scrollTop") - 150) < 3, "scroll offset kept")

@test("state", "swap-keeps-component-instances", desc='A swap morphs rather than replaces: the same element instance survives with its inline edit still open, and finishing the edit lands in the store.', needs_idiomorph=True, viewport=VIEW)
def _(t):
    load(t); p = t.page
    t.step("Open an inline edit in one row", "#todos-t2")
    p.evaluate("window.__row = document.getElementById('todos-t2'); window.__row.startEdit()"); p.wait_for_timeout(100)
    p.keyboard.type(" (edited)")
    t.step("Swap layouts: same element instance, edit still open", "#todos-t2")
    swap(p, "open")
    check(p.evaluate("document.getElementById('todos-t2') === window.__row"), "the row element was reused, not recreated")
    check(p.evaluate("window.__row.editing"), "the edit state survived the swap")
    t.step("Finish the edit: it lands in the store", "#todos-t2")
    p.keyboard.press("Enter"); p.wait_for_timeout(200)
    check("(edited)" in p.evaluate("JSON.stringify(document.getElementById('store-todos').data)"), "store updated")

@test("state", "filtered-view-and-two-columns", desc='Layouts built from one store: an open-only view, and two columns (open and done) where ticking an item moves it across.', needs_idiomorph=True, viewport=VIEW)
def _(t):
    load(t); p = t.page
    t.step("Open-only view shows just the open to-dos", "#outlet")
    swap(p, "open")
    eq(items(p), 8)
    check(p.evaluate("[...document.querySelectorAll('#outlet ui-todo-item')].every(i => !i.checked)"), "all rows unchecked")
    t.step("Two columns: open on the left, done on the right", "#outlet")
    swap(p, "columns")
    eq(p.evaluate("document.querySelectorAll('#open ui-todo-item').length"), 8)
    eq(p.evaluate("document.querySelectorAll('#done ui-todo-item').length"), 2)
    t.step("Tick an open item: it moves to the done column", "#outlet")
    p.evaluate("document.querySelector('#open ui-todo-item').shadowRoot.querySelector('.check').click()"); p.wait_for_timeout(200)
    eq(p.evaluate("document.querySelectorAll('#open ui-todo-item').length"), 7)
    eq(p.evaluate("document.querySelectorAll('#done ui-todo-item').length"), 3)

@test("state", "action-from-outlet-reaches-shell-store", desc='The store lives in the shell outside #outlet; ticking, renaming and deleting a row inside the outlet reach it through ui-action events.', needs_idiomorph=True, viewport=VIEW)
def _(t):
    load(t); p = t.page
    t.capture_events("ui-action")
    t.step("The store lives in the shell, outside #outlet", "#store-todos")
    check(p.evaluate("!document.querySelector('#outlet ui-store') && !!document.getElementById('store-todos')"), "store is in the shell")
    t.step("Tick a row inside the outlet", "#todos-t1")
    p.evaluate("document.querySelector('#todos-t1').shadowRoot.querySelector('.check').click()"); p.wait_for_timeout(150)
    a = t.events("ui-action")[-1]
    eq(a["detail"]["store"], "todos"); eq(a["detail"]["action"], "toggle"); eq(a["detail"]["payload"]["id"], "t1")
    check(a["bubbles"] and a["composed"], "ui-action bubbles and is composed")
    check(p.evaluate("document.getElementById('store-todos').data.items.find(i => i.id === 't1').done"), "the shell store changed")
    t.step("Rename and delete go through actions too", "#todos-t3")
    p.evaluate("const r = document.getElementById('todos-t3').shadowRoot; r.querySelector('.del').click(); r.querySelector('.del').click()"); p.wait_for_timeout(200)
    check(p.evaluate("!document.getElementById('store-todos').data.items.some(i => i.id === 't3')"), "t3 removed from the store")
    eq(items(p), 9)

@test("state", "add-and-reorder-update-the-store", desc="Adding a to-do through the shell's input and reordering with the keyboard both update the store.", needs_idiomorph=True, viewport=VIEW)
def _(t):
    load(t); p = t.page
    t.step("Add a to-do through the shell's input", "#new-todo")
    p.fill("#new-todo", "Brand new"); p.keyboard.press("Enter"); p.wait_for_timeout(150)
    eq(p.evaluate("document.getElementById('store-todos').data.items[0].text"), "Brand new")
    t.step("Reorder with the keyboard: the store follows", "#todos-t1")
    first = p.evaluate("document.querySelector('#outlet ui-todo-item').id")
    p.evaluate("document.querySelector('#outlet ui-todo-item').shadowRoot.querySelector('.handle').focus()")
    p.keyboard.press("Space"); p.keyboard.press("ArrowDown"); p.keyboard.press("Space"); p.wait_for_timeout(200)
    dom = texts(p, "#outlet ui-todo-item")
    eq(p.evaluate("document.getElementById('store-todos').data.items.map(i => i.text)"), dom, "store order == DOM order")
    check(dom[0] != "Brand new", "the first row moved down")

@test("state", "store-element-remove-and-readd", desc='Removing the <ui-store> element keeps the data, which is still rendered; changes made while it is gone survive re-adding it.', needs_idiomorph=True, viewport=VIEW)
def _(t):
    load(t); p = t.page
    t.step("Remove the <ui-store> element from the page", "#store-todos")
    p.click("#toggle-store"); p.wait_for_timeout(200)
    check("REMOVED" in status(p), status(p))
    check(p.locator("#store-todos").count() == 0, "element is gone")
    t.step("The data is still there (and still rendered)", "#status")
    check("10 items" in status(p), status(p)); eq(items(p), 10)
    t.step("Change data while the element is gone, then re-add it", "#status")
    reg(p, "r.set('todos', 'marker', 'kept')")
    p.click("#toggle-store"); p.wait_for_timeout(250)
    check("present" in status(p), status(p))
    eq(reg(p, "r.get('todos', 'marker')"), "kept", "re-adding does not re-apply the seed")
    eq(reg(p, "r.get('todos', 'items').length"), 10)

@test("state", "persist-local-survives-reload", desc='With persist="local" changes survive a reload (items, order, ticked state), and a different schema version ignores stored data and re-seeds.', needs_idiomorph=True, viewport=VIEW)
def _(t):
    load(t); p = t.page
    t.step("Change the data: tick one, add one", "#outlet")
    p.evaluate("document.querySelector('#todos-t1').shadowRoot.querySelector('.check').click()")
    p.fill("#new-todo", "Survives reload"); p.keyboard.press("Enter"); p.wait_for_timeout(500)
    before = texts(p, "#outlet ui-todo-item"); done = p.evaluate("[...document.querySelectorAll('#outlet ui-todo-item')].filter(i => i.checked).length")
    raw = p.evaluate("JSON.parse(localStorage.getItem('ui-store:todos'))")
    eq(raw["v"], "1", "stored with a schema version"); eq(len(raw["data"]["items"]), 11)
    t.step("Reload the page", "#outlet")
    p.reload(); p.wait_for_function("document.querySelectorAll('#outlet ui-todo-item').length > 0"); p.wait_for_timeout(300)
    t.step("Everything is back: items, order, ticked state", "#outlet")
    eq(texts(p, "#outlet ui-todo-item"), before)
    eq(p.evaluate("[...document.querySelectorAll('#outlet ui-todo-item')].filter(i => i.checked).length"), done)
    t.step("A different schema version ignores stored data and re-seeds", "#outlet")
    p.evaluate("localStorage.setItem('ui-store:todos', JSON.stringify({v: 'old', data: {items: []}}))")
    p.reload(); p.wait_for_function("document.querySelectorAll('#outlet ui-todo-item').length > 0")
    eq(items(p), 10, "back to the seed")

@test("state", "chat-panel-in-the-shell", desc="The shell's chat panel and its conversation survive an outlet swap and a page reload.", needs_idiomorph=True, viewport=VIEW)
def _(t):
    load(t); p = t.page
    t.step("Open the shell's chat panel (it persists across swaps)", "#chat")
    p.click("#chat-btn"); p.wait_for_timeout(450)
    p.fill("#chat textarea", "how many left?"); p.keyboard.press("Enter"); p.wait_for_timeout(900)
    msgs = p.evaluate("document.getElementById('chat').messages")
    eq([m["role"] for m in msgs], ["agent", "user", "agent"])
    check("open" in msgs[-1]["text"], msgs[-1]["text"])
    t.step("Swap the outlet: the conversation is untouched", "#chat")
    swap(p, "columns")
    eq(len(p.evaluate("document.getElementById('chat').messages")), 3)
    check(p.evaluate("document.getElementById('chat').open"), "the panel stayed open")
    t.step("Reload: the chat history persists too", "#chat")
    p.reload(); p.wait_for_function("document.getElementById('chat').messages.length > 0")
    eq(len(p.evaluate("document.getElementById('chat').messages")), 3)

@test("state", "outlet-never-swaps-the-shell", desc='Hostile markup swapped into the outlet never touches the shell: the chat panel and store elements are untouched.', needs_idiomorph=True, viewport=VIEW)
def _(t):
    load(t); p = t.page
    t.allow_console("status of 404")        # the sanitized <img src="x"> still tries to load
    t.step("Hostile markup is swapped in", "#outlet")
    evil = '<div id="layout"><ui-store name="todos"></ui-store><ui-chat-panel id="evil" open></ui-chat-panel><script>window.__pwned = 1</script><img src="x" onerror="window.__pwned = 1"><p>safe text</p></div>'
    p.evaluate("(h) => { document.getElementById('playground').value = h; }", evil)
    p.click("#swap-playground"); p.wait_for_timeout(500)
    check(p.evaluate("window.__pwned === undefined"), "nothing executed")
    check(p.locator("#outlet >> text=safe text").count() == 1, "safe content arrived")
    t.step("The shell (chat panel, store element) is untouched", "#chat")
    check(p.evaluate("!!document.getElementById('store-todos') && !!document.getElementById('chat')"), "shell elements intact")
    eq(reg(p, "r.get('todos', 'items').length"), 10, "data intact (a seedless ui-store in the outlet does not reset it)")
