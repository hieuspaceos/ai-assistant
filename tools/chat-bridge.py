#!/usr/bin/env python3
"""chat-bridge.py — cầu nối giữa chat UI trong portal và `devin acp`.

Chạy `devin acp` như một process con, nhận prompt từ browser qua HTTP,
đẩy các event (text stream, tool call, xin phép) về browser bằng polling.

Endpoints (mặc định port 7682, chỉ localhost):
  GET  /api/poll?since=N -> {"events": [...], "next": M, "reset": bool}
  POST /api/prompt       -> {"text": "..."} gửi lời nhắn
  POST /api/respond      -> {"id": N, "optionId": "..."} trả lời xin phép
                            ("__cancel__" = học viên từ chối)
  GET  /api/health       -> {"ok": true, "sessionId": ...}

Event (JSON trong mảng events):
  {"t":"ready","sessionId":...}
  {"t":"text","text":"..."}          - agent đang nói (cộng dồn)
  {"t":"tool","title":"...","status":"in_progress|completed"}
  {"t":"perm","id":N,"title":"...","options":[{optionId,name,kind}]}
  {"t":"done"}                       - agent nói xong một lượt
  {"t":"err","msg":"..."}
"""
import json, os, re, shutil, subprocess, sys, threading, urllib.parse, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 7682
CWD = sys.argv[2] if len(sys.argv) > 2 else "."
DEVIN = sys.argv[3] if len(sys.argv) > 3 else "devin"

event_store = []          # các event còn giữ (đầu store có thể đã bị cắt)
event_base = 0            # số event đã cắt khỏi đầu — cursor poll đếm tuyệt đối
MAX_EVENTS = 3000
store_lock = threading.Lock()

# Chỉ trang local được gọi API từ browser: Origin có host là
# localhost/127.0.0.1/[::1] ở BẤT KỲ port nào (portal có thể chạy port khác
# khi 8080 bận). Request không có Origin (curl / Invoke-RestMethod từ agent)
# vẫn cho qua — trang web bên ngoài không giả được Origin localhost nên bị
# chặn 403.
def is_local_origin(origin):
    try:
        h = urllib.parse.urlsplit(origin).hostname or ""
    except Exception:
        return False
    return h in ("localhost", "127.0.0.1", "::1") or h.endswith(".localhost")

def broadcast(ev):
    global event_base
    with store_lock:
        event_store.append(ev)
        excess = len(event_store) - MAX_EVENTS
        if excess > 0:
            del event_store[:excess]
            event_base += excess

class Acp:
    def __init__(self):
        self.proc = subprocess.Popen(
            [DEVIN, "acp", "--process-model", "in-process"],
            cwd=CWD, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, bufsize=1)
        self.next_id = 10
        self.session_id = None
        self.dead = False
        self.lock = threading.Lock()
        threading.Thread(target=self._reader, daemon=True).start()

    def _write(self, obj):
        self.proc.stdin.write(json.dumps(obj, ensure_ascii=False) + "\n")
        self.proc.stdin.flush()

    def send(self, obj):
        with self.lock:
            self._write(obj)

    def call(self, method, params):
        # id tăng trong cùng lock với ghi — không trùng id khi 2 request tới cùng lúc
        with self.lock:
            mid = self.next_id; self.next_id += 1
            self._write({"jsonrpc": "2.0", "id": mid, "method": method, "params": params})
        return mid

    def _reader(self):
        for line in self.proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                m = json.loads(line)
            except json.JSONDecodeError:
                continue
            self._dispatch(m)
        # stdout đóng = devin acp chết → báo UI thay vì để chat treo im lặng
        self.dead = True
        broadcast({"t": "err",
                   "msg": "trợ lý vừa dừng đột ngột — chạy lại file start rồi thử lại"})

    def _dispatch(self, m):
        # Kết quả của session/new (bất kể id nào)
        if self.session_id is None and isinstance(m.get("result"), dict) and m["result"].get("sessionId"):
            self.session_id = m["result"]["sessionId"]
            broadcast({"t": "ready", "sessionId": self.session_id})
            return
        # Lỗi
        if m.get("error"):
            broadcast({"t": "err", "msg": m["error"].get("message", "lỗi không rõ")})
            return
        # Kết quả cuối của một lượt prompt
        if m.get("id") and isinstance(m.get("result"), dict) and "stopReason" in m["result"]:
            broadcast({"t": "done"})
            return
        # Agent hỏi xin phép -> chuyển cho UI
        if m.get("method") == "session/request_permission":
            p = m.get("params", {})
            tc = p.get("toolCall") or {}
            broadcast({
                "t": "perm", "id": m["id"],
                "title": tc.get("title") or "Trợ lý muốn làm một việc",
                "options": [{"optionId": o.get("optionId"),
                             "name": o.get("name", o.get("kind", "?")),
                             "kind": o.get("kind", "")}
                            for o in p.get("options", [])],
            })
            return
        if m.get("method") != "session/update":
            # Request lạ từ agent (vd: fs/read_text_file, fs/write_text_file,
            # terminal/*) — trả lời lỗi ngay, nếu không agent chờ vô hạn.
            if m.get("id") is not None and m.get("method"):
                self.send({"jsonrpc": "2.0", "id": m["id"],
                           "error": {"code": -32601,
                                     "message": "client không hỗ trợ " + str(m["method"])}})
            return
        u = (m.get("params") or {}).get("update") or {}
        su = u.get("sessionUpdate")
        if su == "agent_message_chunk":
            txt = (u.get("content") or {}).get("text")
            if txt:
                broadcast({"t": "text", "text": txt})
        elif su == "tool_call":
            broadcast({"t": "tool", "title": u.get("title") or "đang làm việc",
                       "status": "in_progress"})
        elif su == "tool_call_update":
            st = u.get("status")
            if st in ("completed", "failed"):
                broadcast({"t": "tool", "title": u.get("title") or "",
                           "status": st})
        elif su == "session_info_update":
            pass

