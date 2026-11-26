"""path_guard.py — policy đường dẫn nhạy cảm dùng CHUNG cho chat-bridge
(validate request/apply) và gen-sandbox (enforcement lúc build profile).

Lý do tách (audit-3 CAO-2): điểm validate và điểm phát quyền nằm ở hai
file khác nhau — nhân bản list = chắc chắn drift, mà drift ở đây là
sandbox escape. Module thuần hàm, không state, chỉ import os.

Tên underscore bắt buộc: file gạch ngang (gen-sandbox.py) không import
được — module dùng chung phải import được bình thường."""
import os

# Folder NHẠY CẢM không được cấp quyền dù request hợp lệ — card xác nhận
# không bảo vệ được người bấm đại "Đồng ý": khoá SSH/cloud, keychain,
# profile trình duyệt (cookie/phiên), credential của não, hay cả home/ổ
# gốc (mở toàn máy — tương đương không sandbox).
# Bộ lọc isabs sau expanduser BẮT BUỘC, không phải phòng hờ: entry
# Windows "~\\AppData\\…" trên POSIX có "\\" không phải sep → expanduser
# trả nguyên literal tương đối → realpath resolve thành
# "<cwd-lúc-import>/~\appdata\…" → two-way check biến MỌI ancestor của
# cwd thành "sensitive" (grant ~/Desktop bị từ chối — regression đã bắt
# trong audit lại). Ngược chiều: "/Library/…" trên Windows cũng không
# isabs (thiếu drive) → bị lọc — đúng, đó là path của macOS. Mỗi nền
# chỉ giữ entry thật sự resolve được trên nền đó.
_SENSITIVE_DIRS = [p for p in (os.path.expanduser(x) for x in (
    "~/.ssh", "~/.gnupg", "~/.aws", "~/.kube", "~/.config/gh",
    "~/.config/devin", "~/.local/share/devin",
    "~/.gemini", "~/.codex", "~/.claude", "~/.claude.json",
    "~/.opencode", "~/.config/opencode",
    "~/Library/Keychains", "~/Library/Cookies", "~/Library/Safari",
    "~/Library/Application Support/Google/Chrome",
    "~/Library/Application Support/Chromium",
    "~/Library/Application Support/Microsoft Edge",
    "~/Library/Application Support/Firefox",
    "~/Library/Application Support/BraveSoftware",
    "~/Library/Application Support/Arc",
    "~/Library/Application Support/Vivaldi",
    "~/Library/Application Support/com.operasoftware.Opera",
    # cookie/session store WebKit + container app sandbox (Zalo, Outlook
    # bản app) + account/plist có thể giữ token
    "~/Library/HTTPStorages", "~/Library/WebKit", "~/Library/Containers",
    "~/Library/Group Containers", "~/Library/Accounts",
    "~/Library/Preferences", "~/Library/IdentityServices",
    # credential cloud/devops + password manager + Firefox trên Linux
    "~/.docker", "~/.azure", "~/.config/gcloud", "~/.password-store",
    "~/.mozilla", "~/Library/Application Support/1Password",
    "~/.config/1Password",
    # Windows browser profile/credential — trên Windows ntpath.expanduser
    # nhận cả "~\\" lẫn "~/" nên resolve đúng; trên POSIX bộ lọc isabs
    # loại chúng ra (xem comment trên tuple).
    "~\\AppData\\Local\\Google\\Chrome", "~\\AppData\\Local\\Microsoft\\Edge",
    "~\\AppData\\Local\\BraveSoftware", "~\\AppData\\Roaming\\Mozilla",
    "~\\AppData\\Roaming\\1Password",
    # persistence + binary chạy NGOÀI sandbox — ghi vào đây = code tự
    # chạy thoát Seatbelt lúc login/boot hoặc lúc user mở app
    "~/Library/LaunchAgents", "~/Library/LaunchDaemons",
    "~/.config/autostart", "~/Applications",
    "/Library/LaunchAgents", "/Library/LaunchDaemons",
    "/Library/StartupItems", "/Applications",
)) if os.path.isabs(p)]
_SENSITIVE_ROOTS = {
    os.path.realpath(p) for p in
    ("/", "/Users", "/etc", "/var", "/private", "/System", "/usr", "/bin",
     "/sbin", os.path.expanduser("~"))}
_SENSITIVE_ROOTS_L = {s.lower() for s in _SENSITIVE_ROOTS}
_SENSITIVE_DIRS_L = [os.path.realpath(p).lower() for p in _SENSITIVE_DIRS]

def path_sensitive(p):
    try:
        rp = os.path.realpath(os.path.expanduser(p))
    except (OSError, ValueError):
        # path không resolve được (null byte…) → fail-closed: coi như
        # nhạy cảm thay vì để lỗi rơi ra ngoài giết handler thread
        return True
    # So case-insensitive: APFS/NTFS mặc định không phân biệt hoa-thường —
    # "~/.SSH" là cùng folder ~/.ssh nhưng realpath giữ nguyên hoa-thường,
    # so case-sensitive sẽ lọt. Trên Linux (~/.SSH là folder KHÁC) thì chặn
    # hơi dư — vẫn an toàn hơn là sót.
    rpl = rp.lower()
    if rpl in _SENSITIVE_ROOTS_L:
        return True
    # So HAI chiều: path NẰM TRONG folder nhạy cảm, hoặc path CHỨA một
    # folder nhạy cảm — chỉ so một chiều thì grant "~/Library" (hay
    # "~/.config") đọc được hết Keychains/Cookies/profile trình duyệt/
    # credential CLI, vô hiệu toàn bộ deny-list con.
    return any(rpl == s or rpl.startswith(s + os.sep)
               or s.startswith(rpl + os.sep)
               for s in _SENSITIVE_DIRS_L)

def rw_grant_ok(p, cwd):
    """read-write chỉ hợp lệ NGOÀI vùng mã nguồn: grant RW trên folder chứa
    project (~/Desktop…) hay folder code bên trong (tools/, web/…) = ghi
    được tools/*.py, brain.json, .git/hooks → spawn/exec kế chạy code
    NGOÀI Seatbelt. Path nằm trong vùng đã writable sẵn (my-course/,
    .devin/skills/, .logs/) thì cho qua — grant thừa nhưng vô hại."""
    try:
        rpl = os.path.realpath(os.path.expanduser(p)).lower()
    except (OSError, ValueError):
        return False        # path không resolve được → không cho RW
    cwdl = os.path.realpath(os.path.abspath(cwd)).lower()
    if not (rpl == cwdl or rpl.startswith(cwdl + os.sep)
            or cwdl.startswith(rpl + os.sep)):
        return True                       # ngoài project — bình thường
    wdirs = [os.path.realpath(os.path.join(cwdl, *d.split("/")))
             for d in ("my-course", ".devin/skills", ".logs")]
    return any(rpl == w or rpl.startswith(w + os.sep) for w in wdirs)
