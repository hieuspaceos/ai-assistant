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
  GET  /api/health       -> {"ok": true, "brain": ..., "version": ...}
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
import hmac, json, os, platform, re, runpy, secrets, shutil, subprocess, sys, tempfile, threading, time, unicodedata, urllib.parse, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from content_guard import (scrub_env, load_env_extra, load_allowlist,
                           exec_allowed)   # noqa: E402
from path_guard import path_sensitive, rw_grant_ok   # noqa: E402
from cmd_deny import brain_cmd_denied as _brain_cmd_denied   # noqa: E402

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 7682
CWD = sys.argv[2] if len(sys.argv) > 2 else "."
# Fail-closed: chỉ bind loopback. Bind ra mạng (relay/remote) phải khai
# TROLY_ALLOW_REMOTE=1 tường minh — mọi giả định auth/Origin hiện tại đều
# dựa trên "chỉ máy local truy cập được".
BIND = os.environ.get("TROLY_BIND") or "127.0.0.1"
if BIND not in ("127.0.0.1", "localhost", "::1") \
        and os.environ.get("TROLY_ALLOW_REMOTE") != "1":
    raise SystemExit("TROLY_BIND không phải loopback — đặt "
                     "TROLY_ALLOW_REMOTE=1 nếu thật sự muốn mở ra mạng")
DEVIN = sys.argv[3] if len(sys.argv) > 3 else "devin"   # tên binary khi không có brain.json

BRAIN_FP = os.path.join(os.path.abspath(CWD), "brain.json")

TOKEN_FP = os.path.join(os.path.abspath(CWD), ".devin", "bridge.token")

# install-brain.py cài "lén" vào DATA/node (node portable → gemini) và
# installer của Devin hay đặt ~/.local/bin — prepend PATH để which()/
# preset detection/spawn thấy não vừa cài mà không cần học viên chỉnh
# PATH tay. Gọi lại mỗi khi check não: node dir SINH RA sau khi bridge
# đã boot (vừa cài xong) nên augment một lần lúc import là không đủ.
def _augment_brain_path():
    for _d in (os.path.join(os.path.abspath(CWD), "node", "bin"),
               os.path.join(os.path.abspath(CWD), "node"),
               os.path.expanduser("~/.local/bin")):
        if os.path.isdir(_d) and \
                _d not in os.environ.get("PATH", "").split(os.pathsep):
            os.environ["PATH"] = _d + os.pathsep \
                + os.environ.get("PATH", "")
