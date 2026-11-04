/* On-screen aids for recorded browser tests. Injected with page.add_init_script.
 *   window.__caption("Step text")   shows a caption bar at the bottom of the page
 * Also draws a cursor dot that follows mouse/touch/pointer input and a small key badge,
 * so a silent GIF shows what the test is doing. No dependencies. */
(() => {
  if (window.__captionInstalled) return;
  window.__captionInstalled = true;
  const KEY = '__caption_text';
  const mk = () => {
    const root = document.createElement('div');
    root.id = '__caption_root';
    root.style.cssText = 'all:initial;position:fixed;inset:0;pointer-events:none;z-index:2147483647;';
    root.innerHTML = `
      <div id="__cap" style="position:fixed;left:8px;right:8px;bottom:8px;padding:6px 10px;border-radius:8px;background:rgba(15,17,23,.88);color:#fff;font:600 14px/1.3 system-ui,sans-serif;display:none"></div>
      <div id="__dot" style="position:fixed;width:16px;height:16px;margin:-8px 0 0 -8px;border-radius:50%;background:rgba(255,80,80,.55);border:2px solid #fff;box-shadow:0 0 0 1px #000;display:none"></div>
      <div id="__key" style="position:fixed;right:8px;top:8px;padding:3px 8px;border-radius:6px;background:rgba(15,17,23,.88);color:#fff;font:600 13px ui-monospace,monospace;display:none"></div>`;
    return root;
  };
  let root, cap, dot, key, keyTimer;
  const ensure = () => {
    if (root && root.isConnected) return;
    root = mk();
    (document.body || document.documentElement).appendChild(root);
    cap = root.querySelector('#__cap'); dot = root.querySelector('#__dot'); key = root.querySelector('#__key');
    let t = ''; try { t = sessionStorage.getItem(KEY) || ''; } catch {}
    if (t) { cap.textContent = t; cap.style.display = 'block'; }
  };
  window.__caption = (text) => {
    ensure();
    try { sessionStorage.setItem(KEY, text); } catch {}
    cap.textContent = text; cap.style.display = text ? 'block' : 'none';
  };
  const move = (x, y) => { ensure(); dot.style.display = 'block'; dot.style.left = x + 'px'; dot.style.top = y + 'px'; };
  addEventListener('pointermove', (e) => move(e.clientX, e.clientY), true);
  addEventListener('pointerdown', (e) => { move(e.clientX, e.clientY); dot.style.background = 'rgba(255,40,40,.9)'; }, true);
  addEventListener('pointerup', () => { if (dot) dot.style.background = 'rgba(255,80,80,.55)'; }, true);
  addEventListener('keydown', (e) => {
    ensure();
    key.textContent = [e.ctrlKey && 'Ctrl', e.altKey && 'Alt', e.shiftKey && 'Shift', e.metaKey && 'Meta', e.key === ' ' ? 'Space' : e.key].filter(Boolean).join('+');
    key.style.display = 'block'; clearTimeout(keyTimer); keyTimer = setTimeout(() => { key.style.display = 'none'; }, 900);
  }, true);
  document.addEventListener('DOMContentLoaded', ensure);
})();
