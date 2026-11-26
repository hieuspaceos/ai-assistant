#!/usr/bin/env python3
"""gen-sandbox.py — sinh Seatbelt profile (.devin/agent.sb) từ permissions.json.

Biến permissions.json từ "văn xuôi nhờ não nghe" thành enforcement kernel:
profile (deny default); GHI = whitelist subpath thuần; ĐỌC = vì bug
compiler trên macOS mới (`allow process*` chỉ compile khi profile có
`file-read*` phủ tới "/"), whitelist-đọc phải dựng ngược — allow đọc "/"
rồi DUYỆT CÂY deny mọi sibling không nằm trên đường tới thư mục được phép
(deny thắng allow, đã verify trên Darwin 27).

Dùng:
    python3 tools/gen-sandbox.py [cwd]          # ghi <cwd>/.devin/agent.sb

chat-bridge.py cũng nạp file này qua runpy gọi build_profile() khi spawn
não — một nguồn logic, không subprocess, chạy được cả trong binary đóng
gói (không có python ngoài). Chỉ có nghĩa trên macOS (Seatbelt); Windows
dùng user-account + NTFS ACL (setup-agent-user.ps1)."""
import json, os, shutil, sys

# runpy.run_path KHÔNG add script-dir vào sys.path → `troly gen-sandbox`
# frozen (sys.path=_MEIPASS, không có _MEIPASS/tools) sẽ không resolve
# được sibling import. BẮT BUỘC bootstrap như chat-bridge.py — thiếu dòng
# này = import hỏng bị try/except nuốt → spawn não KHÔNG Seatbelt.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from path_guard import path_sensitive, rw_grant_ok   # noqa: E402

def _esc(p):
    return p.replace("\\", "\\\\").replace('"', '\\"')

def _sub(op, paths):
    return "(allow " + op + " " + " ".join(
        f'(subpath "{_esc(p)}")' for p in sorted(paths)) + ")"

def _rp(p):
    """Path canonical — Seatbelt so trên đường đã resolve symlink
    (/tmp thật ra là /private/tmp → emit cả hai dạng)."""
    return os.path.normpath(os.path.realpath(p))

# Home/state dir của từng não — đều là file "của chính app não" (não bắt
# buộc đọc credentials của nó để chạy, ghi session db để tạo session, ghi
# lại token khi refresh). Không có trong write-allowlist → ACP session/new
# lỗi "Internal error" / "readonly database" ngay lúc bắt tay.
BRAIN_HOME = {
    "devin":    (".local/share/devin", ".config/devin"),
    "gemini":   (".gemini",),
    "codex":    (".codex",),
    "claude":   (".claude", ".claude.json"),
    "opencode": (".local/share/opencode", ".config/opencode"),
}

def _emit_paths(paths):
    """Mỗi path emit raw + realpath — deny/allow đều cần đúng canonical."""
    out = set()
    for p in paths:
        if not p:
            continue
        out.add(os.path.normpath(os.path.abspath(os.path.expanduser(p))))
        out.add(_rp(os.path.abspath(os.path.expanduser(p))))
    return out

def _deny_siblings(allowed):
    """Đọc-whitelist ngược: duyệt "/" xuống, deny mọi entry không nằm dưới
    một thư mục được phép và cũng không dẫn tới thư mục được phép. Entry
    dẫn tới thư mục được phép (ancestor) → đào tiếp, không deny cả nhánh.
    Giới hạn /Users + các nhánh chứa allowed root (Volumes…) — vùng user
    data. Trả về set path cần deny."""
    denies = set()
    roots = {_rp(p) for p in allowed}

    def under_allowed(p):
        return any(p == a or p.startswith(a + os.sep) for a in roots)

    def leads_to_allowed(p):
        return any(a.startswith(p + os.sep) for a in roots)

    def cover(d):
        try:
            kids = os.listdir(d)
        except OSError:
            return                       # file/lỗi đọc — không đào được
        for k in kids:
            c = os.path.join(d, k)
            rc = _rp(c)
            if under_allowed(rc):
                continue                 # nằm trong vùng được phép
            if leads_to_allowed(rc):
                if os.path.isdir(c):
                    cover(c)             # mở đường xuống điểm được phép
            else:
                denies.add(c)            # deny cả dạng raw lẫn canonical
                denies.add(rc)

    for top in ("/Users", os.path.expanduser("~")):
        if os.path.isdir(top) and not under_allowed(_rp(top)):
            cover(top)
    # nhánh ngoài /Users chứa allowed root (VD /Volumes/data) cũng cần
    # deny sibling — duyệt từ "/" nhưng chỉ xuống nhánh leads_to_allowed
    for a in sorted(roots):
        parts = a.strip(os.sep).split(os.sep)
        if parts and parts[0] == "Users":
            continue                     # /Users đã cover
        cur = os.sep
        for part in parts[:-1]:
            cur = os.path.join(cur, part)
            cover(cur)                   # deny sibling ở mỗi tầng
    return denies