_augment_brain_path()

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
     "auto": True,
     "desc": {"vi": "Não mặc định — đi kèm bộ trợ lý này",
              "en": "Default brain — ships with this assistant"},
     "install": {"url": "https://devin.ai",
                 "hint": {"vi": "mở trang Devin, làm theo hướng dẫn cài CLI rồi đăng nhập",
                          "en": "open Devin's site, follow the CLI install guide, then sign in"}}},
    {"id": "gemini", "label": "Gemini CLI (Google)",
     "cmd": "gemini", "args": ["--acp"],
     "terminal": "gemini", "requires": ["gemini"], "cost": "free",
     "auto": True,
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

# Interpreter/exec-helper deny-list — trích sang cmd_deny.py dùng chung
# với apply-pack lint + content_guard.exec_allowed (audit-5 F9: nhân
# bản list = drift, drift ở đây là kênh code-exec).

def load_brain():
    """brain.json → dict não đang dùng. id khớp preset thì lấy preset làm
    nền rồi đè field người dùng sửa; thiếu file/cmd → rơi về preset devin
    (tên binary vẫn override được bằng argv[3] như trước)."""
    b = load_json(BRAIN_FP, {})
    if not isinstance(b, dict):
        b = {}
    base = next((dict(p) for p in BRAIN_PRESETS if p["id"] == b.get("id")), {})
    out = {**base, **{k: v for k, v in b.items() if v not in (None, "", [])}}
    # cmd/terminal phải là tên lệnh trần — brain.json bị sửa tay (đường
    # dẫn/lệnh lạ) không được spawn; rơi về preset devin. cmd do FILE tự
    # khai nằm trong deny-list cũng rơi về devin (kiểm trên b thô — cmd từ
    # preset như npx của codex/claude là hợp lệ, không được chặn)
    if not out.get("cmd") or \
            not re.fullmatch(r"[A-Za-z0-9_.-]+", str(out["cmd"])) or \
            _brain_cmd_denied(str(b.get("cmd") or "").lower()):
        out = {**next(p for p in BRAIN_PRESETS if p["id"] == "devin"),
               "cmd": DEVIN}
    out.setdefault("args", [])
    # terminal cũng qua deny-list (check trên b thô của FILE): brain.json
    # sửa tay terminal:"sh" → term-gate exec shell trần trong ttyd cho ai
    # có mã kết nối. Terminal preset (devin/gemini/…) không nằm trong list.
    term = str(out.get("terminal") or "")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", term) or \
            _brain_cmd_denied(str(b.get("terminal") or "").lower()):
        term = ""
    out["terminal"] = term or base.get("terminal") or out["cmd"]
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
_hist_f = None                # fd giữ mở — open/close mỗi event là hàng
_hist_writes = 0              # trăm syscall khi stream text
_hist_flush_at = 0.0          # nhịp flush — text stream ra hàng trăm event
_hist_lock = threading.Lock() # ghi/flush xen kẽ giữa threads → dòng jsonl rách
HIST_ROTATE_EVERY = 500       # check rotate định kỳ, không chỉ lúc boot
LOG_MAX_BYTES = 1024 * 1024   # mỗi .logs/*.log giữ tối đa 1MB

def hist_write(ev):
    global _hist_permed, _hist_f, _hist_writes, _hist_flush_at
    if ev.get("t") == "perm":
        return          # card xin phép là transient — không ghi vào file
    # serialize ghi: hai thread (reader não + handler API) viết cùng lúc
    # xen kẽ → dòng jsonl rách; replay bỏ qua dòng lỗi nhưng mất event
    with _hist_lock:
        try:
            if _hist_f is None:
                _hist_f = open(HIST_FP, "a", encoding="utf-8")
            _hist_f.write(json.dumps(ev, ensure_ascii=False) + "\n")
            # flush theo nhịp: event "text" trôi hàng trăm cái một lượt — flush
            # mỗi cái là hàng trăm syscall. Event khác flush ngay; text gom lại
            # 1s một lần — crash xấu nhất mất <1s chữ đang stream.
            now = time.monotonic()
            if ev.get("t") != "text" or now - _hist_flush_at > 1:
                _hist_f.flush()
                _hist_flush_at = now
            if not _hist_permed:  # history chứa nội dung chat — chỉ chủ đọc
                try: os.chmod(HIST_FP, 0o600)
                except OSError: pass
                _hist_permed = True
            _hist_writes += 1
            if _hist_writes % HIST_ROTATE_EVERY == 0:
                _hist_f.close(); _hist_f = None
                rotate_history()
                rotate_logs()
        except OSError:
            try:
                if _hist_f: _hist_f.close()
            except OSError:
                pass
            _hist_f = None        # fd hỏng → event sau mở lại

def rotate_logs():
    """Log stdout các bridge (.logs/*.log) phình mãi theo ngày — quá 1MB
    cắt về tail 256KB. Boot + sau mỗi 500 history write."""
    try:
        for name in os.listdir(os.path.dirname(HIST_FP)):
            if not name.endswith(".log"):
                continue
            fp = os.path.join(os.path.dirname(HIST_FP), name)
            try:
                if os.path.getsize(fp) <= LOG_MAX_BYTES:
                    continue
                with open(fp, "rb") as f:
                    f.seek(-262144, os.SEEK_END)
                    tail = f.read()
                with open(fp, "wb") as f:
                    f.write(tail)
            except OSError:
                pass
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

# Card xin phép chỉ được trả lời khi đang pending — /api/respond trước
# đây nhận id/optionId tuỳ ý → ai có token cũng tự duyệt thay học viên.
perm_pending = {}         # id -> {"options": set(optionId), "ts": epoch}
PERM_TTL = 600            # perm treo >10 phút coi như chết
PERM_MAX = 200            # trần chống phình
NATIVE_MAX = 2            # trần hộp thoại native mở đồng thời — spam
                        # gated endpoint từng spawn một osascript/request
                        # = mưa dialog chồng màn hình (UX-DoS). Đạt trần
                        # thì TỪ CHỐI, không downgrade card.

# Consent gate: write đặc quyền (đổi quyền folder, xoá bài, đổi não tự
# nhập) đi qua card do CHÍNH bridge phát — không qua ACP. API không phân
# biệt được "học viên bấm portal" vs "agent tự gọi" (cùng có token) nên
# mọi thay đổi phải hiện card trong chat để người duyệt. RESIDUAL thành
# thật: agent cũng gọi được /api/respond → card chỉ chặn im lặng + bắt
# phải nghi thức đủ bước, không chặn tuyệt đối kẻ cố ý. Respond cho card
# nội bộ bắt buộc Origin trình duyệt — thêm một vòng nữa.
local_pending = {}        # "local-<hex>" -> {"apply","ts","ev","native","proc"}
_pick_folder_lock = threading.Lock()   # hộp chọn folder — một cái một lúc

# Proof-of-human cho consent gate (macOS): nút "Đồng ý" thật sự nằm trong
# hộp thoại native do BRIDGE spawn — agent trong Seatbelt không exec được
# osascript và không điều khiển GUI → không giả/bấm được (Origin + token
# trên /api/respond chỉ là vòng thủ, không phải bằng chứng người bấm).
# TROLY_NO_NATIVE_GATE=1 hoặc không có GUI → fallback đường Origin cũ.
NATIVE_GATE = (sys.platform == "darwin"
               and shutil.which("osascript") is not None
               and os.environ.get("TROLY_NO_NATIVE_GATE") != "1")

def _asq(s):
    """AppleScript string literal — escape \\ và " để title không phá
    script. Kẹp độ dài vì dialog nhỏ."""
    return '"' + str(s)[:400].replace('\\', '\\\\').replace('"', '\\"') + '"'

def _pick_allow(opts):
    """Ưu tiên allow_once — một cú bấm "Đồng ý" trên dialog không được
    trở thành quyền vĩnh viễn: não xếp ["allow_always","allow_once"] mà
    pick allow* đầu tiên thì học viên duyệt always trong khi nghĩ "lần
    này" (audit-3 M1). Không có once thì allow* bất kỳ, cuối cùng mới
    opts[0] (giữ hành vi cũ). Bẫy: phải lọc allow* TRƯỚC rồi mới tìm
    "once" — tìm "once" toàn cục thì não xếp reject_once lên đầu là pick
    nhầm option TỪ CHỐI gửi cho não."""
    kind = lambda o: str(o.get("kind", "")).lower()
    allows = [o for o in opts if kind(o).startswith("allow")]
    return (next((o for o in allows if "once" in kind(o)), None)
            or (allows or opts or [{}])[0]).get("optionId")

def _allow_match(tc, title):
    """Exec allowlist: trích candidates từ toolCall (title + các field
    text thường mang lệnh trong rawInput) rồi glob-match với patterns
    trong .devin/exec-allowlist.json. Trả pattern khớp hoặc None.
    Đọc file mỗi lần — pack/admin đổi list có tác dụng ngay, không cần
    restart bridge."""
    pats = load_allowlist(os.path.join(os.path.abspath(CWD), ".devin"))
    if not pats:
        return None
    # Candidates: field LỆNH thật (cmd/command trong rawInput) được ưu
    # tiên — text/input có thể chứa đoạn văn bất kỳ, não đặt chuỗi hiền
    # ("ls *") vào đó mà toolCall thật làm việc khác thì auto-duyệt bừa.
    # Không có field lệnh mới dùng title (vẫn do não tự mô tả — tin bằng
    # "lời khai" của não, không tin hơn được).
    raw = tc.get("rawInput")
    cands = []
    if isinstance(raw, dict):
        for k in ("cmd", "command"):
            if isinstance(raw.get(k), str) and raw[k].strip():
                cands.append(raw[k])
    if not cands:
        cands = [title]
    for c in cands:
        m = exec_allowed(c, pats)
        if m is not None:
            return m
    return None

# Hộp thoại native hiện TỪNG CÁI — onboarding phát 4-5 card cùng lúc,
# dialog chồng lên nhau trên màn hình gây rối (F-006). Card được tạo
# ngay (chat vẫn thấy), chỉ phần osascript xếp hàng.
_native_dialog_lock = threading.Lock()

# kind → động từ lời thường cho card xin phép/nhãn tool (F-008/F-010)
_PERM_KIND = {
    "read": "đọc dữ liệu", "edit": "sửa file", "delete": "xoá file",
    "move": "di chuyển file", "search": "tìm trong máy",
    "execute": "chạy một lệnh trên máy", "fetch": "mở một trang web",
    "think": "suy nghĩ", "other": "làm một việc",
}
_PERM_GENERIC = {"", "trợ lý muốn làm một việc", "đang làm việc",
                 "việc nhỏ", "working", "do something", "work"}

def _title_detail(tc):
    """Trích file/lệnh đích của toolCall thành đuôi mô tả ngắn."""
    locs = tc.get("locations")
    if isinstance(locs, list):
        names = []
        for l in locs[:2]:
            if isinstance(l, dict):
                n = os.path.basename(
                    str(l.get("path") or "").rstrip("/\\"))
                if n:
                    names.append(n)
        if names:
            return " " + ", ".join(names)
    raw = tc.get("rawInput")
    if isinstance(raw, dict):
        for k in ("cmd", "command", "path", "filePath", "file_path",
                  "url", "query"):
            v = raw.get(k)
            if isinstance(v, str) and v.strip():
                return ": " + " ".join(v.split())[:100]
    return ""

def _perm_title(tc):
    """Tiêu đề card/hộp thoại Lan đọc hiểu: title của não nếu nó nói rõ
    việc; thiếu hoặc chung chung ("làm một việc") thì tự tả từ kind +
    file/lệnh đích — duyệt mù là không được."""
    t = str(tc.get("title") or "").strip()
    if t and t.lower() not in _PERM_GENERIC:
        return t[:200]
    verb = _PERM_KIND.get(str(tc.get("kind") or "").lower(),
                          "làm một việc")
    return ("Trợ lý muốn " + verb + _title_detail(tc))[:200]

def _tool_title(u):
    """Nhãn tool trong chat: bản dịch mềm của title não gửi — "Ran `x`"
    → "Chạy: x" (mất đuôi version rối mắt); title trống/chung chung thì
    tả từ kind thay vì "việc nhỏ"."""
    t = str(u.get("title") or "").strip()
    m = re.match(r"^(?:ran|run)\s+`?(.+?)`?\s*$", t, re.I)
    if m:
        cmd = " ".join(m.group(1).split())
        # "python3.12 -c …" → "python" — tên lệnh đủ rồi, đuôi version
        # và tham số dài là nhiễu với người không biết code
        first = cmd.split(" ", 1)[0]
        t = "Chạy: " + (re.sub(r"[\d.]*$", "", os.path.basename(first))
                        or first)
    if not t or t.lower() in _PERM_GENERIC:
        verb = _PERM_KIND.get(str(u.get("kind") or "").lower(),
                              "làm một việc")
        t = verb[0].upper() + verb[1:]
    return t[:200]

def _kill_proc(rec):
    """Giết osascript của card khi card bị huỷ/evict/clear — không kill
    thì hộp thoại mồ côi treo trên màn hình tới hết TTL 10'."""
    p = (rec or {}).get("proc")
    if p is not None:
        try:
            p.terminate()
        except Exception:
            pass

def _native_pending():
    """Số card đang chờ quyết định qua hộp thoại native — đếm qua CẢ HAI
    local_pending (card bridge) và perm_pending (card ACP): một hộp thoại
    mỗi rec, kẻo đếm một bên vẫn flood được bằng bên kia."""
    return sum(1 for r in list(local_pending.values())
                        + list(perm_pending.values())
               if r.get("native"))

def gate_local(title, apply_fn):
    """Tạo card xác nhận → trả pending id cho caller trả 202, hoặc None
    khi đạt NATIVE_MAX (caller trả 409). Khi học viên bấm Đồng ý ở
    /api/respond → apply_fn() mới chạy (one-shot + TTL y card xin phép
    của não). Trên macOS, "Đồng ý" chỉ đến từ hộp thoại native
    (_native_confirm) — nút trong chat chỉ còn "Không"."""
    with store_lock:
        if NATIVE_GATE and _native_pending() >= NATIVE_MAX:
            return None          # không tạo card thứ N+1 — reject 409,
                                 # KHÔNG queue/hạ cấp (đường Origin forge
                                 # được, downgrade = kênh attack mới)
        while len(local_pending) >= PERM_MAX:
            _kill_proc(local_pending.pop(next(iter(local_pending)), None))
        rid = "local-" + secrets.token_hex(8)
        ev = {"t": "perm", "id": rid, "title": title,
              "options": [{"optionId": "ok", "name": "Đồng ý"},
                          {"optionId": "__cancel__", "name": "Không"}]}
        rec = {"apply": apply_fn, "ts": time.time(), "ev": ev,
               "native": NATIVE_GATE, "proc": None}
        local_pending[rid] = rec
    broadcast(dict(ev, native=True) if rec["native"] else ev)
    if rec["native"]:
        threading.Thread(target=_native_confirm, args=(rid,), daemon=True).start()
    return rid

def _native_fallback(rid):
    """GUI không chạy được (headless/SSH/osascript lỗi) → hạ về đường
    Origin cũ: phát lại card KHÔNG cờ native để nút Đồng ý trong chat
    dùng được. Kém an toàn hơn dialog nhưng không kẹt học viên."""
    with store_lock:
        rec = local_pending.get(rid)
        if rec is not None:
            rec["native"] = False
    broadcast({"t": "perm_done", "id": rid})
    if rec is not None:
        broadcast(rec["ev"])

def _native_confirm(rid):
    """Chờ hộp thoại macOS — "Đồng ý" ở đây mới là bằng chứng có người
    bấm. Hết hạn/từ chối/cancel qua chat đều đóng card + hủy apply."""
    title = ((local_pending.get(rid) or {}).get("ev") or {}).get("title") or \
            "Trợ lý muốn làm một việc"
    # KHÔNG khai "cancel button": nút cancel khi bấm = error -128 (stdout
    # rỗng) → không phân biệt được "người từ chối" với "dialog hỏng" —
    # trước đây gui_failed → _native_fallback phát lại card không cờ
    # native → agent forge Origin+token tự duyệt NGAY SAU KHI học viên
    # bấm từ chối (audit-3 CAO-1). Bỏ cancel button thì "Không" trả
    # stdout bình thường, Esc cũng không dismiss được — từ chối chỉ còn
    # đường declined, không còn đường xuống fallback.
    script = ("display dialog " + _asq(title) +
              ' with title "Trợ Lý AI — xin phép" with icon note '
              'buttons {"Không", "Đồng ý"} default button "Không" '
              'giving up after ' + str(int(PERM_TTL)))
    with _native_dialog_lock:        # hộp thoại hiện từng cái (F-006)
        with store_lock:
            if rid not in local_pending:
                return               # huỷ khi đang xếp sau dialog khác
        try:
            p = subprocess.Popen(["osascript", "-e", script],
                                 stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                 text=True)
        except Exception:
            p = None
        if p is None:
            return _native_fallback(rid)
        with store_lock:
            rec = local_pending.get(rid)
            if rec is None:          # cancel từ chat trước khi spawn xong
                try:
                    p.terminate()
                except Exception:
                    pass
                return
            rec["proc"] = p
        try:
            out, _ = p.communicate(timeout=PERM_TTL + 60)
            approved = "button returned:Đồng ý" in out
            # "Không" / hết hạn gave-up = quyết định CÓ NGƯỜI → đóng card,
            # KHÔNG fallback (y _perm_native_confirm). Chỉ stdout hoàn toàn
            # rỗng (osascript lỗi/bị terminate từ chat) mới là GUI hỏng.
            declined = "button returned:Không" in out or "gave up:true" in out
            gui_failed = p.returncode != 0 and not approved and not declined
        except Exception:
            approved = False
            gui_failed = True
            try:
                p.kill()
            except Exception:
                pass
    if gui_failed:
        # dialog spawn ĐƯỢC rồi chết giữa chừng (kill/crash —
        # returncode≠0, stdout rỗng) KHÔNG phải "không có GUI" → hạ về
        # đường Origin thì não tự forge duyệt (audit-5 N5). Deny luôn:
        # rơi xuống tail — card đóng, không apply. Chỉ Popen-fail
        # (headless thật, p is None ở trên) mới đi _native_fallback.
        # Warn chỉ khi card CÒN pending: cancel/evict từ chat cũng
        # terminate proc → gui_failed nhưng rec đã pop → không phải
        # hỏng thật. Dùng type "warn" không phải "err" — "err" trong
        # broadcast() kill toàn bộ perm_pending + nhả prompt_lock.
        with store_lock:
            alive = rid in local_pending
        if alive:
            broadcast({"t": "warn", "msg": "hộp thoại xin phép chết "
                       "giữa chừng — coi như từ chối, thử lại nếu cần"})
    with store_lock:
        rec = local_pending.pop(rid, None)
    broadcast({"t": "perm_done", "id": rid})
    if rec is None or not approved:
        return
    try:
        rec["apply"]()
    except Exception as e:
        broadcast({"t": "err", "msg": "làm không được — " + str(e)[:120]})

def _perm_native_fallback(rid):
    """Giống _native_fallback nhưng cho card ACP: GUI hỏng → hạ về đường
    Origin để nút trong chat dùng được (kém an toàn hơn nhưng không kẹt)."""
    with store_lock:
        rec = perm_pending.get(rid)
        if rec is not None:
            rec["native"] = False
    broadcast({"t": "perm_done", "id": rid})
    if rec is not None:
        broadcast({"t": "perm", "id": rid, "title": rec["title"],
                   "options": rec["opts"]})

def _perm_native_confirm(rid):
    """Card xin phép ACP trên macOS. id do CHÍNH não tự khai + nó có sẵn
    BRIDGE_TOKEN → chỉ đòi Origin không đủ (forge được): nút "Đồng ý"
    phải đến từ hộp thoại hệ điều hành. Duyệt thì chọn option allow đầu
    tiên; từ chối/hết hạn → báo cancel cho não y nút "Không" trong chat."""
    title = (perm_pending.get(rid) or {}).get("title") or \
            "Trợ lý muốn làm một việc"
    # KHÔNG khai "cancel button": nút cancel khi bấm = error -128 (stdout
    # rỗng) → không phân biệt được "người từ chối" với "dialog hỏng" —
    # cứ bấm Không là phải báo cancel cho não ngay, không downgrade card
    script = ("display dialog " + _asq(title) +
              ' with title "Trợ Lý AI — xin phép" with icon note '
              'buttons {"Không", "Đồng ý"} default button "Không" '
              'giving up after ' + str(int(PERM_TTL)))
    with _native_dialog_lock:        # hộp thoại hiện từng cái (F-006)
        with store_lock:
            if rid not in perm_pending:
                return               # huỷ khi đang xếp sau dialog khác
        try:
            p = subprocess.Popen(["osascript", "-e", script],
                                 stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                 text=True)
        except Exception:
            p = None
        if p is None:
            return _perm_native_fallback(rid)
        with store_lock:
            rec = perm_pending.get(rid)
            if rec is None:          # cancel từ chat trước khi spawn xong
                try:
                    p.terminate()
                except Exception:
                    pass
                return
            rec["proc"] = p
        try:
            out, _ = p.communicate(timeout=PERM_TTL + 60)
            approved = "button returned:Đồng ý" in out
            # Bấm "Không" / hết hạn gave-up = quyết định CÓ NGƯỜI → báo
            # cancel cho não ngay (agent đang chờ JSON-RPC reply —
            # downgrade card bắt họ bấm "Không" lần nữa trong chat thì
            # não treo thêm vô ích). Chỉ khi KHÔNG có output nào
            # (osascript lỗi/bị terminate từ chat) mới coi là GUI hỏng —
            # trước fallback về card Origin nhưng não forge Origin duyệt
            # được → giờ xử như từ chối (audit-5 N5); chỉ spawn-fail
            # (p is None, headless thật) mới fallback.
            declined = "button returned:Không" in out or "gave up:true" in out
            gui_failed = p.returncode != 0 and not approved and not declined
        except Exception:
            approved = False
            gui_failed = True
            try:
                p.kill()
            except Exception:
                pass
    if gui_failed:
        # Như _native_confirm: deny thay vì _perm_native_fallback —
        # não không được có đường tự duyệt bằng cách giết dialog (N5).
        # "warn" + check pending: không trigger cleanup của "err",
        # không báo khi chính ta cancel/evict card.
        with store_lock:
            alive = rid in perm_pending
        if alive:
            broadcast({"t": "warn", "msg": "hộp thoại xin phép chết "
                       "giữa chừng — coi như từ chối"})
    with store_lock:
        rec = perm_pending.pop(rid, None)
    broadcast({"t": "perm_done", "id": rid})
    if rec is None:
        return
    pick = _pick_allow(rec.get("opts", [])) if approved else None
    if pick is not None:
        payload = {"jsonrpc": "2.0", "id": rid,
                   "result": {"outcome": {"outcome": "selected",
                                          "optionId": pick}}}
    else:
        payload = {"jsonrpc": "2.0", "id": rid,
                   "error": {"code": -32800,
                             "message": "học viên không đồng ý"}}
    try:
        if acp and not acp.dead:
            acp.send(payload)
    except (BrokenPipeError, OSError):
        pass

# long-poll /api/poll: client chờ tới khi có event mới (tối đa wait ms)
# thay vì poll chặt mỗi ~1s — giảm ~97% request và độ trễ hiển thị ~0.
new_event = threading.Condition(store_lock)

# Serialize /api/prompt: 2 tab/2 client gửi đồng thời → event đan xen làm
# rối cả session ACP. acquire không blocking → kẻ đến sau nhận 409.
prompt_lock = threading.Lock()

# Serialize spawn_brain: 2 spawn đồng thời (self-heal ở /api/prompt +
# đổi não ở /api/brain) tạo 2 process ACP — đứa thua race vẫn sống, reader
# thread của nó vẫn broadcast event vào store → stream trộn + process rác.
spawn_lock = threading.Lock()

# Watchdog lượt treo: não sống nhưng không bao giờ trả done/err (API kẹt,
# tool loop vô hạn) → prompt_lock giữ mãi → mọi /api/prompt 409 vĩnh viễn
# và học viên không có nút nào tự gỡ. Mỗi lượt một Timer; turn_gen để
# timer của lượt cũ (vừa hết hạn đúng lúc lượt mới bắt đầu) không giết
# nhầm. TROLY_TURN_TIMEOUT giây — override cho test/debug.
try:
    TURN_TIMEOUT = int(os.environ.get("TROLY_TURN_TIMEOUT") or 1200)
except ValueError:
    TURN_TIMEOUT = 1200
turn_gen = [0]

def _turn_watchdog(gen):
    """Quá TURN_TIMEOUT mà prompt_lock vẫn giữ → não đang treo giữa lượt.
    Báo UI (event err cũng mở lock) rồi giết process — prompt tiếp theo
    đi đường spawn_brain self-heal giống não chết thường."""
    with store_lock:
        # check + đánh dấu chết trong store_lock để atomic với cặp
        # acquire+bump gen ở /api/prompt — kẽo request mới nằm giữa hai
        # bước đó bị watchdog lượt cũ giết nhầm
        if gen != turn_gen[0] or not prompt_lock.locked():
            return
        old = acp
        if old is not None:
            # prompt mới vào spawn_brain ngay, không chờ stdout đóng; reader
            # cũ không báo "dừng đột ngột" trùng với lỗi timeout bên dưới
            old.dead = True
            old.expect_death = True
    broadcast({"t": "err",
               "msg": "trợ lý bị kẹt quá lâu — mình đang khởi động lại não"})
    if old is not None and old.proc:
        try:
            old.proc.terminate()
        except Exception:
            pass

run_id = [0]             # id lượt prompt hiện tại — bump ở /api/prompt;
                         # beacon đếm theo LƯỢT thật, dashboard group được

# F-015: quyền folder chỉ đổi sandbox của não khi spawn LẠI — phiên đang
# chạy giữ profile cũ nên lệnh ghi vẫn bị chặn dù đã cấp (agent phải bảo
# học viên restart app = đứt flow). Apply xong đánh dấu đây; prompt kế
# tiếp respawn não trước khi forward → quyền mới ăn ngay, không cần
# restart. Respawn NGAY khi apply thì giết lượt đang xin quyền — chỉ
# được khi prompt_lock rảnh (lượt trước xong rồi mới đổi quyền).
perm_dirty = [False]

# F-012: lượt kết thúc ngay sau tool failed/denied mà agent không nói
# thêm lời nào → UI dừng ở câu dở ("Mình mở ra đọc nhé:") rồi im — học
# viên chờ vô vọng không biết việc đã chết. Chèn warn ngay trước "done".
_turn_fail = [False, False, -1]   # [saw_fail, text_sau_fail, run_id]

def broadcast(ev):
    ev.setdefault("run_id", run_id[0])
    if ev["run_id"] != _turn_fail[2]:
        _turn_fail[0], _turn_fail[1], _turn_fail[2] = \
            False, False, ev["run_id"]
    t = ev.get("t")
    if t == "tool" and ev.get("status") == "failed":
        _turn_fail[0], _turn_fail[1] = True, False
    elif t == "text" and _turn_fail[0]:
        _turn_fail[1] = True
    elif t == "done" and _turn_fail[0] and not _turn_fail[1]:
        _append({"t": "warn", "run_id": ev["run_id"],
                 "msg": "một bước cần làm không được (chưa được duyệt "
                        "hoặc bị lỗi) — việc chưa xong, bạn nhờ lại nhé"})
    _append(ev)

def _append(ev):
    global event_base
    with store_lock:
        event_store.append(ev)
        if ev.get("t") in ("ready", "done", "err"):
            # lượt mới/kết thúc/lỗi → perm cũ hết hạn; giết luôn dialog
            # native đang mở kẻo mồ côi trên màn hình tới hết TTL
            for _r in perm_pending.values():
                _kill_proc(_r)
            perm_pending.clear()
            if prompt_lock.locked():   # kết lượt (kể cả não chết → err) → mở
                prompt_lock.release()
        excess = len(event_store) - MAX_EVENTS
        if excess > 0:
            del event_store[:excess]
            event_base += excess
        new_event.notify_all()         # đánh thức long-poll đang chờ
    hist_write(ev)          # ghi ngoài lock — IO chậm không chặn stream

def gen_sandbox_profile():
    """Regen .devin/agent.sb từ permissions.json. Nạp gen-sandbox.py qua
    runpy (không subprocess) — chạy được cả trong binary đóng gói không
    có python ngoài. Trả về path profile hoặc None (non-darwin/lỗi)."""
    if sys.platform != "darwin":
        return None
    gen = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "gen-sandbox.py")
    try:
        prof = runpy.run_path(gen)["build_profile"](CWD)
        out = os.path.join(CWD, ".devin", "agent.sb")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            f.write(prof)
        return out
    except Exception:
        return None

