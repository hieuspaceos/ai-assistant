#!/usr/bin/env python3
"""ext-bridge.py — cầu nối giữa trợ lý AI (agent) và extension "Trợ Lý AI"
trong trình duyệt thật của học viên.

Một cổng duy nhất (mặc định 7683, chỉ localhost):
  Agent     →  POST http://localhost:7683/api/browser   {"action": "...", ...}
  Extension →  ws://localhost:7683/ext                  (giữ kết nối mở)

Agent gọi HTTP bằng curl/Invoke-RestMethod — không cần MCP, không cần
cài thêm thư viện (file này chỉ dùng Python chuẩn).

Các action v1:
  status                 — extension có đang kết nối không
  tabs                   — danh sách tab đang mở trong browser của học viên
  open  {url}            — mở tab mới
  activate {tabId}       — chuyển tới tab
  close {tabId}          — đóng tab
  snapshot {tabId?}      — cây phần tử của trang (có ref e1,e2... để bấm)
  click {tabId?, ref|text} — bấm vào phần tử theo ref từ snapshot hoặc theo chữ hiển thị
  type {tabId?, ref, text} — gõ chữ vào ô
  scroll {tabId?, dy, sel?} — cuộn trang hoặc một vùng cuộn
  scrollables {tabId?}   — liệt kê vùng cuộn (s1, s2...) để dùng với scroll sel=
  query {tabId?, sel, attr?} — text/attribute của mọi phần tử khớp CSS selector
  read {tabId?, sel?}    — lấy toàn văn nội dung trang (đã lọc gọn)
  fetch {tabId?, url}    — tải URL bằng phiên đăng nhập của tab (cùng origin)
                          — đọc được sheet/file private, vd gviz CSV Google Sheets
  key {tabId?, sel?, ref?, key} — gửi phím Enter/Tab/Escape/Delete/mũi tên
  paste {tabId?, sel?, text} — dán text/TSV (chỉ app nhận sự kiện giả mới dùng được)
  rect {tabId?, sel|ref} — toạ độ tâm phần tử (phục vụ nhóm t*)
  tclick {tabId?, sel|ref|x,y} — click chuột THẬT qua CDP (app bỏ qua click giả)
  tright {tabId?, sel|ref|x,y} — chuột phải thật (mở context menu)
  tmove {tabId?, sel|ref|x,y} — hover chuột thật (lộ nút/menu ẩn)
  ttype {tabId?, sel|ref, text} — click thật + chèn text thật (editor Zalo #richInput)
  tinsert {tabId?, text, mode?} — chèn text thật tại con trỏ; mode=char bắn
                          phím từng ký tự (ghi được vào grid Google Sheets)
  tkey {tabId?, sel|ref?, key, modifiers?} — nhấn phím thật (modifiers: 4=Cmd/Ctrl)
  tdetach {tabId?}       — tháo debugger, tắt banner "đang gỡ lỗi"
  screenshot {tabId?}    — chụp tab → lưu file, trả đường dẫn
  wait {tabId?, ms}      — chờ trang (tối đa 5s)
  reload                 — nạp lại extension (sau khi sửa code)
"""
import base64, hashlib, json, os, re, socket, struct, sys, threading, time

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 7683
CWD = sys.argv[2] if len(sys.argv) > 2 else "."
WS_MAGIC = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

# Chỉ trang local (host loopback, mọi port) được gọi HTTP API từ browser;
# extension (WS) xài origin chrome-extension://… Request không có Origin
# (curl từ agent) vẫn cho qua.
import urllib.parse
def is_local_origin(origin):
    try:
        h = urllib.parse.urlsplit(origin).hostname or ""
    except Exception:
        return False
    return h in ("localhost", "127.0.0.1", "::1") or h.endswith(".localhost")

EXT_ORIGIN_PREFIXES = ("chrome-extension://", "moz-extension://",
                       "safari-web-extension://", "edge-extension://")

ext_lock = threading.Lock()
ext_send_lock = threading.Lock()
ext_sock = None          # socket của extension đang kết nối (chỉ một)
pending = {}             # id -> {"event": Event, "res": dict}
next_id = [0]

# ---------- websocket (server side, stdlib) ----------

def ws_send(sock, text):
    data = text.encode()
    n = len(data)
    if n < 126:
        head = struct.pack("!BB", 0x81, n)
    elif n < 65536:
        head = struct.pack("!BBH", 0x81, 126, n)
    else:
        head = struct.pack("!BBQ", 0x81, 127, n)
    with ext_send_lock:
        sock.sendall(head + data)

