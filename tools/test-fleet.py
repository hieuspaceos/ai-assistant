#!/usr/bin/env python3
"""test-fleet.py — kiểm chứng hợp đồng beacon ↔ collector (plan
fleet-console). Hai lớp:

1. Static: snapshot keys beacon.py/beacon.ps1 giống nhau; adm-render.js
   được admin.html + collector-web dùng; launcher/start spawn beacon
   đúng điều kiện; chuỗi ký license khớp make-license ↔ collector.
2. Integration: dựng collector THẬT trên port tự do với config + data
   tạm, rồi chạy đủ vòng đời: pair sai key → 401; pair đúng → pending;
   beacon chưa duyệt → 403; approve → re-pair lấy machine_key; beacon
   → 200 + license_status; /api/fleet + /api/license; revoke → máy bị
   đá về revoked. Không cần bridge :7682 — payload giả lập đúng shape
   beacon gửi (drift shape thật được canh bởi phần static).

Chạy: python3 tools/test-fleet.py"""
import json, os, re, socket, subprocess, sys, tempfile, time
import urllib.request, urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
fail = False

def check(ok, msg):
    global fail
    if ok:
        print(f"  ok — {msg}")
    else:
        print(f"FAIL — {msg}")
        fail = True

def read(fp):
    return open(fp, encoding="utf-8-sig").read()

# ---------- phần 1: static ----------

SNAP_KEYS = ["beacon_ver", "machine_id", "hostname", "os", "version",
             "pack_version", "org", "ts", "license", "counts", "snapshot"]
py_beacon = read(os.path.join(TOOLS, "beacon.py"))
ps_beacon = read(os.path.join(TOOLS, "beacon.ps1"))
for k in SNAP_KEYS:
    check(k in py_beacon, f"beacon.py có field snapshot '{k}'")
    check(k in ps_beacon, f"beacon.ps1 có field snapshot '{k}'")

for fname in ("beacon.cursor", "machine.id", "machine.key",
              "fleet-inbox.json", "fleet.json", "license.json"):
    check(fname in py_beacon and fname in ps_beacon,
          f"cả hai beacon dùng file '{fname}'")

admin = read(os.path.join(ROOT, "web", "admin.html"))
dash = read(os.path.join(ROOT, "collector-web", "index.html"))
check('src="adm-render.js"' in admin, "admin.html dùng adm-render.js")
check('src="adm-render.js"' in dash, "collector-web dùng adm-render.js")
check(os.path.isfile(os.path.join(ROOT, "web", "adm-render.js")),
      "web/adm-render.js tồn tại")

launcher = read(os.path.join(TOOLS, "launcher.py"))
check('"beacon"' in launcher and "fleet.json" in launcher,
      "launcher.py spawn beacon khi có fleet.json")
check("beacon.py" in read(os.path.join(ROOT, "start.sh")),
      "start.sh spawn beacon.py")
check("beacon.ps1" in read(os.path.join(ROOT, "start.bat")),
      "start.bat spawn beacon.ps1")

# chuỗi ký license phải khớp nguyên mẫu hai phía — drift = mọi license
# invalid ngay khi deploy
mk_lic = read(os.path.join(TOOLS, "make-license.py"))
collector_src = read(os.path.join(TOOLS, "collector.py"))
check('f"{org}|{seats}|{expiry}|{issued}"' in mk_lic,
      "make-license.py ký 'org|seats|expiry|issued'")
check('lic.get("org"), lic.get("seats"), lic.get("expiry")'
      in collector_src,
      "collector.py ghép cùng trường org|seats|expiry|issued")

# collector.py (canonical) ↔ worker/index.js (port) — endpoint drift:
# collector xoá/đổi endpoint nào là worker phải theo; worker thêm
# endpoint ngoài danh sách admin 2-tầng là phải khai TƯỜNG MINH
def api_names(src):
    return set(re.findall(r'"(/api/[a-z][a-z-]*)', src))

worker_src = read(os.path.join(ROOT, "worker", "src", "index.js"))
col_eps, wrk_eps = api_names(collector_src), api_names(worker_src)
# endpoint chỉ worker có — hệ thống tài khoản 2-tầng collector.py
# (self-host, admin_key phẳng) không có và không cần
WORKER_ONLY = {"/api/whoami", "/api/login", "/api/logout",
               "/api/bootstrap", "/api/password", "/api/orgs",
               "/api/admins", "/api/audit"}
