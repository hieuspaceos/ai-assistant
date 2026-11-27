#!/usr/bin/env python3
"""install-brain.py — cài "não" cho onboarding bằng một nút bấm.

Chạy: install-brain.py <brain-id> <DATA>   (DATA = ~/TroLyAI)

Hai não cài tự động được:
  gemini — tải Node bản portable về DATA/node (không cần admin/brew/
           winget) rồi `npm install -g @google/gemini-cli`. gemini.cmd
           nằm trong node dir → chat-bridge prepend dir đó vào PATH.
  devin  — installer chính thức của Devin (irm|iex trên Windows,
           curl|bash trên macOS/Linux). Cài về ~/.local/bin.

Tiến trình ghi ra stdout dạng JSON-line VÀ file trạng thái
`.devin/install-brain.json` — bridge đọc file này trả cho onboarding
poll (sống được qua cả restart bridge).

Cài xong não vẫn cần ĐĂNG NHẬP (OAuth trình duyệt) — onboarding mở
terminal chạy `gemini`/`devin` qua POST /api/install-brain {"login":1}.
"""
import hashlib, json, os, platform, shutil, subprocess, sys, tarfile
import tempfile, time, urllib.request, zipfile

NODE_VER = "v26.13.1"
NODE_BASE = f"https://nodejs.org/dist/{NODE_VER}/"
NODE_DIST = {
    ("Windows", "AMD64"):  (f"node-{NODE_VER}-win-x64.zip",
        "e2edda75bfb089654705cf65a13b58933bfd5f57148e8ebda916f58a2474f1f7"),
    ("Darwin", "arm64"):   (f"node-{NODE_VER}-darwin-arm64.tar.gz",
        "aec2514ea1ceb2ba52455e9ec65986f6749a06dd759e5db2a72e6889668c9735"),
    ("Darwin", "x86_64"):  (f"node-{NODE_VER}-darwin-x64.tar.gz",
        "82bb96078a24ca50b9c9a38f2379e6be6d87171fcd400fc14c8934b3bce96e2f"),
    ("Linux", "x86_64"):   (f"node-{NODE_VER}-linux-x64.tar.gz",
        "518674de2b621728a5e4486f5fb3b7d2900bb3cc4aa97969edaa463db99f9778"),
}

BRAIN = sys.argv[1] if len(sys.argv) > 1 else ""
DATA = os.path.abspath(
    sys.argv[2] if len(sys.argv) > 2 else os.path.expanduser("~/TroLyAI"))
STATE_FP = os.path.join(DATA, ".devin", "install-brain.json")
LOG = []
WIN = platform.system() == "Windows"

def state(st, step=""):
    os.makedirs(os.path.dirname(STATE_FP), exist_ok=True)
    with open(STATE_FP, "w", encoding="utf-8") as f:
        json.dump({"id": BRAIN, "state": st, "step": step,
                   "log": LOG[-30:], "ts": int(time.time())}, f)

def say(msg, step=""):
    LOG.append(msg)
    print(json.dumps({"step": step, "msg": msg}, ensure_ascii=False),
          flush=True)
    state("running", step)

def fail(msg):
    say("!! " + msg, "error")
    state("error")
    sys.exit(1)

def bin_dirs():
    """Chỗ não cài lén nằm — bridge prepend cùng list này vào PATH."""
    d = [os.path.join(DATA, "node", "bin"),   # node portable unix
         os.path.join(DATA, "node"),          # node portable windows
         os.path.expanduser("~/.local/bin")]  # devin installer
    return [x for x in d if os.path.isdir(x)]

def path_env():
    return os.pathsep.join(bin_dirs() + [os.environ.get("PATH", "")])

def which(cmd):
    return shutil.which(cmd, path=path_env())

def env():
    e = os.environ.copy()
    e["PATH"] = path_env()
    return e