def _read(sock, n):
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("đứt kết nối")
        buf += chunk
    return buf

def ws_recv(sock):
    msg = b""
    while True:
        b1, b2 = _read(sock, 2)
        fin, op = b1 & 0x80, b1 & 0x0F
        n = b2 & 0x7F
        if n == 126:
            n = struct.unpack("!H", _read(sock, 2))[0]
        elif n == 127:
            n = struct.unpack("!Q", _read(sock, 8))[0]
        mask = _read(sock, 4) if b2 & 0x80 else None
        payload = _read(sock, n)
        if mask:
            payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        if op == 8:
            raise ConnectionError("extension đóng kết nối")
        if op == 9:      # ping → pong (frame từ server không được mask)
            sock.sendall(b"\x8a\x00")
            continue
        if op in (0, 1, 2):
            msg += payload
        if fin:
            return msg.decode("utf-8", "replace")

def ws_handshake(sock, headers):
    # Chỉ nhận WS từ extension (origin chrome-extension://...) hoặc không có
    # Origin — trang web (kể cả trang localhost) không được vào: nó chiếm slot
    # extension và nhận được mọi lệnh agent gửi xuống.
    mo = re.search(r"^origin:\s*(\S+)", headers, re.I | re.M)
    if mo:
        o = mo.group(1).strip()
        if not o.startswith(EXT_ORIGIN_PREFIXES):
            return False
    key = re.search(r"sec-websocket-key:\s*(\S+)", headers, re.I)
    if not key:
        return False
    accept = base64.b64encode(
        hashlib.sha1((key.group(1) + WS_MAGIC).encode()).digest()).decode()
    sock.sendall((
        "HTTP/1.1 101 Switching Protocols\r\n"
        "Upgrade: websocket\r\nConnection: Upgrade\r\n"
        f"Sec-WebSocket-Accept: {accept}\r\n\r\n").encode())
    return True

# ---------- vòng đời extension ----------

def ext_reader(sock):
    """Đọc message JSON từ extension, khớp response theo id."""
    global ext_sock
    try:
        while True:
            m = json.loads(ws_recv(sock))
            p = pending.get(m.get("id"))
            if p:
                p["res"] = m
                p["event"].set()
    except Exception:
        pass
    finally:
        # chỉ xoá slot nếu vẫn là kết nối của mình — extension mới có thể
        # đã chiếm chỗ từ trước (connect mới thay thế connect cũ)
        with ext_lock:
            if ext_sock is sock:
                ext_sock = None
        print("ext-bridge: extension ngắt kết nối")

def ext_call(action, params, timeout=20):
    """Gửi lệnh tới extension, chờ kết quả. Trả về dict {ok, ...}."""
    with ext_lock:
        s = ext_sock
    if not s:
        return {"ok": False, "err": "extension chưa kết nối — học viên cần mở trình duyệt có cài Trợ Lý AI"}
    next_id[0] += 1
    rid = next_id[0]
    ev = threading.Event()
    pending[rid] = {"event": ev, "res": None}
    try:
        ws_send(s, json.dumps({"id": rid, "action": action, "params": params}))
    except Exception:
        pending.pop(rid, None)
        return {"ok": False, "err": "mất kết nối extension"}
    if not ev.wait(timeout):
        pending.pop(rid, None)
        return {"ok": False, "err": "extension không trả lời (timeout)"}
    res = pending.pop(rid, {}).get("res")
    return res if res is not None else {"ok": True}

# ---------- http tối thiểu ----------

def read_http(sock):
    data = b""
    sock.settimeout(15)
    while b"\r\n\r\n" not in data:
        chunk = sock.recv(8192)
        if not chunk:
            return None
        data += chunk
        if len(data) > 1_000_000:
            return None
    head, _, body = data.partition(b"\r\n\r\n")
    m = re.search(rb"content-length:\s*(\d+)", head, re.I)
    if m:
        if int(m.group(1)) > 1_000_000:
            return None
        need = int(m.group(1)) - len(body)
        while need > 0:
            chunk = sock.recv(min(need, 65536))
            if not chunk:
                break
            body += chunk
            need -= len(chunk)
    return head.decode("latin-1"), body