for e in sorted(col_eps - wrk_eps):
    check(False, f"collector có {e} mà worker thiếu — port bị drift")
for e in sorted(wrk_eps - col_eps - WORKER_ONLY):
    check(False, f"worker có {e} chưa khai trong WORKER_ONLY")
check(not (col_eps - wrk_eps) and not (wrk_eps - col_eps - WORKER_ONLY),
      f"endpoint collector↔worker khớp ({len(col_eps & wrk_eps)} chung"
      f" + {len(wrk_eps - col_eps)} worker-only đã khai)")

# ---------- phần 2: integration với collector thật ----------

def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]; s.close(); return p

def http(method, url, headers=None, body=None):
    req = urllib.request.Request(
        url, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except Exception:
            return e.code, {}

tmp = tempfile.mkdtemp(prefix="troly-fleet-test-")
cfg_fp = os.path.join(tmp, "collector.json")
data_dir = os.path.join(tmp, "data")
web_dir = os.path.join(ROOT, "collector-web")
SEC_B, SEC_L, SEC_A = "beacon-sec-test", "lic-sec-test", "admin-key-test"
json.dump({"orgs": {"TST": {"beacon_secret": SEC_B,
                            "license_secret": SEC_L,
                            "admin_key": SEC_A}}},
          open(cfg_fp, "w"))
port = free_port()
base = f"http://127.0.0.1:{port}"
proc = subprocess.Popen(
    [sys.executable, os.path.join(TOOLS, "collector.py"),
     "--config", cfg_fp, "--port", str(port),
     "--bind", "127.0.0.1", "--data", data_dir, "--web", web_dir],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(50):                     # chờ collector boot — chỉ cần
        try:                                # HTTP lên, KHÔNG parse JSON
            urllib.request.urlopen(base + "/", timeout=1).read()
            break
        except Exception:
            time.sleep(0.2)
    # license thật do make-license cấp (subprocess → đúng code vendor)
    lic_fp = os.path.join(tmp, "license.json")
    env = dict(os.environ, TROLY_LICENSE_SECRET=SEC_L)
    subprocess.run([sys.executable,
                    os.path.join(TOOLS, "make-license.py"),
                    "--org", "TST", "--seats", "3",
                    "--expiry", "2099-01-01", "--out", lic_fp],
                   env=env, check=True, capture_output=True)
    lic = json.load(open(lic_fp))
    bad_lic = dict(lic, seats=99)           # sửa field → sig phải hỏng

    pair_body = {"machine_id": "m-test-1", "hostname": "PC-01",
                 "os": "Windows 11", "org": "TST", "license": lic}
    code, _ = http("POST", base + "/api/pair",
                   {"X-Beacon-Key": "sai"}, pair_body)
    check(code == 401, f"pair sai beacon_secret → 401 (got {code})")
    code, r = http("POST", base + "/api/pair",
                   {"X-Beacon-Key": SEC_B}, pair_body)
    check(code == 200 and r.get("status") == "pending",
          f"pair đúng → pending (got {code} {r.get('status')})")

    code, _ = http("POST", base + "/api/beacon",
                   {"X-Beacon-Key": "chua-pair"}, {})
    check(code == 403, f"beacon chưa pair → 403 (got {code})")

    code, _ = http("GET", base + "/api/pending")
    check(code == 401, f"pending không key → 401 (got {code})")
    code, r = http("GET", base + "/api/pending",
                   {"X-Admin-Key": SEC_A})
    check(code == 200 and len(r.get("pending") or []) == 1,
          "admin thấy 1 máy pending")

    code, r = http("POST", base + "/api/pair-approve",
                   {"X-Admin-Key": SEC_A}, {"machine_id": "m-test-1"})
    mkey = r.get("machine_key")
    check(code == 200 and mkey, "approve → cấp machine_key")

    code, r = http("POST", base + "/api/pair",
                   {"X-Beacon-Key": SEC_B}, pair_body)
    check(r.get("status") == "approved"
          and r.get("machine_key") == mkey,
          "re-pair sau duyệt → trả lại đúng machine_key")

    snap = {"bridge_up": True,
            "health": {"ok": True, "version": "1.0.2",
                       "extVersion": "0.9"},
            "brain": {"current": {"id": "devin", "label": "Devin"}},
            "config": {"language": "vi", "learner_name": "Test"},
            "bots": {"active": "b1", "bots": [{"id": "b1"}]},
            "perms": {"folders": []}, "conns": {"apps": []}}
    beacon_body = {"beacon_ver": 1, "machine_id": "m-test-1",
                   "hostname": "PC-01", "os": "Windows 11",
                   "version": "1.0.2", "pack_version": "1",
                   "org": "TST", "ts": int(time.time()),
                   "license": lic, "counts": {"done": 4, "err": 1},
                   "snapshot": snap}
    code, r = http("POST", base + "/api/beacon",
                   {"X-Beacon-Key": mkey}, beacon_body)
    check(code == 200 and r.get("ok"),
          f"beacon đầu → 200 (got {code})")

    code, r = http("GET", base + "/api/fleet", {"X-Admin-Key": SEC_A})
    ms = r.get("machines") or []
    check(code == 200 and len(ms) == 1, "fleet list 1 máy")
    if ms:
        m = ms[0]
        check(m["license_status"] == "ok",
              f"license ok (got {m['license_status']})")
        check(m["learner"] == "Test" and m["version"] == "1.0.2",
              "fleet row có learner + version")
        check((m["today"] or {}).get("done") == 4,
              "usage hôm nay gộp counts")

    code, r = http("GET", base + "/api/license", {"X-Admin-Key": SEC_A})
    check(r.get("seats") == 3 and r.get("status") == "ok",
          f"/api/license: seats=3, ok (got {r.get('seats')}/"
          f"{r.get('status')})")

    # beacon thứ hai: license bị sửa → vẫn 200 nhưng flag invalid
    code, r = http("POST", base + "/api/beacon",
                   {"X-Beacon-Key": mkey},
                   dict(beacon_body, license=bad_lic,
                        counts={"done": 2}))
    check(code == 200, "beacon license xấu vẫn nhận (gentle)")
    code, r = http("GET", base + "/api/fleet", {"X-Admin-Key": SEC_A})
    check(r["machines"][0]["license_status"] == "invalid",
          "license sửa field → flag invalid trên dashboard")
    check(r["machines"][0]["today"]["done"] == 6,
          "usage cộng dồn 4+2 theo ngày")

    code, r = http("GET", base + "/api/license", {"X-Admin-Key": SEC_A})
    check(r.get("status") == "invalid" and r.get("seats") is None,
          "/api/license: mọi license invalid → seats=None, "
          "status invalid")

    code, _ = http("POST", base + "/api/pair-revoke",
                   {"X-Admin-Key": SEC_A}, {"machine_id": "m-test-1"})
    check(code == 200, "revoke → 200")
    code, r = http("POST", base + "/api/beacon",
                   {"X-Beacon-Key": mkey}, beacon_body)
    check(code == 403 and r.get("status") == "revoked",
          f"beacon sau revoke → 403 revoked (got {code})")

    code, r = http("GET", base + "/api/fleet/m-test-1",
                   {"X-Admin-Key": SEC_A})
    check(code == 200 and r.get("snapshot", {}).get("bridge_up"),
          "detail trả snapshot đầy đủ cho trang chi tiết")

    # dashboard tĩnh phục vụ không cần key (data thì khoá)
    try:
        urllib.request.urlopen(base + "/", timeout=5)
        code = 200
    except urllib.error.HTTPError as e:
        code = e.code
    check(code == 200, "GET / dashboard → 200")
    req = urllib.request.Request(base + "/adm-render.js")
    try:
        urllib.request.urlopen(req, timeout=5)
        code = 200
    except urllib.error.HTTPError as e:
        code = e.code
    check(code == 200, "GET /adm-render.js → 200 (fallback web/)")
finally:
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except Exception:
        proc.kill()

if fail:
    sys.exit(1)
print("PASS — fleet contract: pairing, license, usage, revoke, dashboard")
