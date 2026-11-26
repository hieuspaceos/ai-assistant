#!/usr/bin/env python3
"""beacon.py — đẩy snapshot định kỳ từ máy nhân viên lên fleet collector
của công ty. Máy là bên CHỦ ĐỘNG push — không port nào mở ra mạng, giữ
nguyên threat model loopback của các bridge.

Beacon chỉ gửi SỐ ĐẾM sự kiện + metadata trạng thái (version, não, bot
đang dùng, folder được phép), KHÔNG gửi nội dung chat/tin nhắn/file —
dashboard cty thấy "ai dùng, dùng nhiều không, lỗi gì", không thấy
"nói gì". Chi tiết: docs/fleet.md.

Chỉ chạy khi có .devin/fleet.json (bộ cài cty đặt sẵn — máy cá nhân
không có file này thì beacon im lặng thoát, launcher không restart):

    {"collector": "https://fleet.cty.vn",   # hoặc http://may-IT:8790
     "org": "IMA",
     "beacon_secret": "vé-vào-cửa do vendor cấp, chung cả org"}

Vòng đời pairing (mô hình GoClaw — shared secret cả org chỉ là vé vào
cửa, không phải chìa khoá):
  1. Chưa có .devin/machine.key → POST /api/pair kèm beacon_secret
     → máy hiện "pending" trên dashboard cty.
  2. Admin duyệt → collector cấp machine_key riêng → beacon ghi
     .devin/machine.key (0600).
  3. Mọi beacon sau dùng machine_key làm X-Beacon-Key → revoke từng
     máy được (nhân viên nghỉ việc / mất máy) mà không đổi gì cả org.
  4. Bị revoke → máy quay lại bước 1 (hiện pending lần nữa — admin
     thấy và quyết).

  python3 tools/beacon.py [DATA_DIR]     # thường do launcher/start gọi
"""
import json, os, platform, secrets, socket, subprocess, sys, time
import urllib.request

# Windows console/logfile mặc định cp1252 không encode được tiếng Việt —
# print chữ có dấu raise UnicodeEncodeError và giết cả vòng beacon.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="backslashreplace")
    except Exception:
        pass

ROOT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else
                       os.environ.get("TROLY_DATA") or os.getcwd())
DEVIN = os.path.join(ROOT, ".devin")
TOOLS = os.path.dirname(os.path.abspath(__file__))
FLEET_FP = os.path.join(DEVIN, "fleet.json")
MID_FP = os.path.join(DEVIN, "machine.id")
MKEY_FP = os.path.join(DEVIN, "machine.key")
CURSOR_FP = os.path.join(DEVIN, "beacon.cursor")
INBOX_FP = os.path.join(DEVIN, "fleet-inbox.json")
LIC_FP = os.path.join(DEVIN, "license.json")
PACKV_FP = os.path.join(DEVIN, "pack-version")
BRIDGE = "http://127.0.0.1:7682"
BEACON_VER = 1
INTERVAL = int(os.environ.get("TROLY_BEACON_INTERVAL") or 900)
# nhịp thăm dò khi đang chờ admin duyệt — nhanh hơn nhịp beacon thường
# vì người bấm duyệt đang đợi máy vào fleet
PAIR_RETRY = int(os.environ.get("TROLY_PAIR_RETRY") or 300)
# backoff khi collector không tới được: 5' → 15' → 30' rồi quay vòng;
# máy offline vẫn chạy bình thường, beacon là phụ
FAIL_SLEEPS = [300, 900, 1800]


