#!/usr/bin/env python3
"""update.py — kiểm tra + stage bản release mới của Trợ Lý AI.

Chạy khi:
  (a) launcher khởi động (--check — manifest fetch nhanh, timeout ngắn)
  (b) beacon gọi khi `.devin/fleet-inbox.json` báo {"update": ...}

Mô hình pull: máy chủ động hỏi, không ai push vào máy. update.py chỉ
TẢI + VERIFY + STAGE — việc đè code xảy ra ở `launcher.bootstrap()`
giữa hai lần boot (Windows khoá file đang chạy, pattern né được).

Chuỗi tin cậy (theo thứ tự — một mắt xích gãy thì abort, không đè):
  1. manifest chỉ từ host cấu hình (collector trong fleet.json trước —
     LAN nhanh; fallback origin vendor). KHÔNG follow redirect — server
     bị sửa DNS/proxy kéo về host lạ → abort (học ssrf.go của GoClaw).
  2. sha256(zip) khớp manifest.
  3. sig ed25519(sha256) verify bằng tools/vendor-pubkey nhúng sẵn —
     kẻ chiếm collector không forge được release (không có private key).
  4. zip chỉ chứa whitelist path (code dirs + skill-packs + docs) —
     entry ngoài tập / `..` / absolute / backslash → abort (zip-slip).
  5. backup.py chụp state trước; launcher swap vào bản mới lúc boot,
     giữ `.devin/backup-code-*` để rollback nếu con mới crash-loop.

  python3 tools/update.py [DATA_DIR] [--check]
"""
import hashlib, json, os, re, shutil, subprocess, sys, time
import urllib.error, urllib.parse, urllib.request, zipfile

ROOT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1
                       and not sys.argv[1].startswith("-") else
                       os.environ.get("TROLY_DATA") or os.getcwd())
QUICK = "--check" in sys.argv
DEVIN = os.path.join(ROOT, ".devin")
FLEET_FP = os.path.join(DEVIN, "fleet.json")
MKEY_FP = os.path.join(DEVIN, "machine.key")
PENDING_FP = os.path.join(DEVIN, "update-pending.json")
STAGE = os.path.join(DEVIN, "update-stage")
DLDIR = os.path.join(os.path.expanduser("~"), ".troly-update")
TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)
from ed25519 import checkvalid            # noqa: E402

ORIGIN = os.environ.get("TROLY_UPDATE_ORIGIN") or \
    "https://troly.hieuspace.com/releases/latest.json"
TIMEOUT = 3 if QUICK else 8
# trần đọc: manifest là JSON vài KB; zip ≤ REL_CAP phía collector
# (200MB). Collector hostile trước đây đổ response không đáy xuống máy
# — r.read() trọn = đầy disk/RAM (audit-5 N11)
MAN_CAP = 1_000_000
ZIP_CAP = 200_000_000

# entry zip được phép có — mọi thứ ngoài tập này là đáng ngờ
# phải khớp đúng danh sách zip của build-release.sh — thiếu dir nào
# trong zip → mọi release abort ở check_zip_safety
ALLOW_DIRS = ("tools/", "web/", "extension/", "templates/", "docs/",
              "collector-web/", ".devin/skill-packs/")
