#!/usr/bin/env python3
"""test-worker.py — kiểm chứng worker/index.js (tier vendor-hosted) bằng
wrangler dev + D1 LOCAL. Bù lỗ hổng audit 2-tầng: collector.py đã có
test-fleet.py, worker trước đây chỉ được verify bằng tay.

Vòng đời test: legacy key → bootstrap (self-lock) → login session →
tạo org → ký license (verify HMAC khớp make-license.py) → tạo cty-admin
→ phân quyền (403/404 cross-org) → pair/beacon máy con → audit →
rotate-secret (kể cả kill_machines) → logout.

Yêu cầu: worker/.dev.vars có ORGS_JSON + VENDOR_KEY; node + wrangler
đã cài. Chỉ chạy LOCAL — reset D1 local mỗi lần (xoá sạch rows).

Chạy: python3 tools/test-worker.py"""
import hmac as hmac_mod, hashlib, json, os, re, socket, subprocess, sys
import tempfile, time
import urllib.request, urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKER = os.path.join(ROOT, "worker")
fail = False

def check(ok, msg):
    global fail
    if ok:
        print(f"  ok — {msg}")
    else:
        print(f"FAIL — {msg}")
        fail = True

def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]; s.close(); return p

def http(method, url, headers=None, body=None):
    req = urllib.request.Request(
        url, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except Exception:
            return e.code, {}

def d1(sql):
    """Chạy SQL trên D1 local (.wrangler/state) — trả rows đầu."""
    r = subprocess.run(
        ["wrangler", "d1", "execute", "troly-fleet-db", "--local",
         "--command", sql, "--json"],
        cwd=WORKER, capture_output=True, text=True, timeout=60)
    out = r.stdout[r.stdout.find("["):]
    try:
        return (json.loads(out)[0].get("results") or [])
    except Exception:
        print("FAIL — d1 execute:", r.stdout[-300:], r.stderr[-300:])
        global fail; fail = True
        return []

# ---------- .dev.vars ----------
envvars = {}
for line in open(os.path.join(WORKER, ".dev.vars"), encoding="utf-8"):
    m = re.match(r"^([A-Z_]+)=(.*)$", line.strip())
    if m: envvars[m.group(1)] = m.group(2)
VENDOR_KEY = envvars.get("VENDOR_KEY", "")
try:
    ENV_ORGS = json.loads(envvars.get("ORGS_JSON", "{}"))
except Exception:
    ENV_ORGS = {}
if not VENDOR_KEY or not ENV_ORGS:
    print("FAIL — worker/.dev.vars cần VENDOR_KEY + ORGS_JSON")
    sys.exit(1)
env_org, env_org_cfg = next(iter(ENV_ORGS.items()))

# ---------- reset D1 local → trạng thái xác định ----------
with tempfile.NamedTemporaryFile("w", suffix=".sql", delete=False) as f:
    f.write(open(os.path.join(WORKER, "schema.sql"), encoding="utf-8").read())
    f.write("\nDELETE FROM sessions; DELETE FROM audit; "
            "DELETE FROM admins; DELETE FROM orgs; "
            "DELETE FROM usage; DELETE FROM machines; "
            "DELETE FROM org_pings;\n")
    schema_fp = f.name
r = subprocess.run(
    ["wrangler", "d1", "execute", "troly-fleet-db", "--local",
     "--file", schema_fp],
    cwd=WORKER, capture_output=True, text=True, timeout=120)
os.unlink(schema_fp)
check('"success": true' in r.stdout or '"success":true' in r.stdout,
      "reset + migrate D1 local")

# ---------- wrangler dev ----------
port = free_port()
base = f"http://127.0.0.1:{port}"
proc = subprocess.Popen(
    ["wrangler", "dev", "--port", str(port)],
    cwd=WORKER, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    up = False
    for _ in range(120):
        try:
            urllib.request.urlopen(base + "/", timeout=1).read()
            up = True; break
        except Exception:
            if proc.poll() is not None:
                break
            time.sleep(0.5)
    check(up, "wrangler dev lên")

    H = lambda k: {"X-Admin-Key": k}
    B = lambda t: {"Authorization": "Bearer " + t}

    # --- legacy key (kênh cũ, phải sống song song) ---
    s, d = http("GET", base + "/api/whoami")
    check(s == 401, "whoami không auth → 401")
    s, d = http("GET", base + "/api/whoami", H(VENDOR_KEY))
    check(s == 200 and d.get("role") == "master" and d.get("org") == "*"
          and d.get("via") == "key",
          "vendor_key → master '*' qua key cũ")
    s, d = http("GET", base + "/api/whoami", H(env_org_cfg["admin_key"]))
    check(s == 200 and d.get("role") == "admin" and d.get("org") == env_org,
          f"admin_key env org → admin '{env_org}'")

    # --- bootstrap + session ---
    s, d = http("POST", base + "/api/bootstrap",
                body={"user": "x@test.local", "pass": "Passw0rd!x"})
    check(s == 401, "bootstrap thiếu vendor key → 401")
    s, d = http("POST", base + "/api/bootstrap", H(VENDOR_KEY),
                body={"user": "t-master@test.local", "pass": "Passw0rd!x"})
    check(s == 200 and d.get("ok"), "bootstrap master đầu tiên")
    s, d = http("POST", base + "/api/bootstrap", H(VENDOR_KEY),
                body={"user": "second@test.local", "pass": "Passw0rd!x"})
    check(s == 409, "bootstrap lần 2 → 409 (self-lock)")
    s, d = http("POST", base + "/api/login",
                body={"user": "t-master@test.local", "pass": "sai"})
    check(s == 401, "login sai pass → 401")
    s, d = http("POST", base + "/api/login",
                body={"user": "t-master@test.local", "pass": "Passw0rd!x"})
    check(s == 200 and d.get("token"), "login đúng → token")
    tok = d["token"]
    s, d = http("GET", base + "/api/whoami", B(tok))
    check(s == 200 and d.get("via") == "session",
          "whoami Bearer → via session")

    # --- master tạo org + cấp license ---
    s, d = http("POST", base + "/api/orgs", B(tok),
                body={"name": "TSTCO", "note": "org test"})
    check(s == 200 and d.get("ok") and d["fleet"]["beacon_secret"],
          "master tạo org TSTCO → có fleet.json + admin_key")
    BS_TSTCO, AK_TSTCO = d["fleet"]["beacon_secret"], d["admin_key"]
    s, d = http("POST", base + "/api/orgs", B(tok), body={"name": "TSTCO"})
    check(s == 409, "tạo org trùng → 409")
    exp = time.strftime("%Y-%m-%d",
                        time.gmtime(time.time() + 90 * 86400))
    s, d = http("POST", base + "/api/orgs/TSTCO/license", B(tok),
                body={"seats": 5, "expiry": exp})
    lic = d.get("license") or {}
    check(s == 200 and lic.get("sig"), "master ký license")
    ls = d1("SELECT license_secret FROM orgs WHERE name='TSTCO'")
    if ls and lic.get("sig"):
        expect = hmac_mod.new(
            ls[0]["license_secret"].encode(),
            f"TSTCO|5|{exp}|{lic['issued']}".encode(),
            hashlib.sha256).hexdigest()
        check(expect == lic["sig"],
              "sig license khớp HMAC make-license.py semantics")

    # --- cty-admin + phân quyền ---
    s, d = http("POST", base + "/api/admins", B(tok),
                body={"username": "it-tstco", "password": "Passw0rd!y",
                      "role": "admin", "org": "TSTCO"})
    check(s == 200 and d.get("ok"), "master tạo cty-admin")
    s, d = http("POST", base + "/api/login",
                body={"user": "it-tstco", "pass": "Passw0rd!y"})
    tok2 = d.get("token", "")
    check(bool(tok2) and d.get("org") == "TSTCO",
          "cty-admin login → org TSTCO")
    s, d = http("POST", base + "/api/orgs", B(tok2), body={"name": "EVIL"})
    check(s == 403, "cty-admin tạo org → 403")
    s, d = http("GET", base + "/api/admins", B(tok2))
    check(s == 403, "cty-admin xem accounts → 403")
    s, d = http("POST", base + "/api/orgs/TSTCO/license", B(tok2),
                body={"seats": 1, "expiry": exp})
    check(s == 403, "cty-admin ký license → 403")

    # --- máy con pair → approve → beacon ---
    def pair(mid, sec):
        return http("POST", base + "/api/pair", {"X-Beacon-Key": sec},
                    body={"machine_id": mid, "hostname": "m-test",
                          "os": "win"})
    s, d = pair("m-test-1", BS_TSTCO)
    check(s == 200 and d.get("status") == "pending",
          "máy pair đúng secret → pending")
    s, d = pair("m-test-1", "sai-secret")
    check(s == 401, "pair sai secret → 401")
    s, d = http("POST", base + "/api/pair-approve", B(tok2),
                body={"machine_id": "m-test-1"})
    check(s == 200 and d.get("machine_key"),
          "cty-admin duyệt máy org mình")
    mk = d["machine_key"]
    # approve ghi pending_key — máy chỉ nhận key qua pair kế (repair
    # flow, parity collector.py). Beacon ngay = key chưa active
    s, d = http("POST", base + "/api/beacon", {"X-Beacon-Key": mk},
                body={"hostname": "m-test", "version": "1.0.0"})
    check(s == 403, "beacon bằng pending_key trước pair → 403")
    s, d = pair("m-test-1", BS_TSTCO)
    check(s == 200 and d.get("status") == "approved"
          and d.get("machine_key") == mk,
          "pair sau duyệt → nhận machine_key")
    s, d = http("POST", base + "/api/beacon", {"X-Beacon-Key": mk},
                body={"hostname": "m-test", "version": "1.0.0",
                      "snapshot": {"conns": {"apps": [
                          {"id": "zalo", "name": "Zalo",
                           "status": "connected"}]}}})
    check(s == 200 and d.get("ok"), "beacon máy đã duyệt → ok")

    # repair flow (N1): re-pair máy ĐÃ CÓ key → KHÔNG trả key chỉ vì
    # biết beacon_secret — flag repair, chờ admin duyệt cấp lại
    s, d = pair("m-test-1", BS_TSTCO)
    check(s == 200 and d.get("status") == "pending"
          and "machine_key" not in d,
          "re-pair máy đã duyệt → pending, không lộ key")
    s, d = http("GET", base + "/api/pending", B(tok2))
    check(any(p.get("repair") == 1 and p["machine_id"] == "m-test-1"
              for p in d.get("pending") or []),
          "máy repair hiện trong /api/pending")
    s, d = http("POST", base + "/api/pair-approve", B(tok2),
                body={"machine_id": "m-test-1"})
    mk_new = d.get("machine_key")
    check(s == 200 and mk_new and mk_new != mk,
          "duyệt repair → key mới vào pending_key")
    s, d = pair("m-test-1", BS_TSTCO)
    check(d.get("status") == "approved"
          and d.get("machine_key") == mk_new,
          "pair kế nhận key mới sau duyệt repair")
    s, d = http("POST", base + "/api/beacon", {"X-Beacon-Key": mk},
                body={"hostname": "m-test", "version": "1.0.0"})
    check(s == 403, "key cũ chết sau rotate qua repair")
    mk = mk_new
    s, d = http("GET", base + "/api/fleet", B(tok2))
    row = [m for m in d.get("machines", []) if m["machine_id"] == "m-test-1"]
    check(row and row[0].get("conns") == [{"n": "Zalo", "s": "connected"}],
          "/api/fleet trả conns gọn per máy")

    # cross-org: máy của env org — cty-admin TSTCO không đụng được
    pair("m-env-1", env_org_cfg["beacon_secret"])
    s, d = http("POST", base + "/api/pair-approve", B(tok2),
                body={"machine_id": "m-env-1"})
    check(s == 404, "cty-admin duyệt máy org khác → 404")

    # --- audit ghi đủ actor ---
    s, d = http("GET", base + "/api/audit", B(tok))
    acts = {a["action"]: a["actor"] for a in d.get("audit", [])}
    check(acts.get("org-create") == "t-master@test.local"
          and acts.get("pair-approve") == "it-tstco",
          "audit ghi đúng actor từng hành động")

    # --- chống lockout: khoá master cuối cùng bị chặn ---
    mid_m = d1("SELECT id FROM admins "
               "WHERE username='t-master@test.local'")[0]["id"]
    s, d = http("POST", base + f"/api/admins/{mid_m}", B(tok),
                body={"disabled": True})
    check(s == 400, "khoá master cuối cùng → 400")

    # --- pass chứa " : audit redact phải gọn, không lộ đuôi ---
    aid = d1("SELECT id FROM admins WHERE username='it-tstco'")[0]["id"]
    s, d = http("POST", base + f"/api/admins/{aid}", B(tok),
                body={"password": 'pa"ss12345'})
    check(s == 200, "reset pass chứa quote")
    s, d = http("GET", base + "/api/audit", B(tok))
    det = "".join(a.get("detail") or "" for a in d.get("audit", []))
    check("ss12345" not in det and '"password":"***"' in det,
          "audit redact gọn pass chứa quote")
    # reset xoá session it-tstco — login lại bằng pass mới (chứng tỏ
    # PBKDF2 xử lý quote đúng) để các bước sau dùng tiếp
    s, d = http("POST", base + "/api/login",
                body={"user": "it-tstco", "pass": 'pa"ss12345'})
    tok2 = d.get("token") or tok2
    check(bool(d.get("token")), "login lại bằng pass chứa quote")

    # --- rotate-secret ---
    s, d = http("POST", base + "/api/orgs/TSTCO/rotate-secret", B(tok2),
                body={})
    check(s == 403, "cty-admin rotate-secret → 403")
    s, d = http("POST", base + "/api/orgs/TSTCO/rotate-secret", B(tok),
                body={})
    check(s == 200 and d.get("ok"), "master rotate-secret")
    BS2, AK2 = d["fleet"]["beacon_secret"], d["admin_key"]
    check(BS2 != BS_TSTCO and AK2 != AK_TSTCO, "secret thật sự đổi")
    s, d = http("GET", base + "/api/whoami", H(AK_TSTCO))
    check(s == 401, "admin_key cũ chết ngay sau rotate")
    s, d = http("GET", base + "/api/whoami", H(AK2))
    check(s == 200 and d.get("org") == "TSTCO", "admin_key mới sống")
    s, d = pair("m-new-1", BS_TSTCO)
    check(s == 401, "beacon_secret cũ pair → 401")
    # session cty-admin (tài khoản) KHÔNG chết — rotate chỉ đụng key
    s, d = http("GET", base + "/api/whoami", B(tok2))
    check(s == 200, "session cty-admin sống qua rotate")

    # kill_machines — đá toàn bộ máy về pending
    s, d = http("POST", base + "/api/orgs/TSTCO/rotate-secret", B(tok),
                body={"kill_machines": True})
    check(s == 200 and d.get("machines_killed") == 1,
          "rotate kill_machines → đá 1 máy")
    BS3 = d["fleet"]["beacon_secret"]
    s, d = http("POST", base + "/api/beacon", {"X-Beacon-Key": mk})
    check(s == 403, "machine_key cũ beacon → 403")
    s, d = pair("m-test-1", BS3)
    check(s == 200 and d.get("status") == "pending",
          "máy re-pair bằng secret mới → pending")

    # --- audit-6 F4: /api/org-ping nhận PING_KEY (telemetry outbound)
    # hoặc master — endpoint đứng TRƯỚC admin gate vì PING_KEY không
    # phải admin credential
    s, d = http("POST", base + "/api/org-ping",
                H("test-ping-key-audit6"),
                body={"org": "TSTCO", "machines": 3})
    check(s == 200, "org-ping với PING_KEY → 200")
    s, d = http("POST", base + "/api/org-ping", H("sai-key"),
                body={"org": "TSTCO"})
    check(s == 403, "org-ping key sai → 403")
    s, d = http("POST", base + "/api/org-ping", body={"org": "TSTCO"})
    check(s == 403, "org-ping không key → 403")
    s, d = http("POST", base + "/api/org-ping", H(VENDOR_KEY),
                body={"org": "TSTCO", "machines": 3})
    check(s == 200, "org-ping với master key → 200 (fallback)")
    rows = d1("SELECT org FROM org_pings WHERE org='TSTCO'")
    check(len(rows) == 2, "org-ping ghi được 2 payload vào org_pings")

    # --- logout ---
    s, d = http("POST", base + "/api/logout", B(tok))
    s, d = http("GET", base + "/api/whoami", B(tok))
    check(s == 401, "logout → session chết")
finally:
    proc.terminate()
    try: proc.wait(timeout=10)
    except Exception: proc.kill()

print("FAIL — có lỗi" if fail else
      "PASS — worker đủ vòng đời 2-tầng (key cũ, session, org, license, "
      "phân quyền, audit, rotate)")
sys.exit(1 if fail else 0)