def run(cmd, step):
    """Chạy lệnh cài, stream output về log; fail → exit 1."""
    say("$ " + " ".join(str(c) for c in cmd), step)
    if WIN and str(cmd[0]).lower().endswith((".cmd", ".bat")):
        cmd = [os.environ.get("COMSPEC", "cmd.exe"), "/c"] + list(cmd)
    p = subprocess.Popen([str(c) for c in cmd], cwd=DATA, env=env(),
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True, errors="replace")
    out = []
    for line in p.stdout:
        line = line.rstrip()
        if line:
            out.append(line)
            say("   " + line[:200], step)
    p.wait()
    if p.returncode != 0:
        fail(f"lệnh chạy sai (code {p.returncode}) — xem log phía trên")
    return out

def sha256(fp):
    h = hashlib.sha256()
    with open(fp, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def fetch(url, dst, want_sha):
    say("tải " + url, "node")
    urllib.request.urlretrieve(url, dst)     # nodejs.org không redirect
    if want_sha and sha256(dst) != want_sha:
        fail("file tải lệch chữ ký sha256 — hủy cài")

def ensure_node():
    """node+npm sẵn trên PATH (kể cả bundle cũ) → bỏ qua; không thì tải
    bản portable về DATA/node — không cần admin/winget/brew."""
    if which("node") and which("npm"):
        say("node đã có sẵn", "node")
        return
    key = (platform.system(), platform.machine())
    fname, want_sha = NODE_DIST.get(key, (None, None))
    if not fname:
        fail("chưa hỗ trợ tải node trên "
             f"{platform.system()}/{platform.machine()} — cài node tay")
    tmpd = tempfile.mkdtemp(prefix="troly-node-")
    arc = os.path.join(tmpd, fname)
    fetch(NODE_BASE + fname, arc, want_sha)
    say("giải nén node…", "node")
    exd = os.path.join(tmpd, "x")
    if fname.endswith(".zip"):
        with zipfile.ZipFile(arc) as z:
            z.extractall(exd)
    else:
        with tarfile.open(arc) as t:
            try:
                t.extractall(exd, filter="data")
            except TypeError:        # python <3.12 chưa có filter=
                t.extractall(exd)
    inner = os.path.join(exd,
        fname.replace(".tar.gz", "").replace(".zip", ""))
    dst = os.path.join(DATA, "node")
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    shutil.move(inner, dst)
    shutil.rmtree(tmpd, ignore_errors=True)
    if not which("node") or not which("npm"):
        fail("giải nén xong nhưng không thấy node/npm trong " + dst)
    say("node " + NODE_VER + " cài xong vào " + dst, "node")

def install_gemini():
    ensure_node()
    npm = which("npm")
    # --prefix cố định DATA/node: gemini luôn rơi vào chỗ bridge đã biết
    # (node hệ thống hay node bundle đều không ảnh hưởng)
    prefix = os.path.join(DATA, "node")
    os.makedirs(prefix, exist_ok=True)
    run([npm, "install", "-g", "--prefix", prefix,
         "@google/gemini-cli"], "gemini")
    if not which("gemini"):
        fail("npm xong nhưng không thấy lệnh gemini — thử lại")
    say("gemini CLI cài xong — còn bước đăng nhập Google", "gemini")

def install_devin():
    if WIN:
        run(["powershell", "-NoProfile", "-Command",
             "irm https://cli.devin.ai/install.ps1 | iex"], "devin")
    else:
        run(["bash", "-c",
             "curl -fsSL https://cli.devin.ai/install.sh | bash"], "devin")
    if not which("devin"):
        fail("installer xong nhưng không thấy lệnh devin — mở lại app rồi kiểm tra")
    say("devin CLI cài xong — còn bước đăng nhập", "devin")

INSTALLERS = {"gemini": install_gemini, "devin": install_devin}

def main():
    fn = INSTALLERS.get(BRAIN)
    if not fn:
        fail(f"không có installer cho '{BRAIN}' — cài tay theo trang hãng")
    state("running")
    say(f"bắt đầu cài não '{BRAIN}'…")
    try:
        fn()
    except SystemExit:
        raise
    except Exception as e:
        fail(str(e))
    state("done")
    print(json.dumps({"step": "done", "msg": "xong"}, ensure_ascii=False))

if __name__ == "__main__":
    main()