def _sandbox_wrap(argv):
    """macOS: bọc não trong Seatbelt — permissions.json thành enforcement
    kernel thay vì văn xuôi nhờ não nghe. TROLY_NO_SANDBOX=1 = escape
    hatch debug (ghi trong runbook), KHÔNG set mặc định."""
    if sys.platform != "darwin" or os.environ.get("TROLY_NO_SANDBOX") == "1":
        return argv
    sb = gen_sandbox_profile()          # regen mỗi spawn → quyền mới cấp
    if not sb or not shutil.which("sandbox-exec"):
        return argv                     # thiếu tool → chạy thường, không kẹt
    return ["/usr/bin/sandbox-exec", "-f", sb] + argv

class Acp:
    def __init__(self, brain):
        self.next_id = 10
        self.session_id = None
        self.dead = False
        self.expect_death = False  # True khi BRIDGE tự giết (watchdog/đổi não)
        self.lock = threading.Lock()
        self._waiters = {}   # mid → Event — call_sync chờ reply theo id
        self._replies = {}   # mid → message trả lời (chỉ id đang chờ)
        self.proc = None
        self.brain_id = brain.get("id", brain["cmd"])
        try:
            # env scrub (content-guard ph-3.5): não + mọi process con của
            # nó trong sandbox thừa hưởng env user — `printenv` trong
            # sandbox đọc được OPENAI_API_KEY/AWS đang set trong shell.
            # Spawn bằng allowlist (content_guard.scrub_env); cty cần
            # truyền thêm biến khai trong .devin/env-allowlist.json.
            benv, dropped = scrub_env(
                windows=(platform.system() == "Windows"),
                extra=load_env_extra(
                    os.path.join(os.path.abspath(CWD), ".devin")))
            if dropped:
                broadcast({"t": "env_scrub", "dropped": dropped})
            self.proc = subprocess.Popen(
                _sandbox_wrap([brain["cmd"]] +
                              [str(a) for a in brain.get("args") or []]),
                cwd=CWD, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, text=True, bufsize=1,
                env=benv)
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

    def call_sync(self, method, params, timeout=30):
        # Gửi rồi CHỜ response của đúng id — handshake ACP bắt buộc tuần
        # tự (initialize xong mới được session/new — não từ chối
        # "Invalid request" nếu session/new đi trước).
        ev = threading.Event()
        with self.lock:
            mid = self.next_id; self.next_id += 1
            self._waiters[mid] = ev
            try:
                self._write({"jsonrpc": "2.0", "id": mid,
                             "method": method, "params": params})
            except Exception:
                self._waiters.pop(mid, None)
                return None
        # chờ từng nhịp ngắn + coi self.dead — não chết trước/sau khi đăng
        # ký waiter thì thoát sớm, không đợi hết timeout
        waited = 0.0
        while waited < timeout:
            if ev.wait(0.2) or self.dead:
                break
            waited += 0.2
        self._waiters.pop(mid, None)
        return self._replies.pop(mid, None)

    def _reader(self):
        # readline(SIZE): kẹp một "dòng" vô hạn — não gây lỗi phát stream
        # không-newline thì RAM không phình; đoạn cắt ra không parse được
        # JSON nên rớt xuống continue như rác thường
        while True:
            line = self.proc.stdout.readline(4 * 1024 * 1024)
            if not line:
                break
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
        # stdout đóng = devin acp chết → báo UI thay vì để chat treo im lặng.
        # expect_death: chính bridge giết (watchdog timeout/đổi não) —
        # đã báo lỗi đúng nghĩa rồi, không thêm "dừng đột ngột" gây hoang.
        self.dead = True
        # não chết → đánh thức mọi call_sync đang chờ reply, khỏi chờ hết
        # timeout (server bind/respawn bị trễ khi não không lên được)
        for ev in list(self._waiters.values()):
            ev.set()
        if not self.expect_death:
            broadcast({"t": "err",
                       "msg": "trợ lý vừa dừng đột ngột — chạy lại file start rồi thử lại"})

    def _dispatch(self, m):
        # Reply của một call_sync đang chờ — ghi trước, vẫn cho các nhánh
        # dưới xử lý tiếp (sessionId, err, done) như thường
        mid = m.get("id")
        if mid in self._waiters and ("result" in m or "error" in m):
            self._replies[mid] = m
            self._waiters[mid].set()
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
            # id do CHÍNH não tự khai — không phải scalar (dict/list không
            # băm được, null vô nghĩa) thì bỏ; báo lỗi để agent khỏi chờ
            if not isinstance(m.get("id"), (int, str)) or m.get("id") is None:
                try:
                    self.send({"jsonrpc": "2.0", "id": m.get("id"),
                               "error": {"code": -32602,
                                         "message": "id không hợp lệ"}})
                except Exception:
                    pass
                return
            p = m.get("params", {})
            tc = p.get("toolCall") or {}
            # kẹp cả số option lẫn độ dài string — não phình list dài/MB
            # text thì lọt thẳng vào event_store + chat-history.jsonl
            opts = [{"optionId": str(o.get("optionId"))[:60],
                     "name": str(o.get("name", o.get("kind", "?")))[:60],
                     "kind": str(o.get("kind", ""))[:40]}
                    for o in p.get("options", [])[:10]
                    if isinstance(o, dict)]
            # tiêu đề Lan đọc hiểu — não khai chung chung thì tự tả từ
            # kind + file/lệnh đích (F-008: duyệt mù "một việc" là không)
            title = _perm_title(tc)
            # exec allowlist (content-guard ph-3): lệnh khớp glob trong
            # .devin/exec-allowlist.json → auto-duyệt, KHÔNG hiện card.
            # Đây là ask=on-miss của GoClaw: giảm consent fatigue khi
            # deploy cty — gate vẫn chặn mọi lệnh NGOÀI list như cũ.
            # Candidates: title + text trong rawInput (cmd/command/input)
            matched = _allow_match(tc, title)
            if matched is not None:
                pick = _pick_allow(opts)
                broadcast({"t": "perm:auto", "title": title,
                           "pattern": matched})
                try:
                    if pick is not None:
                        self.send({"jsonrpc": "2.0", "id": m["id"],
                                   "result": {"outcome": {
                                       "outcome": "selected",
                                       "optionId": pick}}})
                    else:
                        # không có option allow nào (request lạ) — báo
                        # lỗi thay vì bỏ treo agent
                        self.send({"jsonrpc": "2.0", "id": m["id"],
                                   "error": {"code": -32602,
                                             "message": "không có "
                                             "option duyệt"}})
                except Exception:
                    pass
                return
            with store_lock:
                if len(perm_pending) >= PERM_MAX:
                    for _r in perm_pending.values():
                        _kill_proc(_r)
                    perm_pending.clear()
                # Cap dialog native y gate_local — não spam
                # request_permission trước đây cũng được một osascript
                # mỗi card. Đạt trần → báo lỗi JSON-RPC cho não ngay
                # (không đăng ký card, không downgrade — não chọn lại).
                native_full = NATIVE_GATE \
                    and _native_pending() >= NATIVE_MAX
                # id trùng card đang mở = não CỐ Ý che card khác: đọc được
                # id card local qua /api/poll → trùng id thì respond ưu
                # tiên nhánh nào cũng là bẫy (bấm "Đồng ý" cho grant folder
                # mà resolve tool call của não). Từ chối + báo lỗi — agent
                # chân chính chọn id khác.
                dup = (m["id"] in perm_pending or m["id"] in local_pending)
                if not dup and not native_full:
                    perm_pending[m["id"]] = {
                        "options": {o["optionId"] for o in opts},
                        "opts": opts, "title": title,
                        "native": NATIVE_GATE, "proc": None,
                        "ts": time.time()}
            if dup or native_full:
                try:
                    self.send({"jsonrpc": "2.0", "id": m["id"],
                               "error": {"code": -32602,
                                         "message": "id trùng card đang mở"
                                         if dup else
                                         "đang có thẻ xác nhận chờ — duyệt "
                                         "hoặc huỷ trước đã"}})
                except Exception:
                    pass
                return
            # native=True (macOS): nút Đồng ý chỉ ở hộp thoại hệ điều hành —
            # não cầm token + tự khai id nên Origin thuần vẫn forge được
            broadcast({"t": "perm", "id": m["id"], "title": title,
                       "options": opts, "native": NATIVE_GATE})
            if NATIVE_GATE:
                threading.Thread(target=_perm_native_confirm,
                                 args=(m["id"],), daemon=True).start()
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
            broadcast({"t": "tool",
                       "title": _tool_title(u) or "đang làm việc",
                       "status": "in_progress"})
        elif su == "tool_call_update":
            st = u.get("status")
            if st in ("completed", "failed"):
                broadcast({"t": "tool",
                           "title": _tool_title(u),
                           "status": st})
        elif su == "session_info_update":
            pass

acp = None   # spawn_brain() gần cuối file gán instance thật (load_json
             # cần được định nghĩa trước khi load_brain chạy)

# ---------- permissions.json + connections.json (Phase 0) ----------

MC_DIR = os.path.join(os.path.abspath(CWD), "workspace")
PERM_FP = os.path.join(MC_DIR, "permissions.json")
CONN_FP = os.path.join(MC_DIR, "connections.json")
CONFIG_FP = os.path.join(MC_DIR, "config.json")
INSTALL_FP = os.path.join(os.path.abspath(CWD), ".devin",
                         "install-brain.json")
INSTALL_PROC = {"proc": None}   # process install-brain đang chạy (1 cái)
SKILL_PACKS = os.path.join(os.path.abspath(CWD), ".devin", "skill-packs")
SKILLS_DIR = os.path.join(os.path.abspath(CWD), ".devin", "skills")
ROLES_DIR = os.path.join(SKILL_PACKS, "roles")
BOTS_FP = os.path.join(MC_DIR, "bots.json")
BOT_MD_FP = os.path.join(MC_DIR, "bot.md")

