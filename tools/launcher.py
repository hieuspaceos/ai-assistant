#!/usr/bin/env python3
"""
troly — Trợ Lý AI đóng gói một file. Cùng binary đóng 4 vai:

    troly run              → bootstrap ~/TroLyAI + supervisor 3 bridge + watchdog
    troly serve|chat-bridge|ext-bridge [port] [cwd]
                           → vai con: chạy đúng tools/<vai>.py trong user dir
    troly --register-startup / --unregister-startup
                           → tự chạy cùng máy (Run key / LaunchAgent / autostart)

Chạy từ source (python3 tools/launcher.py run) hoặc đóng PyInstaller
onefile — payload (web/, tools/, extension/, templates/, skill-packs…) đi
kèm trong binary rồi "bung" ra folder user lần chạy đầu.

Update path: binary mới có VERSION khác ~/TroLyAI/VERSION → chỉ đè phần
CODE (CODE_DIRS/CODE_FILES), không đụng workspace/, brain.json, .devin/
skills, secrets, token — "update = tải exe mới rồi mở lại".
"""
import json, os, platform, runpy, secrets, shutil, signal, subprocess, sys
import time, urllib.request, webbrowser

FROZEN = getattr(sys, "frozen", False)
HERE = os.path.dirname(os.path.abspath(__file__))
# Payload nguồn: source mode = repo root; frozen = thư mục PyInstaller giải nén
SRC = os.path.dirname(HERE) if not FROZEN else sys._MEIPASS
DATA = os.environ.get("TROLY_DATA") or os.path.join(os.path.expanduser("~"), "TroLyAI")
LOGDIR = os.path.join(DATA, ".logs")

# Phần "code": được đè khi VERSION mới — không chứa dữ liệu học viên
CODE_DIRS = ["web", "tools", "extension", "templates", "docs",
             "collector-web", "intro",
             os.path.join(".devin", "skill-packs")]
CODE_FILES = ["AGENTS.md", "CLAUDE.md", "SETUP.md", "README.md",
              "requirements.txt", "VERSION", "start.sh", "start.bat"]
# Phần "dữ liệu": chỉ đổ vào lần đầu, update KHÔNG bao giờ đè
SEED_DIRS = ["workspace"]
SEED_FILES = ["brain.json"]

