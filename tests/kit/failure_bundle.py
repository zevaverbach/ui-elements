"""Write a failure bundle: everything a person or an agent needs to understand a failed browser test.

    tests/failures/<test-name>/
        failure.gif      animation, for humans
        filmstrip.png    contact sheet of key frames (agents can read images, rarely animations)
        report.json      test name, failing step, error, console errors, URL, catalog entry, DOM snapshot
        console.log      every console message and page error, in order

Stdlib only (plus video_to_gif.py / filmstrip.py next to it).
"""
import json, os, re, shutil, traceback

from video_to_gif import video_to_gif
from filmstrip import filmstrip

def slug(name):
    return re.sub(r"[^a-zA-Z0-9._-]+", "-", name).strip("-").lower()

# Serializes an element (or the body) including open shadow roots, trimmed, for report.json.
DOM_SNAPSHOT_JS = """(sel) => {
  const ser = (n, d) => {
    if (n.nodeType === 3) return n.textContent.trim().slice(0, 80);
    if (n.nodeType !== 1) return '';
    const attrs = [...n.attributes].map(a => ` ${a.name}="${a.value.slice(0, 60)}"`).join('');
    const kids = [...n.childNodes].map(c => ser(c, d + 1)).filter(Boolean);
    if (n.shadowRoot) kids.unshift('<#shadow-root>' + [...n.shadowRoot.childNodes].map(c => ser(c, d + 1)).filter(Boolean).join('') + '</#shadow-root>');
    const value = 'value' in n && n.value !== undefined && n.tagName !== 'BUTTON' ? ` [value="${String(n.value).slice(0, 60)}"]` : '';
    return `<${n.localName}${attrs}${value}>${kids.join('')}</${n.localName}>`;
  };
  let el = null;
  try { el = sel ? document.querySelector(sel) : null; } catch (e) {}
  el = el || document.body;
  return ser(el, 0);
}"""

def snapshot(page, selector=None, limit=6000):
    try:
        html = page.evaluate(DOM_SNAPSHOT_JS, selector)
    except Exception as e:  # page may be closed or crashed
        return f"<snapshot failed: {e}>"
    return html if len(html) <= limit else html[:limit] + f"... [trimmed, {len(html)} chars]"

def write_failure_bundle(out_root, name, video_path, error, step, console, url, catalog_entry=None,
                         dom_snapshot="", video_start=0.0, video_end=None, extra=None):
    d = os.path.join(out_root, slug(name))
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)
    report = {
        "test": name,
        "failing_step": step,
        "error": "".join(traceback.format_exception_only(type(error), error)).strip() if isinstance(error, BaseException) else str(error),
        "console_errors": [c for c in console if c.get("type") in ("error", "pageerror")],
        "page_url": url,
        "catalog_entry": catalog_entry,
        "dom_snapshot": dom_snapshot,
        "files": ["failure.gif", "filmstrip.png", "console.log"],
    }
    if isinstance(error, BaseException):
        report["traceback"] = "".join(traceback.format_exception(type(error), error, error.__traceback__))[-3000:]
    if extra:
        report.update(extra)
    with open(os.path.join(d, "report.json"), "w") as f:
        json.dump(report, f, indent=2)
    with open(os.path.join(d, "console.log"), "w") as f:
        for c in console:
            f.write(f"[{c.get('t', 0):7.2f}s] {c.get('type', '?'):8} {c.get('text', '')}\n")
    if video_path and os.path.exists(video_path):
        try:
            video_to_gif(video_path, os.path.join(d, "failure.gif"), start=video_start, end=video_end, max_bytes=4_000_000)
        except Exception as e:
            report["files"].remove("failure.gif"); report["gif_error"] = str(e)
        try:
            filmstrip(video_path, os.path.join(d, "filmstrip.png"), frames=8, start=video_start, end=video_end)
        except Exception as e:
            report["files"].remove("filmstrip.png"); report["filmstrip_error"] = str(e)
        with open(os.path.join(d, "report.json"), "w") as f:
            json.dump(report, f, indent=2)
    return d