def load_json(fp, fallback):
    # utf-8-sig: file ghi bằng PowerShell (Set-Content UTF8) có BOM —
    # utf-8 thường đọc sẽ lỗi và fallback im lặng làm mất dữ liệu
    try:
        return json.load(open(fp, encoding="utf-8-sig"))
    except Exception:
        return fallback

def save_json(fp, obj):
    # ghi ra file tạm rồi đổi tên — crash giữa chừng không corrupt file.
    # mkstemp cho tên tạm DUY NHẤT mỗi call: bản cũ dùng fp+".tmp" cố định
    # nên 2 request ghi cùng file (vd check-connection song song) đè tmp
    # của nhau → os.replace FileNotFoundError (đã thấy trong log) + lost
    # update lẫn nhau.
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(fp) or ".",
                               prefix=os.path.basename(fp) + ".",
                               suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
        os.replace(tmp, fp)
    except Exception:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise

# path_sensitive / rw_grant_ok / _SENSITIVE_* đã move sang
# tools/path_guard.py — policy đường dẫn dùng chung với gen-sandbox
# (enforcement point phải kiểm cùng một list, không nhân bản).

def validate_probe(probe):
    """probe trong connections.json phải khớp schema cố định — client ghi
    probe tuỳ ý (file:// oracle đọc file ngoài sandbox, URL attacker nhận
    creds) bị chặn ở hai đầu: upsert từ chối + run_probe kiểm lại trước
    khi chạy (probe cũ lọt vào file từ trước khi có check)."""
    if not isinstance(probe, dict):
        return False
    t = probe.get("type")
    if t == "http":
        try:
            u = urllib.parse.urlsplit(str(probe.get("url") or ""))
        except Exception:
            return False
        h = u.hostname or ""
        # chỉ probe nội bộ được chỏ URL — http tới host ngoài là kênh exfil
        return u.scheme in ("http", "https") and (
            h in ("localhost", "127.0.0.1", "::1")
            or h.endswith(".localhost"))
    if t == "tabs":
        return isinstance(probe.get("url_contains"), str) \
            and len(probe["url_contains"]) <= 120
    if t == "path":
        # chỉ probe dưới ~ và KHÔNG đụng .devin/ — nếu không thành oracle
        # tồn-tại-file cho secrets.local.json & cả
        p = os.path.abspath(os.path.expanduser(str(probe.get("path") or "")))
        home = os.path.abspath(os.path.expanduser("~"))
        dev = os.path.join(os.path.abspath(CWD), ".devin")
        # path_sensitive: probe tới ~/.ssh, Keychains… = oracle tồn-tại-
        # file cho đúng vùng mà deny-list giữ kín — chặn y như grant
        return p.startswith(home + os.sep) \
            and not (p == dev or p.startswith(dev + os.sep)) \
            and not path_sensitive(p)
    if t == "mcp":
        return isinstance(probe.get("name"), str) and len(probe["name"]) <= 40
    return t in ("wp", "zalo-oa")

def run_probe(probe):
    """Kiểm tra một kết nối còn sống không → {ok, msg}.

    msg là chữ hiện thẳng dưới tên app trong panel Cài đặt của học viên —
    viết bằng lời thường, không thuật ngữ (token/MCP/extension…)."""
    if not probe:
        return {"ok": False, "msg": "chưa cài — cứ nhờ trợ lý trong chat, nó làm giúp"}
    if not validate_probe(probe):
        return {"ok": False, "msg": "kiểu kết nối lạ — nhờ trợ lý xem"}
    try:
        if probe["type"] == "http":
            req = urllib.request.Request(probe["url"])
            # probe tới API của chính 2 bridge thì phải kèm mã kết nối,
            # không là 401 mãi (probe "trinh-duyet" trong seed). NHƯNG chỉ
            # đính cho đúng 2 port đó: validate_probe cho mọi URL loopback
            # → đính bừa là rò token sang server local lạ do agent tự thêm
            # app (upsert không đổi open_url không qua gate). Cùng lý do
            # BRIDGE_PORTS trong bridge-token.js.
            if urllib.parse.urlsplit(probe["url"]).port in (PORT, 7684):
                req.add_header("X-Bridge-Token", BRIDGE_TOKEN)
            with urllib.request.urlopen(req, timeout=4) as r:
                d = json.loads(r.read(1048576))
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
                d = json.loads(r.read(1048576))
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
                    d = json.loads(r.read(1048576))
            except urllib.error.HTTPError as e:
                d = json.loads(e.read(65536) or b"{}")
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
            if not url.startswith("https://"):
                # Basic auth qua http = gửi mật khẩu plaintext — chỉ https
                return {"ok": False, "msg": "địa chỉ site phải bắt đầu bằng https:// — nhờ trợ lý sửa giúp"}
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

# --- Bot (trợ lý theo nghề) -------------------------------------------------
# Bot = tên + avatar + tham chiếu skill + instructions. Skill pool
# .devin/skills/ dùng chung — bot chỉ trỏ tên, không sở hữu, nên đổi/xoá bot
# không mất skill. Template theo nghề nằm trong skill-packs/roles/*.json.

SKILL_NAME_RE = re.compile(r"[a-zA-Z0-9_-]{1,64}")

def slug_id(s):
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.replace("đ", "d").replace("Đ", "D")
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s or "bot"

def role_templates():
    if not os.path.isdir(ROLES_DIR):
        return []
    out = []
    for f in sorted(os.listdir(ROLES_DIR)):
        if f.endswith(".json"):
            t = load_json(os.path.join(ROLES_DIR, f), None)
            if isinstance(t, dict) and t.get("id"):
                out.append(t)
    return out

def _clean_recipes(raw):
    """Chuẩn hoá recipes về đúng schema {command, meaning} + kẹp số
    lượng lẫn độ dài — bot do agent tạo/import có thể nhồi payload hoặc
    phình bots.json/manifest không trần (audit-3 M2). Schema phải khớp
    skill-packs/recipes/*.json và chỗ app.js render c.meaning — ghi sai
    tên field là mất dữ liệu lặng lẽ."""
    if not isinstance(raw, list):
        return []
    return [{"command": str(r.get("command") or "")[:60],
             "meaning": str(r.get("meaning") or "")[:120]}
            for r in raw[:20] if isinstance(r, dict)]

def write_bot_md(bot):
    cfg = load_json(CONFIG_FP, {})
    lang = cfg.get("language") or "vi"
    ins = bot.get("instructions", "")
    if isinstance(ins, dict):
        ins = ins.get(lang) or ins.get("vi") or ""
    os.makedirs(MC_DIR, exist_ok=True)
    with open(BOT_MD_FP, "w", encoding="utf-8") as f:
        f.write(f"# Trợ lý đang làm việc: {bot.get('name','')} "
                f"({bot.get('role','')})\n\n{ins}\n\n"
                "_Mọi luật an toàn trong AGENTS.md đứng trên file này._\n")

def activate_bot(bot):
    """Cài skill còn thiếu + ghi bot.md + gộp recipes vào manifest.
    Trả về list tên skill không cài được (để báo học viên)."""
    cfg = load_json(CONFIG_FP, {})
    lang = cfg.get("language") or "vi"
    smap = load_json(os.path.join(SKILL_PACKS, "skill-map.json"), {})
    missing = []
    os.makedirs(SKILLS_DIR, exist_ok=True)
    for s in bot.get("skills") or []:
        if lang == "en":
            if s not in smap:
                missing.append(s)   # không map được → báo rõ, không cài nhầm
                continue
            name = smap[s]
        else:
            name = s
        # Tên skill đi thẳng vào đường dẫn file — bots.json có thể đến từ
        # file nhập (đầu vào không tin) nên chỉ nhận tên thường: tên chứa
        # "..", "/", "\" coi như không cài được, tuyệt đối không join.
        if not SKILL_NAME_RE.fullmatch(name):
            missing.append(name)
            continue
        dst = os.path.join(SKILLS_DIR, name)
        src = os.path.join(SKILL_PACKS, lang, name)
        if os.path.isdir(dst):
            continue               # skill đang có — không bao giờ đè
        if os.path.isdir(src):
            shutil.copytree(src, dst)
        else:
            missing.append(name)
    write_bot_md(bot)
    # gộp recipes của bot vào manifest — giữ recipes chung, không đè
    mf = os.path.join(MC_DIR, "manifest.json")
    m = load_json(mf, {})
    rec = m.get("recipes") if isinstance(m.get("recipes"), list) else []
    have = {r.get("command") for r in rec if isinstance(r, dict)}
    for r in bot.get("recipes") or []:
        if isinstance(r, dict) and r.get("command") not in have:
            rec.append(r)
    m["recipes"] = rec
    save_json(mf, m)
    return missing

def deactivate_bot():
    try:
        os.remove(BOT_MD_FP)
    except OSError:
        pass

# --- Nhập bot từ file chia sẻ ----------------------------------------------
# Hai bước: /api/bot-import bung zip vào temp + trả preview (học viên ĐỌC
# instructions trước) → /api/bot-import-confirm mới ghi thật. Stage giữ
# trong RAM — bridge restart thì nhập lại từ đầu, không để temp mồ côi.
IMPORT_STAGES = {}   # stage_id -> {"dir": tmp, "bot": {...}, "skills": [...]}

def stage_bot_bundle(b64):
    """Bung zip base64 vào temp → (preview_dict, err). Chỉ nhận
    bot.json / README.txt / skills/<tên>/... — chống zip-slip."""
    import base64, io, zipfile, tempfile
    try:
        raw = base64.b64decode(b64 or "", validate=True)
        zf = zipfile.ZipFile(io.BytesIO(raw))
    except Exception:
        return None, "file không đọc được — có phải file trợ lý (.zip) không?"
    tmp = tempfile.mkdtemp(prefix="troly-bot-")
    skills, bot, total = [], None, 0
    for m in zf.infolist():
        parts = m.filename.replace("\\", "/").split("/")
        if m.is_dir() or ".." in parts or parts[0] in ("", ".", "__MACOSX"):
            continue
        total += m.file_size
        if total > 64 * 1024 * 1024:   # 8MB nén có thể bung ra rất lớn (zip bomb)
            shutil.rmtree(tmp, ignore_errors=True)
            return None, "file bung ra quá lớn — không nhập được"
        rel = "/".join(p for p in parts if p not in ("", "."))
        if rel == "bot.json":
            try:
                bot = json.loads(zf.read(m).decode("utf-8"))
            except Exception:
                shutil.rmtree(tmp, ignore_errors=True)
                return None, "bot.json trong file hỏng — file này không dùng được"
        elif rel == "README.txt" or (parts[0] == "skills" and len(parts) > 1):
            dst = os.path.join(tmp, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, "wb") as f:
                f.write(zf.read(m))
            if parts[0] == "skills" and len(parts) >= 3:
                skills.append(parts[1])   # skills/<dir>/<file> — dir là tên skill
    if not isinstance(bot, dict) or not bot.get("name"):
        shutil.rmtree(tmp, ignore_errors=True)
        return None, "file này thiếu bot.json — không phải file trợ lý"
    # preview không xác nhận thì stage nằm mãi trong RAM + temp — giữ tối đa
    # 10 stage, đuổi cái cũ nhất (kèm dọn temp) khi đầy
    while len(IMPORT_STAGES) >= 10:
        old = IMPORT_STAGES.pop(next(iter(IMPORT_STAGES)))
        shutil.rmtree(old["dir"], ignore_errors=True)
    sid = secrets.token_hex(6)
    IMPORT_STAGES[sid] = {"dir": tmp, "bot": bot, "skills": sorted(set(skills))}
    return {"stage": sid, "name": bot.get("name"), "avatar": bot.get("avatar"),
            "role": bot.get("role"), "instructions": bot.get("instructions"),
            "skills": bot.get("skills") or [], "needs": bot.get("needs") or [],
            "bundled": sorted(set(skills))}, None

def confirm_bot_bundle(sid):
    """Ghi thật: cài skill kèm zip (không đè) + thêm bot vào bots.json.
    KHÔNG tự activate — học viên tự chọn khi sẵn sàng."""
    st = IMPORT_STAGES.pop(sid, None)
    if not st:
        return "hết hạn rồi — nhập lại file nhé"
    try:
        os.makedirs(SKILLS_DIR, exist_ok=True)
        for s in st["skills"]:
            if not SKILL_NAME_RE.fullmatch(s):
                continue            # tên dir lạ trong zip — không chép
            src = os.path.join(st["dir"], "skills", s)
            dst = os.path.join(SKILLS_DIR, s)
            if os.path.isdir(src) and not os.path.exists(dst):
                shutil.copytree(src, dst)
        # Chỉ giữ đúng field schema + kẹp độ dài — file nhập là đầu vào
        # không tin, id do file gửi bị bỏ (id là khoá nội bộ của máy này)
        raw = st["bot"]
        bot = {"name": str(raw.get("name") or "").strip()[:60],
               "avatar": str(raw.get("avatar") or "")[:8],
               "role": str(raw.get("role") or "").strip()[:40],
               "skills": [s for s in map(str, raw.get("skills") or [])
                          if SKILL_NAME_RE.fullmatch(s)],
               "needs": [str(n)[:40] for n in raw.get("needs") or []],
               "recipes": _clean_recipes(raw.get("recipes")),
               "instructions": raw.get("instructions")
                               if isinstance(raw.get("instructions"), (str, dict)) else "",
               "triggers": []}
        if isinstance(bot["instructions"], str):
            bot["instructions"] = bot["instructions"][:2000]
        elif isinstance(bot["instructions"], dict):
            # dict {vi,en} cũng phải kẹp — trước chỉ str bị cắt, dict trôi
            # → bot.md khổng lồ nhồi prompt mỗi phiên
            bot["instructions"] = {k: str(v)[:2000]
                                   for k, v in bot["instructions"].items()
                                   if k in ("vi", "en")}
        b = load_json(BOTS_FP, {"active": None, "bots": []})
        bots = b.setdefault("bots", [])
        bid = slug_id(bot["name"])
        base, n = bid, 2
        while any(x.get("id") == bid for x in bots):
            bid = f"{base}-{n}"; n += 1
        bot["id"] = bid
        bots.append(bot)
        save_json(BOTS_FP, b)
        return None
    finally:
        shutil.rmtree(st["dir"], ignore_errors=True)

