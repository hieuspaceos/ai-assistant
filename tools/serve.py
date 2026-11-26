#!/usr/bin/env python3
"""serve.py — static server nhỏ cho portal (macOS/Linux), chỉ localhost.

Bản tương đương tools/serve.ps1 trên Windows. Phục vụ folder ai-assistant/
nhưng CHẶN dotfile/dot-folder ở mọi cấp (.devin, .git...) — secrets nằm
trong .devin/, không được lộ ra web.

  python3 tools/serve.py [port] [root]
"""
import http.server, os, sys, threading, urllib.parse

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
ROOT = os.path.realpath(sys.argv[2] if len(sys.argv) > 2 else "..")
# Fail-closed: chỉ bind loopback trừ khi khai TROLY_ALLOW_REMOTE=1
BIND = os.environ.get("TROLY_BIND") or "127.0.0.1"
if BIND not in ("127.0.0.1", "localhost", "::1") \
        and os.environ.get("TROLY_ALLOW_REMOTE") != "1":
    raise SystemExit("TROLY_BIND không phải loopback — đặt "
                     "TROLY_ALLOW_REMOTE=1 nếu thật sự muốn mở ra mạng")
ROOT_PREFIX = ROOT + os.sep

# mimetypes của một số OS chưa biết font web → khai báo tay
EXTRA_MIME = {".woff": "font/woff", ".woff2": "font/woff2", ".ttf": "font/ttf"}

# CSP cho .html dưới vùng nội dung (slide/clone do agent sinh — nguồn duy
# nhất có thể bị prompt-injection). Hai lớp:
#  - sandbox → trang rơi vào OPAQUE ORIGIN: không đọc được localStorage
#    (bridge_token), không DOM-đọc được iframe/window.open tới portal,
#    không register được service worker. Top-nav chỉ khi CÓ user
#    activation (audit-5 F14 — trang độc không tự điều hướng cả tab;
#    Chrome 58+/Safari 11.1+ đều hỗ trợ). allow-popups giữ target=_blank
#    của trang clone sống; KHÔNG có allow-same-origin — có nó thì mọi
#    thứ mất nghĩa.
#  - connect-src 'none' → script không fetch/XHR/WS được đâu cả.
# KHÔNG áp cho /web/ (portal phải gọi bridge được). clone-view sửa trang
# qua srcdoc thay vì đọc DOM iframe vì trang giờ opaque.
CSP_PATHS = ("/my-course/", "/intro/")
CSP = ("sandbox allow-scripts allow-top-navigation-by-user-activation "
       "allow-popups allow-modals; "
       "default-src 'self'; "
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

    def setup(self):
        super().setup()
        # chống slow-drip: client nhỏ giọt header giữ thread vô hạn;
        # keep-alive idle bị đóng sau 30s thì browser tự mở lại.
        self.connection.settimeout(30)

    def log_message(self, *a):
        pass

    def end_headers(self):
        # vendor (font/marked/purify) không đổi theo request → cache 1h;
        # chỗ khác giữ no-store (manifest/course luôn cần bản mới nhất).
        # Tính giá trị TRƯỚC — gửi MỘT header duy nhất.
        cc = "max-age=3600" if self.path.startswith("/web/vendor/") else "no-store"
        self.send_header("Cache-Control", cc)
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    def translate_path(self, path):
        # chặn dotfile/dot-folder ở mọi cấp + giữ request trong ROOT
        raw = urllib.parse.unquote(urllib.parse.urlparse(path).path)
        if raw in ("/", "/web", "/web/"):
            raw = "/web/index.html"
        parts = [p for p in raw.split("/") if p]
        if any(p.startswith(".") for p in parts):
            return None
        # JSON điều khiển quyền/cấu hình + persona bot: đọc qua API có
        # token, không để GET trần trên :8080 (mọi process local đọc được
        # → lộ danh sách folder, tên học viên, trạng thái app). So hoa-
        # thường bắt buộc: FS macOS/Windows không phân biệt case.
        low = [p.lower() for p in parts]
        if (len(low) == 2 and low[0] == "my-course" and low[1] in (
                "permissions.json", "connections.json", "config.json",
                "bots.json", "bot.md")) \
                or low == ["brain.json"]:
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
                if not s and not e:
                    raise ValueError          # "bytes=-" — vô nghĩa → 200
                if not s:                      # suffix: bytes=-500 = 500 byte cuối
                    start = max(0, size - int(e))
                    end = size - 1
                else:
                    start = int(s)
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
            # trang lạ iframe portal → clickjacking; SAMEORIGIN vẫn cho
            # iframe nội bộ (chat-frame, term-frame, clone-view)
            self.send_header("X-Frame-Options", "SAMEORIGIN")
            # CSP phải đi kèm MỌI response của vùng nội dung — kể cả 206;
            # bỏ sót thì trang độc đoạn Range trả về render không sandbox
            raw_path = urllib.parse.unquote(
                urllib.parse.urlparse(self.path).path)
            if raw_path.lower().startswith(CSP_PATHS) \
                    and raw_path.lower().endswith((".html", ".htm")):
                self.send_header("Content-Security-Policy", CSP)
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
        # trang lạ iframe portal → clickjacking; SAMEORIGIN vẫn cho
        # iframe nội bộ (chat-frame, term-frame, clone-view)
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        raw_path = urllib.parse.unquote(urllib.parse.urlparse(self.path).path)
        # .lower() BẮT BUỘC: FS macOS/Windows không phân biệt hoa-thường nên
        # /MY-COURSE/x.html resolve ra cùng file — nếu so case-sensitive thì
        # content độc chỉ cần location.href sang alias hoa là thoát CSP.
        if raw_path.lower().startswith(CSP_PATHS) \
                and raw_path.lower().endswith((".html", ".htm")):
            self.send_header("Content-Security-Policy", CSP)
        self.end_headers()
        return f

class BoundedServer(http.server.ThreadingHTTPServer):
    # thread-per-connection không trần → kết nối treo phình thread/fd;
    # nắp 64 slot, quá hạn xếp backlog. daemon_threads để Ctrl+C gọn.
    daemon_threads = True
    _slots = threading.BoundedSemaphore(64)

    def process_request(self, request, client_address):
        self._slots.acquire()
        try:
            super().process_request(request, client_address)
        except Exception:
            self._slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._slots.release()

if __name__ == "__main__":
    with BoundedServer((BIND, PORT), Handler) as srv:
        print(f"portal: http://localhost:{PORT}/web/  (root={ROOT})")
        srv.serve_forever()