def _grant_ok(p, access, cwd):
    """Grant chỉ emit khi path còn đúng như lúc học viên duyệt — chặn
    TOCTOU symlink (audit-3 CAO-2): agent grant my-course/x (hợp lệ) rồi
    rmdir + ln -s ~/Library/LaunchAgents x trước spawn → request-time
    check đã qua nhưng realpath ở ĐÂY (enforcement point) bắt được.

    Hai check độc lập, thiếu cái nào cũng còn lỗ:
    - path_sensitive: realpath đích rơi vào folder nhạy cảm → chặn.
    - Divergence: realpath khác normpath = có symlink component TRÊN
      đường đi — kể cả đích KHÔNG nhạy cảm (ln -s ~/Documents x) vẫn
      chặn, vì card chỉ hiện "my-course/x" chứ sandbox lại được quyền
      ~/Documents. Cho qua duy nhất canonicalization /private của macOS
      (/tmp,/var,/etc → /private/*). So .lower(): APFS không phân biệt
      hoa-thường, grant gõ "~/documents" không bị drop oan.
    Trade-off đã cân: folder thật nằm sau symlink (Documents → ổ ngoài)
    sẽ bị drop — hiếm, an toàn hơn, và _apply báo err thấy được."""
    if path_sensitive(p):          # realpath bên trong — đích symlink
        return False               # vào sensitive đã bị chặn ở đây luôn
    np = os.path.normpath(os.path.abspath(os.path.expanduser(p)))
    rp = os.path.realpath(p)
    if rp.lower() != np.lower() \
            and rp.lower() != ("/private" + np).lower():
        return False
    if access == "read-write" and not rw_grant_ok(p, cwd):
        return False
    return True