class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        # chống slow-drip: client nhỏ giọt header/body giữ thread vô hạn.
        # 45s > wait_ms tối đa của long-poll (30s) nên không cắt nhầm.
        self.connection.settimeout(45)

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
        # chống DNS rebinding: chỉ nhận Host loopback — trang web lạ rebind
        # DNS về 127.0.0.1 thì Host vẫn là domain của nó → 403 (y serve.py)
        h = (self.headers.get("Host") or "").strip()
        if h.startswith("[") and "]" in h:
            h = h[1:h.index("]")]              # [::1]:7682 → ::1
        elif not h.startswith("["):
            h = h.rsplit(":", 1)[0]            # localhost:7682 → localhost
        if h not in ("localhost", "127.0.0.1", "::1") \
                and not h.endswith(".localhost"):
            self._json({"err": "Host không được phép"}, 403)
            return True
        return False

    def do_OPTIONS(self):
        if self._blocked():
            return
        self.send_response(204); self._cors(); self.end_headers()

    # Route table — danh sách endpoint thành DỮ LIỆU đọc được bằng
    # code: test-gates.py enumerate dict này thay vì regex-parse elif
    # chain, nên thêm endpoint POST mới = thêm key + một method _h_*.
    GET_ROUTES = {
        "/api/health":        "_g_health",
        "/api/brain":         "_g_brain",
        "/api/poll":          "_g_poll",
        "/api/permissions":   "_g_permissions",
        "/api/connections":   "_g_connections",
        "/api/config":        "_g_config",
        "/api/check-path":    "_g_check_path",
        "/api/count-glob":    "_g_count_glob",
        "/api/pick-folder":   "_g_pick_folder_probe",
        "/api/bots":          "_g_bots",
        "/api/install-brain": "_g_install_brain",
    }
    POST_ROUTES = {
        "/api/prompt":        "_h_prompt",
        "/api/respond":       "_h_respond",
        "/api/brain":         "_h_brain",
        "/api/delete-lesson": "_h_delete_lesson",
        "/api/save-page":     "_h_save_page",
        "/api/permissions":   "_h_permissions",
        "/api/remove-permission":"_h_remove_permission",
        "/api/connections":   "_h_connections",
        "/api/remove-connection":"_h_remove_connection",
        "/api/secrets":       "_h_secrets",
        "/api/setup":         "_h_setup",
        "/api/check-connection":"_h_check_connection",
        "/api/config":        "_h_config",
        "/api/bot":           "_h_bot",
        "/api/bot-import":    "_h_bot_import",
        "/api/bot-import-confirm":"_h_bot_import_confirm",
        "/api/emit-event":    "_h_emit_event",
        "/api/install-brain": "_h_install_brain",
        "/api/pick-folder":   "_h_pick_folder",
        "/api/reveal":        "_h_reveal",
    }

    def do_GET(self):
        if self._blocked():
            return
        path = urllib.parse.urlparse(self.path).path
        if path != "/api/health" and not self._authed():
            return self._json({"err": "thiếu hoặc sai mã kết nối"}, 401)
        # .get() trả None khi path lạ — getattr(name=None) raise TypeError
        # (default chỉ tính khi attr name là string) → phải check trước;
        # vẫn giữ default None cho trường hợp dict trỏ tới method không
        # tồn tại → 404 chứ không để AttributeError giết handler thread
        mn = self.GET_ROUTES.get(path)
        h = getattr(self, mn, None) if mn else None
        if h is None:
            return self._json({"err": "not found"}, 404)
        h()

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
        cl = max(0, cl)     # số âm → read(-n) đọc tới timeout, giữ slot
        # save-page + bot-import cần limit lớn hơn — file clone/base64 zip
        cap = 8_000_000 if path in ("/api/save-page", "/api/bot-import") else 1_000_000
        if cl > cap:
            self._json({"err": "body quá lớn"}, 413); return
        body = self.rfile.read(cl)
        try:
            data = json.loads(body or b"{}")
        except json.JSONDecodeError:
            data = {}
        if not isinstance(data, dict):
            # JSON hợp lệ nhưng không phải object ([], "x", 5) — để nguyên
            # thì data.get(...) raise AttributeError → handler thread chết
            data = {}
        mn = self.POST_ROUTES.get(path)
        h = getattr(self, mn, None) if mn else None
        if h is None:
            return self._json({"err": "not found"}, 404)
        h(data)

    def _g_health(self):
        # không trả sessionId — endpoint không auth, session id là
        # handle nội bộ không ai dùng (portal chỉ đọc ok/brain/version)
        self._json({"ok": True,
                    "brain": getattr(acp, "brain_id", None) or load_brain().get("id"),
                    "version": app_version(),
                    "extVersion": ext_expected_version()})

    def _g_brain(self):
        _augment_brain_path()   # não vừa cài xong → node dir mới sinh
        cur = load_brain()
        presets = []
        for p in BRAIN_PRESETS:
            presets.append({
                "id": p["id"], "label": p["label"],
                "cost": p.get("cost", "paid"),
                "desc": p.get("desc", {}),
                "auto": bool(p.get("auto")),
                "install": p.get("install"),
                "cmd_display": " ".join([p["cmd"]] + p["args"]),
                "installed": all(shutil.which(r)
                                 for r in p.get("requires", [p["cmd"]])),
            })
        self._json({"current": {k: cur.get(k)
                                for k in ("id", "label", "cmd", "args", "terminal")},
                    "presets": presets})

    def _g_poll(self):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        try:
            since = int(q.get("since", ["0"])[0])
        except ValueError:
            since = 0
        try:
            wait_ms = min(int(q.get("wait", ["0"])[0] or 0), 30000)
        except ValueError:
            wait_ms = 0
        with store_lock:
            total = event_base + len(event_store)
            # reset: cursor của client trỏ ngoài vùng event còn giữ —
            # thường là bridge vừa restart → replay toàn bộ cho client dựng lại
            reset = since < 0 or since < event_base or since > total
            # long-poll: không có event mới và không cần reset → chờ tới
            # wait hoặc broadcast() đánh thức. wait() tự release lock khi
            # ngủ và reacquire khi dậy — xong phải TÍNH LẠI mọi thứ.
            if wait_ms and not reset and total <= since:
                new_event.wait(wait_ms / 1000)
                total = event_base + len(event_store)
                reset = since < 0 or since < event_base or since > total
            evs = list(event_store) if reset else list(event_store[since - event_base:])
        self._json({"events": evs, "next": total, "reset": reset})

    def _g_permissions(self):
        self._json(load_json(PERM_FP, {"folders": []}))

    def _g_connections(self):
        self._json(load_json(CONN_FP, {"apps": []}))

    def _g_config(self):
        self._json(load_json(CONFIG_FP, {}))

    def _g_check_path(self):
        # onboarding hỏi "folder này có tồn tại không" trước khi thêm —
        # POST /api/permissions tạo card nên không dùng để kiểm được.
        # Chỉ trả isdir, không lộ metadata; vẫn đòi token.
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        p = os.path.expanduser((q.get("path") or [""])[0].strip())
        # path nhạy cảm không trả kết quả — endpoint này vốn chỉ để
        # onboarding hỏi folder, trả isdir của ~/.ssh/… thành oracle
        # dò-tồn-tại-file cho bất kỳ ai cầm token
        self._json({"ok": True, "isdir":
                    os.path.isdir(p) if p and not path_sensitive(p) else False})

    def _g_pick_folder_probe(self):
        """UI hỏi có hiện nút 'duyệt folder' không — chỉ macOS có hộp
        chọn folder qua osascript; OS khác → UI giấu nút, giữ ô gõ tay."""
        self._json({"ok": True, "supported":
                    sys.platform == "darwin"
                    and shutil.which("osascript") is not None})

    def _h_pick_folder(self, data):
        """Mở hộp chọn folder của macOS — nút 'duyệt' kiểu đính kèm file
        cho người không biết gõ path. Serial một hộp; timeout giết hộp
        treo khi học viên bỏ đi."""
        if sys.platform != "darwin" or not shutil.which("osascript"):
            return self._json({"ok": False, "err": "không hỗ trợ"})
        if not _pick_folder_lock.acquire(timeout=1):
            return self._json({"ok": False,
                               "err": "đang có hộp chọn mở"}, 409)
        try:
            p = subprocess.run(
                ["osascript", "-e",
                 'POSIX path of (choose folder with prompt '
                 '"Chọn folder trợ lý được đọc")'],
                capture_output=True, text=True, timeout=180)
            out = (p.stdout or "").strip()
            if p.returncode != 0 or not out:
                return self._json({"ok": True, "cancelled": True})
            # Dạng ~/... để khớp preset "📁 Downloads" — path tuyệt đối
            # trùng Downloads sẽ sinh mục trùng trong danh sách chọn.
            home = os.path.expanduser("~")
            if out == home or out.startswith(home + os.sep):
                out = "~" + out[len(home):]
            self._json({"ok": True, "path": out.rstrip("/")})
        except subprocess.TimeoutExpired:
            self._json({"ok": True, "cancelled": True})
        except Exception:
            self._json({"ok": False, "err": "không mở được hộp chọn"})
        finally:
            _pick_folder_lock.release()

    def _h_reveal(self, data):
        """Nút 'Mở trong Finder' của walkthrough — `open -R <path>` =
        REVEAL trong Finder (chọn sẵn item), KHÔNG phải `open` thường:
        `open` thực thi .app/.command → agent (có sẵn token) gọi endpoint
        là chạy được file ngoài sandbox. -R không bao giờ chạy file.
        Cùng chống-oracle của check-path: chỉ dưới ~, không đụng .devin,
        không vùng nhạy (deny-list)."""
        if sys.platform != "darwin":
            return self._json({"ok": False, "err": "không hỗ trợ"})
        p = os.path.abspath(os.path.expanduser(str(data.get("path") or "")))
        home = os.path.abspath(os.path.expanduser("~"))
        dev = os.path.join(os.path.abspath(CWD), ".devin")
        if not (p.startswith(home + os.sep)
                and not (p == dev or p.startswith(dev + os.sep))
                and not path_sensitive(p)):
            return self._json({"ok": False, "err": "path này không mở được"})
        if not os.path.exists(p):
            return self._json({"ok": False, "err": "chưa thấy path này"})
        subprocess.Popen(["open", "-R", p],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self._json({"ok": True})

    # ---- Terminal (ttyd) — tuỳ chọn nâng cao, mặc định TẮT ----
    # config.terminal=true thì mới spawn ttyd (launcher đọc cùng flag
    # lúc boot); bridge spawn ngay khi user bật trong Cài đặt để khỏi
    # phải restart app. Pidfile .devin/ttyd.pid để tắt được sau.
    TTYD_PID = os.path.join(os.path.abspath(CWD), ".devin", "ttyd.pid")

    def _ttyd_cmd(self):
        brain_term = "devin"
        try:
            brain_term = json.load(open(os.path.join(CWD, "brain.json"),
                                        encoding="utf-8")).get("terminal") or "devin"
        except Exception:
            pass
        env = os.environ.copy(); env["BRAIN_TERM"] = brain_term
        if platform.system() == "Windows":
            gate = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                    "-File", os.path.join(CWD, "tools", "term-gate.ps1")]
        else:
            gate = ["sh", os.path.join(CWD, "tools", "term-gate.sh")]
        return (["ttyd", "-p", "7681", "-i", "127.0.0.1", "-W", "-a", "-O"]
                + gate), env

    def _ttyd_up(self):
        import socket as _s
        try:
            _s.create_connection(("127.0.0.1", 7681), 0.4).close(); return True
        except OSError:
            return False

    def _h_config(self, data):
        """Cài đặt nhỏ do user lật trong portal — hiện chỉ whitelist key
        `terminal` (bật/tắt tab Terminal). terminal:true → spawn ttyd
        ngay (khỏi restart); false → giết process theo pidfile/port."""
        patch = {}
        if "terminal" in data:
            patch["terminal"] = bool(data.get("terminal"))
        if not patch:
            return self._json({"err": "không có key nào được phép"}, 400)
        cfg = load_json(CONFIG_FP, {})
        cfg.update(patch)
        save_json(CONFIG_FP, cfg)
        if "terminal" in patch:
            if patch["terminal"] and not self._ttyd_up() and shutil.which("ttyd"):
                cmd, env = self._ttyd_cmd()
                p = subprocess.Popen(cmd, cwd=CWD, env=env,
                                     stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL)
                try:
                    os.makedirs(os.path.dirname(self.TTYD_PID), exist_ok=True)
                    open(self.TTYD_PID, "w").write(str(p.pid))
                except Exception:
                    pass
            elif not patch["terminal"]:
                # tắt: kill theo pidfile (do bridge spawn) hoặc lsof port
                # (do launcher spawn). Watchdog cũng skip respawn vì flag
                # đã về false.
                try:
                    pid = int(open(self.TTYD_PID).read().strip())
                    os.kill(pid, 15)
                except Exception:
                    try:
                        out = subprocess.run(
                            ["lsof", "-ti:7681"], capture_output=True,
                            text=True, timeout=3).stdout.split()
                        for s in out:
                            os.kill(int(s), 15)
                    except Exception:
                        pass
                try:
                    os.unlink(self.TTYD_PID)
                except Exception:
                    pass
        self._json({"ok": True, "config": cfg})

    def _g_count_glob(self):
        # verify engine của workflow hỏi "folder này có bao nhiêu file
        # khớp pattern" — trả SỐ, không trả tên (danh sách file = lộ
        # nội dung máy). Cùng chống-oracle của check-path.
        import glob as _glob
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        d = os.path.normpath(os.path.expanduser(
            (q.get("path") or [""])[0].strip()))
        pat = (q.get("pattern") or ["*"])[0].strip()[:100]
        # pattern không được leo lên trên (../) — chỉ glob trong dir
        if ".." in pat or "/" in pat or "\\" in pat:
            pat = "*"
        if d and os.path.isdir(d) and not path_sensitive(d):
            n = sum(1 for _ in _glob.iglob(
                os.path.join(d, pat), recursive=False))
            self._json({"ok": True, "count": min(n, 2000),
                        "capped": n > 2000})
        else:
            self._json({"ok": True, "count": 0})

    def _g_bots(self):
        b = load_json(BOTS_FP, {"active": None, "bots": []})
        self._json({"active": b.get("active"),
                    "bots": b.get("bots") or [],
                    "templates": role_templates()})

    def _h_prompt(self, data):
        if acp is None or acp.dead:
            # não chết (process rớt hoặc chưa cài) → thử bật lại một lần,
            # học viên không phải tự chạy lại file start
            spawn_brain()
            self._json({"err": "đang khởi động lại trợ lý — gửi lại sau vài giây"}, 503); return
        if not acp.session_id:
            self._json({"err": "chưa có session"}, 503); return
        # acquire + bump gen PHẢI atomic so với watchdog (cùng
        # store_lock): lượt N vừa xong, lock mở, lượt N+1 giữ lock
        # nhưng chưa kịp gen++ → timer cũ thấy gen khớp + locked()
        # → giết não giữa lượt mới. Cửa sổ chỉ vài µs nhưng thật.
        with store_lock:
            locked = prompt_lock.acquire(blocking=False)
            if locked:
                turn_gen[0] += 1   # đánh dấu lượt mới — timer lượt cũ
                                   # thấy gen lệch → không giết nhầm
                run_id[0] += 1     # lượt mới — event con cháu kèm
                                   # run_id này (beacon đếm theo lượt)
        if not locked:
            self._json({"err": "trợ lý đang xử lý câu trước"}, 409); return
        if perm_dirty[0]:
            # quyền folder vừa đổi trong khi não đang sống → sandbox cũ
            # vẫn chặn ghi; respawn não ở đầu lượt mới để quyền ăn ngay
            # (F-015 — trước đây agent phải bảo học viên restart app)
            perm_dirty[0] = False
            spawn_brain()
            if acp is None or acp.dead or not acp.session_id:
                prompt_lock.release()
                self._json({"err": "đang khởi động lại trợ lý — "
                                   "gửi lại sau vài giây"}, 503); return
            broadcast({"t": "warn", "msg": "mình vừa nạp lại quyền "
                                           "mới — làm tiếp ngay nhé"})
        try:
            acp.call("session/prompt", {
                "sessionId": acp.session_id,
                "prompt": [{"type": "text", "text": data.get("text", "")}]})
        except (BrokenPipeError, OSError):
            prompt_lock.release()   # não chết ngay khi gửi → không kẹt busy
            self._json({"err": "trợ lý đã dừng — chạy lại file start"}, 503); return
        threading.Timer(TURN_TIMEOUT, _turn_watchdog,
                        args=(turn_gen[0],)).start()
        self._json({"ok": True})

    def _h_respond(self, data):
        rid = data.get("id")
        oid = data.get("optionId")
        # rid/oid không phải scalar (list/dict từ JSON) → get()/[in]
        # raise TypeError giết thread — trả lỗi gọn thay vì crash
        if not isinstance(rid, (int, str)) \
                or not isinstance(oid, (str, int)):
            self._json({"err": "yêu cầu không còn hiệu lực"}, 404); return
        # id PHẢI đang pending cho cả hai đường — __cancel__ chỉ miễn
        # check optionId (option ảo do UI tự thêm), không miễn check id;
        # nếu không kẻ có token vẫn bơm được id rác vào kênh điều khiển.
        # Validate + consume PHẢI atomic trong lock, và chỉ pop khi hợp
        # lệ — nếu pop trước thì request optionId lạ cũng giết card
        # (kẻ xấu DoS được nút bấm của học viên).
        o = self.headers.get("Origin")
        with store_lock:
            rec = perm_pending.get(rid)
            # Card não (ACP): id do chính não tự khai + nó có sẵn token
            # nên PHẢI đòi Origin trình duyệt y như card nội bộ, kẻo
            # não (hay script nhiễm trong trang) tự duyệt tool call của
            # mình. Card native (macOS) còn siết hơn: chỉ "__cancel__"
            # qua chat — mọi option duyệt phải từ hộp thoại hệ điều
            # hành (_perm_native_confirm), forge Origin cũng không ăn.
            valid = (rec is not None
                     and time.time() - rec["ts"] <= PERM_TTL
                     and (oid == "__cancel__" or oid in rec["options"])
                     and bool(o) and is_local_origin(o)
                     and not (rec.get("native") and oid != "__cancel__"))
            if valid:
                perm_pending.pop(rid, None)   # one-shot, không replay
            lrec = local_pending.get(rid)
            lfresh = lrec is not None \
                and time.time() - lrec["ts"] <= PERM_TTL
            # chỉ pop khi đủ điều kiện — thiếu Origin/oid lạ KHÔNG được
            # giết card (agent bơm request rác vẫn không DoS được nút
            # xác nhận của học viên). Card native (macOS) mà oid="ok"
            # cũng không pop: approve chỉ qua hộp thoại GUI — request
            # này sẽ nhận 403 gợi ý ở dưới, card vẫn pending chờ.
            lvalid = (lfresh and oid in ("ok", "__cancel__")
                      and bool(o) and is_local_origin(o)
                      and not (lrec.get("native") and oid == "ok"))
            if lvalid:
                local_pending.pop(rid, None)
        # Card nội bộ (consent gate — đổi quyền/xoá bài/đổi não): trả
        # lời phải kèm Origin trình duyệt — agent gọi tay thường không
        # có Origin (giả vẫn được, chỉ là thêm một vòng thủ). Trên
        # macOS có NATIVE_GATE thì "ok" còn bị chặn hẳn — chỉ nút
        # trong hộp thoại native mới là proof-of-human.
        # NHÁNH LOCAL ĐỨNG TRƯỚC: không còn trường hợp trùng id nữa
        # (đã chặn lúc đăng ký) nhưng vẫn ưu tiên local — lỡ có đường
        # nào khác chen id vào perm_pending thì click của học viên
        # vẫn resolve hành động local họ thấy, không nuôi card não.
        if lrec is not None:
            if not lfresh:
                self._json({"err": "yêu cầu không còn hiệu lực"}, 404); return
            if not (o and is_local_origin(o)):
                self._json({"err": "thiếu Origin trình duyệt"}, 403); return
            if lrec.get("native") and oid == "ok":
                self._json({"err": "bấm Đồng ý trong hộp thoại trên "
                            "màn hình máy bạn"}, 403); return
            if not lvalid:
                self._json({"err": "lựa chọn không hợp lệ"}, 400); return
            if oid == "ok":
                try:
                    lrec["apply"]()
                except Exception as e:
                    self._json({"err": "làm không được — "
                                + str(e)[:120]}, 500); return
            else:
                # cancel từ chat: giết luôn hộp thoại native đang mở
                # và đóng card (event perm_done → UI remove).
                p = lrec.get("proc")
                if p is not None:
                    try:
                        p.terminate()
                    except Exception:
                        pass
                broadcast({"t": "perm_done", "id": rid})
            self._json({"ok": True}); return
        if rec is None or time.time() - rec["ts"] > PERM_TTL:
            self._json({"err": "yêu cầu không còn hiệu lực"}, 404); return
        if not (o and is_local_origin(o)):
            self._json({"err": "thiếu Origin trình duyệt"}, 403); return
        if rec.get("native") and oid != "__cancel__":
            self._json({"err": "bấm Đồng ý trong hộp thoại trên "
                        "màn hình máy bạn"}, 403); return
        if not valid:
            self._json({"err": "lựa chọn không hợp lệ"}, 400); return
        if oid == "__cancel__":
            # học viên từ chối / card không có nút nào → báo cancel cho agent
            payload = {"jsonrpc": "2.0", "id": rid,
                       "error": {"code": -32800, "message": "học viên không đồng ý"}}
        else:
            payload = {"jsonrpc": "2.0", "id": rid,
                       "result": {"outcome": {"outcome": "selected",
                                              "optionId": oid}}}
        # cancel từ chat: giết luôn hộp thoại native đang mở (nếu có)
        p = rec.get("proc")
        if p is not None:
            try:
                p.terminate()
            except Exception:
                pass
        try:
            if acp and not acp.dead:
                acp.send(payload)
        except (BrokenPipeError, OSError):
            pass
        broadcast({"t": "perm_done", "id": rid})
        self._json({"ok": True})

    def _h_brain(self, data):
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
            if _brain_cmd_denied(cmd.lower()):
                # .lower() bắt buộc: APFS/NTFS không phân biệt hoa-thường
                # nên "Python3" which-resolve vẫn ra python3 — deny mà
                # so nguyên xi là lọt (ps1 đã ToLower, load_brain cũng vậy)
                self._json({"err": "lệnh này chạy code tuỳ ý — không dùng làm não được"}, 400); return
            term = str(data.get("terminal", cmd))
            if not re.fullmatch(r"[A-Za-z0-9_.-]+", term):
                self._json({"err": "lệnh terminal không hợp lệ"}, 400); return
            if _brain_cmd_denied(term.lower()):
                self._json({"err": "lệnh terminal này chạy code tuỳ ý — "
                                   "không dùng được"}, 400); return
            args = data.get("args")
            args = [str(a)[:200] for a in args[:20]] if isinstance(args, list) else []
            b = {"id": bid or "custom",
                 "label": str(data.get("label", cmd))[:60],
                 "cmd": cmd, "args": args,
                 "terminal": term}
            requires = [cmd]
        _augment_brain_path()   # vừa cài xong → resolve được não mới
        missing = [r for r in requires if not shutil.which(r)]
        if missing:
            self._json({"err": "chưa cài trên máy: " + ", ".join(missing),
                        "missing": missing}, 404); return
        # Mọi đổi não đều qua card — kể cả preset: agent cũng gọi được
        # endpoint này (BRIDGE_TOKEN có sẵn trong env) nên preset đổi
        # thẳng = agent tự kill session/spam spawn/ghi brain.json qua
        # cửa vòng (audit-3 M5). Text custom nói thẳng "chạy lệnh tuỳ
        # ý" — denylist không bao giờ đầy đủ, đừng để học viên tưởng
        # lệnh đã được lọc.
        disp = " ".join([b["cmd"]] + b.get("args", []))[:80]
        title = (f"Đổi não sang {preset['label']}?" if preset
                 else f"Chạy lệnh tùy ý \"{disp}\" làm não?")
        def _apply(b=b):
            save_json(BRAIN_FP, b)
            spawn_brain()
        rid = gate_local(title, _apply)
        self._gate_resp(rid, "đã gửi thẻ xác nhận vào chat — bấm Đồng ý để đổi não")

    def _g_install_brain(self):
        # onboarding poll trạng thái cài não — script tự ghi INSTALL_FP
        # nên sống được qua restart bridge
        st = load_json(INSTALL_FP, {})
        running = INSTALL_PROC["proc"] is not None \
            and INSTALL_PROC["proc"].poll() is None
        # proc chết giữa chừng (bridge restart, kill) mà file state kẹt
        # "running" → onboarding poll mãi. Ép về error để UI cho cài lại.
        state = "running" if running else st.get("state")
        if not running and state == "running":
            state = "error"
        self._json({"ok": True, "running": running, "state": state,
                    "id": st.get("id"), "step": st.get("step"),
                    "log": (st.get("log") or [])[-12:]})

    def _h_install_brain(self, data):
        # Cài não bằng một nút (tools/install-brain.py) hoặc mở terminal
        # để đăng nhập não {"login": true}. Máy đã onboard/fleet → qua
        # thẻ xác nhận vì agent cũng gọi được endpoint này; máy CHƯA
        # onboard thì chưa có agent nào giả nút bấm → chạy luôn (nút
        # bấm của học viên chính là consent — y hệt _h_setup lần đầu).
        bid = str(data.get("id", "")).strip()
        preset = next((p for p in BRAIN_PRESETS if p["id"] == bid), None)
        if not preset:
            self._json({"err": "không có não này"}, 400); return
        login = bool(data.get("login"))
        if not login and not preset.get("auto"):
            self._json({"err": "não này chưa cài tự động được — "
                               "làm theo trang hướng dẫn của hãng"}, 400)
            return
        onboarded = load_json(CONFIG_FP, {}).get("language") or \
            os.path.isfile(os.path.join(os.path.abspath(CWD), ".devin",
                                        "fleet.json"))
        def _apply():
            if login:
                self._brain_login(preset)
            else:
                self._brain_install(preset)
        if onboarded:
            rid = gate_local(
                (f"Mở terminal đăng nhập não {preset['label']}?" if login
                 else f"Cài não {preset['label']} lên máy?"), _apply)
            self._gate_resp(rid, "đã gửi thẻ xác nhận vào chat — "
                                 "bấm Đồng ý để chạy")
            return
        try:
            _apply()
        except OSError as e:
            self._json({"err": str(e)}, 500); return
        self._json({"ok": True})

    def _brain_install(self, preset):
        if INSTALL_PROC["proc"] is not None \
                and INSTALL_PROC["proc"].poll() is None:
            return                       # đang cài rồi — POST lặp là no-op
        if getattr(sys, "frozen", False):
            # binary đóng gói: vai con qua `troly <role>` (launcher)
            cmd = [sys.executable, "install-brain",
                   preset["id"], os.path.abspath(CWD)]
        else:
            cmd = [sys.executable,
                   os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "install-brain.py"),
                   preset["id"], os.path.abspath(CWD)]
        logdir = os.path.join(os.path.abspath(CWD), ".logs")
        os.makedirs(logdir, exist_ok=True)
        log = open(os.path.join(logdir, "install-brain.log"), "ab",
                   buffering=0)
        try:
            INSTALL_PROC["proc"] = subprocess.Popen(
                cmd, cwd=os.path.abspath(CWD),
                stdout=log, stderr=subprocess.STDOUT)
        finally:
            log.close()   # con đã giữ fd riêng — không lấp fd trong bridge

    def _brain_login(self, preset):
        """Mở cửa sổ terminal chạy CLI của não — OAuth chỉ hoàn tất
        được trong terminal thật (browser bật ra, não tự lưu creds)."""
        term = preset.get("terminal") or preset["cmd"]
        # PATH của bridge đã gồm DATA/node — resolve ra path tuyệt đối
        # kẻo terminal mới (không thừa hưởng PATH đã prepend) không tìm
        # thấy não vừa cài lén
        _augment_brain_path()
        term = shutil.which(term) or term
        sysname = platform.system()
        # não trong DATA/node là "lén" — shell login của terminal mới KHÔNG
        # có DATA/node/bin trong PATH mà shim npm cần env node → chích PATH
        # ngay trong lệnh mở terminal (Windows npm shim tự tìm node.exe
        # cạnh nó, POSIX shim thì không)
        termdir = os.path.dirname(term)
        prefix = f'export PATH="{termdir}:$PATH"; ' if termdir else ""
        if sysname == "Windows":
            setp = f'set "PATH={termdir};%PATH%" && ' if termdir else ""
            subprocess.Popen(["cmd", "/c", "start", "", "cmd", "/k",
                              setp + f'"{term}"'])
        elif sysname == "Darwin":
            # ensure_ascii=False: đường dẫn có chữ Việt (home "Nguyễn")
            # mà dumps mặc định thành \uXXXX → AppleScript không hiểu
            cmd = prefix + f'"{term}"; exit'
            subprocess.Popen(["osascript", "-e",
                'tell application "Terminal" to do script ' +
                json.dumps(cmd, ensure_ascii=False)])
        else:
            raise OSError("chưa hỗ trợ mở terminal trên Linux — "
                          "tự mở terminal chạy lệnh não")

    def _h_delete_lesson(self, data):
        folder = str(data.get("folder", ""))
        if not re.fullmatch(r"[a-zA-Z0-9_-]+", folder):
            self._json({"err": "tên folder lạ"}, 400); return
        course = os.path.realpath(os.path.join(os.path.abspath(CWD), "workspace"))
        target = os.path.realpath(os.path.join(course, folder))
        if not target.startswith(course + os.sep) or not os.path.isdir(target):
            self._json({"err": "không thấy folder bài"}, 404); return
        def _apply(target=target, folder=folder, course=course):
            # không xoá hẳn — move vào workspace/.trash/ để khôi phục
            # được (bấm nhầm Đồng ý vẫn cứu lại bài); tên kèm timestamp
            # + hex ngắn tránh đụng khi xoá lại folder cùng tên
            trash = os.path.join(course, ".trash")
            os.makedirs(trash, exist_ok=True)
            dst = os.path.join(trash, folder + "-" +
                               time.strftime("%Y%m%d-%H%M%S") + "-" +
                               secrets.token_hex(3))
            shutil.move(target, dst)
            # GC thùng rác: không dọn thì video.mp4 trong bài xoá tích
            # luỹ vĩnh viễn. Giữ 20 bản mới nhất; cũ hơn 30 ngày xoá
            # hẳn (đã qua consent + 30 ngày khôi phục là đủ).
            try:
                ents = sorted(
                    (os.path.join(trash, d) for d in os.listdir(trash)),
                    key=os.path.getmtime)
                now = time.time()
                for i, e in enumerate(ents):
                    if len(ents) - i > 20 \
                            or now - os.path.getmtime(e) > 30 * 86400:
                        shutil.rmtree(e, ignore_errors=True)
            except OSError:
                pass
            mf = os.path.join(course, "manifest.json")
            try:
                m = json.load(open(mf, encoding="utf-8"))
                m["lessons"] = [b for b in m.get("lessons", [])
                                if b.get("folder") != folder]
                save_json(mf, m)   # atomic — crash giữa ghi không corrupt
            except Exception:
                pass
        # xoá bài là hành động phá nhưng hoàn tác được — qua card xác
        # nhận của học viên, bài nằm lại trong workspace/.trash/
        rid = gate_local(f"Xoá bài học {folder}? (vào thùng rác — khôi phục được)", _apply)
        self._gate_resp(rid, "đã gửi thẻ xác nhận vào chat — bấm Đồng ý để xoá (bài giữ trong thùng rác)")

    def _h_save_page(self, data):
        # clone-view.html lưu bản đã chỉnh — chỉ cho ghi file .html
        # trong workspace/, chặn path ra ngoài
        rel = str(data.get("file", "")).strip().lstrip("/")
        html = str(data.get("html", ""))
        course = os.path.realpath(os.path.join(os.path.abspath(CWD), "workspace"))
        target = os.path.realpath(os.path.join(os.path.abspath(CWD), rel))
        if not rel.startswith("workspace/") or ".." in rel or \
           not target.startswith(course + os.sep) or \
           not re.search(r"\.html?$", target, re.I):
            self._json({"err": "chỉ lưu file .html trong workspace/"}, 400); return
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

    def _h_permissions(self, data):
        # Đổi quyền folder = đổi sandbox profile spawn kế → bắt buộc
        # qua card xác nhận (agent tự cấp "/" = tự cởi còng). Batch
        # {"paths": [...]} = MỘT card — onboarding thêm nhiều folder
        # không spam card (mỗi card riêng = không card nào được đọc).
        access = str(data.get("access", "read"))
        if access not in ("read", "read-write"):
            self._json({"err": "access phải là read hoặc read-write"}, 400); return
        raw = data.get("paths") if isinstance(data.get("paths"), list) \
            else [data.get("path")]
        if len(raw) > 20:
            self._json({"err": "quá nhiều folder một lần"}, 400); return
        paths, bad = [], []
        for rp in raw:
            p = os.path.expanduser(str(rp or "").strip())
            if not p or not os.path.isdir(p):
                bad.append(str(rp or ""))
                continue
            if path_sensitive(p):
                self._json({"err": "folder chứa dữ liệu nhạy cảm — "
                                   "không cấp quyền được: " + p}, 400); return
            if access == "read-write" and not rw_grant_ok(p, CWD):
                self._json({"err": "không cấp ghi trong folder mã nguồn "
                                   "của trợ lý — ghi được là code chạy "
                                   "ngoài sandbox: " + p}, 400); return
            paths.append(p)
        if not paths:
            self._json({"err": "không thấy folder này trên máy"}, 404); return
        note = str(data.get("note", ""))[:120]
        def _apply(paths=paths, access=access, note=note):
            # Re-validate LÚC APPLY (audit-3 CAO-2): giữa request và
            # bấm Đồng ý agent có thể rmdir + ln -s folder nhạy cảm —
            # request-time check đã qua nhưng đích mới phải bị bắt ở
            # đây. (Lớp chặn cuối vẫn là gen-sandbox._grant_ok lúc
            # build profile mỗi spawn — đây là lớp báo lỗi thấy được.)
            ok, refused = [], []
            for p in paths:
                if (not os.path.isdir(p) or path_sensitive(p)
                        or (access == "read-write"
                            and not rw_grant_ok(p, CWD))):
                    refused.append(p)
                else:
                    ok.append(p)
            if ok:
                q = load_json(PERM_FP, {"folders": []})
                # file hỏng/thiếu key → qua fallback hết — không crash
                q["folders"] = [f for f in (q.get("folders") or [])
                                if os.path.expanduser(str(f.get("path", "")))
                                not in ok]
                for p in ok:
                    q["folders"].append({"path": p, "access": access,
                                         "note": note})
                save_json(PERM_FP, q)
                gen_sandbox_profile()   # quyền mới áp ngay spawn não kế tiếp
                perm_dirty[0] = True    # F-015: não đang sống vẫn giữ sb cũ
            if refused:
                broadcast({"t": "err",
                           "msg": "bỏ qua folder không còn hợp lệ: "
                                  + ", ".join(refused)[:160]})
        disp = paths[0] if len(paths) == 1 \
            else f"{len(paths)} folder ({', '.join(paths)[:120]})"
        rid = gate_local(f"Thêm quyền {access} cho {disp}?", _apply)
        self._gate_resp(rid,
            "đã gửi thẻ xác nhận vào chat — bấm Đồng ý để có hiệu lực",
            {"skipped": bad} if bad else None)

    def _h_remove_permission(self, data):
        p = os.path.expanduser(str(data.get("path", "")).strip())
        def _apply(p=p):
            q = load_json(PERM_FP, {"folders": []})
            q["folders"] = [f for f in (q.get("folders") or [])
                            if os.path.expanduser(str(f.get("path", ""))) != p]
            save_json(PERM_FP, q)
            gen_sandbox_profile()   # thu hồi cũng phải regen
            perm_dirty[0] = True        # F-015: respawn não ở prompt kế
        rid = gate_local(f"Gỡ quyền folder {p}?", _apply)
        self._gate_resp(rid, "đã gửi thẻ xác nhận vào chat — bấm Đồng ý để có hiệu lực")

    def _h_connections(self, data):
        # Upsert một app vào registry kết nối — thay tại chỗ để giữ
        # thứ tự hiển thị trong panel Cài đặt
        app = data.get("app")
        if not isinstance(app, dict) or not app.get("id"):
            self._json({"err": "thiếu app.id"}, 400); return
        if "probe" in app and not validate_probe(app["probe"]):
            self._json({"err": "kiểu kiểm tra kết nối không hợp lệ"}, 400); return
        # open_url là link nút "Mở trang" trong portal — javascript:/
        # data: chạy được script trong origin portal → chỉ nhận http(s)
        ou = str(app.get("open_url") or "")
        if ou and not re.match(r"^https?://", ou, re.I):
            self._json({"err": "open_url chỉ nhận link http(s)"}, 400); return
        k = load_json(CONN_FP, {"apps": []})
        old_ou = next((str(a.get("open_url") or "")
                       for a in (k.get("apps") or [])
                       if a.get("id") == app["id"]), "")
        if ou and ou != old_ou:
            # open_url MỚI hoặc ĐỔI → nút "Mở trang" quen-thuộc trỏ
            # site lạ (phishing) → card cho học viên thấy đích đến
            # trước khi tin (audit v6). Upsert status/name hay giữ
            # nguyên open_url thì chạy thẳng — portal cập nhật thường
            # xuyên, không thể card mỗi lần.
            def _apply(app=app):
                kk = load_json(CONN_FP, {"apps": []})
                kk["apps"] = kk.get("apps") or []
                for i, a in enumerate(kk["apps"]):
                    if a.get("id") == app["id"]:
                        kk["apps"][i] = app
                        break
                else:
                    kk["apps"].append(app)
                save_json(CONN_FP, kk)
            rid = gate_local(
                f"Đặt link \"Mở trang\" của {app['id']} → {ou}?", _apply)
            self._gate_resp(rid, "đã gửi thẻ xác nhận vào chat — bấm Đồng ý để đặt link")
            return
        k["apps"] = k.get("apps") or []
        for i, a in enumerate(k["apps"]):
            if a.get("id") == app["id"]:
                k["apps"][i] = app
                break
        else:
            k["apps"].append(app)
        save_json(CONN_FP, k)
        self._json({"ok": True})

    def _h_remove_connection(self, data):
        # Gỡ app khỏi registry — agent tự gọi là mất nút kết nối âm
        # thầm → gate (audit v6). Không UI nào gọi endpoint này nên
        # card không thêm ma sát.
        aid = str(data.get("id", ""))
        def _apply(aid=aid):
            k = load_json(CONN_FP, {"apps": []})
            k["apps"] = [a for a in (k.get("apps") or [])
                         if a.get("id") != aid]
            save_json(CONN_FP, k)
        rid = gate_local(f"Gỡ kết nối {aid}?", _apply)
        self._gate_resp(rid, "đã gửi thẻ xác nhận vào chat — bấm Đồng ý để gỡ")

    def _h_secrets(self, data):
        # Form "Cài" trong panel Cài đặt: học viên dán app password WP /
        # mã OA… → ghi vào .devin/secrets.local.json (đã gitignore).
        # Chỉ GHI — không endpoint nào đọc secret ra ngoài.
        # Ghi credential là đặc quyền → consent gate (audit v6): agent
        # tự gọi với url mới = xoá creds thật (wipe-khi-đổi-url), còn
        # url + pass đến host lạ = kênh exfil.
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
        # Card báo trước cả wipe (đọc creds cũ chỉ để so) — học viên
        # thấy "sẽ xoá thông tin cũ" TRƯỚC khi bấm Đồng ý.
        old0 = load_json(fp, {}).get(app) or {}
        wipe = any(k in clean and clean[k] != old0.get(k)
                   for k in ("url", "host", "endpoint"))
        def _apply(app=app, clean=clean):
            creds = load_json(fp, {})
            old = creds.get(app) or {}
            # Đổi endpoint (url/host/endpoint) thì phải nhập lại TOÀN
            # BỘ thông tin — giữ user+password cũ qua host mới = probe
            # sau đó gửi creds thật tới host attacker (exfil).
            for k in ("url", "host", "endpoint"):
                if k in clean and clean[k] != old.get(k):
                    creds[app] = clean
                    break
            else:
                creds[app] = {**old, **clean}
            os.makedirs(os.path.dirname(fp), exist_ok=True)
            save_json(fp, creds)
            try:
                # credential của học viên — quyền như bridge.token
                os.chmod(fp, 0o600)
            except OSError:
                pass                 # Windows không có chmod — bỏ qua
        title = (f"Lưu thông tin đăng nhập cho {app} — đổi địa chỉ "
                 f"site sẽ XOÁ thông tin cũ?" if wipe
                 else f"Lưu thông tin đăng nhập cho {app}?")
        rid = gate_local(title, _apply)
        self._gate_resp(rid, "đã gửi thẻ xác nhận vào chat — bấm Đồng ý để lưu")

    def _h_setup(self, data):
        # Onboarding lần đầu: ngôn ngữ + tên → config.json + skill pack đúng ngôn ngữ
        lang = str(data.get("language", ""))
        name = str(data.get("learner_name", "")).strip()[:80]
        if lang not in ("vi", "en"):
            self._json({"err": "language phải là vi hoặc en"}, 400); return
        def _apply(lang=lang, name=name):
            os.makedirs(MC_DIR, exist_ok=True)
            cfg_old = load_json(CONFIG_FP, {})   # giữ key cũ (terminal…)
            cfg_old.update({"language": lang, "learner_name": name})
            save_json(CONFIG_FP, cfg_old)
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
                save_json(mf, m)
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
                    for n in os.listdir(bak):
                        src = os.path.join(bak, n)
                        dst = os.path.join(SKILLS_DIR, n)
                        if os.path.isdir(src) and not os.path.exists(dst):
                            shutil.copytree(src, dst)
        # Setup đã chạy rồi (config có language) mà bị gọi lại → agent
        # có thể đang cố đè skills/config — qua card xác nhận. Máy FLEET
        # (có .devin/fleet.json — bộ cài cty provision sẵn) thì LUÔN
        # gate: skill/config trên máy cty do pack quản, agent không được
        # tự ý chạy lại onboarding đè lên (audit-5 S3). Chỉ onboarding
        # lần đầu thật trên máy cá nhân mới chạy luôn.
        fleet = os.path.isfile(os.path.join(
            os.path.abspath(CWD), ".devin", "fleet.json"))
        if load_json(CONFIG_FP, {}).get("language") or fleet:
            rid = gate_local(
                "Chạy lại thiết lập ban đầu — sẽ cài đè bộ skill?", _apply)
            self._gate_resp(rid, "đã gửi thẻ xác nhận vào chat — bấm Đồng ý để chạy lại")
            return
        _apply()
        self._json({"ok": True})

    def _h_check_connection(self, data):
        aid = str(data.get("id", ""))
        k = load_json(CONN_FP, {"apps": []})
        app = next((a for a in (k.get("apps") or [])
                    if a.get("id") == aid), None)
        if not app:
            self._json({"err": "không thấy app"}, 404); return
        res = run_probe(app.get("probe"))
        app["status"] = "connected" if res["ok"] else "not-connected"
        app["check_message"] = res["msg"]
        save_json(CONN_FP, k)
        self._json(res)

    def _h_bot(self, data):
        action = str(data.get("action", ""))
        b = load_json(BOTS_FP, {"active": None, "bots": []})
        bots = b.setdefault("bots", [])
        if action == "create":
            name = str(data.get("name", "")).strip()[:60]
            role = str(data.get("role", "")).strip()[:40]
            ins = str(data.get("instructions", "")).strip()
            if not name:
                self._json({"err": "thiếu tên bot"}, 400); return
            if len(ins) > 500:
                self._json({"err": "lời dặn quá 500 chữ — viết ngắn lại giúp"}, 400); return
            # không cap thì agent loop tạo hàng nghìn bot → bots.json
            # phình (cấu trúc không-trần duy nhất còn lại)
            if len(bots) >= 50:
                self._json({"err": "tối đa 50 trợ lý — xoá bớt trợ lý cũ trước"}, 400); return
            bid = slug_id(name + "-" + role)
            base, n = bid, 2
            while any(x.get("id") == bid for x in bots):
                bid = f"{base}-{n}"; n += 1
            bot = {"id": bid, "name": name, "role": role,
                   "avatar": str(data.get("avatar", ""))[:8],
                   "skills": [s for s in
                              (str(s)[:40] for s in
                               (data.get("skills") if isinstance(data.get("skills"), list) else []))
                              if SKILL_NAME_RE.fullmatch(s)],
                   "needs": [str(s)[:40] for s in
                             (data.get("needs") if isinstance(data.get("needs"), list) else [])],
                   # recipes cap: trước nhận list tuỳ ý không trần →
                   # bot độc nhồi payload / phình bots.json (M2).
                   "recipes": _clean_recipes(data.get("recipes")),
                   "instructions": ins,
                   "triggers": []}
            bots.append(bot)
            save_json(BOTS_FP, b)
            self._json({"ok": True, "bot": bot})
        elif action == "activate":
            # activate/deactivate = ghi bots.json (file mà sandbox cố
            # ý deny-write — bridge là cửa duy nhất) + viết lại bot.md
            # (instruction của não) + cài skill. Y hệt các write đặc
            # quyền khác → consent gate, nếu không agent tự đổi/xoá
            # persona của chính mình âm thầm.
            bid = data.get("id")
            if bid not in (None, "") and not any(
                    x.get("id") == bid for x in bots):
                self._json({"err": "không thấy bot này"}, 404); return
            bot0 = next((x for x in bots if x.get("id") == bid), None) or {}
            name = bot0.get("name") or "Trợ lý chung"
            # card phải preview lời dặn — instructions ≤500 chữ là
            # payload chạy vào mọi session, chỉ hiện tên thì agent
            # tạo bot độc rồi xin activate lách review (audit-3 M2)
            ins_prev = str(bot0.get("instructions") or "").strip()[:80]
            def _apply(bid=bid):
                # đọc lại từ đĩa — bot có thể đổi giữa lúc chờ bấm
                bb = load_json(BOTS_FP, {"active": None, "bots": []})
                if bid in (None, ""):
                    bb["active"] = None      # về trợ lý chung
                    deactivate_bot()
                    save_json(BOTS_FP, bb)
                    return
                bot = next((x for x in (bb.get("bots") or [])
                            if x.get("id") == bid), None)
                if not bot:
                    broadcast({"t": "err", "msg": "không thấy bot này nữa"})
                    return
                missing = activate_bot(bot)
                bb["active"] = bot["id"]
                save_json(BOTS_FP, bb)
                if missing:
                    broadcast({"t": "err",
                               "msg": "đã đổi trợ lý nhưng chưa cài được: "
                                      + ", ".join(missing)
                                      + " — nhờ trợ lý trong chat cài thêm"})
            rid = gate_local(
                f"Đặt {name} làm trợ lý đang làm việc?"
                + (f" Lời dặn: \"{ins_prev}…\"" if ins_prev else ""),
                _apply)
            self._gate_resp(rid, "đã gửi thẻ xác nhận vào chat — bấm Đồng ý để đổi trợ lý")
        elif action == "delete":
            # xoá bot là vĩnh viễn (không có thùng rác) → gate y như
            # delete-lesson dù thứ kia còn khôi phục được
            bid = str(data.get("id", ""))
            bot = next((x for x in bots if x.get("id") == bid), None)
            if not bot:
                self._json({"err": "không thấy bot này"}, 404); return
            def _apply(bid=bid):
                bb = load_json(BOTS_FP, {"active": None, "bots": []})
                bb["bots"] = [x for x in (bb.get("bots") or [])
                              if x.get("id") != bid]
                if bb.get("active") == bid:
                    bb["active"] = None
                    deactivate_bot()   # không để bot.md mồ côi
                save_json(BOTS_FP, bb)
            rid = gate_local(
                f"Xoá trợ lý {bot.get('name') or bid}?", _apply)
            self._gate_resp(rid, "đã gửi thẻ xác nhận vào chat — bấm Đồng ý để xoá")
        elif action == "rename":
            bid = str(data.get("id", ""))
            bot = next((x for x in bots if x.get("id") == bid), None)
            if not bot:
                self._json({"err": "không thấy bot này"}, 404); return
            if data.get("name"):
                bot["name"] = str(data["name"]).strip()[:60]
            if data.get("avatar") is not None:
                bot["avatar"] = str(data["avatar"])[:8]
            save_json(BOTS_FP, b)
            if b.get("active") == bid:
                write_bot_md(bot)   # bot.md theo tên mới
            self._json({"ok": True, "bot": bot})
        else:
            self._json({"err": "action phải là create/activate/delete/rename"}, 400)

    def _h_bot_import(self, data):
        prev, err = stage_bot_bundle(str(data.get("file", "")))
        if err:
            self._json({"err": err}, 400); return
        self._json({"ok": True, "preview": prev})

    def _h_bot_import_confirm(self, data):
        # Cài skill + bot từ file ngoài = nạp instruction + recipe cho
        # não — không gate thì agent tự stage + confirm được im lặng
        sid = str(data.get("stage", ""))
        st = IMPORT_STAGES.get(sid)
        if not st:
            self._json({"err": "hết hạn rồi — nhập lại file nhé"}, 400); return
        def _apply(sid=sid):
            err = confirm_bot_bundle(sid)
            if err:
                broadcast({"t": "err", "msg": err})
        bname = str(st["bot"].get("name") or "?")[:60]
        rid = gate_local(
            f"Cài trợ lý \"{bname}\" từ file chia sẻ?", _apply)
        self._gate_resp(rid, "đã gửi thẻ xác nhận vào chat — bấm Đồng ý để cài")

    def _h_emit_event(self, data):
        # Đồng nghiệp bridge nội bộ (ext-bridge → inj_suspect, launcher
        # → env_scrub…) append event thống kê vào store để beacon đếm.
        # Whitelist type — giới hạn thiệt hại khi agent tự gọi (chỉ
        # inflate được đếm trên dashboard, không đổi state).
        t = str(data.get("t") or "")
        if t not in ("inj_suspect", "perm:auto", "env_scrub",
                     "pack_applied", "update_applied"):
            self._json({"err": "event type không được phép"}, 400)
            return
        ev = {k: data[k] for k in ("t", "action", "patterns",
                                   "dropped", "title", "pattern",
                                   "msg")
              if k in data}
        broadcast(ev)
        self._json({"ok": True})

    def _json(self, obj, code=200):
        b = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self._cors(); self.end_headers()
        self.wfile.write(b)

    def _gate_resp(self, rid, msg, extra=None):
        """Trả 202 kèm card id sau gate_local, hoặc 409 khi gate từ chối
        (đạt NATIVE_MAX — đang có dialog chờ, không spawn thêm)."""
        if rid is None:
            self._json({"err": "đang có thẻ xác nhận chờ — duyệt hoặc "
                               "huỷ trước đã"}, 409)
            return
        out = {"pending": rid, "msg": msg}
        if extra:
            out.update(extra)
        self._json(out, 202)

