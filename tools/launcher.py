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
CODE (CODE_DIRS/CODE_FILES), không đụng my-course/, brain.json, .devin/
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
             os.path.join(".devin", "skill-packs")]
CODE_FILES = ["AGENTS.md", "CLAUDE.md", "SETUP.md", "README.md",
              "requirements.txt", "VERSION"]
# Phần "dữ liệu": chỉ đổ vào lần đầu, update KHÔNG bao giờ đè
SEED_DIRS = ["my-course"]
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

def bootstrap():
    """Bung payload vào DATA; update-đè-code khi VERSION đổi. Trả về bool
    'đã update code' — caller báo học viên nếu cần."""
    src_ver, dst_ver = _read(os.path.join(SRC, "VERSION"), "0"), \
                       _read(os.path.join(DATA, "VERSION"), "")
    os.makedirs(DATA, exist_ok=True)
    fresh = not dst_ver
    if fresh or src_ver != dst_ver:
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
    return not fresh and src_ver != dst_ver

def ensure_token():
    """Sinh 'chìa khoá nhà' một lần, TRƯỚC khi spawn child — cùng thiết kế
    start.sh (child fallback vẫn có nhưng không bao giờ phải chạy)."""
    fp = os.path.join(DATA, ".devin", "bridge.token")
    tok = _read(fp)
    if not tok:
        tok = secrets.token_hex(24)
        fd = os.open(fp, os.O_CREAT | os.O_WRONLY, 0o600)
        os.write(fd, tok.encode()); os.close(fd)
    os.environ["BRIDGE_TOKEN"] = tok
    return tok

# ---------- vai con: chạy tools/<name>.py trong DATA ----------

def run_tool(name, argv):
    script = os.path.join(DATA, "tools", name + ".py")
    if not os.path.isfile(script):
        script = os.path.join(SRC, "tools", name + ".py")   # fallback source
    sys.argv = [script] + argv
    runpy.run_path(script, run_name="__main__")

# ---------- supervisor ----------

def child_cmd(name, port):
    if FROZEN:
        return [sys.executable, name, str(port), DATA]
    return [sys.executable, os.path.join(DATA, "tools", name + ".py"), str(port), DATA]

def spawn(name, cmd, log_fp):
    log = open(log_fp, "ab", buffering=0)
    return subprocess.Popen(cmd, cwd=DATA, env=os.environ.copy(),
                            stdout=log, stderr=subprocess.STDOUT)

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
    if platform.system() == "Darwin":
        # Sinh Seatbelt profile trước khi spawn — term-gate bọc não theo
        # file này; chat-bridge regen mỗi spawn nên đây chỉ là phòng bị
        # cho Terminal mode và spawn đầu. Lỗi → unsandboxed, không kẹt boot.
        try:
            run_tool("gen-sandbox", [DATA])
        except Exception:
            pass
    if shutil.which("ttyd"):
        # ttyd không tự xác thực được → spawn qua term-gate (đòi mã kết nối
        # trong shell trước khi exec não); -a để portal tự điền mã qua ?arg=.
        # term-gate.* nằm trong tools/ → CODE_DIRS đã copy sang DATA.
        os.environ["BRAIN_TERM"] = brain_terminal()
        if platform.system() == "Windows":
            gate = ["cmd", "/c", os.path.join(DATA, "tools", "term-gate.cmd")]
        else:
            gate = ["sh", os.path.join(DATA, "tools", "term-gate.sh")]
        jobs.append(("ttyd", ["ttyd", "-p", "7681", "-i", "127.0.0.1",
                              "-W", "-a"] + gate))
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
    if a and a[0] in ("serve", "chat-bridge", "ext-bridge"):
        run_tool(a[0], a[1:])
        return
    if "--register-startup" in a or "--unregister-startup" in a:
        register_startup("--register-startup" in a)
        return
    # mặc định: `troly` hoặc `troly run`
    updated = bootstrap()
    tok = ensure_token()
    try:
        urllib.request.urlopen("http://127.0.0.1:7682/api/health", timeout=1)
        webbrowser.open(f"http://localhost:8080/web/?t={tok}")
        print("Trợ Lý AI đang chạy sẵn — đã mở lại portal.")
        return                                     # instance khác đang chạy
    except Exception:
        pass
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
    supervisor()                                   # tới khi Ctrl-C / kill

if __name__ == "__main__":
    main()