acp = Acp()
acp.call("initialize", {
    "protocolVersion": 1,
    "clientCapabilities": {"fs": {"readTextFile": False, "writeTextFile": False},
                           "terminal": False}})
acp.call("session/new", {"cwd": CWD, "mcpServers": []})

# ---------- permissions.json + connections.json (Phase 0) ----------

MC_DIR = os.path.join(os.path.abspath(CWD), "my-course")
PERM_FP = os.path.join(MC_DIR, "permissions.json")
CONN_FP = os.path.join(MC_DIR, "connections.json")
CONFIG_FP = os.path.join(MC_DIR, "config.json")
SKILL_PACKS = os.path.join(os.path.abspath(CWD), ".devin", "skill-packs")
SKILLS_DIR = os.path.join(os.path.abspath(CWD), ".devin", "skills")

def load_json(fp, fallback):
    # utf-8-sig: file ghi bằng PowerShell (Set-Content UTF8) có BOM —
    # utf-8 thường đọc sẽ lỗi và fallback im lặng làm mất dữ liệu
    try:
        return json.load(open(fp, encoding="utf-8-sig"))
    except Exception:
        return fallback

def save_json(fp, obj):
    # ghi ra file tạm rồi đổi tên — crash giữa chừng không corrupt file
    tmp = fp + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, fp)