def spawn_brain():
    """Bật (hoặc đổi) não: giết agent cũ nếu còn sống, spawn theo brain.json
    rồi bắt tay ACP chuẩn (initialize + session/new)."""
    global acp
    with spawn_lock:
        old = acp
        acp = Acp(load_brain())
        if old and old.proc:
            old.expect_death = True   # đổi não là có chủ đích, không phải crash
            try:
                old.proc.terminate()
                # wait ngắn để stdout đóng hẳn — não cũ đang sống lèo
                # broadcast vài event lẫn vào stream của não mới
                old.proc.wait(timeout=2)
            except Exception:
                # não cứng đầu không chịu terminate → kill hẳn, kẻo zombie
                # sống sót và reader cũ cứ broadcast lẫn vào stream não mới
                try:
                    old.proc.kill()
                except Exception:
                    pass
        if not acp.dead:
            # initialize PHẢI có result trước khi session/new — bắn liền
            # nhau thì não trả "Invalid request" (ACP đòi init xong trước)
            # và session_id mãi rỗng → mọi prompt bị "chưa có session".
            r = acp.call_sync("initialize", {
                "protocolVersion": 1,
                "clientCapabilities": {"fs": {"readTextFile": False,
                                              "writeTextFile": False},
                                       "terminal": False}})
            # result tồn tại và không null — KHÔNG check truthy: não trả
            # result:{} rỗng vẫn là handshake thành công, dict rỗng mà
            # falsy là bỏ session/new luôn
            if r and r.get("result") is not None:
                # chờ luôn session/new để session_id sẵn khi hàm trả về
                acp.call_sync("session/new", {"cwd": CWD,
                                              "mcpServers": []})

