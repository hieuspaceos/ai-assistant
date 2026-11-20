#!/usr/bin/env python3
"""chat-bridge.py — cầu nối giữa chat UI trong portal và "não" AI qua ACP.

Chạy một agent CLI nói chuẩn ACP (Agent Client Protocol, JSON-RPC qua
stdin/stdout) như process con — mặc định `devin acp`, đổi được sang não
khác qua brain.json ở gốc project hoặc POST /api/brain. Nhận prompt từ
browser qua HTTP, đẩy event (text stream, tool call, xin phép) về bằng polling.

Endpoints (mặc định port 7682, chỉ localhost):
  GET  /api/poll?since=N -> {"events": [...], "next": M, "reset": bool}
  POST /api/prompt       -> {"text": "..."} gửi lời nhắn
  POST /api/respond      -> {"id": N, "optionId": "..."} trả lời xin phép
                            ("__cancel__" = học viên từ chối)
  GET  /api/health       -> {"ok": true, "sessionId": ...}
  GET  /api/brain        -> não hiện tại + danh sách preset (kèm đã cài chưa)
  POST /api/brain        -> {"id": <preset>} hoặc {"cmd": "...", "args": [...]}
                            đổi não → ghi brain.json + khởi động lại agent

Event (JSON trong mảng events):
  {"t":"ready","sessionId":...}
  {"t":"text","text":"..."}          - agent đang nói (cộng dồn)
  {"t":"tool","title":"...","status":"in_progress|completed"}
  {"t":"perm","id":N,"title":"...","options":[{optionId,name,kind}]}
  {"t":"done"}                       - agent nói xong một lượt
  {"t":"err","msg":"..."}
"""
import hmac, json, os, re, secrets, shutil, subprocess, sys, threading, time, urllib.parse, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 7682
CWD = sys.argv[2] if len(sys.argv) > 2 else "."
DEVIN = sys.argv[3] if len(sys.argv) > 3 else "devin"   # tên binary khi không có brain.json

BRAIN_FP = os.path.join(os.path.abspath(CWD), "brain.json")

TOKEN_FP = os.path.join(os.path.abspath(CWD), ".devin", "bridge.token")