def build_profile(cwd):
    """Trả về nội dung profile Seatbelt cho process não chạy tại `cwd`."""
    cwd = os.path.abspath(cwd)
    home = os.path.expanduser("~")
    L = ["(version 1)",
         "(deny default)",
         ";; fork/exec/IPC — siết file+net la du",
         "(allow process*)",
         "(allow mach* sysctl-read file-read-metadata)",
         ";; nao BAT BUOC goi API LLM + bridge localhost — residual: exfil",
         ";; qua outbound van duoc, do la gioi han co huu cua 'nao can net'",
         "(allow network-outbound)",
         "(deny network-bind network-inbound)",
         ";; osascript = AppleEvents — kenh vuot mat file-sandbox (lai",
         ";; app khac, doc man hinh, lay cookie Safari). Nao khong can.",
         '(deny process-exec (literal "/usr/bin/osascript"))',
         ";; Binary 'thoat sandbox' (open/launchctl/security/pbpaste...) bi",
         ";; deny file-read* o cuoi profile — deny-exec literal bi lach bang",
         ";; `cp binary tmp/x`, con khong doc duoc thi khong exec duoc.",
         ";; TUI cua nao (che do Terminal qua ttyd) ioctl pty de lay size/",
         ";; mode — deny default chan -> 'Scrollback error: io error'.",
         '(allow file-ioctl (regex #"^/dev/ttys[0-9]+$")',
         '        (literal "/dev/tty") (literal "/dev/ptmx"))',
         ";; COMPILER QUIRK (Darwin 27): 'allow process*' chi compile khi",
         ";; profile co file-read* phu toi '/' — whitelist-doc thuan lam",
         ";; profile crash luc load. Doc duoc gate lai bang deny enumeration.",
         _sub("file-read*", ["/"])]

    # --- vùng WRITE (whitelist thuần) — CHỈ 3 vùng, đúng luật AGENTS.md:
    # "file cho học viên chỉ trong my-course/ hoặc folder được cấp quyền".
    # Trước đây rw={cwd} → não bị lừa ghi được tools/*.py, brain.json,
    # permissions.json = tự cấp quyền + đặt payload chạy NGOÀI sandbox.
    tmps = {"/tmp", "/private/tmp", "/var/tmp"}
    t = os.environ.get("TMPDIR")
    if t:
        tmps.add(os.path.realpath(t))
    sysw = {os.path.join(home, d) for d in (
        ".npm", ".cache", ".pnpm-store", "Library/Caches")}
    rw = {os.path.join(cwd, "my-course"),
          os.path.join(cwd, ".devin", "skills"),
          os.path.join(cwd, ".logs")} | tmps | sysw

    # --- vùng READ bổ sung (system + tool dirs) ---
    sysr = {"/usr", "/System", "/bin", "/sbin", "/Library", "/opt",
            "/private/etc", "/private/var", "/dev"}
    sysr |= {os.path.join(home, d) for d in (
        ".nvm", ".local", ".pyenv", ".volta", ".asdf", ".cargo", ".rustup",
        ".deno", ".bun", ".gem", ".rbenv", "go",
        "Library/Python", "Library/pnpm")}
    # não vẫn ĐỌC được cả project (AGENTS.md, tools/, templates/) — chỉ
    # vùng ghi siết xuống allowlist
    ro = set(sysr) | {cwd}

    # auto-allow cha của binary não đang dùng — não cài chỗ lạ vẫn đọc lib được
    try:
        brain = json.load(open(os.path.join(cwd, "brain.json"),
                               encoding="utf-8"))
        exe = shutil.which(brain.get("cmd") or "") or shutil.which(
            brain.get("terminal") or "")
        if exe:
            ro.add(os.path.dirname(os.path.realpath(exe)))
        # state dir riêng của não đang chọn (xem BRAIN_HOME)
        bid = str(brain.get("id") or os.path.basename(exe or ""))
        for d in BRAIN_HOME.get(bid, ()):
            rw.add(os.path.join(home, d))
    except Exception:
        pass

    # permissions.json — đúng semantics access=read|read-write
    try:
        perm = json.load(open(os.path.join(cwd, "my-course",
                                           "permissions.json"),
                              encoding="utf-8"))
        for f in perm.get("folders", []):
            p = os.path.abspath(os.path.expanduser(str(f.get("path", ""))))
            if len(p) < 2:
                continue                     # bỏ qua "/" và rác
            # Re-validate TẠI enforcement point: request-time check trong
            # chat-bridge không chặn được symlink swap sau approve; file
            # permissions.json bị sửa tay cũng lọt nếu không kiểm lại ở
            # đây (grant divergent/sensitive → im lặng bỏ, như file mồ côi).
            if not _grant_ok(p, str(f.get("access", "")), cwd):
                continue
            (rw if f.get("access") == "read-write" else ro).add(p)
    except Exception:
        pass

    L.append(_sub("file-read* file-write*", _emit_paths(rw)))
    L.append(_sub("file-read*", _emit_paths(ro)))

    # Binary thoát-sandbox (xem comment ở header profile) — cần CẢ HAI:
    # process-exec chặn chạy binary thật, file-read* chặn `cp` ra chỗ khác
    # rồi exec bản copy (hardlink vào /usr/bin đã bị macOS chặn sẵn — đã
    # verify trên máy thật, chỉ copy là đường lách).
    for b in ("/usr/bin/open", "/bin/launchctl", "/usr/bin/crontab",
              "/usr/bin/at", "/usr/bin/atq", "/usr/bin/atrm",
              "/usr/bin/automator", "/usr/bin/osascript",
              "/usr/bin/security", "/usr/bin/pbcopy", "/usr/bin/pbpaste",
              "/usr/sbin/screencapture", "/usr/bin/tmutil"):
        L.append(f'(deny process-exec (literal "{b}"))')
        L.append(f'(deny file-read* (literal "{b}"))')
    # Kênh mach đi thẳng tới pboard — chặn cả đường FFI (ctypes/objc)
    # đọc clipboard qua AppKit, phòng khi binary nào đó sót.
    L.append('(deny mach-lookup (global-name "com.apple.pasteboard.1"))')

    # --- đọc-whitelist ngược: deny mọi vùng user data không được phép ---
    for d in sorted(_deny_siblings(rw | ro)):
        L.append(f'(deny file-read* (subpath "{_esc(d)}"))')

    # --- carve-out trong CWD — deny thắng allow bất kể thứ tự ---
    # bridge.token: não ĐỌC được (cần gọi bridge) nhưng không GHI — agent
    # bị lừa không đổi được chìa khoá. secrets/MCP local: agent không cần.
    # literal emit cả raw + realpath: CWD qua symlink (/var→/private/var)
    # thì Seatbelt so canonical — thiếu dạng nào cũng lọt.
    dev = os.path.join(cwd, ".devin")
    # exec-allowlist.json: não ghi được = tự thêm pattern "cp/mv/rm *"
    # rồi auto-duyệt lệnh huỷ — chỉ bridge/fleet-pack được đặt list này.
    for f, ops in (("bridge.token", "file-write*"),
                   ("secrets.local.json", "file-read* file-write*"),
                   ("mcp_config.local.json", "file-read* file-write*"),
                   ("exec-allowlist.json", "file-write*")):
        for lit in _emit_paths([os.path.join(dev, f)]):
            L.append(f'(deny {ops} (literal "{_esc(lit)}"))')

    # JSON điều khiển quyền hạn: chỉ bridge (chạy ngoài sandbox) được ghi
    # — não ghi trực tiếp = tự cởi còng (ghi permissions.json "/" rồi
    # respawn = profile phình toàn ổ). bot.md cố ý KHÔNG deny — skill
    # phong-van ghi nó khi onboarding.
    mc = os.path.join(cwd, "my-course")
    for f in ("permissions.json", "connections.json", "bots.json",
              "config.json"):
        for lit in _emit_paths([os.path.join(mc, f)]):
            L.append(f'(deny file-write* (literal "{_esc(lit)}"))')

    # Vùng mã nguồn + file điều khiển: deny-write LUÔN, kể cả khi
    # permissions.json (sửa tay, hay grant RW hợp lệ trên folder CHA của
    # cwd như ~/Desktop) mở đường — ghi được tools/*.py, brain.json hay
    # .git/hooks là spawn/exec kế chạy code NGOÀI sandbox. Deny thắng
    # allow; đọc vẫn mở (não cần đọc AGENTS.md, tools/).
    for d in ("tools", "web", "extension", "templates", "site", "intro",
              "docs", "plans", "build", "dist",
              ".git", ".github",
              os.path.join(".devin", "skill-packs")):
        for lit in _emit_paths([os.path.join(cwd, d)]):
            L.append(f'(deny file-write* (subpath "{_esc(lit)}"))')
    for f in ("brain.json", "index.html", "start.sh", "start.bat",
              "AGENTS.md", "CLAUDE.md", "README.md", "SETUP.md", "PLAN.md",
              "requirements.txt", "VERSION", "troly.spec",
              os.path.join(".devin", "agent.sb")):
        for lit in _emit_paths([os.path.join(cwd, f)]):
            L.append(f'(deny file-write* (literal "{_esc(lit)}"))')
    return "\n".join(L) + "\n"

def main():
    cwd = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.getcwd())
    out = os.path.join(cwd, ".devin", "agent.sb")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    prof = build_profile(cwd)
    try:
        if open(out, encoding="utf-8").read() == prof:
            print(out)                       # không đổi → không ghi lại
            return
    except OSError:
        pass
    with open(out, "w", encoding="utf-8") as f:
        f.write(prof)
    print(out)

if __name__ == "__main__":
    main()