class BoundedServer(ThreadingHTTPServer):
    """Thread-per-connection KHÔNG trần → hàng nghìn kết nối treo là hết
    thread/fd. Nắp 64 slot: connection quá hạn xếp backlog thay vì phình
    thread. daemon_threads để Ctrl+C không bị thread treo níu lại."""
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
    rotate_history()
    rotate_logs()
    replay_history()
    # stage import bot rồi crash → temp rác — dọn lúc boot (>1h)
    try:
        td = tempfile.gettempdir()
        for d in os.listdir(td):
            if not d.startswith("troly-bot-"):
                continue
            p = os.path.join(td, d)
            try:
                if time.time() - os.path.getmtime(p) > 3600:
                    shutil.rmtree(p, ignore_errors=True)
            except OSError:
                pass
    except OSError:
        pass
    # .logs/*.log chỉ quay vòng khi có history-write hoặc boot — máy ít
    # chat thì log phình theo tháng. Thread daemon quay theo GIỜ.
    def _log_rotator():
        while True:
            time.sleep(3600)
            try:
                rotate_logs()
            except Exception:
                pass
    threading.Thread(target=_log_rotator, daemon=True).start()
    spawn_brain()
    print(f"chat-bridge: http://localhost:{PORT}  (cwd={CWD})")
    BoundedServer((BIND, PORT), Handler).serve_forever()