def _read(fp, default=""):
    try:
        with open(fp, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return default

def _copy_tree(src, dst, overwrite):
    """Copy cây thư mục; overwrite=False thì bỏ qua file đã có."""
    for root, dirs, files in os.walk(src):
        # clone-work = workspace clone site thật — DOM bên thứ 3, phình
        # và không phải seed; skills chỉ cài từ skill-packs
        dirs[:] = [d for d in dirs
                   if d not in ("__pycache__", ".git", "skills", "clone-work")]
        rel = os.path.relpath(root, src)
        for f in files:
            if f.endswith((".pyc", ".log")) or f == "bridge.token":
                continue
            s, d = os.path.join(root, f), os.path.join(dst, rel, f)
            if not overwrite and os.path.exists(d):
                continue
            os.makedirs(os.path.dirname(d), exist_ok=True)
            shutil.copy2(s, d)

def apply_pending():
    """Áp bản update.py đã stage (`.devin/update-pending.json` +
    `update-stage/`) — chạy TRƯỚC supervisor nên file code không bị
    process con khoá (Windows). Code cũ giữ lại `.devin/backup-code-*`
    để `troly --rollback` dựng lại. Trả ver mới áp, hoặc None."""
    devin = os.path.join(DATA, ".devin")
    pend_fp = os.path.join(devin, "update-pending.json")
    stage = os.path.join(devin, "update-stage")
    if os.path.abspath(DATA) == os.path.abspath(SRC):
        return None                    # DATA trùng SRC (dev) — bỏ qua
    try:
        pend = json.load(open(pend_fp, encoding="utf-8"))
    except Exception:
        return None
    if not pend.get("ver") or not os.path.isdir(stage):
        return None
    # chụp code hiện tại trước khi đè — giữ 2 bản gần nhất
    back = os.path.join(devin,
                        "backup-code-" + time.strftime("%Y%m%d-%H%M%S"))
    os.makedirs(back, exist_ok=True)
    for d in CODE_DIRS:
        s = os.path.join(DATA, d)
        if os.path.isdir(s):
            shutil.copytree(s, os.path.join(back, d))
    for f in CODE_FILES:
        s = os.path.join(DATA, f)
        if os.path.isfile(s):
            shutil.copy2(s, os.path.join(back, f))
    # stage chỉ chứa path đã qua whitelist của update.py — copy đè
    for item in os.listdir(stage):
        s = os.path.join(stage, item)
        d = os.path.join(DATA, item)
        if os.path.isdir(s):
            shutil.copytree(s, d, dirs_exist_ok=True)
        else:
            shutil.copy2(s, d)
    with open(os.path.join(DATA, "VERSION"), "w") as f:
        f.write(str(pend["ver"]))
    shutil.rmtree(stage, ignore_errors=True)
    os.remove(pend_fp)
    backs = sorted(b for b in os.listdir(devin)
                   if b.startswith("backup-code-")
                   and os.path.isdir(os.path.join(devin, b)))
    for old in backs[:-2]:
        shutil.rmtree(os.path.join(devin, old), ignore_errors=True)
    return str(pend["ver"])

def rollback():
    """`troly --rollback` — dựng lại code từ backup-code mới nhất khi
    bản vừa áp hỏng (crash-loop). Version file cũng quay theo."""
    devin = os.path.join(DATA, ".devin")
    backs = sorted(b for b in os.listdir(devin)
                   if b.startswith("backup-code-")
                   and os.path.isdir(os.path.join(devin, b))) \
        if os.path.isdir(devin) else []
    if not backs:
        print("Không có bản code dự phòng nào để quay lại.")
        return
    src = os.path.join(devin, backs[-1])
    for item in os.listdir(src):
        s, d = os.path.join(src, item), os.path.join(DATA, item)
        if os.path.isdir(s):
            shutil.rmtree(d, ignore_errors=True)
            shutil.copytree(s, d)
        else:
            shutil.copy2(s, d)
    ver = _read(os.path.join(src, "VERSION"), "?")
    print(f"Đã quay về bản trước (v{ver}). Mở lại Trợ Lý AI là xong.")

def bootstrap():
    """Áp staged update (nếu có), rồi bung payload vào DATA + đè code
    khi VERSION nguồn đổi. Trả về bool 'đã update code'."""
    os.makedirs(DATA, exist_ok=True)
    # migrate: folder dữ liệu đổi tên my-course → workspace (sản phẩm
    # không còn là "khoá học" mà là bộ công cụ). Cả hai cùng có thì gom
    # phần thiếu vào workspace rồi bỏ my-course.
    old = os.path.join(DATA, "my-course")
    new = os.path.join(DATA, "workspace")
    if os.path.isdir(old):
        if not os.path.isdir(new):
            os.rename(old, new)
        else:
            _copy_tree(old, new, overwrite=False)
            shutil.rmtree(old, ignore_errors=True)
        # file text trong DATA có thể trỏ "my-course" (agent.sb quyền
        # ghi, permissions.json, html clone…) — rewrite cho khỏi lệch
        for dp, dns, fns in os.walk(DATA):
            dns[:] = [d for d in dns if d not in
                      (".logs", "node", ".trash", "__pycache__")]
            for fn in fns:
                if not fn.endswith((".json", ".md", ".sb", ".html",
                                    ".js", ".txt", ".jsonl")):
                    continue
                fp = os.path.join(dp, fn)
                try:
                    if os.path.getsize(fp) > 1_000_000:
                        continue
                    s = open(fp, encoding="utf-8").read()
                    if "my-course" in s:
                        open(fp, "w", encoding="utf-8").write(
                            s.replace("my-course", "workspace"))
                except (OSError, UnicodeDecodeError):
                    continue
    applied = apply_pending()
    src_ver, dst_ver = _read(os.path.join(SRC, "VERSION"), "0"), \
                       _read(os.path.join(DATA, "VERSION"), "")
    fresh = not dst_ver
    if fresh or (src_ver != dst_ver and not applied):
        # đã áp staged update thì không đè lại bằng payload nguồn —
        # staged là bản MỚI HơN exe/bundle đang chạy
        for d in CODE_DIRS:
            s = os.path.join(SRC, d)
            if os.path.isdir(s):
                _copy_tree(s, os.path.join(DATA, d), overwrite=True)
        for f in CODE_FILES:
            s = os.path.join(SRC, f)
            if os.path.isfile(s):
                shutil.copy2(s, os.path.join(DATA, f))
    if fresh:                       # seed dữ liệu chỉ lần đầu
        for d in SEED_DIRS:
            s = os.path.join(SRC, d)
            if os.path.isdir(s):
                _copy_tree(s, os.path.join(DATA, d), overwrite=False)
        for f in SEED_FILES:
            s = os.path.join(SRC, f)
            if os.path.isfile(s) and not os.path.exists(os.path.join(DATA, f)):
                shutil.copy2(s, os.path.join(DATA, f))
    os.makedirs(os.path.join(DATA, ".devin"), exist_ok=True)
    os.makedirs(LOGDIR, exist_ok=True)
    return bool(applied) or (not fresh and src_ver != dst_ver)

def ensure_token():
    """Sinh 'chìa khoá nhà' MỚI mỗi lần start, TRƯỚC khi spawn child —
    audit 2-tầng: token trước đây persist mãi, same-user process đọc
    được là lái mọi bridge. Rotate miễn phí vì child đọc file lúc
    boot (chat/ext-bridge) hoặc lazy mỗi cycle (beacon); session
    extension đang sống thì chết cùng restart — vốn đã reset state."""
    fp = os.path.join(DATA, ".devin", "bridge.token")
    tok = secrets.token_hex(24)
    fd = os.open(fp, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
    os.write(fd, tok.encode()); os.close(fd)
    try:
        os.chmod(fp, 0o600)   # file từ bản cũ — siết lại perm
    except OSError:
        pass
    os.environ["BRIDGE_TOKEN"] = tok
    return tok

# ---------- vai con: chạy tools/<name>.py trong DATA ----------

def run_tool(name, argv):
    script = os.path.join(DATA, "tools", name + ".py")
    if not os.path.isfile(script):
        script = os.path.join(SRC, "tools", name + ".py")   # fallback source
    sys.argv = [script] + argv
    runpy.run_path(script, run_name="__main__")

def run_tool_silent(name, argv):
    """Subprocess im lặng cho tool chạy nền (update --check…) — KHÔNG
    dùng run_tool: runpy đổi sys.argv chung, gọi từ thread sẽ phá.
    FROZEN: sys.executable là troly.exe — gọi qua vai con `troly <name>`
    chứ không truyền path .py (exe không chạy file py được — argv lạ rơi
    vào `troly run` → supervisor thứ hai)."""
    if FROZEN:
        cmd = [sys.executable, name] + argv
    else:
        script = os.path.join(DATA, "tools", name + ".py")
        if not os.path.isfile(script):
            return
        cmd = [sys.executable, script] + argv
    try:
        subprocess.Popen(cmd, cwd=DATA,
                         stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    except Exception:
        pass

# ---------- supervisor ----------

def child_cmd(name, port=None):
    # port=None cho vai không có cổng (beacon — chỉ cần DATA)
    args = [] if port is None else [str(port)]
    if FROZEN:
        return [sys.executable, name] + args + [DATA]
    return [sys.executable, os.path.join(DATA, "tools", name + ".py")] \
        + args + [DATA]

def spawn(name, cmd, log_fp):
    log = open(log_fp, "ab", buffering=0)
    return subprocess.Popen(cmd, cwd=DATA, env=os.environ.copy(),
                            stdout=log, stderr=subprocess.STDOUT)

def terminal_enabled():
    # Tab Terminal trong portal là tuỳ chọn nâng cao (Cài đặt → Nâng cao).
    # Mặc định TẮT: không spawn ttyd → tiết kiệm RAM + học viên không
    # lạc vào màn hình đen. Bật trong Cài đặt → config.terminal=true.
    try:
        cfg = json.load(open(os.path.join(DATA, "workspace", "config.json"),
                             encoding="utf-8"))
        return bool(cfg.get("terminal"))
    except Exception:
        return False


def brain_terminal():
    try:
        return json.load(open(os.path.join(DATA, "brain.json"),
                              encoding="utf-8")).get("terminal") or "devin"
    except Exception:
        return "devin"

STOPPING = False

def supervisor():
    """Spawn mọi child rồi chạy watchdog — gọi ở MAIN thread (signal chỉ
    đăng ký được ở main thread). Trả khi STOPPING, đã terminate hết con."""
    jobs = [("serve", 8080), ("chat-bridge", 7682), ("ext-bridge", 7684)]
    if os.path.isfile(os.path.join(DATA, ".devin", "fleet.json")):
        # máy thuộc fleet của một cty — beacon đẩy snapshot lên collector
        # (push, không mở port; thiếu file → máy cá nhân, không spawn)
        jobs.append(("beacon", None))
    if platform.system() == "Darwin":
        # Sinh Seatbelt profile trước khi spawn — term-gate bọc não theo
        # file này; chat-bridge regen mỗi spawn nên đây chỉ là phòng bị
        # cho Terminal mode và spawn đầu. Lỗi → unsandboxed, không kẹt boot.
        try:
            run_tool("gen-sandbox", [DATA])
        except Exception:
            pass
    if shutil.which("ttyd") and terminal_enabled():
        # ttyd không tự xác thực được → spawn qua term-gate (đòi mã kết nối
        # trong shell trước khi exec não); -a để portal tự điền mã qua ?arg=.
        # term-gate.* nằm trong tools/ → CODE_DIRS đã copy sang DATA.
        os.environ["BRAIN_TERM"] = brain_terminal()
        if platform.system() == "Windows":
            # PHẢI là .ps1: ?arg= đi qua %1 trong .cmd là re-lex injection
            # (" phá quote → & chạy lệnh); PowerShell nhận argv an toàn
            gate = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                    "-File", os.path.join(DATA, "tools", "term-gate.ps1")]
        else:
            gate = ["sh", os.path.join(DATA, "tools", "term-gate.sh")]
        jobs.append(("ttyd", ["ttyd", "-p", "7681", "-i", "127.0.0.1",
                              "-W", "-a", "-O"] + gate))
    procs, fails, born = {}, {n: 0 for n, _ in jobs}, {}

    def cmd_of(n, spec):
        return spec if isinstance(spec, list) else child_cmd(n, spec)

    for n, spec in jobs:
        procs[n] = spawn(n, cmd_of(n, spec), os.path.join(LOGDIR, n + ".log"))
        born[n] = time.time()

    while not STOPPING:
        time.sleep(1)
        for n, spec in jobs:
            p = procs[n]
            if p.poll() is None:
                continue
            # chết sớm (<10s sống) = crash-loop → tính fail; sống lâu rồi
            # chết là sự cố bình thường → bật lại ngay, không tính
            fails[n] = fails[n] + 1 if time.time() - born[n] < 10 else 0
            if fails[n] > 5:
                continue                  # crash-loop → bỏ, portal báo offline
            if n == "ttyd" and not terminal_enabled():
                continue                  # user vừa tắt Terminal → để chết
            time.sleep(2)
            procs[n] = spawn(n, cmd_of(n, spec), os.path.join(LOGDIR, n + ".log"))
            born[n] = time.time()

    for p in procs.values():
        try:
            p.terminate()
        except Exception:
            pass

def wait_health(url, tries=50):
    for _ in range(tries):
        try:
            urllib.request.urlopen(url, timeout=1).read()
            return True
        except Exception:
            time.sleep(0.2)
    return False

# ---------- tự chạy cùng máy ----------

def register_startup(on):
    # argv đầy đủ để chạy "troly run" — frozen: exe trần; source: python + launcher
    argv = [os.path.abspath(sys.executable)] if FROZEN else \
           [sys.executable, os.path.abspath(__file__)]
    cmdline = " ".join(f'"{p}"' for p in argv) + " run"
    if platform.system() == "Windows":
        import winreg
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_SET_VALUE)
        try:
            if on:
                winreg.SetValueEx(k, "TroLyAI", 0, winreg.REG_SZ, cmdline)
            else:
                winreg.DeleteValue(k, "TroLyAI")
        finally:
            winreg.CloseKey(k)
    elif platform.system() == "Darwin":
        fp = os.path.expanduser("~/Library/LaunchAgents/ai.troly.plist")
        if on:
            os.makedirs(os.path.dirname(fp), exist_ok=True)
            with open(fp, "w", encoding="utf-8") as f:
                f.write(f"""<?xml version="1.0" encoding="UTF-8"?>
<plist version="1.0"><dict>
<key>Label</key><string>ai.troly</string>
<key>ProgramArguments</key><array>{"".join(f"<string>{p}</string>" for p in argv)}<string>run</string></array>
<key>RunAtLoad</key><true/></dict></plist>""")
        elif os.path.exists(fp):
            os.remove(fp)
    else:
        fp = os.path.expanduser("~/.config/autostart/troly.desktop")
        if on:
            os.makedirs(os.path.dirname(fp), exist_ok=True)
            with open(fp, "w", encoding="utf-8") as f:
                f.write(f"[Desktop Entry]\nType=Application\nName=TroLyAI\nExec={cmdline}\n")
        elif os.path.exists(fp):
            os.remove(fp)
    print(("đã bật" if on else "đã tắt") + " tự chạy cùng máy")

# ---------- main ----------

def _stop(*_):
    global STOPPING
    STOPPING = True

def main():
    a = sys.argv[1:]
    if a and a[0] in ("serve", "chat-bridge", "ext-bridge", "beacon",
                      "update", "apply-pack", "backup", "gen-sandbox",
                      "install-brain", "ensure-deps"):
        run_tool(a[0], a[1:])
        return
    if "--register-startup" in a or "--unregister-startup" in a:
        register_startup("--register-startup" in a)
        return
    if "--rollback" in a:
        rollback()
        return
    # mặc định: `troly` hoặc `troly run`
    updated = bootstrap()
    # gói Python cho skill Excel/Word — venv riêng trong DATA, fire-and-
    # forget (Popen không chặn); đã đủ thì script tự về ngay. Chạy cả khi
    # instance khác đang giữ port: deps có thể thiếu sau update mới.
    run_tool_silent("ensure-deps", [DATA])
    try:
        # health-check TRƯỚC rotate: instance cũ còn giữ token cũ trong
        # memory — ghi đè file ở đây phá portal (?t=T2 vs bridge giữ T1
        # → 401) và beacon (đọc lazy mỗi cycle → bridge_get fail mãi)
        urllib.request.urlopen("http://127.0.0.1:7682/api/health", timeout=1)
        tok = _read(os.path.join(DATA, ".devin", "bridge.token"))
        webbrowser.open(f"http://localhost:8080/web/?t={tok}")
        print("Trợ Lý AI đang chạy sẵn — đã mở lại portal.")
        return                                     # instance khác đang chạy
    except Exception:
        pass
    tok = ensure_token()    # chỉ rotate khi thật sự start mới
    if updated:
        print(f"Cập nhật phần mềm xong (v{_read(os.path.join(DATA, 'VERSION'))}).")
    print(f"Mở Trợ Lý AI… dữ liệu nằm ở {DATA}")
    signal.signal(signal.SIGINT, _stop); signal.signal(signal.SIGTERM, _stop)
    # mở portal ngay khi bridge sống — thread phụ, supervisor chạy main thread
    import threading
    def _open_when_ready():
        if wait_health("http://127.0.0.1:7682/api/health"):
            webbrowser.open(f"http://localhost:8080/web/?t={tok}")
        else:
            print(f"Portal: http://localhost:8080/web/?t={tok}")
    threading.Thread(target=_open_when_ready, daemon=True).start()
    # check update lúc boot — thread phụ (timeout 3s trong update.py
    # --check), kéo về + stage xong sẽ áp ở lần mở app sau
    threading.Thread(
        target=lambda: run_tool_silent("update", [DATA, "--check"]),
        daemon=True).start()
    supervisor()                                   # tới khi Ctrl-C / kill

if __name__ == "__main__":
    main()