def load_token():
    # "chìa khoá nhà" dùng chung cho mọi bridge — start script sinh trước;
    # đây chỉ là fallback atomic (O_EXCL: thằng thua race đọc token của
    # thằng thắng, không ghi đè)
    try:
        with open(TOKEN_FP, encoding="utf-8") as f:
            t = f.read().strip()
            if t:
                return t
    except OSError:
        pass
    t = secrets.token_hex(24)
    try:
        os.makedirs(os.path.dirname(TOKEN_FP), exist_ok=True)
        fd = os.open(TOKEN_FP, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.write(fd, t.encode())
        os.close(fd)
        return t
    except FileExistsError:
        # Thua race → thằng thắng đang ghi file, chờ nó xong rồi đọc.
        # File tồn tại mà rỗng (ai đó tạo file trống) → ghi thẳng, file
        # rỗng không chứa gì để mất.
        time.sleep(0.05)
        try:
            with open(TOKEN_FP, encoding="utf-8") as f:
                t2 = f.read().strip()
                if t2:
                    return t2
        except OSError:
            pass
        with open(TOKEN_FP, "w", encoding="utf-8") as f:
            f.write(t)
        return t

BRIDGE_TOKEN = load_token()
os.environ.setdefault("BRIDGE_TOKEN", BRIDGE_TOKEN)  # cho process não kế thừa

def app_version():
    try:
        with open(os.path.join(os.path.abspath(CWD), "VERSION"), encoding="utf-8") as f:
            return f.read().strip() or "0"
    except OSError:
        return "0"

def ext_expected_version():
    # version extension "đúng" = version trong payload đang chạy
    try:
        with open(os.path.join(os.path.abspath(CWD), "extension", "manifest.json"),
                  encoding="utf-8") as f:
            return json.load(f).get("version")
    except (OSError, json.JSONDecodeError):
        return None

# Các "não" biết nói ACP mà onboarding gợi ý. requires = binary phải có
# trên PATH thì preset mới coi là "đã cài" (adapter chạy qua npx nên vẫn
# cần CLI gốc để đăng nhập — vd codex-acp cần `codex`).
BRAIN_PRESETS = [
    {"id": "devin", "label": "Devin",
     "cmd": "devin", "args": ["acp", "--process-model", "in-process"],
     "terminal": "devin", "requires": ["devin"], "cost": "paid",
     "desc": {"vi": "Não mặc định — đi kèm bộ trợ lý này",
              "en": "Default brain — ships with this assistant"},
     "install": {"url": "https://devin.ai",
                 "hint": {"vi": "mở trang Devin, làm theo hướng dẫn cài CLI rồi đăng nhập",
                          "en": "open Devin's site, follow the CLI install guide, then sign in"}}},
    {"id": "gemini", "label": "Gemini CLI (Google)",
     "cmd": "gemini", "args": ["--acp"],
     "terminal": "gemini", "requires": ["gemini"], "cost": "free",
     "desc": {"vi": "Miễn phí với tài khoản Google cá nhân — não gợi ý cho người mới",
              "en": "Free with a personal Google account — suggested brain for new users"},
     "install": {"url": "https://github.com/google-gemini/gemini-cli",
                 "hint": {"vi": "làm theo mục Install trong trang này — cần Node.js",
                          "en": "follow the Install section on this page — needs Node.js"}}},
    {"id": "codex", "label": "Codex CLI (OpenAI)",
     "cmd": "npx", "args": ["-y", "@agentclientprotocol/codex-acp"],
     "terminal": "codex", "requires": ["npx", "codex"], "cost": "paid",
     "desc": {"vi": "Qua adapter codex-acp — cần cài + đăng nhập Codex CLI",
              "en": "Via codex-acp adapter — needs Codex CLI installed and signed in"},
     "install": {"url": "https://github.com/openai/codex",
                 "hint": {"vi": "làm theo mục Install trong trang này rồi đăng nhập tài khoản OpenAI",
                          "en": "follow the Install section, then sign in with your OpenAI account"}}},
    {"id": "claude", "label": "Claude Code (Anthropic)",
     "cmd": "npx", "args": ["-y", "@agentclientprotocol/claude-agent-acp"],
     "terminal": "claude", "requires": ["npx", "claude"], "cost": "paid",
     "desc": {"vi": "Qua adapter claude-agent-acp — cần cài + đăng nhập Claude Code",
              "en": "Via claude-agent-acp adapter — needs Claude Code installed and signed in"},
     "install": {"url": "https://claude.com/claude-code",
                 "hint": {"vi": "mở trang Claude Code, cài theo hướng dẫn rồi đăng nhập",
                          "en": "open the Claude Code page, install per instructions, then sign in"}}},
    {"id": "opencode", "label": "OpenCode",
     "cmd": "opencode", "args": ["acp"],
     "terminal": "opencode", "requires": ["opencode"], "cost": "byok",
     "desc": {"vi": "App miễn phí — cần tự nối model (API key) của bạn",
              "en": "Free app — needs your own model (API key) connected"},
     "install": {"url": "https://opencode.ai",
                 "hint": {"vi": "mở trang OpenCode rồi làm theo hướng dẫn cài",
                          "en": "open the OpenCode site and follow its install guide"}}},
    {"id": "goose", "label": "Goose (Block)",
     "cmd": "goose", "args": ["acp"],
     "terminal": "goose", "requires": ["goose"], "cost": "byok",
     "desc": {"vi": "App miễn phí — cần tự nối model (API key) của bạn",
              "en": "Free app — needs your own model (API key) connected"},
     "install": {"url": "https://block.github.io/goose",
                 "hint": {"vi": "mở trang Goose rồi làm theo hướng dẫn cài",
                          "en": "open the Goose site and follow its install guide"}}},
]

def load_brain():
    """brain.json → dict não đang dùng. id khớp preset thì lấy preset làm
    nền rồi đè field người dùng sửa; thiếu file/cmd → rơi về preset devin
    (tên binary vẫn override được bằng argv[3] như trước)."""
    b = load_json(BRAIN_FP, {})
    if not isinstance(b, dict):
        b = {}
    base = next((dict(p) for p in BRAIN_PRESETS if p["id"] == b.get("id")), {})
    out = {**base, **{k: v for k, v in b.items() if v not in (None, "", [])}}
    if not out.get("cmd"):
        out = {**next(p for p in BRAIN_PRESETS if p["id"] == "devin"), "cmd": DEVIN}
    out.setdefault("args", [])
    out.setdefault("terminal", out["cmd"])
    return out

event_store = []          # các event còn giữ (đầu store có thể đã bị cắt)
event_base = 0            # số event đã cắt khỏi đầu — cursor poll đếm tuyệt đối
MAX_EVENTS = 3000
store_lock = threading.Lock()

# Lịch sử chat persist: mỗi dòng một event JSON — restart bridge (tắt máy,
# đổi não) replay lại để portal không mất ngữ cảnh. .logs/ chỉ launcher tạo
# — chạy trực tiếp (start.sh) thì chưa chắc có, phải tự makedirs nếu không
# history âm thầm không bao giờ ghi trên máy cài mới.
HIST_FP = os.path.join(os.path.abspath(CWD), ".logs", "chat-history.jsonl")
HIST_MAX_BYTES = 2 * 1024 * 1024
os.makedirs(os.path.dirname(HIST_FP), exist_ok=True)
_hist_permed = False

def hist_write(ev):
    global _hist_permed
    try:
        with open(HIST_FP, "a", encoding="utf-8") as f:
            f.write(json.dumps(ev, ensure_ascii=False) + "\n")
        if not _hist_permed:      # history chứa nội dung chat — chỉ chủ đọc
            try: os.chmod(HIST_FP, 0o600)
            except OSError: pass
            _hist_permed = True
    except OSError:
        pass

def rotate_history():
    # file > 2MB → giữ MAX_EVENTS dòng cuối, không để phình mãi trên máy
    try:
        if os.path.getsize(HIST_FP) <= HIST_MAX_BYTES:
            return
        with open(HIST_FP, encoding="utf-8-sig") as f:
            lines = f.readlines()[-MAX_EVENTS:]
        with open(HIST_FP, "w", encoding="utf-8") as f:
            f.writelines(lines)
    except OSError:
        pass

def replay_history():
    global event_base
    try:
        with open(HIST_FP, encoding="utf-8-sig") as f:
            for line in f:
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if ev.get("t") == "perm":
                    continue        # card xin phép là transient — bỏ
                with store_lock:
                    event_store.append(ev)
    except OSError:
        return
    with store_lock:
        excess = len(event_store) - MAX_EVENTS
        if excess > 0:
            del event_store[:excess]
            event_base += excess

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
    hist_write(ev)          # ghi ngoài lock — IO chậm không chặn stream

class Acp:
    def __init__(self, brain):
        self.next_id = 10
        self.session_id = None
        self.dead = False
        self.lock = threading.Lock()
        self.proc = None
        self.brain_id = brain.get("id", brain["cmd"])
        try:
            self.proc = subprocess.Popen(
                [brain["cmd"]] + [str(a) for a in brain.get("args") or []],
                cwd=CWD, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, text=True, bufsize=1)
        except OSError:
            # binary não chưa cài → báo UI, bridge vẫn sống để học viên đổi não
            self.dead = True
            broadcast({"t": "err",
                       "msg": "không chạy được '" + brain["cmd"] +
                              "' — não trợ lý chưa cài. Vào mục Cài đặt đổi sang não khác."})
            return
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
            try:
                self._dispatch(m)
            except Exception:
                # send vào não đã chết (BrokenPipe) hoặc lỗi dispatch lạ —
                # không được để reader chết, nếu không dead không bao giờ
                # được set và self-heal ở /api/prompt không chạy
                continue
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

acp = None   # spawn_brain() gần cuối file gán instance thật (load_json
             # cần được định nghĩa trước khi load_brain chạy)

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
                "http://127.0.0.1:7684/api/browser",
                data=json.dumps({"action": "tabs"}).encode(),
                headers={"Content-Type": "application/json",
                         "X-Bridge-Token": BRIDGE_TOKEN})
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
        self.send_header("Access-Control-Allow-Headers",
                         "Content-Type, X-Bridge-Token")

    def _authed(self):
        # Mọi API ngoại trừ /api/health phải trình "chìa khoá nhà": header
        # X-Bridge-Token (fetch/curl) hoặc ?token= (WS, iframe, lệnh 1 dòng).
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        tok = self.headers.get("X-Bridge-Token") or (q.get("token") or [""])[0]
        # so trên bytes: token lạ có ký tự non-ASCII thì compare_digest(str)
        # raise TypeError → thread chết thay vì trả 401 gọn
        return hmac.compare_digest(
            (tok or "").encode("utf-8", "replace"), BRIDGE_TOKEN.encode())

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
        if path != "/api/health" and not self._authed():
            return self._json({"err": "thiếu hoặc sai mã kết nối"}, 401)
        if path == "/api/health":
            self._json({"ok": True, "sessionId": acp.session_id if acp else None,
                        "brain": getattr(acp, "brain_id", None) or load_brain().get("id"),
                        "version": app_version(),
                        "extVersion": ext_expected_version()})
        elif path == "/api/brain":
            cur = load_brain()
            presets = []
            for p in BRAIN_PRESETS:
                presets.append({
                    "id": p["id"], "label": p["label"],
                    "cost": p.get("cost", "paid"),
                    "desc": p.get("desc", {}),
                    "install": p.get("install"),
                    "cmd_display": " ".join([p["cmd"]] + p["args"]),
                    "installed": all(shutil.which(r)
                                     for r in p.get("requires", [p["cmd"]])),
                })
            self._json({"current": {k: cur.get(k)
                                    for k in ("id", "label", "cmd", "args", "terminal")},
                        "presets": presets})
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
        if not self._authed():
            return self._json({"err": "thiếu hoặc sai mã kết nối"}, 401)
        try:
            cl = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            cl = 0
        # save-page cần limit lớn hơn — file clone nhúng ảnh base64 dễ qua 1MB
        cap = 8_000_000 if path == "/api/save-page" else 1_000_000
        if cl > cap:
            self._json({"err": "body quá lớn"}, 413); return
        body = self.rfile.read(cl)
        try:
            data = json.loads(body or b"{}")
        except json.JSONDecodeError:
            data = {}
        if path == "/api/prompt":
            if acp is None or acp.dead:
                # não chết (process rớt hoặc chưa cài) → thử bật lại một lần,
                # học viên không phải tự chạy lại file start
                spawn_brain()
                self._json({"err": "đang khởi động lại trợ lý — gửi lại sau vài giây"}, 503); return
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
                payload = {"jsonrpc": "2.0", "id": data.get("id"),
                           "error": {"code": -32800, "message": "học viên không đồng ý"}}
            else:
                payload = {"jsonrpc": "2.0", "id": data.get("id"),
                           "result": {"outcome": {"outcome": "selected",
                                                  "optionId": data.get("optionId")}}}
            try:
                if acp and not acp.dead:
                    acp.send(payload)
            except (BrokenPipeError, OSError):
                pass
            self._json({"ok": True})
        elif path == "/api/brain":
            # Đổi não: {"id": <preset>} hoặc lệnh tự nhập {"cmd","args","terminal"}.
            # cmd chỉ cho phép tên lệnh trần (không path) — trang local bị
            # nhiễm vẫn không trỏ được vào script lạ trên máy.
            bid = str(data.get("id", "")).strip()
            preset = next((p for p in BRAIN_PRESETS if p["id"] == bid), None)
            if preset:
                b = {"id": preset["id"], "label": preset["label"],
                     "cmd": preset["cmd"], "args": list(preset["args"]),
                     "terminal": preset["terminal"]}
                requires = preset.get("requires", [preset["cmd"]])
            else:
                cmd = str(data.get("cmd", "")).strip()
                if not re.fullmatch(r"[A-Za-z0-9_.-]+", cmd or ""):
                    self._json({"err": "lệnh não không hợp lệ — chỉ nhận tên lệnh"}, 400); return
                args = data.get("args")
                args = [str(a)[:200] for a in args[:20]] if isinstance(args, list) else []
                b = {"id": bid or "custom",
                     "label": str(data.get("label", cmd))[:60],
                     "cmd": cmd, "args": args,
                     "terminal": str(data.get("terminal", cmd))[:60]}
                requires = [cmd]
            missing = [r for r in requires if not shutil.which(r)]
            if missing:
                self._json({"err": "chưa cài trên máy: " + ", ".join(missing),
                            "missing": missing}, 404); return
            save_json(BRAIN_FP, b)
            spawn_brain()
            self._json({"ok": True, "brain": b})
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
        elif path == "/api/save-page":
            # clone-view.html lưu bản đã chỉnh — chỉ cho ghi file .html
            # trong my-course/, chặn path ra ngoài
            rel = str(data.get("file", "")).strip().lstrip("/")
            html = str(data.get("html", ""))
            course = os.path.realpath(os.path.join(os.path.abspath(CWD), "my-course"))
            target = os.path.realpath(os.path.join(os.path.abspath(CWD), rel))
            if not rel.startswith("my-course/") or ".." in rel or \
               not target.startswith(course + os.sep) or \
               not re.search(r"\.html?$", target, re.I):
                self._json({"err": "chỉ lưu file .html trong my-course/"}, 400); return
            if not html:
                self._json({"err": "trang trống"}, 400); return
            os.makedirs(os.path.dirname(target), exist_ok=True)
            # backup bản trước khi ghi đè — học viên sửa hỏng còn về được
            if os.path.exists(target):
                try:
                    shutil.copy2(target, target + ".bak")
                except OSError:
                    pass
            with open(target, "w", encoding="utf-8") as f:
                f.write(html)
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
            try:
                # credential của học viên — quyền như bridge.token
                os.chmod(fp, 0o600)
            except OSError:
                pass                     # Windows không có chmod — bỏ qua
            self._json({"ok": True})
        elif path == "/api/setup":
            # Onboarding lần đầu: ngôn ngữ + tên → config.json + skill pack đúng ngôn ngữ
            lang = str(data.get("language", ""))
            name = str(data.get("learner_name", "")).strip()[:80]
            if lang not in ("vi", "en"):
                self._json({"err": "language phải là vi hoặc en"}, 400); return
            os.makedirs(MC_DIR, exist_ok=True)
            save_json(CONFIG_FP, {"language": lang, "learner_name": name})
            # Đồng bộ tên + recipes (công thức nhanh) vào manifest khoá học —
            # recipes đi kèm pack ngôn ngữ nên sidebar đúng lệnh, đúng tiếng
            mf = os.path.join(MC_DIR, "manifest.json")
            try:
                m = json.load(open(mf, encoding="utf-8"))
                if name:
                    m["learner_name"] = name
                rec = load_json(os.path.join(SKILL_PACKS, "recipes",
                                             lang + ".json"), {})
                if rec.get("recipes"):
                    m["recipes"] = rec["recipes"]
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

def spawn_brain():
    """Bật (hoặc đổi) não: giết agent cũ nếu còn sống, spawn theo brain.json
    rồi bắt tay ACP chuẩn (initialize + session/new)."""
    global acp
    old = acp
    acp = Acp(load_brain())
    if old and old.proc:
        try:
            old.proc.terminate()
        except Exception:
            pass
    if not acp.dead:
        acp.call("initialize", {
            "protocolVersion": 1,
            "clientCapabilities": {"fs": {"readTextFile": False,
                                          "writeTextFile": False},
                                   "terminal": False}})
        acp.call("session/new", {"cwd": CWD, "mcpServers": []})

if __name__ == "__main__":
    rotate_history()
    replay_history()
    spawn_brain()
    print(f"chat-bridge: http://localhost:{PORT}  (cwd={CWD})")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