def run_probe(probe):
    """Kiểm tra một kết nối còn sống không → {ok, msg}.

    msg là chữ hiện thẳng dưới tên app trong panel Cài đặt của học viên —
    viết bằng lời thường, không thuật ngữ (token/MCP/extension…)."""
    if not probe:
        return {"ok": False, "msg": "chưa cài — cứ nhờ trợ lý trong chat, nó làm giúp"}
    try:
        if probe["type"] == "http":
            with urllib.request.urlopen(probe["url"], timeout=4) as r:
                d = json.loads(r.read())
            key = probe.get("expect_key")
            ok = True if key is None else d.get(key) == probe.get("expect_val")
            return {"ok": ok, "msg": "đang hoạt động" if ok
                    else "chưa nối — mở trình duyệt rồi bật tiện ích Trợ Lý AI"}
        if probe["type"] == "tabs":
            # Có trang web đang mở khớp URL — vd: đã mở Zalo/Outlook trong browser
            req = urllib.request.Request(
                "http://127.0.0.1:7683/api/browser",
                data=json.dumps({"action": "tabs"}).encode(),
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=6) as r:
                d = json.loads(r.read())
            if not d.get("ok"):
                return {"ok": False, "msg": "trình duyệt chưa nối — mở Chrome/Edge lên trước"}
            needle = str(probe.get("url_contains") or "").lower()
            ok = bool(needle) and any(
                needle in str(t.get("url", "")).lower() for t in d.get("tabs", []))
            return {"ok": ok, "msg": "đang mở sẵn — nhờ được ngay" if ok
                    else "chưa mở — bấm nút Mở trang rồi đăng nhập"}
        if probe["type"] == "zalo-oa":
            creds = load_json(os.path.join(os.path.abspath(CWD), ".devin", "secrets.local.json"), {})
            tok = str((creds.get("zalo-oa") or {}).get("access_token") or "")
            if not tok:
                return {"ok": False, "msg": "chưa có mã kết nối — nhờ trợ lý trong chat cài giúp"}
            req = urllib.request.Request("https://openapi.zalo.me/v2.0/oa/getoa")
            req.add_header("access_token", tok)
            try:
                with urllib.request.urlopen(req, timeout=8) as r:
                    d = json.loads(r.read())
            except urllib.error.HTTPError as e:
                d = json.loads(e.read() or b"{}")
            ok = d.get("error") == 0
            return {"ok": ok, "msg": "đang kết nối" if ok
                    else "mã kết nối sai hoặc hết hạn — nhờ trợ lý làm mới giúp"}
        if probe["type"] == "path":
            p = os.path.expanduser(probe["path"])
            ok = os.path.exists(p)
            return {"ok": ok, "msg": "thấy folder" if ok else "không thấy folder này"}
        if probe["type"] == "mcp":
            cfg = os.path.join(os.path.abspath(CWD), ".devin", "mcp_config.local.json")
            servers = load_json(cfg, {}).get("mcpServers") or load_json(cfg, {}).get("servers") or {}
            ok = probe["name"] in servers
            return {"ok": ok, "msg": "đã cài sẵn" if ok
                    else "chưa cài — nhờ trợ lý trong chat cài giúp"}
        if probe["type"] == "wp":
            # WordPress REST: đọc credentials từ secrets.local.json (gitignored),
            # GET /wp-json/wp/v2/users/me với Basic auth → 200 mới là kết nối thật
            creds = load_json(os.path.join(os.path.abspath(CWD), ".devin", "secrets.local.json"), {})
            wp = creds.get("wordpress") or {}
            url = (wp.get("url") or "").rstrip("/")
            user = wp.get("user") or ""
            pw = (wp.get("app_password") or "").replace(" ", "")
            if not (url and user and pw):
                return {"ok": False, "msg": "chưa có thông tin đăng nhập — nhờ trợ lý cài giúp"}
            req = urllib.request.Request(url + "/wp-json/wp/v2/users/me")
            import base64
            req.add_header("Authorization", "Basic " + base64.b64encode((user + ":" + pw).encode()).decode())
            try:
                with urllib.request.urlopen(req, timeout=8) as r:
                    ok = r.status == 200
            except Exception:
                ok = False
            return {"ok": ok, "msg": "đang kết nối" if ok
                    else "sai thông tin đăng nhập, hoặc không vào được site"}
    except Exception:
        return {"ok": False, "msg": "có lỗi khi kiểm tra — nhờ trợ lý xem giúp"}
    return {"ok": False, "msg": "kiểu kết nối lạ — nhờ trợ lý xem"}

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _cors(self):
        o = self.headers.get("Origin")
        if o is not None and is_local_origin(o):
            self.send_header("Access-Control-Allow-Origin", o)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _blocked(self):
        o = self.headers.get("Origin")
        if o is not None and not is_local_origin(o):
            self._json({"err": "origin không được phép"}, 403)
            return True
        return False

    def do_OPTIONS(self):
        if self._blocked():
            return
        self.send_response(204); self._cors(); self.end_headers()

    def do_GET(self):
        if self._blocked():
            return
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/health":
            self._json({"ok": True, "sessionId": acp.session_id})
        elif path == "/api/poll":
            qs = urllib.parse.urlparse(self.path).query
            try:
                since = int(urllib.parse.parse_qs(qs).get("since", ["0"])[0])
            except ValueError:
                since = 0
            with store_lock:
                total = event_base + len(event_store)
                # reset: cursor của client trỏ ngoài vùng event còn giữ —
                # thường là bridge vừa restart → replay toàn bộ cho client dựng lại
                reset = since < 0 or since < event_base or since > total
                evs = list(event_store) if reset else list(event_store[since - event_base:])
            self._json({"events": evs, "next": total, "reset": reset})
        elif path == "/api/permissions":
            self._json(load_json(PERM_FP, {"folders": []}))
        elif path == "/api/connections":
            self._json(load_json(CONN_FP, {"apps": []}))
        elif path == "/api/config":
            self._json(load_json(CONFIG_FP, {}))
        else:
            self._json({"err": "not found"}, 404)

    def do_POST(self):
        if self._blocked():
            return
        path = urllib.parse.urlparse(self.path).path
        try:
            cl = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            cl = 0
        if cl > 1_000_000:
            self._json({"err": "body quá lớn"}, 413); return
        body = self.rfile.read(cl)
        try:
            data = json.loads(body or b"{}")
        except json.JSONDecodeError:
            data = {}
        if path == "/api/prompt":
            if acp.dead:
                self._json({"err": "trợ lý đã dừng — chạy lại file start"}, 503); return
            if not acp.session_id:
                self._json({"err": "chưa có session"}, 503); return
            try:
                acp.call("session/prompt", {
                    "sessionId": acp.session_id,
                    "prompt": [{"type": "text", "text": data.get("text", "")}]})
            except (BrokenPipeError, OSError):
                self._json({"err": "trợ lý đã dừng — chạy lại file start"}, 503); return
            self._json({"ok": True})
        elif path == "/api/respond":
            if data.get("optionId") == "__cancel__":
                # học viên từ chối / card không có nút nào → báo cancel cho agent
                acp.send({"jsonrpc": "2.0", "id": data.get("id"),
                          "error": {"code": -32800, "message": "học viên không đồng ý"}})
            else:
                acp.send({"jsonrpc": "2.0", "id": data.get("id"),
                          "result": {"outcome": {"outcome": "selected",
                                                 "optionId": data.get("optionId")}}})
            self._json({"ok": True})
        elif path == "/api/delete-lesson":
            folder = str(data.get("folder", ""))
            if not re.fullmatch(r"[a-zA-Z0-9_-]+", folder):
                self._json({"err": "tên folder lạ"}, 400); return
            course = os.path.realpath(os.path.join(os.path.abspath(CWD), "my-course"))
            target = os.path.realpath(os.path.join(course, folder))
            if not target.startswith(course + os.sep) or not os.path.isdir(target):
                self._json({"err": "không thấy folder bài"}, 404); return
            shutil.rmtree(target)
            mf = os.path.join(course, "manifest.json")
            try:
                m = json.load(open(mf, encoding="utf-8"))
                m["lessons"] = [b for b in m.get("lessons", [])
                                if b.get("folder") != folder]
                json.dump(m, open(mf, "w", encoding="utf-8"),
                          ensure_ascii=False, indent=2)
            except Exception:
                pass
            self._json({"ok": True})
        elif path == "/api/permissions":
            # Học viên (hoặc trợ lý) thêm folder được phép đọc/ghi
            p = os.path.expanduser(str(data.get("path", "")).strip())
            access = str(data.get("access", "read"))
            if access not in ("read", "read-write"):
                self._json({"err": "access phải là read hoặc read-write"}, 400); return
            if not os.path.isdir(p):
                self._json({"err": "không thấy folder này trên máy"}, 404); return
            q = load_json(PERM_FP, {"folders": []})
            # so sánh sau expanduser — entry cũ ghi "~/Downloads" vẫn khớp được
            q["folders"] = [f for f in q["folders"]
                            if os.path.expanduser(str(f.get("path", ""))) != p]
            q["folders"].append({"path": p, "access": access,
                                 "note": str(data.get("note", ""))[:120]})
            save_json(PERM_FP, q)
            self._json({"ok": True})
        elif path == "/api/remove-permission":
            p = os.path.expanduser(str(data.get("path", "")).strip())
            q = load_json(PERM_FP, {"folders": []})
            q["folders"] = [f for f in q["folders"]
                            if os.path.expanduser(str(f.get("path", ""))) != p]
            save_json(PERM_FP, q)
            self._json({"ok": True})
        elif path == "/api/connections":
            # Upsert một app vào registry kết nối — thay tại chỗ để giữ
            # thứ tự hiển thị trong panel Cài đặt
            app = data.get("app")
            if not isinstance(app, dict) or not app.get("id"):
                self._json({"err": "thiếu app.id"}, 400); return
            k = load_json(CONN_FP, {"apps": []})
            for i, a in enumerate(k["apps"]):
                if a.get("id") == app["id"]:
                    k["apps"][i] = app
                    break
            else:
                k["apps"].append(app)
            save_json(CONN_FP, k)
            self._json({"ok": True})
        elif path == "/api/remove-connection":
            aid = str(data.get("id", ""))
            k = load_json(CONN_FP, {"apps": []})
            k["apps"] = [a for a in k["apps"] if a.get("id") != aid]
            save_json(CONN_FP, k)
            self._json({"ok": True})
        elif path == "/api/secrets":
            # Form "Cài" trong panel Cài đặt: học viên dán app password WP /
            # mã OA… → ghi vào .devin/secrets.local.json (đã gitignore).
            # Chỉ GHI — không endpoint nào đọc secret ra ngoài.
            app = str(data.get("app", ""))
            fields = data.get("fields")
            if not re.match(r"^[a-z0-9-]+$", app) or not isinstance(fields, dict):
                self._json({"err": "thiếu app hoặc fields"}, 400); return
            clean = {str(k)[:40]: str(v).strip()[:500]
                     for k, v in list(fields.items())[:10]
                     if isinstance(v, str) and v.strip()}
            if not clean:
                self._json({"err": "chưa nhập gì"}, 400); return
            fp = os.path.join(os.path.abspath(CWD), ".devin", "secrets.local.json")
            creds = load_json(fp, {})
            creds[app] = {**(creds.get(app) or {}), **clean}
            os.makedirs(os.path.dirname(fp), exist_ok=True)
            save_json(fp, creds)
            self._json({"ok": True})
        elif path == "/api/setup":
            # Onboarding lần đầu: ngôn ngữ + tên → config.json + skill pack đúng ngôn ngữ
            lang = str(data.get("language", ""))
            name = str(data.get("learner_name", "")).strip()[:80]
            if lang not in ("vi", "en"):
                self._json({"err": "language phải là vi hoặc en"}, 400); return
            os.makedirs(MC_DIR, exist_ok=True)
            save_json(CONFIG_FP, {"language": lang, "learner_name": name})
            # Đồng bộ tên vào manifest khoá học
            mf = os.path.join(MC_DIR, "manifest.json")
            try:
                m = json.load(open(mf, encoding="utf-8"))
                if name:
                    m["learner_name"] = name
                json.dump(m, open(mf, "w", encoding="utf-8"),
                          ensure_ascii=False, indent=2)
            except Exception:
                pass
            # Cài bộ skill theo ngôn ngữ: pack đè lên .devin/skills/ nhưng
            # skill học viên TỰ TẠO (không có trong pack) phải giữ lại —
            # dir cũ backup sang skills.bak rồi merge phần riêng về.
            pack = os.path.join(SKILL_PACKS, lang)
            if os.path.isdir(pack):
                bak = SKILLS_DIR + ".bak"
                if os.path.isdir(SKILLS_DIR):
                    if os.path.isdir(bak):
                        shutil.rmtree(bak)
                    os.replace(SKILLS_DIR, bak)
                shutil.copytree(pack, SKILLS_DIR)
                if os.path.isdir(bak):
                    for name in os.listdir(bak):
                        src = os.path.join(bak, name)
                        dst = os.path.join(SKILLS_DIR, name)
                        if os.path.isdir(src) and not os.path.exists(dst):
                            shutil.copytree(src, dst)
            self._json({"ok": True})
        elif path == "/api/check-connection":
            aid = str(data.get("id", ""))
            k = load_json(CONN_FP, {"apps": []})
            app = next((a for a in k["apps"] if a.get("id") == aid), None)
            if not app:
                self._json({"err": "không thấy app"}, 404); return
            res = run_probe(app.get("probe"))
            app["status"] = "connected" if res["ok"] else "not-connected"
            app["check_message"] = res["msg"]
            save_json(CONN_FP, k)
            self._json(res)
        else:
            self._json({"err": "not found"}, 404)

    def _json(self, obj, code=200):
        b = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self._cors(); self.end_headers()
        self.wfile.write(b)

if __name__ == "__main__":
    print(f"chat-bridge: http://localhost:{PORT}  (cwd={CWD})")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