ALLOW_FILES = {"AGENTS.md", "CLAUDE.md", "SETUP.md", "README.md",
               "requirements.txt", "VERSION", "start.sh", "start.bat"}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Redirect → trả None → urlopen raise HTTPError. Release chỉ nhận
    từ đúng host cấu hình; bị redirect là dấu hiệu DNS/proxy bị chơi."""
    def redirect_request(self, *a, **k):
        return None


OPENER = urllib.request.build_opener(NoRedirect)


def _read(fp, default=""):
    try:
        with open(fp, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return default


def _jload(fp):
    try:
        return json.load(open(fp, encoding="utf-8"))
    except Exception:
        return None


def fetch(url, key=None, timeout=TIMEOUT, cap=MAN_CAP):
    """GET bytes — không redirect, timeout ngắn. `cap` = trần byte:
    đọc cap+1 để PHÁT HIỆN vượt trần (server nói dối Content-Length
    cũng bị bắt) — response quá trần → raise, không dùng dữ liệu cụt.
    Lỗi → raise."""
    req = urllib.request.Request(url)
    # Cloudflare chặn UA "Python-urllib" (1010) — cần UA riêng
    req.add_header("User-Agent", "TroLyAI-Update/1")
    if key:
        req.add_header("X-Beacon-Key", key)
    with OPENER.open(req, timeout=timeout) as r:
        data = r.read(cap + 1)
    if len(data) > cap:
        raise ValueError(f"response vượt trần {cap} bytes")
    return data


def manifest_sources():
    """Thứ tự nguồn: collector của cty trước (LAN nhanh — cty có thể
    chặn outbound cho máy NV), rồi origin vendor."""
    out = []
    fleet = _jload(FLEET_FP)
    if fleet and fleet.get("collector"):
        out.append((fleet["collector"].rstrip("/")
                    + "/api/releases/latest", _read(MKEY_FP)))
    out.append((ORIGIN, None))
    return out


def ver_tuple(s):
    try:
        return tuple(int(x) for x in str(s).split("."))
    except Exception:
        return ()


def _man_ok(man):
    """Manifest hợp lệ HÌNH THỨC trước khi tin mà tải zip (audit-5 S4):
    manifest nói dối format (version không phải x.y.z, sha256/sig không
    đúng hex) thì bỏ nguồn NGAY — không tốn một zip fetch. Sig ed25519
    = 64 bytes → 128 hex; sha256 = 32 bytes → 64 hex."""
    try:
        return bool(
            re.fullmatch(r"\d+\.\d+\.\d+", str(man["version"]))
            and isinstance(man.get("url"), str) and man["url"]
            and re.fullmatch(r"[0-9a-fA-F]{64}", str(man["sha256"]))
            and re.fullmatch(r"[0-9a-fA-F]{128}", str(man["sig"])))
    except Exception:
        return False


def pick_manifest():
    """Trả (manifest, source_url, source_key) mới nhất hợp lệ —
    manifest phải qua _man_ok (đủ field + đúng format). key đi theo
    nguồn (collector → machine.key, ORIGIN vendor → None) — zip fetch
    đính đúng key nguồn đó, không đính machine.key cho host lạ (F16)."""
    best, best_url, best_key = None, None, None
    for url, key in manifest_sources():
        try:
            man = json.loads(fetch(url, key))
            if _man_ok(man):
                if best is None or ver_tuple(man["version"]) \
                        > ver_tuple(best["version"]):
                    best, best_url, best_key = man, url, key
        except Exception:
            continue
    return best, best_url, best_key


def check_zip_safety(zf):
    """Whitelist entry + chống zip-slip — return list entry hợp lệ hay
    raise."""
    names = zf.namelist()
    for n in names:
        n = n.replace("\\", "/")
        if n.startswith("/") or ".." in n.split("/"):
            raise ValueError(f"zip-slip: {n}")
        top = n.split("/", 1)[0] + "/"
        if n in ALLOW_FILES or top in ALLOW_DIRS \
                or n.startswith(".devin/skill-packs/"):
            continue
        raise ValueError(f"entry ngoài whitelist: {n}")
    return names


def main():
    man, man_url, man_key = pick_manifest()
    if not man:
        return                                  # không nguồn nào tới
    cur = _read(os.path.join(ROOT, "VERSION"), "0")
    if ver_tuple(man["version"]) <= ver_tuple(cur):
        return                                  # đã mới nhất
    if ver_tuple(man.get("min_ver") or "0") > ver_tuple(cur):
        print(f"update: {man['version']} đòi nền >= "
              f"{man['min_ver']} (máy đang {cur}) — chờ bản trung gian",
              flush=True)
        return                                  # phải qua bản trung gian
    pend = _jload(PENDING_FP)
    if pend and pend.get("ver") == man["version"]:
        return                                  # đã stage rồi
    # URL zip: tương đối → resolve theo manifest; tuyệt đối → host phải
    # trùng host manifest (chặn manifest trỏ zip về host lạ)
    zip_url = urllib.parse.urljoin(man_url, man["url"])
    if urllib.parse.urlparse(zip_url).netloc != \
            urllib.parse.urlparse(man_url).netloc:
        print("update: zip ở host khác manifest — abort", flush=True)
        return
    try:
        data = fetch(zip_url, man_key, timeout=max(TIMEOUT, 30),
                     cap=ZIP_CAP)
    except Exception as e:
        print(f"update: tải zip lỗi — {e}", flush=True)
        return
    sha = hashlib.sha256(data).hexdigest()
    if sha != man["sha256"]:
        print("update: sha256 zip không khớp manifest — abort",
              flush=True)
        return
    # ed25519: sig ký trên bytes của sha256 hexdigest
    pub = _read(os.environ.get("TROLY_VENDOR_PUBKEY") or
                os.path.join(TOOLS, "vendor-pubkey"))
    if not pub:
        print("update: thiếu tools/vendor-pubkey — abort", flush=True)
        return
    try:
        checkvalid(bytes.fromhex(man["sig"]), bytes.fromhex(sha),
                   bytes.fromhex(pub))
    except Exception as e:
        print(f"update: chữ ký release SAI — abort ({e})", flush=True)
        return
    # qua hết rào: backup state trước rồi stage — frozen thì gọi vai con
    # `troly backup` (exe không chạy được path .py)
    try:
        cmd = [sys.executable, "backup", ROOT, "--why", "update"] \
            if getattr(sys, "frozen", False) else \
            [sys.executable, os.path.join(TOOLS, "backup.py"), ROOT,
             "--why", "update"]
        subprocess.run(cmd, timeout=300)
    except Exception:
        pass                                    # backup lỗi vẫn stage
    os.makedirs(DLDIR, exist_ok=True)
    fp_zip = os.path.join(DLDIR, f"troly-{man['version']}.zip")
    with open(fp_zip, "wb") as f:
        f.write(data)
    shutil.rmtree(STAGE, ignore_errors=True)
    os.makedirs(STAGE, exist_ok=True)
    try:
        with zipfile.ZipFile(fp_zip) as zf:
            names = check_zip_safety(zf)
            zf.extractall(STAGE, [n for n in names
                                  if not n.endswith("/")])
    except Exception as e:
        print(f"update: zip không hợp lệ — abort ({e})", flush=True)
        shutil.rmtree(STAGE, ignore_errors=True)
        return
    with open(PENDING_FP, "w") as f:
        json.dump({"ver": man["version"], "sha256": sha,
                   "ts": int(time.time())}, f)
    print(f"update: đã stage {man['version']} — áp dụng ở lần mở app "
          f"sau", flush=True)


if __name__ == "__main__":
    main()
