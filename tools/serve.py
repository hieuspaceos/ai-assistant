#!/usr/bin/env python3
"""serve.py — static server nhỏ cho portal (macOS/Linux), chỉ localhost.

Bản tương đương tools/serve.ps1 trên Windows. Phục vụ folder ai-assistant/
nhưng CHẶN dotfile/dot-folder ở mọi cấp (.devin, .git...) — secrets nằm
trong .devin/, không được lộ ra web.

  python3 tools/serve.py [port] [root]
"""
import http.server, os, sys, urllib.parse

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
ROOT = os.path.realpath(sys.argv[2] if len(sys.argv) > 2 else "..")
ROOT_PREFIX = ROOT + os.sep

# mimetypes của một số OS chưa biết font web → khai báo tay
EXTRA_MIME = {".woff": "font/woff", ".woff2": "font/woff2", ".ttf": "font/ttf"}

class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def translate_path(self, path):
        # chặn dotfile/dot-folder ở mọi cấp + giữ request trong ROOT
        raw = urllib.parse.unquote(urllib.parse.urlparse(path).path)
        if raw in ("/", "/web", "/web/"):
            raw = "/web/index.html"
        parts = [p for p in raw.split("/") if p]
        if any(p.startswith(".") for p in parts):
            return None
        fp = os.path.realpath(os.path.join(ROOT, *parts))
        if not (fp == ROOT or fp.startswith(ROOT_PREFIX)):
            return None
        return fp

    def send_head(self):
        # chống DNS rebinding: chỉ phục vụ Host loopback. Trang web lạ rebind
        # DNS về 127.0.0.1 thì Host header vẫn là domain của nó → 403.
        # (Windows: serve.ps1 nhờ http.sys prefix đã chặn sẵn ở kernel.)
        h = (self.headers.get("Host") or "").strip()
        if h.startswith("[") and "]" in h:
            h = h[1:h.index("]")]              # [::1]:8080 → ::1
        elif not h.startswith("["):
            h = h.rsplit(":", 1)[0]            # localhost:8080 → localhost
        # Host dị dạng ("[", "[]", thiếu hẳn) → h lạ → rơi vào 403 dưới đây
        if h not in ("localhost", "127.0.0.1", "::1") \
                and not h.endswith(".localhost"):
            self.send_error(403, "Host khong duoc phep")   # reason phải latin-1
            return None
        fp = self.translate_path(self.path)
        if fp is None or os.path.isdir(fp):
            self.send_error(404, "Not found")
            return None
        try:
            f = open(fp, "rb")
        except OSError:
            self.send_error(404, "Not found")
            return None
        self.send_response(200)
        self.send_header("Content-Type",
                         EXTRA_MIME.get(os.path.splitext(fp)[1].lower())
                         or self.guess_type(fp))
        self.send_header("Content-Length", str(os.fstat(f.fileno()).st_size))
        self.end_headers()
        return f

if __name__ == "__main__":
    with http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler) as srv:
        print(f"portal: http://localhost:{PORT}/web/  (root={ROOT})")
        srv.serve_forever()
