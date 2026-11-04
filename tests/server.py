"""Tiny static file server for the tests (stdlib only).

serve(root) -> Server(url, close())
serve(root).pages["/x.html"] = html   serves generated pages from memory (same origin as the files)
serve(root, cdn_layout=True)   also answers jsDelivr-style paths:  /gh/<user>/<repo>@<ref>/<path>  ->  <root>/<path>
                               and sends CORS headers, so a page on another port can import modules from it
                               exactly as it would from cdn.jsdelivr.net.
"""
import functools, http.server, re, threading

CDN = re.compile(r"^/gh/[^/]+/[^/@]+@[^/]+/(.*)$")

class _Handler(http.server.SimpleHTTPRequestHandler):
    cdn_layout = False
    pages = {}                            # path -> html served from memory (set per server, see Server.pages)

    def log_message(self, *a):            # quiet
        pass

    def do_GET(self):
        if self.path.startswith("/favicon.ico"):
            self.send_response(204); self.end_headers(); return
        key = self.path.split("?")[0]
        if key in self.pages:
            body = self.pages[key].encode()
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body); return
        if self.cdn_layout:
            m = CDN.match(self.path.split("?")[0])
            if m:
                self.path = "/" + m.group(1)
        super().do_GET()

    def end_headers(self):
        if self.cdn_layout:
            self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

class Server:
    def __init__(self, root, cdn_layout=False):
        self.pages = {}
        handler = type("H", (_Handler,), {"cdn_layout": cdn_layout, "pages": self.pages})
        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(handler, directory=root))
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown(); self.httpd.server_close()

def serve(root, cdn_layout=False):
    return Server(root, cdn_layout)