def _read(fp, default=""):
    try:
        with open(fp, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return default


def _jload(fp, fallback=None):
    try:
        return json.load(open(fp, encoding="utf-8"))
    except Exception:
        return fallback


def _write600(fp, text):
    """Ghi file secret với quyền 0600 — cùng ý bridge.token."""
    fd = os.open(fp, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
    os.write(fd, text.encode()); os.close(fd)


def machine_id():
    mid = _read(MID_FP)
    if not mid:
        mid = secrets.token_hex(16)          # uuid4 dạng hex, KHÔNG rotate
        _write600(MID_FP, mid)
    return mid


def bridge_get(path, token, timeout=4):
    req = urllib.request.Request(BRIDGE + path)
    req.add_header("X-Bridge-Token", token)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def collector_post(path, key, payload, base):
    """POST JSON lên collector; trả (http_code, obj|None). Lỗi mạng →
    raise — caller xếp vào backoff."""
    # User-Agent bắt buộc: Cloudflare chặn UA mặc định "Python-urllib"
    # (error 1010 → 403 HTML) — request không bao giờ tới worker
    req = urllib.request.Request(
        base + path, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "User-Agent": f"TroLyAI-Beacon/{BEACON_VER}",
                 "X-Beacon-Key": key}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except Exception:
            return e.code, None


def collect_snapshot():
    """Gom trạng thái máy qua các GET read-only của bridge + đếm event
    mới kể từ cursor lần trước. Bridge chết vẫn trả snapshot tối thiểu
    (bridge_up=false) — collector thấy 'máy mở nhưng trợ lý tắt'."""
    token = _read(os.path.join(DEVIN, "bridge.token"))
    snap = {"bridge_up": False}
    counts = {}
    try:
        health = bridge_get("/api/health", token)
        snap["bridge_up"] = bool(health.get("ok"))
        snap["health"] = health
        for name, path in (("brain", "/api/brain"),
                           ("config", "/api/config"),
                           ("bots", "/api/bots"),
                           ("perms", "/api/permissions"),
                           ("conns", "/api/connections")):
            try:
                snap[name] = bridge_get(path, token)
            except Exception:
                pass                       # endpoint lỗi → thiếu, không chết
        # poll theo cursor — since=0 mỗi 15' kéo lại cả event store
        cur = int(_read(CURSOR_FP, "0") or 0)
        poll = bridge_get(f"/api/poll?since={cur}&wait=0", token)
        if not poll.get("reset"):
            for e in poll.get("events") or []:
                t = e.get("t") or "?"
                counts[t] = counts.get(t, 0) + 1
        # reset:true = event store bị xoay (bridge restart) — events trả
        # về có thể đã đếm ở window trước → chỉ nhảy cursor, không đếm
        _write600(CURSOR_FP, str(poll.get("next") or 0))
    except Exception:
        pass                               # bridge down → snapshot tối thiểu
    return snap, counts


def build_payload(fleet, mid):
    snap, counts = collect_snapshot()
    return {
        "beacon_ver": BEACON_VER,
        "machine_id": mid,
        "hostname": socket.gethostname(),
        "os": f"{platform.system()} {platform.release()}",
        "version": _read(os.path.join(ROOT, "VERSION"), "?"),
        "pack_version": _read(PACKV_FP) or None,
        "org": fleet.get("org"),
        "ts": int(time.time()),
        "license": _jload(LIC_FP),
        "counts": counts,
        "snapshot": snap,
    }


def pair(fleet, mid, base):
    """Xin vào fleet khi chưa có machine.key. Trả trạng thái để caller
    chọn nhịp ngủ: approved/pending/revoked/err."""
    code, resp = collector_post("/api/pair", fleet["beacon_secret"], {
        "machine_id": mid,
        "hostname": socket.gethostname(),
        "os": f"{platform.system()} {platform.release()}",
        "org": fleet.get("org"),
        "license": _jload(LIC_FP),
    }, base)
    if code == 200 and resp:
        if resp.get("status") == "approved" and resp.get("machine_key"):
            _write600(MKEY_FP, resp["machine_key"])
            print("beacon: admin đã duyệt — vào fleet", flush=True)
            return "approved"
        if resp.get("status") == "revoked":
            print("beacon: máy đang bị thu hồi — chờ admin mở lại",
                  flush=True)
            return "revoked"
        print("beacon: chờ admin duyệt máy trên dashboard", flush=True)
        return "pending"
    if code in (401, 403):
        print(f"beacon: collector từ chối pair ({code}) — kiểm tra "
              f"beacon_secret/org trong fleet.json", flush=True)
    return "err"


def main():
    fleet = _jload(FLEET_FP)
    if not fleet or not fleet.get("collector"):
        # máy cá nhân không thuộc fleet nào — thoát êm để launcher/start
        # không restart-loop; in một dòng cho log dễ hiểu
        print("beacon: không có .devin/fleet.json — chế độ máy đơn, ngủ",
              flush=True)
        return
    base = fleet["collector"].rstrip("/")
    if not fleet.get("beacon_secret"):
        print("beacon: fleet.json thiếu beacon_secret — ngủ", flush=True)
        return
    mid = machine_id()
    fails = 0
    while True:
        nap = INTERVAL
        try:
            if not _read(MKEY_FP):
                st = pair(fleet, mid, base)
                if st == "approved":
                    fails = 0
                elif st == "pending":
                    nap = PAIR_RETRY        # chờ người bấm — thăm dò
                elif st == "revoked":
                    pass                    # im lặng theo nhịp thường
                else:
                    fails += 1              # err mạng/HTTP → backoff
            else:
                payload = build_payload(fleet, mid)
                code, resp = collector_post(
                    "/api/beacon", _read(MKEY_FP), payload, base)
                if code == 200:
                    fails = 0
                    if resp and (resp.get("update") or resp.get("pack")):
                        # collector báo có release/pack mới → ghi inbox
                        # rồi đá update/apply-pack chạy nền — beacon giữ
                        # nhịp của mình, kéo về là việc của tiến trình kia
                        inbox = {"ts": int(time.time())}
                        if resp.get("update"):
                            inbox["update"] = resp["update"]
                        if resp.get("pack"):
                            inbox["pack"] = resp["pack"]
                        _write600(INBOX_FP, json.dumps(inbox))
                        for tool in ("update", "apply-pack"):
                            # frozen (troly.exe): vai con `troly <tool>`
                            # — exe không chạy được path .py, argv lạ rơi
                            # vào `troly run` → supervisor thứ hai
                            cmd = [sys.executable, tool, ROOT] \
                                if getattr(sys, "frozen", False) else \
                                [sys.executable,
                                 os.path.join(TOOLS, tool + ".py"), ROOT]
                            try:
                                subprocess.Popen(
                                    cmd, cwd=ROOT,
                                    stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL)
                            except Exception:
                                pass
                    if resp and resp.get("status") == "revoked":
                        # admin vừa revoke giữa chừng → bỏ key, về pairing
                        try:
                            os.remove(MKEY_FP)
                        except OSError:
                            pass
                elif code in (401, 403):
                    # machine_key không còn được tin (revoke/reset DB) —
                    # bỏ key để vòng sau re-pair hiện pending cho admin
                    body = resp if isinstance(resp, dict) else {}
                    if body.get("status") == "revoked" or code == 403:
                        try:
                            os.remove(MKEY_FP)
                        except OSError:
                            pass
                    fails += 1
                else:
                    fails += 1
        except KeyboardInterrupt:
            return
        except Exception as e:
            fails += 1
            print(f"beacon: lỗi vòng lặp — {e}", flush=True)
        # fails>0 → backoff quay vòng 5'→15'→30'→5'… (không spam collector
        # khi nó chết dài hạn); fails=0 → nap do trạng thái quyết
        if os.environ.get("TROLY_BEACON_ONCE"):
            return                      # chạy đúng một vòng — test/agent
        time.sleep(FAIL_SLEEPS[(fails - 1) % len(FAIL_SLEEPS)]
                   if fails else nap)


if __name__ == "__main__":
    main()
