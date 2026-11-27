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
             "pack_version", "bank_version", "org", "ts", "license",
             "counts", "snapshot"]
py_beacon = read(os.path.join(TOOLS, "beacon.py"))
ps_beacon = read(os.path.join(TOOLS, "beacon.ps1"))
for k in SNAP_KEYS:
    check(k in py_beacon, f"beacon.py có field snapshot '{k}'")
    check(k in ps_beacon, f"beacon.ps1 có field snapshot '{k}'")

for fname in ("beacon.cursor", "machine.id", "machine.key",
              "fleet-inbox.json", "fleet.json", "license.json",
              "bank-version"):
    check(fname in py_beacon and fname in ps_beacon,
          f"cả hai beacon dùng file '{fname}'")

admin = read(os.path.join(ROOT, "web", "admin.html"))
dash = read(os.path.join(ROOT, "collector-web", "index.html"))
check('src="adm-render.js"' in admin, "admin.html dùng adm-render.js")
check('src="adm-render.js"' in dash, "collector-web dùng adm-render.js")
check(os.path.isfile(os.path.join(ROOT, "web", "adm-render.js")),
      "web/adm-render.js tồn tại")
check(read(os.path.join(ROOT, "web", "adm-render.js"))
      == read(os.path.join(ROOT, "collector-web", "adm-render.js")),
      "hai bản adm-render.js đồng bộ")
# audit-6 F11: beacon.ps1 ghi tool_fail vào snapshot; adm-render
# hiển thị row cảnh báo từ d.tool_fail
check("tool_fail" in ps_beacon,
      "beacon.ps1 có logic ghi snap.tool_fail")
check('toolFail' in read(os.path.join(ROOT, "web", "adm-render.js")),
      "adm-render.js có i18n key toolFail")
check("api/skills-bank" in dash and "api/harvest" in dash,
      "dashboard gọi skills-bank + harvest")
