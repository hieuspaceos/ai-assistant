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

# CSP cho .html dưới vùng nội dung (slide/clone do agent sinh — nguồn duy
# nhất có thể bị prompt-injection). connect-src 'none' là chìa khoá: script
# trong đó vẫn chạy nhưng KHÔNG gọi được bridge :7682/:7684 hay gửi data đi
# đâu bằng JS. KHÔNG áp cho /web/ (portal phải gọi bridge được).
CSP_PATHS = ("/my-course/", "/intro/")
CSP = ("default-src 'self'; "
       "script-src 'self' 'unsafe-inline' https:; "
       "style-src 'self' 'unsafe-inline' https:; "
       "img-src 'self' data: https:; "
       "font-src 'self' data: https:; "
       "media-src 'self' data:; "
       "connect-src 'none'; "
       "form-action 'none'; "
       "base-uri 'none'; "
       "object-src 'none'; "
       "frame-src 'self' https:; "
       "frame-ancestors 'self'")

class Handler(http.server.SimpleHTTPRequestHandler):
    # HTTP/1.1 keep-alive: mặc định HTTP/1.0 → mỗi asset (font, vendor js,
    # manifest...) một TCP connection + một thread mới. Content-Length đã
    # được gửi trên mọi response file nên keep-alive hợp lệ.
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def end_headers(self):
        # vendor (font/marked/purify) không đổi theo request → cache 1h;
        # chỗ khác giữ no-store (manifest/course luôn cần bản mới nhất).
        # Tính giá trị TRƯỚC — gửi MỘT header duy nhất.
        cc = "max-age=3600" if self.path.startswith("/web/vendor/") else "no-store"
        self.send_header("Cache-Control", cc)
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
        ctype = EXTRA_MIME.get(os.path.splitext(fp)[1].lower()) \
            or self.guess_type(fp)
        size = os.fstat(f.fileno()).st_size
        # Range cho video bài học — không có thì Chrome phải tải hết mới tua.
        # Chỉ single-range: multi-range (bytes=a-b,c-d) và chuỗi không parse
        # được đều bỏ qua → trả 200 trọn file (hợp lệ theo spec); còn range
        # hợp lệ cú pháp nhưng vượt biên → 416.
        rng = self.headers.get("Range")
        parts = None
        if rng and rng.startswith("bytes=") and "," not in rng:
            try:
                s, _, e = rng[6:].partition("-")
                start = int(s) if s else 0
                end = int(e) if e else size - 1
                if start > end or start >= size:
                    f.close()
                    self.send_error(416)
                    return None
                parts = (start, min(end, size - 1))
            except ValueError:
                pass
        if parts:
            start, end = parts
            self.send_response(206)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(end - start + 1))
            self.end_headers()
            # CẠM BẪY: KHÔNG được `return f` — copyfile() của base class sẽ
            # gửi từ start TỚI EOF, nhiều hơn Content-Length → vỡ keep-alive
            # HTTP/1.1 (client đọc thừa byte, connection desync). Tự ghi đúng
            # đoạn rồi đóng file.
            if self.command == "GET":
                f.seek(start)
                remaining = end - start + 1
                while remaining > 0:
                    chunk = f.read(min(remaining, 262144))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
            f.close()
            return None
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(size))
        self.send_header("Accept-Ranges", "bytes")
        raw_path = urllib.parse.unquote(urllib.parse.urlparse(self.path).path)
        if raw_path.startswith(CSP_PATHS) \
                and raw_path.lower().endswith((".html", ".htm")):
            self.send_header("Content-Security-Policy", CSP)
        self.end_headers()
        return f

if __name__ == "__main__":
    with http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler) as srv:
        print(f"portal: http://localhost:{PORT}/web/  (root={ROOT})")
        srv.serve_forever()
