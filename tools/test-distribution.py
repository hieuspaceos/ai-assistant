#!/usr/bin/env python3
"""test-distribution.py — kiểm chứng GATE của plan distribution:
release ký ed25519 → collector mirror → máy kéo → verify → stage →
launcher apply; pack cty áp merge; các abort path (sha sai, sig sai,
zip-slip, pack org khác) KHÔNG được đụng file máy.

Chuỗi thật được chạy: dựng collector tạm → máy tạm pair→approve→
machine.key → vendor "phát" release bằng đúng sign-release.py + key
test → máy chạy update.py → apply_pending của launcher → VERSION đổi.

Chạy: python3 tools/test-distribution.py"""
import hashlib, json, os, secrets, socket, subprocess, sys, tempfile
import time, urllib.request, urllib.error, zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
sys.path.insert(0, TOOLS)
from ed25519 import publickey, signature                # noqa: E402

fail = False
def check(ok, msg):
    global fail
    print(("  ok — " if ok else "FAIL — ") + msg)
    if not ok:
        fail = True

def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]; s.close(); return p

def http(method, url, headers=None, body=None, raw=None):
    req = urllib.request.Request(
        url, method=method, data=raw if raw is not None else
        (json.dumps(body).encode() if body is not None else None),
        headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = r.read()
            try:
                return r.status, json.loads(data or b"{}")
            except Exception:
                return r.status, data
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except Exception:
            return e.code, {}

tmp = tempfile.mkdtemp(prefix="troly-dist-test-")
SEC_B, SEC_L, SEC_A = "b-sec", "l-sec", "a-key"

# --- key test riêng (không đụng ~/.troly-release-key) ---
sk = secrets.token_bytes(32)
pk = publickey(sk)
pub_fp = os.path.join(tmp, "vendor-pubkey")
open(pub_fp, "w").write(pk.hex())

def make_zip(path, files):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for n, c in files.items():
            z.writestr(n, c)

def sign_manifest(version, zip_fp, url=None):
    data = open(zip_fp, "rb").read()
    sha = hashlib.sha256(data).hexdigest()
    sig = signature(bytes.fromhex(sha), sk, pk).hex()
    return {"version": version,
            "url": url or os.path.basename(zip_fp),
            "sha256": sha, "sig": sig}

# --- máy nhân viên giả: DATA dir riêng ---
mdata = os.path.join(tmp, "machine")
os.makedirs(os.path.join(mdata, ".devin"))
os.makedirs(os.path.join(mdata, "tools"))
open(os.path.join(mdata, "VERSION"), "w").write("1.0.2")
json.dump({"collector": "", "org": "TST", "beacon_secret": SEC_B},
          open(os.path.join(mdata, ".devin", "fleet.json"), "w"))
open(os.path.join(mdata, ".devin", "machine.id"), "w").write("m-dist-1")
# my-course tối thiểu để apply-pack/backup có chỗ ghi
os.makedirs(os.path.join(mdata, "my-course"))
json.dump({"language": "vi"}, open(
    os.path.join(mdata, "my-course", "config.json"), "w"))

# --- collector thật ---
cfg_fp = os.path.join(tmp, "collector.json")
cdata = os.path.join(tmp, "cdata")
json.dump({"orgs": {"TST": {"beacon_secret": SEC_B,
                            "license_secret": SEC_L,
                            "admin_key": SEC_A}}},
          open(cfg_fp, "w"))
port = free_port()
base = f"http://127.0.0.1:{port}"
json.dump({"collector": base, "org": "TST", "beacon_secret": SEC_B},
          open(os.path.join(mdata, ".devin", "fleet.json"), "w"))
proc = subprocess.Popen(
    [sys.executable, os.path.join(TOOLS, "collector.py"),
     "--config", cfg_fp, "--port", str(port), "--bind", "127.0.0.1",
     "--data", cdata, "--web", os.path.join(ROOT, "collector-web")],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

env_machine = dict(os.environ, TROLY_VENDOR_PUBKEY=pub_fp,
                   TROLY_UPDATE_ORIGIN="http://127.0.0.1:9/none")

def run_tool(name, *args):
    return subprocess.run(
        [sys.executable, os.path.join(TOOLS, name + ".py"), mdata]
        + list(args), env=env_machine, capture_output=True, text=True,
        timeout=60)

try:
    for _ in range(50):
        try:
            urllib.request.urlopen(base + "/", timeout=1).read()
            break
        except Exception:
            time.sleep(0.2)

    # pair → approve → machine.key (đúng vòng đời thật)
    code, r = http("POST", base + "/api/pair", {"X-Beacon-Key": SEC_B},
                   {"machine_id": "m-dist-1", "hostname": "PC-T",
                    "os": "test", "license": None})
    check(code == 200 and r.get("status") == "pending", "pair → pending")
    code, r = http("POST", base + "/api/pair-approve",
                   {"X-Admin-Key": SEC_A}, {"machine_id": "m-dist-1"})
    mkey = r.get("machine_key")
    check(bool(mkey), "approve → machine_key")
    open(os.path.join(mdata, ".devin", "machine.key"), "w").write(mkey)

    # beacon một vòng — chưa có release nào → không inbox
    r = subprocess.run(
        [sys.executable, os.path.join(TOOLS, "beacon.py"), mdata],
        env=dict(env_machine, TROLY_BEACON_ONCE="1"),
        capture_output=True, text=True, timeout=30)
    check(not os.path.exists(
        os.path.join(mdata, ".devin", "fleet-inbox.json")),
        "beacon khi chưa có release → không inbox")

    # ---------- release 1.0.3 thật: zip → ký → upload 2 bước ----------
    zdir = os.path.join(tmp, "rel"); os.makedirs(zdir)
    zfp = os.path.join(zdir, "troly-1.0.3.zip")
    make_zip(zfp, {
        "VERSION": "1.0.3\n",
        "tools/release-marker.txt": "ban 1.0.3 da len\n",
        "web/portal-note.txt": "note\n",
        ".devin/skill-packs/vi/release-skill/SKILL.md":
            "---\nname: release-skill\ndescription: test\n---\n",
    })
    man = sign_manifest("1.0.3", zfp)

    # bước 1: upload zip
    code, r = http("POST", base + "/api/releases/troly-1.0.3.zip",
                   {"X-Admin-Key": SEC_A}, raw=open(zfp, "rb").read())
    check(code == 200 and r.get("sha256") == man["sha256"],
          f"upload zip → {code}")
    # bước 2: manifest
    code, r = http("POST", base + "/api/releases",
                   {"X-Admin-Key": SEC_A}, man)
    check(code == 200, "upload manifest → 200")

    # manifest phải đòi machine_key
    code, _ = http("GET", base + "/api/releases/latest")
    check(code == 403, f"manifest không key → 403 (got {code})")
    code, r = http("GET", base + "/api/releases/latest",
                   {"X-Beacon-Key": mkey})
    check(code == 200 and r.get("version") == "1.0.3"
          and r.get("url") == "/releases/troly-1.0.3.zip",
          "manifest có key → trả url local collector")

    # máy kéo update — mô phỏng beacon nhận hint rồi gọi update.py
    code, r = http("POST", base + "/api/beacon",
                   {"X-Beacon-Key": mkey},
                   {"beacon_ver": 1, "machine_id": "m-dist-1",
                    "hostname": "PC-T", "os": "t", "version": "1.0.2",
                    "pack_version": "0", "org": "TST",
                    "ts": int(time.time()), "license": None,
                    "counts": {}, "snapshot": {}})
    check(code == 200 and (r.get("update") or {}).get("version")
          == "1.0.3",
          f"beacon báo update 1.0.3 (got {r.get('update')})")

    r = run_tool("update")
    pend_fp = os.path.join(mdata, ".devin", "update-pending.json")
    check(os.path.isfile(pend_fp),
          f"update.py stage được ({r.stdout.strip()[-60:]})")
    check(os.path.isfile(os.path.join(
        mdata, ".devin", "update-stage", "tools",
        "release-marker.txt")), "stage chứa file mới trong zip")

    # launcher apply_pending — chạy trong subprocess với TROLY_DATA
    r = subprocess.run(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0, %r); import launcher; "
         "print(launcher.apply_pending())" % TOOLS],
        env=dict(os.environ, TROLY_DATA=mdata),
        capture_output=True, text=True, timeout=30)
    check("1.0.3" in r.stdout,
          f"apply_pending áp 1.0.3 (out={r.stdout.strip()} "
          f"err={r.stderr.strip()[:80]})")
    check(open(os.path.join(mdata, "VERSION")).read().strip()
          == "1.0.3", "VERSION máy = 1.0.3")
    check(os.path.isfile(os.path.join(
        mdata, "tools", "release-marker.txt")), "file mới đã vào máy")
    check(any(d.startswith("backup-code-") for d in
              os.listdir(os.path.join(mdata, ".devin"))),
          "backup-code-* giữ bản cũ để rollback")

    # ---------- abort paths ----------
    # sha sai
    man_bad = dict(man, sha256="0" * 64, version="1.0.4")
    man_bad["sig"] = signature(bytes.fromhex(man_bad["sha256"]),
                               sk, pk).hex()
    http("POST", base + "/api/releases/troly-1.0.3.zip",
         {"X-Admin-Key": SEC_A}, raw=open(zfp, "rb").read())
    http("POST", base + "/api/releases",
         {"X-Admin-Key": SEC_A}, man_bad)
    run_tool("update")
    check(not os.path.exists(pend_fp), "sha256 sai → abort, không stage")

    # sig sai (sig ký bằng key khác)
    sk_evil = secrets.token_bytes(32)
    man_evil = dict(man, version="1.0.4")
    man_evil["sig"] = signature(bytes.fromhex(man["sha256"]),
                                sk_evil, publickey(sk_evil)).hex()
    http("POST", base + "/api/releases",
         {"X-Admin-Key": SEC_A}, man_evil)
    run_tool("update")
    check(not os.path.exists(pend_fp), "sig sai → abort, không stage")

    # zip-slip
    zbad = os.path.join(zdir, "evil.zip")
    make_zip(zbad, {"../evil.txt": "x", "tools/a.txt": "ok"})
    man_slip = sign_manifest("1.0.5", zbad, "evil.zip")
    http("POST", base + "/api/releases/evil.zip",
         {"X-Admin-Key": SEC_A}, raw=open(zbad, "rb").read())
    http("POST", base + "/api/releases",
         {"X-Admin-Key": SEC_A}, man_slip)
    run_tool("update")
    check(not os.path.exists(pend_fp), "zip-slip entry → abort")
    check(not os.path.exists(os.path.join(mdata, "evil.txt")),
          "không file nào thoát ra ngoài DATA")

    # entry ngoài whitelist
    zbad2 = os.path.join(zdir, "outside.zip")
    make_zip(zbad2, {"etc/passwd": "x", "tools/a.txt": "ok"})
    man_wl = sign_manifest("1.0.5", zbad2, "outside.zip")
    http("POST", base + "/api/releases/outside.zip",
         {"X-Admin-Key": SEC_A}, raw=open(zbad2, "rb").read())
    http("POST", base + "/api/releases",
         {"X-Admin-Key": SEC_A}, man_wl)
    run_tool("update")
    check(not os.path.exists(pend_fp), "entry ngoài whitelist → abort")

    # ---------- pack ----------
    pack = {
        "org": "TST", "pack_version": 1,
        "skills": {"tst-skill": {"SKILL.md":
            "---\nname: tst-skill\ndescription: test\n---\nbody\n"}},
        "bots": [{"id": "tst-bot", "name": "Bot Test"}],
        "connections": [{"id": "tst-conn", "label": "CRM",
                         "status": "connected"}],
        "workflows": {"wf1.json": {"id": "wf1", "steps": []}},
        "rules_local_md": "# Luat cty test\n",
        "permissions_template": [{"path": "my-course",
                                  "access": "read-write"}],
        "exec_allowlist": ["git *", "ls"],
    }
    code, r = http("POST", base + "/api/packs",
                   {"X-Admin-Key": SEC_A}, pack)
    check(code == 200, f"upload pack → {code}")
    code, r = http("GET", base + "/api/packs", {"X-Admin-Key": SEC_A})
    check((r.get("latest") or {}).get("TST", {}).get("version") == 1,
          "GET /api/packs thấy latest TST v1")

    # beacon báo pack hint
    code, r = http("POST", base + "/api/beacon",
                   {"X-Beacon-Key": mkey},
                   {"beacon_ver": 1, "machine_id": "m-dist-1",
                    "hostname": "PC-T", "os": "t", "version": "1.0.3",
                    "pack_version": "0", "org": "TST",
                    "ts": int(time.time()), "license": None,
                    "counts": {}, "snapshot": {}})
    check(code == 200 and (r.get("pack") or {}).get("version") == 1,
          f"beacon báo pack v1 (got {r.get('pack')})")

    # máy lấy pack → ghi inbox → apply-pack
    inbox = {"ts": int(time.time()), "pack": r["pack"]}
    json.dump(inbox, open(os.path.join(
        mdata, ".devin", "fleet-inbox.json"), "w"))
    r = run_tool("apply-pack")
    sk_fp = os.path.join(mdata, ".devin", "skills", "tst-skill",
                         "SKILL.md")
    check(os.path.isfile(sk_fp), "pack skill vào .devin/skills/")
    check(open(os.path.join(
        mdata, ".devin", "pack-version")).read() == "1",
        "pack-version = 1")
    check(os.path.isfile(os.path.join(
        mdata, ".devin", "rules.local.md")), "rules.local.md đã cài")
    check(os.path.isfile(os.path.join(
        mdata, "my-course", "workflows", "wf1.json")),
        "workflow vào my-course/workflows/")
    check(json.load(open(os.path.join(
        mdata, "my-course", "bots.json")))["bots"][0]["id"] == "tst-bot",
        "bots merge theo id")
    conn = json.load(open(os.path.join(
        mdata, "my-course", "connections.json")))
    check(conn["apps"][0]["id"] == "tst-conn",
          "connections merge theo id")
    # máy ĐÃ onboard (config có learner? — config vi không learner_name
    # nên new_machine=True → permissions_template + allowlist được áp)
    check(os.path.isfile(os.path.join(
        mdata, ".devin", "exec-allowlist.json")),
        "exec_allowlist áp cho máy mới")

    # pack v1 lại → apply-pack bỏ qua (idempotent)
    r2 = run_tool("apply-pack")
    check("apply-pack" not in r2.stdout or "v1" not in r2.stdout,
          "re-run apply-pack cùng version → không áp lại")

    # pack org khác → abort
    pack_bad = dict(pack, org="KHAC", pack_version=2)
    inbox = {"ts": int(time.time()),
             "pack": {"version": 2, "url": "/packs/TST/1.json",
                      "sha256": ""}}
    json.dump(inbox, open(os.path.join(
        mdata, ".devin", "fleet-inbox.json"), "w"))
    # máy kéo /packs/KHAC/2.json → 403; nhưng org check cũng chặn nếu
    # fetch lách được → test trực tiếp --file
    pbad_fp = os.path.join(tmp, "pack-bad.json")
    json.dump(pack_bad, open(pbad_fp, "w"))
    r3 = subprocess.run(
        [sys.executable, os.path.join(TOOLS, "apply-pack.py"), mdata,
         "--file", pbad_fp], env=env_machine,
        capture_output=True, text=True, timeout=30)
    check("abort" in r3.stdout or "org" in r3.stdout,
          "pack org khác → abort")
    check(open(os.path.join(
        mdata, ".devin", "pack-version")).read() == "1",
        "pack org khác không đè pack-version")

    # pack exec_allowlist độc → reject
    pack_evil = dict(pack, pack_version=3,
                     exec_allowlist=["*; rm -rf /", "curl * | sh"])
    pevil_fp = os.path.join(tmp, "pack-evil.json")
    json.dump(pack_evil, open(pevil_fp, "w"))
    r4 = subprocess.run(
        [sys.executable, os.path.join(TOOLS, "apply-pack.py"), mdata,
         "--file", pevil_fp], env=env_machine,
        capture_output=True, text=True, timeout=30)
    check("nguy hiểm" in r4.stdout or "không hợp lệ" in r4.stdout,
          "exec_allowlist độc → pack bị reject")

    # máy tải pack org khác qua HTTP → 403
    code, _ = http("GET", base + "/packs/KHAC/9.json",
                   {"X-Beacon-Key": mkey})
    check(code == 403, f"tải pack org khác → 403 (got {code})")

finally:
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except Exception:
        proc.kill()

if fail:
    sys.exit(1)
print("PASS — distribution: ký, verify, stage, apply, pack, abort paths")