check("bank" in read(os.path.join(TOOLS, "apply-pack.py")),
      "apply-pack.py xử lý inbox bank")

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
# org thứ hai + telemetry key: cần cho PoC traversal (vendor "*") và
# license org-chéo. telemetry không có "url" → loop tự tắt, không gọi
# ra ngoài.
SEC_B2, SEC_L2, SEC_A2 = "beacon2-sec", "lic2-sec", "admin2-key"
VEND = "vendor-key-test"          # telemetry.key — chỉ ghi org-ping
VREAD = "vread-key-test"          # vendor_read_key — chỉ đọc rollup
RELKEY = "release-key-test"       # release_key — đẩy release
json.dump({"orgs": {"TST": {"beacon_secret": SEC_B,
                            "license_secret": SEC_L,
                            "admin_key": SEC_A},
                    "ORG2": {"beacon_secret": SEC_B2,
                             "license_secret": SEC_L2,
                             "admin_key": SEC_A2}},
           "telemetry": {"key": VEND},
           "vendor_read_key": VREAD,
           "release_key": RELKEY},
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
    # license của ORG2 — sig HỢP LỆ dưới secret ORG2 nhưng org khác máy
    # → collector phải flag invalid (verify theo org của row, không tin
    # lic["org"] máy tự khai)
    lic2_fp = os.path.join(tmp, "license-org2.json")
    env2 = dict(os.environ, TROLY_LICENSE_SECRET=SEC_L2)
    subprocess.run([sys.executable,
                    os.path.join(TOOLS, "make-license.py"),
                    "--org", "ORG2", "--seats", "5",
                    "--expiry", "2099-01-01", "--out", lic2_fp],
                   env=env2, check=True, capture_output=True)
    lic_org2 = json.load(open(lic2_fp))

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

    # pair sau duyệt → máy NHẬN key (approve ghi pending_key, pair phát)
    code, r = http("POST", base + "/api/pair",
                   {"X-Beacon-Key": SEC_B}, pair_body)
    check(r.get("status") == "approved"
          and r.get("machine_key") == mkey,
          "pair sau duyệt → nhận machine_key")

    # repair flow (audit-4 1.3): re-pair máy ĐÃ CÓ key → KHÔNG trả key
    # chỉ vì biết beacon_secret — flag repair, chờ admin duyệt; duyệt →
    # pending_key, máy nhận key MỚI ở pair kế, key cũ chết (rotate)
    code, r = http("POST", base + "/api/pair",
                   {"X-Beacon-Key": SEC_B}, pair_body)
    check(r.get("status") == "pending" and "machine_key" not in r,
          "re-pair máy đã có key → pending, không trả key")
    code, r = http("GET", base + "/api/pending",
                   {"X-Admin-Key": SEC_A})
    check(code == 200 and any(p.get("repair")
                              for p in r.get("pending") or []),
          "pending list hiện repair=1 cho máy xin cấp lại")
    code, r = http("POST", base + "/api/pair-approve",
                   {"X-Admin-Key": SEC_A}, {"machine_id": "m-test-1"})
    mkey2 = r.get("machine_key")
    check(code == 200 and mkey2 and mkey2 != mkey,
          "approve repair → key mới khác key cũ")
    code, r = http("POST", base + "/api/pair",
                   {"X-Beacon-Key": SEC_B}, pair_body)
    check(r.get("status") == "approved"
          and r.get("machine_key") == mkey2,
          "re-pair sau duyệt repair → nhận key mới")
    code, _ = http("POST", base + "/api/beacon",
                   {"X-Beacon-Key": mkey}, {})
    check(code == 403, "beacon bằng key cũ sau rotate → 403")
    mkey = mkey2

    snap = {"bridge_up": True,
            "health": {"ok": True, "version": "1.0.2",
                       "extVersion": "0.9"},
            "brain": {"current": {"id": "devin", "label": "Devin"}},
            "config": {"language": "vi", "learner_name": "Test"},
            "bots": {"active": "b1", "bots": [{"id": "b1"}]},
            "perms": {"folders": []}, "conns": {"apps": []},
            "skills": [{"id": "s-tuan", "name": "Cong thuc A",
                        "desc": "mo ta"}],
            "tool_fail": "no-python"}
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
        check(m.get("n_skills") == 1,
              "fleet row đếm công thức từ snapshot.skills")

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

    # ---- regression audit-4 phase-01 ----
    # detail check chạy TRƯỚC junk beacon — junk sẽ ghi snapshot_json
    # "{}" đè lên snapshot thật
    code, r = http("GET", base + "/api/fleet/m-test-1",
                   {"X-Admin-Key": SEC_A})
    check(code == 200 and r.get("snapshot", {}).get("bridge_up"),
          "detail trả snapshot đầy đủ cho trang chi tiết")
    # audit-6 F11: tool_fail nằm trong snapshot → collector persist
    # qua snapshot_json, drawer đọc được
    check(r.get("snapshot", {}).get("tool_fail") == "no-python",
          "snapshot.tool_fail persist qua collector")

    # label + seats export (1click-b2b 06): admin gán tên NV vào máy,
    # CSV báo cáo ghế có cột label — vendor read key bị chặn cả hai
    code, r = http("POST", base + "/api/machine/m-test-1/label",
                   {"X-Admin-Key": SEC_A}, {"label": "An, marketing"})
    check(code == 200 and r.get("label") == "An, marketing",
          f"label máy → 200 (got {code})")
    code, r = http("GET", base + "/api/fleet/m-test-1",
                   {"X-Admin-Key": SEC_A})
    check(r.get("label") == "An, marketing",
          "detail trả label vừa gán")
    code, r = http("GET", base + "/api/fleet", {"X-Admin-Key": SEC_A})
    check(r["machines"][0].get("label") == "An, marketing",
          "/api/fleet list trả label")
    code, _ = http("POST", base + "/api/machine/m-test-1/label",
                   {"X-Admin-Key": SEC_A2}, {"label": "x"})
    check(code == 404, f"label máy org khác → 404 (got {code})")
    code, _ = http("POST", base + "/api/machine/m-test-1/label",
                   {"X-Admin-Key": VREAD}, {"label": "x"})
    check(code == 403, f"vendor key label → 403 (got {code})")
    code, _ = http("GET", base + "/api/seats/export",
                   {"X-Admin-Key": VREAD})
    check(code == 403, f"vendor key export CSV → 403 (got {code})")
    req = urllib.request.Request(base + "/api/seats/export",
                                 headers={"X-Admin-Key": SEC_A})
    with urllib.request.urlopen(req, timeout=8) as resp:
        csv_body = resp.read().decode("utf-8-sig")
        ctype = resp.headers.get("Content-Type", "")
        check(resp.status == 200 and "text/csv" in ctype
              and "An, marketing" in csv_body
              and "m-test-1" in csv_body,
              "export CSV chứa label + machine_id")

    # ---- skill bank / harvest (bàn giao công thức khi NV nghỉ) ----
    # máy tự ý upload nội dung skill khi admin CHƯA xin → 403 — cam
    # kết privacy "không upload chữ nếu không được yêu cầu"
    code, _ = http("POST", base + "/api/skills",
                   {"X-Beacon-Key": mkey},
                   {"skills": {"s-a": {"SKILL.md": "x"}}})
    check(code == 403,
          f"skills upload trước khi admin xin → 403 (got {code})")

    # admin bấm "Gom công thức" → cờ đi qua beacon response
    code, r = http("POST", base + "/api/harvest",
                   {"X-Admin-Key": SEC_A}, {"machine_id": "m-test-1"})
    check(code == 200 and r.get("ok"), f"harvest → 200 (got {code})")
    code, r = http("GET", base + "/api/fleet/m-test-1",
                   {"X-Admin-Key": SEC_A})
    check(r.get("harvest") is True, "detail trả harvest=1")
    code, r = http("POST", base + "/api/beacon",
                   {"X-Beacon-Key": mkey}, dict(beacon_body, counts={}))
    check(code == 200 and r.get("harvest") is True,
          "beacon resp báo harvest khi admin đã xin")

    # máy upload → bank entry; cờ tự tắt + banked_ts
    code, r = http("POST", base + "/api/skills",
                   {"X-Beacon-Key": mkey},
                   {"skills": {"s-tuan": {"SKILL.md": "---\nname: A\n---"}}})
    check(code == 200 and r.get("n") == 1,
          f"skills upload sau xin → 200 (got {code})")
    code, r = http("GET", base + "/api/fleet/m-test-1",
                   {"X-Admin-Key": SEC_A})
    check(r.get("harvest") is False and r.get("banked_ts"),
          "upload xong → cờ tắt + banked_ts")

    # xin lại rồi upload path độc → lint chặn; off → cờ tắt
    http("POST", base + "/api/harvest", {"X-Admin-Key": SEC_A},
         {"machine_id": "m-test-1"})
    code, _ = http("POST", base + "/api/skills",
                   {"X-Beacon-Key": mkey},
                   {"skills": {"../x": {"f": "y"}}})
    check(code == 400, f"skill id '../x' → 400 (got {code})")
    code, r = http("POST", base + "/api/harvest",
                   {"X-Admin-Key": SEC_A},
                   {"machine_id": "m-test-1", "off": True})
    check(code == 200, "harvest off → 200")
    code, _ = http("POST", base + "/api/skills",
                   {"X-Beacon-Key": mkey}, {"skills": {}})
    check(code == 403, "sau off → upload bị chặn lại")

    # vendor key không được xin gom / xem bank (PII)
    code, _ = http("POST", base + "/api/harvest",
                   {"X-Admin-Key": VREAD}, {"machine_id": "m-test-1"})
    check(code == 403, f"vendor key harvest → 403 (got {code})")
    code, _ = http("GET", base + "/api/skills-bank",
                   {"X-Admin-Key": VREAD})
    check(code == 403, f"vendor key bank → 403 (got {code})")
    code, _ = http("POST", base + "/api/harvest",
                   {"X-Admin-Key": SEC_A2}, {"machine_id": "m-test-1"})
    check(code == 404, f"harvest máy org khác → 404 (got {code})")

    # bank list cho admin org — đủ attribution (label/learner/hostname)
    code, r = http("GET", base + "/api/skills-bank",
                   {"X-Admin-Key": SEC_A})
    ent = r.get("bank") or []
    check(code == 200 and len(ent) == 1
          and ent[0]["n_skills"] == 1
          and ent[0]["label"] == "An, marketing"
          and ent[0]["skills"] == ["s-tuan"],
          f"skills-bank: 1 entry đủ attribution (got {len(ent)})")

    # máy kéo bank.json — cùng org được, khác org/key lạ 403
    code, bank = http("GET", base + "/packs/TST/bank.json",
                      {"X-Beacon-Key": mkey})
    bv = bank.get("bank_version")
    check(code == 200 and bv and "s-tuan" in (bank.get("skills") or {}),
          f"bank.json merged có công thức (got {code})")
    code, _ = http("GET", base + "/packs/ORG2/bank.json",
                   {"X-Beacon-Key": mkey})
    check(code == 403, f"bank.json org khác → 403 (got {code})")
    code, _ = http("GET", base + "/packs/TST/bank.json",
                   {"X-Beacon-Key": "sai-key"})
    check(code == 403, f"bank.json key lạ → 403 (got {code})")

    # beacon bank_version thấp → hint; đủ mới → hết hint
    code, r = http("POST", base + "/api/beacon",
                   {"X-Beacon-Key": mkey},
                   dict(beacon_body, bank_version=0, counts={}))
    check(r.get("bank", {}).get("version") == bv
          and r["bank"]["url"] == "/packs/TST/bank.json",
          "beacon bank_version thấp → hint kéo bank")
    code, r = http("POST", base + "/api/beacon",
                   {"X-Beacon-Key": mkey},
                   dict(beacon_body, bank_version=bv, counts={}))
    check("bank" not in r, "bank_version đủ mới → không hint")

    # máy mới vào thay: pair → approve → beacon đầu → hint → kéo bank
    # đủ công thức của máy cũ (flow "Phương nhận đủ công thức Tuấn")
    code, r = http("POST", base + "/api/pair",
                   {"X-Beacon-Key": SEC_B},
                   dict(pair_body, machine_id="m-test-2",
                        hostname="PC-02"))
    check(r.get("status") == "pending", "máy mới pair → pending")
    code, r = http("POST", base + "/api/pair-approve",
                   {"X-Admin-Key": SEC_A}, {"machine_id": "m-test-2"})
    code, r = http("POST", base + "/api/pair",
                   {"X-Beacon-Key": SEC_B},
                   dict(pair_body, machine_id="m-test-2",
                        hostname="PC-02"))
    mkey2b = r.get("machine_key")
    check(bool(mkey2b), "máy mới nhận machine_key")
    code, r = http("POST", base + "/api/beacon",
                   {"X-Beacon-Key": mkey2b},
                   dict(beacon_body, machine_id="m-test-2",
                        hostname="PC-02", counts={}))
    check(r.get("bank", {}).get("version") == bv,
          "máy mới beacon đầu → hint bank")
    code, bank2 = http("GET", base + r["bank"]["url"],
                       {"X-Beacon-Key": mkey2b})
    check(code == 200 and "s-tuan" in (bank2.get("skills") or {}),
          "máy mới kéo bank.json → nhận công thức máy cũ")

    # body top-level sai kiểu → 400 có response (trước: handler crash,
    # connection rớt)
    code, _ = http("POST", base + "/api/beacon",
                   {"X-Beacon-Key": mkey}, [1, 2, 3])
    check(code == 400, f"beacon body list → 400 (got {code})")
    code, _ = http("POST", base + "/api/pair-approve",
                   {"X-Admin-Key": SEC_A}, [1, 2, 3])
    check(code == 400, f"approve body list → 400 (got {code})")

    # nested sai kiểu → 200, không traceback; snapshot_json "{}" cũng
    # không được làm /api/fleet phía sau crash
    code, r = http("POST", base + "/api/beacon",
                   {"X-Beacon-Key": mkey},
                   dict(beacon_body, snapshot=[1, 2], counts=[1, 2]))
    check(code == 200 and r.get("ok"),
          f"nested non-dict → 200 không crash (got {code})")
    code, r = http("GET", base + "/api/fleet", {"X-Admin-Key": SEC_A})
    check(code == 200, "snapshot_json '{}' không làm fleet crash")

    # license org khác → invalid (verify theo org của máy, không tin
    # lic["org"] máy khai — trước: verify bằng secret ORG2 → "ok")
    code, r = http("POST", base + "/api/beacon",
                   {"X-Beacon-Key": mkey},
                   dict(beacon_body, license=lic_org2, counts={}))
    check(code == 200, "beacon license org khác vẫn nhận (gentle)")
    code, r = http("GET", base + "/api/fleet", {"X-Admin-Key": SEC_A})
    check(r["machines"][0]["license_status"] == "invalid",
          "license ORG2 trên máy TST → invalid")

    # vendor key tách (audit-4 1.2): telemetry.key chỉ ghi org-ping —
    # không còn quyền admin inbound; vendor_read_key đọc rollup nhưng
    # không machine-level, không write
    code, _ = http("GET", base + "/api/fleet", {"X-Admin-Key": VEND})
    check(code == 401, f"telemetry.key GET /api/fleet → 401 (got {code})")
    code, _ = http("POST", base + "/api/packs",
                   {"X-Admin-Key": VEND},
                   {"org": "TST", "pack_version": 9})
    check(code == 401, f"telemetry.key POST pack → 401 (got {code})")
    code, r = http("POST", base + "/api/org-ping",
                   {"X-Admin-Key": VEND},
                   {"org": "TST", "machines_active": 1})
    check(code == 200 and r.get("ok"),
          f"telemetry.key POST org-ping → 200 (got {code})")
    code, r = http("GET", base + "/api/org-pings",
                   {"X-Admin-Key": VREAD})
    check(code == 200 and len(r.get("pings") or []) >= 1,
          f"vendor_read_key đọc org-pings (got {code})")
    code, r = http("GET", base + "/api/license",
                   {"X-Admin-Key": VREAD})
    check(code == 200, f"vendor_read_key GET license → 200 (got {code})")
    code, _ = http("GET", base + "/api/fleet", {"X-Admin-Key": VREAD})
    check(code == 403,
          f"vendor_read_key GET /api/fleet → 403, không machine-level "
          f"(got {code})")
    code, _ = http("GET", base + "/api/fleet/m-test-1",
                   {"X-Admin-Key": VREAD})
    check(code == 403, f"vendor_read_key GET fleet detail → 403 "
          f"(got {code})")
    code, _ = http("POST", base + "/api/packs",
                   {"X-Admin-Key": VREAD},
                   {"org": "TST", "pack_version": 9})
    check(code == 403, f"vendor_read_key POST pack → 403 (got {code})")
    code, _ = http("POST", base + "/api/pair-approve",
                   {"X-Admin-Key": VREAD}, {"machine_id": "m-test-1"})
    check(code == 403, f"vendor_read_key approve → 403 (got {code})")

    # porg traversal (PoC audit): org "../.." trước ghi được JSON ra
    # ngoài DATA/ — giờ 400 ngay từ validate
    code, _ = http("POST", base + "/api/packs",
                   {"X-Admin-Key": SEC_A},
                   {"org": "../../esc2", "pack_version": 9,
                    "payload": "x"})
    check(code == 400
          and not os.path.exists(os.path.join(tmp, "esc2")),
          f"porg '../..' → 400, không ghi ngoài DATA (got {code})")
    code, _ = http("POST", base + "/api/packs",
                   {"X-Admin-Key": SEC_A},
                   {"org": "TST", "pack_version": 1, "payload": "x"})
    check(code == 200 and os.path.isfile(
            os.path.join(data_dir, "packs", "TST", "1.json")),
          "pack hợp lệ → ghi packs/TST/1.json")
    code, _ = http("POST", base + "/api/packs",
                   {"X-Admin-Key": SEC_A},
                   {"org": "TST", "pack_version": True})
    check(code == 400, f"pack_version bool → 400 (got {code})")

    # release upload cần release_key riêng (audit-4 1.5b) — admin_key
    # org không được đẩy release xuống fleet org khác
    code, _ = http("POST", base + "/api/releases/foo-x.zip",
                   {"X-Admin-Key": SEC_A}, {"x": 1})
    check(code == 401, f"admin_key upload release → 401 (got {code})")
    code, _ = http("POST", base + "/api/releases/latest.json",
                   {"X-Admin-Key": RELKEY}, {"x": 1})
    check(code == 400, f"upload latest.json → 400 (got {code})")
    code, r = http("POST", base + "/api/releases/foo-1.0.zip",
                   {"X-Admin-Key": RELKEY}, {"x": 1})
    check(code == 200 and r.get("sha256"),
          f"release_key upload zip → 200 (got {code})")
    code, _ = http("POST", base + "/api/releases",
                   {"X-Admin-Key": SEC_A},
                   {"version": "9.9.9", "url": "foo-1.0.zip",
                    "sha256": "x", "sig": "y"})
    check(code == 401, f"admin_key POST manifest → 401 (got {code})")
    code, r2 = http("POST", base + "/api/releases",
                    {"X-Admin-Key": RELKEY},
                    {"version": "9.9.9", "url": "foo-1.0.zip",
                     "sha256": r.get("sha256"), "sig": "fakesig"})
    check(code == 200 and json.load(open(
            os.path.join(data_dir, "releases", "latest.json"))
            )["version"] == "9.9.9",
          "manifest qua POST /api/releases → latest.json ghi đúng")

    code, _ = http("POST", base + "/api/pair-revoke",
                   {"X-Admin-Key": SEC_A}, {"machine_id": "m-test-1"})
    check(code == 200, "revoke → 200")
    code, r = http("POST", base + "/api/beacon",
                   {"X-Beacon-Key": mkey}, beacon_body)
    check(code == 403 and r.get("status") == "revoked",
          f"beacon sau revoke → 403 revoked (got {code})")

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
