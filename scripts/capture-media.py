# Regenerates docs/media/* by driving the demo page in headless Chromium.
# Dev-only. Needs: pip install playwright && playwright install chromium, and ffmpeg
# for the GIF/MP4 step (see the ffmpeg commands at the bottom of this file).
from playwright.sync_api import sync_playwright
import subprocess, time, glob, os, shutil
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OUT=ROOT+"/docs/media"; VID="/tmp/ui-elements-capture"
shutil.rmtree(VID, ignore_errors=True)
srv = subprocess.Popen(["python3","-m","http.server","8766","-d",ROOT],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); time.sleep(1)
U="http://localhost:8766/demo/"
try:
  with sync_playwright() as p:
    b=p.chromium.launch()
    for scheme in ("light","dark"):
      pg=b.new_page(viewport={"width":760,"height":700},device_scale_factor=2,color_scheme=scheme); pg.goto(U); pg.wait_for_timeout(400)
      pg.locator("#single").screenshot(path=f"{OUT}/todo-item-{scheme}.png")
      pg.close()
    # chat open + mid-drag
    pg=b.new_page(viewport={"width":900,"height":640},device_scale_factor=2); pg.goto(U); pg.wait_for_timeout(300)
    pg.click("#toggle-chat-2"); pg.wait_for_timeout(500)
    pg.locator("#chat textarea").fill("how many left?"); pg.keyboard.press("Enter"); pg.wait_for_timeout(1100)
    pg.screenshot(path=f"{OUT}/chat-panel.png"); pg.close()
    pg=b.new_page(viewport={"width":760,"height":700},device_scale_factor=2); pg.goto(U)
    pg.locator("#list").scroll_into_view_if_needed()
    h=pg.locator("#list ui-todo-item").nth(0).locator(".handle"); bb=h.bounding_box()
    pg.mouse.move(bb["x"]+10,bb["y"]+10); pg.mouse.down(); pg.mouse.move(bb["x"]+10,bb["y"]+75,steps=6); pg.wait_for_timeout(300)
    pg.locator("#list").screenshot(path=f"{OUT}/reorder-drag.png"); pg.mouse.up(); pg.close()
    # video
    ctx=b.new_context(viewport={"width":900,"height":620},record_video_dir=VID,record_video_size={"width":900,"height":620}); pg=ctx.new_page(); pg.goto(U)
    pg.evaluate("document.querySelector('#list').scrollIntoView({block:'center'})"); pg.wait_for_timeout(900)
    pg.fill("#new-text","Water the plants"); pg.wait_for_timeout(500); pg.keyboard.press("Enter"); pg.wait_for_timeout(900)
    pg.locator("#list ui-todo-item").nth(1).locator(".check").click(); pg.wait_for_timeout(700)
    h=pg.locator("#list ui-todo-item").nth(3).locator(".handle"); bb=h.bounding_box(); top=pg.locator("#list ui-todo-item").nth(0).bounding_box()
    pg.mouse.move(bb["x"]+10,bb["y"]+10); pg.mouse.down(); pg.mouse.move(bb["x"]+10,top["y"]+5,steps=25); pg.wait_for_timeout(500); pg.mouse.up(); pg.wait_for_timeout(900)
    pg.locator("#list ui-todo-item").nth(2).locator(".handle").focus(); pg.keyboard.press("Space"); pg.wait_for_timeout(300)
    pg.keyboard.press("ArrowUp"); pg.wait_for_timeout(500); pg.keyboard.press("Space"); pg.wait_for_timeout(900)
    pg.click("#toggle-chat-2"); pg.wait_for_timeout(900)
    pg.locator("#chat textarea").type("how many left?",delay=60); pg.wait_for_timeout(300); pg.keyboard.press("Enter"); pg.wait_for_timeout(1800)
    pg.keyboard.press("Escape"); pg.wait_for_timeout(900)
    pg.click("#theme"); pg.wait_for_timeout(1200)
    ctx.close(); b.close()
finally: srv.kill()

# ffmpeg -y -i vid/*.webm -vf "fps=12,scale=720:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128[p];[b][p]paletteuse=dither=bayer:bayer_scale=4" docs/media/demo.gif
# ffmpeg -y -i vid/*.webm -c:v libx264 -pix_fmt yuv420p -crf 28 -movflags +faststart docs/media/demo.mp4