def send_json(sock, obj, code=200, origin=None):
    b = json.dumps(obj, ensure_ascii=False).encode()
    cors = ""
    if origin and is_local_origin(origin):
        cors = f"Access-Control-Allow-Origin: {origin}\r\nVary: Origin\r\n"
    sock.sendall((
        f"HTTP/1.1 {code} OK\r\nContent-Type: application/json; charset=utf-8\r\n"
        f"{cors}Access-Control-Allow-Headers: Content-Type\r\n"
        f"Content-Length: {len(b)}\r\n\r\n").encode() + b)

def handle_api(method, path, body):
    if path == "/api/browser/status":
        return {"connected": ext_sock is not None}
    if path == "/api/browser" and method == "POST":
        try:
            d = json.loads(body or b"{}")
        except json.JSONDecodeError:
            return {"ok": False, "err": "json lỗi"}
        if not isinstance(d, dict):
            return {"ok": False, "err": "body phải là json object"}
        action = d.pop("action", "")
        res = ext_call(action, d)
        # screenshot lớn → ghi file, trả đường dẫn cho gọn
        if res.get("ok") and res.get("png_b64"):
            d2 = os.path.join(os.path.abspath(CWD), "my-course", ".shots")
            os.makedirs(d2, exist_ok=True)
            fp = os.path.join(d2, f"shot-{int(time.time()*1000)}.png")
            with open(fp, "wb") as f:
                f.write(base64.b64decode(res.pop("png_b64")))
            res["file"] = os.path.relpath(fp, os.path.abspath(CWD))
            # ảnh chụp tích luỹ mãi — chỉ giữ 50 tấm mới nhất
            try:
                shots = sorted(
                    (os.path.join(d2, f) for f in os.listdir(d2)
                     if f.startswith("shot-") and f.endswith(".png")),
                    key=os.path.getmtime)
                for old in shots[:-50]:
                    os.remove(old)
            except OSError:
                pass
        return res
    return {"err": "not found"}, 404

def serve_conn(sock):
    global ext_sock
    try:
        r = read_http(sock)
        if not r:
            sock.close(); return
        head, body = r
        first = head.split("\r\n", 1)[0]
        parts = first.split(" ")
        method, path = parts[0], parts[1] if len(parts) > 1 else "/"
        if method == "GET" and path == "/ext" and "upgrade: websocket" in head.lower():
            if ws_handshake(sock, head):
                # read_http đặt timeout 15s để đọc header — phải gỡ ra, nếu
                # không WS rớt sau 15s im lặng (extension flap liên tục)
                sock.settimeout(None)
                with ext_lock:
                    old = ext_sock
                    ext_sock = sock
                # đóng kết nối cũ (nếu có) để thread reader của nó thoát
                if old is not None and old is not sock:
                    try:
                        old.close()
                    except Exception:
                        pass
                print("ext-bridge: extension đã kết nối")
                # Ping định kỳ: giữ service worker MV3 không ngủ → WS sống
                def pinger():
                    while True:
                        time.sleep(20)
                        with ext_lock:
                            s = ext_sock
                        if s is not sock:
                            return
                        try:
                            ws_send(sock, json.dumps({"t": "ping"}))
                        except Exception:
                            return
                threading.Thread(target=pinger, daemon=True).start()
                ext_reader(sock)
            return
        mo = re.search(r"^origin:\s*(\S+)", head, re.I | re.M)
        origin = mo.group(1).strip() if mo else None
        if origin is not None and not is_local_origin(origin):
            send_json(sock, {"err": "origin không được phép"}, 403)
            return
        if method == "OPTIONS":
            cors = (f"Access-Control-Allow-Origin: {origin}\r\n".encode()
                    if origin and is_local_origin(origin) else b"")
            sock.sendall(b"HTTP/1.1 204 No Content\r\n" + cors +
                         b"Access-Control-Allow-Methods: GET,POST\r\n"
                         b"Access-Control-Allow-Headers: Content-Type\r\n\r\n")
            sock.close(); return
        out = handle_api(method, path, body)
        if isinstance(out, tuple):
            send_json(sock, out[0], out[1], origin)
        else:
            send_json(sock, out, 200, origin)
    except Exception:
        pass
    finally:
        with ext_lock:
            if ext_sock is sock:
                pass
            else:
                try:
                    sock.close()
                except Exception:
                    pass

def main():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", PORT))
    srv.listen(16)
    print(f"ext-bridge: http://localhost:{PORT}  (agent API) + ws/ext (extension)")
    while True:
        c, _ = srv.accept()
        threading.Thread(target=serve_conn, args=(c,), daemon=True).start()

if __name__ == "__main__":
    main()
