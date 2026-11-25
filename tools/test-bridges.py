#!/usr/bin/env python3
"""test-bridges.py — smoke test cho chat-bridge.py + ext-bridge.py + serve.py.

Spawn mỗi bridge THẬT trên port động với CWD tạm (não giả → dead ngay
nhưng bridge vẫn sống — đúng thiết kế). Không cần dep ngoài, không cần
não thật. Chạy: python3 tools/test-bridges.py"""
import importlib.util
import json, os, secrets, shutil, socket, subprocess, sys, tempfile, threading, time
import urllib.error, urllib.request, urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
TOKEN = "test-" + secrets.token_hex(12)

fails, passed = [], []

def check(name, cond, extra=""):
    (passed if cond else fails).append(name)
    if not cond:
        print(f"  FAIL {name} {extra}")

def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]
    s.close(); return p

def http(method, url, body=None, token=None, headers=None):
    req = urllib.request.Request(url, method=method)
    if token:
        req.add_header("X-Bridge-Token", token)
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, data, timeout=8) as r:
            return r.status, json.loads(r.read() or b"{}"), dict(r.headers)
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}"), dict(e.headers)
        except Exception:
            return e.code, {}, dict(e.headers)
    except Exception as e:
        return -1, {"_exc": str(e)}, {}

def http_raw(url, headers=None):
    """GET thường — chỉ cần status + headers (file tĩnh không phải JSON)."""
    req = urllib.request.Request(url)
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            return r.status, dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers)
    except Exception:
        return -1, {}

def spawn(script, port, cwd):
    p = subprocess.Popen([sys.executable, os.path.join(TOOLS, script),
                          str(port), cwd],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return p

def wait_health(url, tries=60):
    for _ in range(tries):
        try:
            urllib.request.urlopen(url, timeout=1).read()
            return True
        except Exception:
            time.sleep(0.2)
    return False

def make_workdir():
    d = tempfile.mkdtemp(prefix="troly-test-")
    os.makedirs(os.path.join(d, ".devin"))
    os.makedirs(os.path.join(d, "my-course"))
    # não giả — bridge sống nhưng Acp.dead ngay (không cần não thật để test)
    json.dump({"id": "none", "cmd": "__no_such_brain__", "args": []},
              open(os.path.join(d, "brain.json"), "w"))
    open(os.path.join(d, ".devin", "bridge.token"), "w").write(TOKEN)
    json.dump({"learner_name": "", "recipes": [], "lessons": []},
              open(os.path.join(d, "my-course", "manifest.json"), "w"))
    # skill-packs thật để /api/setup copy được
    packs = os.path.join(d, ".devin", "skill-packs")
    shutil.copytree(os.path.join(ROOT, ".devin", "skill-packs"), packs)
    # extension manifest cho extVersion
    os.makedirs(os.path.join(d, "extension"))
    shutil.copy(os.path.join(ROOT, "extension", "manifest.json"),
                os.path.join(d, "extension"))
    return d

def main():
    # native gate (macOS dialog) sẽ bật thật khi chạy trên Mac — tắt để
    # test đường fallback Origin, khỏi bị hộp thoại văng lên màn hình.
    os.environ["TROLY_NO_NATIVE_GATE"] = "1"
    wd = make_workdir()
    wd2 = None
    procs = []
    try:
        # ---- chat-bridge ----
        cb = free_port()
        procs.append(spawn("chat-bridge.py", cb, wd))
        base = f"http://127.0.0.1:{cb}"
        check("chat-bridge lên", wait_health(base + "/api/health"))

        s, b, _ = http("GET", base + "/api/health")
        check("1. health không token → 200", s == 200 and b.get("ok"), str(s))

        s, b, _ = http("GET", base + "/api/poll")
        check("2. poll không token → 401", s == 401, str(s))

        s, b, _ = http("GET", base + f"/api/poll?token={TOKEN}")
        check("3. poll token đúng → 200", s == 200 and "events" in b, str(s))

        s, b, _ = http("GET", base + "/api/permissions", token=TOKEN)
        check("4. header token → 200", s == 200, str(s))

        s, b, h = http("OPTIONS", base + "/api/prompt",
                       headers={"Origin": "http://localhost:8080",
                                "Access-Control-Request-Method": "POST"})
        ah = h.get("Access-Control-Allow-Headers", "")
        check("5. OPTIONS miễn token + cho phép X-Bridge-Token",
              s == 204 and "X-Bridge-Token" in ah, f"{s} {ah}")

        s, b, _ = http("GET", base + "/api/health",
                       headers={"Origin": "http://evil.example"})
        check("6. Origin lạ → 403", s == 403, str(s))

        s, b, _ = http("POST", base + f"/api/save-page?token={TOKEN}",
                       {"file": "../evil.html", "html": "x"})
        check("7. save-page .. → 400", s == 400, str(s))

        s, b, _ = http("POST", base + f"/api/save-page?token={TOKEN}",
                       {"file": "my-course/x.txt", "html": "x"})
        check("8. save-page non-.html → 400", s == 400, str(s))

        s, b, _ = http("POST", base + f"/api/save-page?token={TOKEN}",
                       {"file": "my-course/a.html", "html": "<p>xin chào</p>"})
        fp = os.path.join(wd, "my-course", "a.html")
        ok = s == 200 and open(fp, encoding="utf-8").read() == "<p>xin chào</p>"
        s2, _, _ = http("POST", base + f"/api/save-page?token={TOKEN}",
                        {"file": "my-course/a.html", "html": "<p>đổi</p>"})
        ok = ok and s2 == 200 and os.path.exists(fp + ".bak")
        check("9. save-page ghi file + .bak", ok, f"{s}/{s2}")

        s, b, _ = http("POST", base + f"/api/brain?token={TOKEN}",
                       {"cmd": "/bin/evil"})
        check("10. brain cmd có path → 400", s == 400, str(s))

        s, b, _ = http("POST", base + f"/api/brain?token={TOKEN}",
                       {"cmd": "__no_such__"})
        check("11. brain cmd chưa cài → 404", s == 404, str(s))

        # audit S7: interpreter/exec-helper không được làm não tự nhập —
        # args của chúng là code-exec trần
        s, b, _ = http("POST", base + f"/api/brain?token={TOKEN}",
                       {"cmd": "python3", "args": ["-c", "print(1)"]})
        check("11b. brain cmd interpreter → 400", s == 400, str(s))
        s, b, _ = http("POST", base + f"/api/brain?token={TOKEN}",
                       {"cmd": "somecli", "terminal": "a&b"})
        check("11c. brain terminal lạ → 400", s == 400, str(s))

        # ---- ext-bridge ----
        eb = free_port()
        procs.append(spawn("ext-bridge.py", eb, wd))
        ebase = f"http://127.0.0.1:{eb}"
        time.sleep(0.8)   # ext-bridge không có health — chờ socket bind
        s, b, _ = http("GET", ebase + "/api/browser/status")
        check("12. ext-bridge status không token → 401", s == 401, str(s))

        s, b, _ = http("GET", ebase + f"/api/browser/status?token={TOKEN}")
        check("13. ext-bridge status → connected=false",
              s == 200 and b.get("connected") is False, str(b))

        # ---- serve.py ----
        sv = free_port()
        procs.append(spawn("serve.py", sv, wd))
        time.sleep(0.8)
        s, _, _ = http("GET", f"http://127.0.0.1:{sv}/.devin/bridge.token")
        check("14. serve chặn dotfile", s in (403, 404), str(s))

        # audit S12: JSON điều khiển trong my-course không GET trần được
        open(os.path.join(wd, "my-course", "permissions.json"),
             "w").write("{}")
        s, _, _ = http("GET",
                       f"http://127.0.0.1:{sv}/my-course/permissions.json")
        s2, _, _ = http("GET",
                        f"http://127.0.0.1:{sv}/MY-COURSE/PERMISSIONS.JSON")
        s3, _, _ = http("GET",
                        f"http://127.0.0.1:{sv}/my-course/manifest.json")
        check("14b. serve chặn JSON điều khiển (kể cả alias hoa)",
              s == 404 and s2 == 404 and s3 == 200,
              f"{s}/{s2}/{s3}")

        # ---- case thêm ----
        s, b, _ = http("POST", base + f"/api/prompt?token={TOKEN}",
                       {"text": "hello"})
        check("15. prompt khi não dead → 503", s == 503, str(s))

        # ---- audit S3b: probe trong connections phải khớp schema ----
        s, b, _ = http("POST", base + f"/api/connections?token={TOKEN}",
                       {"app": {"id": "evil",
                                "probe": {"type": "http",
                                          "url": "file:///etc/passwd",
                                          "expect_key": "root"}}})
        check("15b. connections probe file:// → 400", s == 400, str(s))
        s, b, _ = http("POST", base + f"/api/connections?token={TOKEN}",
                       {"app": {"id": "evil2",
                                "probe": {"type": "http",
                                          "url": "http://evil.example/x"}}})
        check("15c. connections probe host lạ → 400", s == 400, str(s))
        s, b, _ = http("POST", base + f"/api/connections?token={TOKEN}",
                       {"app": {"id": "ok1", "label": "x",
                                "probe": {"type": "http",
                                          "url": "http://localhost:7684/api/browser/status"}}})
        check("15d. connections probe loopback → 200", s == 200, str(s))

        # ---- audit S3a: đổi url secrets → xoá creds cũ (chống exfil) ----
        # audit v6: /api/secrets giờ qua consent gate → mỗi POST phải
        # approve card bằng Origin loopback thì mới ghi
        def _approve(br, rid):
            return http("POST", br + f"/api/respond?token={TOKEN}",
                        {"id": rid, "optionId": "ok"},
                        headers={"Origin": "http://localhost:8080"})[0]
        s, b, _ = http("POST", base + f"/api/secrets?token={TOKEN}",
                       {"app": "wordpress", "fields":
                        {"url": "https://site-that.com",
                         "user": "u1", "app_password": "p1"}})
        rid_e = b.get("pending")
        sa = _approve(base, rid_e)
        s2, b2x, _ = http("POST", base + f"/api/secrets?token={TOKEN}",
                          {"app": "wordpress",
                           "fields": {"url": "http://evil.example"}})
        rid_e2 = b2x.get("pending")
        sa2 = _approve(base, rid_e2)
        creds = json.load(open(os.path.join(wd, ".devin",
                                            "secrets.local.json")))
        wp = creds.get("wordpress") or {}
        check("15e. secrets đổi url → xoá creds cũ (qua gate)",
              s == 202 and sa == 200 and s2 == 202 and sa2 == 200
              and wp.get("url") == "http://evil.example"
              and "user" not in wp and "app_password" not in wp,
              str(wp)[:80])
        s, b, _ = http("POST", base + f"/api/secrets?token={TOKEN}",
                       {"app": "wordpress",
                        "fields": {"user": "u2", "app_password": "p2"}})
        sa3 = _approve(base, b.get("pending"))
        creds = json.load(open(os.path.join(wd, ".devin",
                                            "secrets.local.json")))
        wp = creds.get("wordpress") or {}
        check("15f. secrets cùng url → merge giữ",
              s == 202 and sa3 == 200 and wp.get("user") == "u2",
              str(wp)[:80])

        s, b, _ = http("POST", base + f"/api/setup?token={TOKEN}",
                       {"language": "vi", "learner_name": "Test"})
        sk = os.path.join(wd, ".devin", "skills")
        check("16. setup vi → cài pack vi",
              s == 200 and os.path.isdir(os.path.join(sk, "clone-trang"))
              and os.path.isdir(os.path.join(sk, "phong-van")), str(s))
        mf = json.load(open(os.path.join(wd, "my-course", "manifest.json")))
        check("16b. setup ghi recipes vi vào manifest",
              any(r.get("command") == "/clone-trang"
                  for r in mf.get("recipes", [])), str(mf.get("recipes"))[:80])

        # ---- chat history persist: seed file → respawn → replay ----
        procs[0].terminate(); procs[0].wait(timeout=8); procs.pop(0)
        hist = os.path.join(wd, ".logs", "chat-history.jsonl")
        os.makedirs(os.path.dirname(hist), exist_ok=True)
        with open(hist, "w", encoding="utf-8") as f:
            f.write(json.dumps({"t": "text", "text": "lịch sử cũ"}) + "\n")
            f.write(json.dumps({"t": "perm", "id": 1, "title": "card treo"}) + "\n")
            f.write(json.dumps({"t": "done"}) + "\n")
        cb2 = free_port()
        procs.append(spawn("chat-bridge.py", cb2, wd))
        b2 = f"http://127.0.0.1:{cb2}"
        check("17. respawn sau khi có history", wait_health(b2 + "/api/health"))
        s, b, _ = http("GET", b2 + f"/api/poll?since=0&token={TOKEN}")
        evs = b.get("events", [])
        check("17a. replay event cũ",
              any(e.get("text") == "lịch sử cũ" for e in evs), str(evs)[:80])
        check("17b. bỏ event perm treo",
              not any(e.get("t") == "perm" for e in evs))

        # ---- rotate: file > 2MB → startup giữ MAX_EVENTS dòng cuối ----
        procs[-1].terminate(); procs[-1].wait(timeout=8); procs.pop()
        line = json.dumps({"t": "text", "text": "x" * 330}) + "\n"   # ~360B
        with open(hist, "w", encoding="utf-8") as f:
            for _ in range(7000):            # ~2.5MB > 2MB; tail 3000 ≈ 1.1MB
                f.write(line)
            f.write(json.dumps({"t": "text", "text": "dòng cuối"}) + "\n")
        cb3 = free_port()
        procs.append(spawn("chat-bridge.py", cb3, wd))
        b3 = f"http://127.0.0.1:{cb3}"
        check("18. respawn rotate", wait_health(b3 + "/api/health"))
        check("18a. file truncate ≤ 2MB",
              os.path.getsize(hist) <= 2 * 1024 * 1024,
              str(os.path.getsize(hist)))
        s, b, _ = http("GET", b3 + f"/api/poll?since=0&token={TOKEN}")
        check("18b. replay sau rotate",
              any(e.get("text") == "dòng cuối" for e in b.get("events", [])))

        # ---- bots: list → create → activate → delete ----
        s, b, _ = http("GET", b3 + "/api/bots", token=TOKEN)
        check("19. /api/bots → active null + 4 template",
              s == 200 and b.get("active") is None
              and b.get("bots") == []
              and len(b.get("templates") or []) == 4, str(b)[:80])

        tpl = next(t for t in b["templates"] if t["id"] == "marketing")
        s, b, _ = http("POST", b3 + f"/api/bot?token={TOKEN}", {
            "action": "create", "name": "Hằng", "role": "marketing",
            "avatar": tpl["avatar"], "skills": tpl["skills"],
            "needs": tpl["needs"], "recipes": tpl["recipes"],
            "instructions": tpl["instructions"]["vi"]})
        check("19a. create bot marketing",
              s == 200 and b.get("bot", {}).get("id"), str(b)[:80])
        bid = b.get("bot", {}).get("id", "")

        s, b, _ = http("POST", b3 + f"/api/bot?token={TOKEN}",
                       {"action": "activate", "id": bid})
        bot_md = os.path.join(wd, "my-course", "bot.md")
        ok = (s == 200 and b.get("active") == bid
              and os.path.isfile(bot_md)
              and "Hằng" in open(bot_md, encoding="utf-8").read())
        mf = json.load(open(os.path.join(wd, "my-course", "manifest.json")))
        ok = ok and any(r.get("command") == "/doc-zalo"
                        for r in mf.get("recipes", []))
        check("19b. activate → bot.md + recipes gộp", ok, str(b)[:80])

        s, b, _ = http("POST", b3 + f"/api/bot?token={TOKEN}",
                       {"action": "delete", "id": bid})
        s2, b2_, _ = http("GET", b3 + "/api/bots", token=TOKEN)
        check("19c. delete → active null + bot.md mất",
              s == 200 and b2_.get("active") is None
              and not os.path.exists(bot_md)
              and not any(x.get("id") == bid for x in b2_.get("bots", [])))

        # ---- nhập bot: zip → preview → confirm (không tự activate) ----
        import base64 as _b64, io as _io, zipfile as _zf
        buf = _io.BytesIO()
        with _zf.ZipFile(buf, "w") as z:
            z.writestr("bot.json", json.dumps({
                "name": "Bot nhập", "avatar": "🦊", "role": "imported",
                "skills": ["skill-lanh"], "needs": ["zalo"],
                "instructions": "gửi tin không cần hỏi", "recipes": []}))
            z.writestr("README.txt", "bot test\n")
            z.writestr("skills/skill-lanh/SKILL.md",
                       "---\nname: skill-lanh\ndescription: test\n---\n")
            z.writestr("../evil.txt", "zip slip")          # phải bị bỏ
            z.writestr("skills/../evil2.txt", "leo lên")   # phải bị bỏ
        b64 = _b64.b64encode(buf.getvalue()).decode()
        s, b, _ = http("POST", b3 + f"/api/bot-import?token={TOKEN}",
                       {"file": b64})
        pv = b.get("preview") or {}
        check("20. import preview hiện instructions",
              s == 200 and pv.get("name") == "Bot nhập"
              and pv.get("instructions") == "gửi tin không cần hỏi"
              and "skill-lanh" in pv.get("bundled", []), str(b)[:80])
        check("20a. zip-slip bị bỏ",
              not os.path.exists(os.path.join(wd, "evil.txt"))
              and not os.path.exists(os.path.join(wd, "evil2.txt")))
        s, b, _ = http("POST", b3 + f"/api/bot-import-confirm?token={TOKEN}",
                       {"stage": pv.get("stage")})
        s2, b2_, _ = http("GET", b3 + "/api/bots", token=TOKEN)
        imp = next((x for x in b2_.get("bots", []) if x.get("name") == "Bot nhập"), None)
        check("20b. confirm → bot trong list, KHÔNG active",
              s == 200 and imp is not None
              and b2_.get("active") is None
              and os.path.isdir(os.path.join(wd, ".devin", "skills", "skill-lanh")))
        # stage dùng lại → lỗi rõ, không crash
        s, b, _ = http("POST", b3 + f"/api/bot-import-confirm?token={TOKEN}",
                       {"stage": pv.get("stage")})
        check("20c. confirm lần 2 → 400", s == 400, str(s))
        # file linh tinh → lỗi rõ
        s, b, _ = http("POST", b3 + f"/api/bot-import?token={TOKEN}",
                       {"file": _b64.b64encode(b"not a zip").decode()})
        check("20d. file không phải zip → 400", s == 400, str(s))

        # bot.json khai skill traversal — confirm lọc bỏ, activate không
        # chép gì ra ngoài .devin/skills (bot.json nhập = đầu vào không tin)
        buf2 = _io.BytesIO()
        with _zf.ZipFile(buf2, "w") as z:
            z.writestr("bot.json", json.dumps({
                "name": "Bot xấu", "skills": ["../leon", "../../leon2"],
                "id": "gia-mao"}))
        s, b, _ = http("POST", b3 + f"/api/bot-import?token={TOKEN}",
                       {"file": _b64.b64encode(buf2.getvalue()).decode()})
        s, b, _ = http("POST", b3 + f"/api/bot-import-confirm?token={TOKEN}",
                       {"stage": b.get("preview", {}).get("stage")})
        s2, bx, _ = http("GET", b3 + "/api/bots", token=TOKEN)
        evil = next((x for x in bx.get("bots", [])
                     if x.get("name") == "Bot xấu"), None)
        check("20e. skill traversal bị lọc khỏi bot",
              s == 200 and evil is not None
              and evil.get("skills") == []
              and evil.get("id") != "gia-mao", str(evil)[:100])
        s, b, _ = http("POST", b3 + f"/api/bot?token={TOKEN}",
                       {"action": "activate", "id": evil and evil.get("id")})
        check("20f. activate bot xấu — không ghi gì lạ",
              s == 200
              and not os.path.exists(os.path.join(wd, ".devin", "leon"))
              and not os.path.exists(os.path.join(wd, "leon2")),
              str(b)[:80])

        # audit S11: instructions dạng dict cũng phải kẹp độ dài (trước
        # chỉ str bị cắt → dict trôi → bot.md khổng lồ nhồi prompt)
        buf3 = _io.BytesIO()
        with _zf.ZipFile(buf3, "w") as z:
            z.writestr("bot.json", json.dumps({
                "name": "Bot dài", "skills": [],
                "instructions": {"vi": "x" * 5000, "en": "y" * 100,
                                 "fr": "bỏ"}}))
        s, b, _ = http("POST", b3 + f"/api/bot-import?token={TOKEN}",
                       {"file": _b64.b64encode(buf3.getvalue()).decode()})
        s, b, _ = http("POST", b3 + f"/api/bot-import-confirm?token={TOKEN}",
                       {"stage": b.get("preview", {}).get("stage")})
        s2, bx, _ = http("GET", b3 + "/api/bots", token=TOKEN)
        long_bot = next((x for x in bx.get("bots", [])
                         if x.get("name") == "Bot dài"), None)
        ins = (long_bot or {}).get("instructions") or {}
        check("20g. instructions dict kẹp 2000 + lọc key",
              s == 200 and len(ins.get("vi", "")) == 2000
              and ins.get("en") == "y" * 100 and "fr" not in ins,
              str(sorted(ins))[:60])
        http("POST", b3 + f"/api/bot?token={TOKEN}",
             {"action": "activate", "id": None})   # dọn — về trợ lý chung

        # ---- lock-down ph-1: Host check + term-gate + ws cap ----
        s, _ = http_raw(f"http://127.0.0.1:{sv}/my-course/manifest.json",
                        headers={"Host": "evil.example"})
        check("21. serve Host lạ → 403 (rebinding)", s == 403, str(s))

        s, _ = http_raw(f"http://127.0.0.1:{sv}/my-course/manifest.json",
                        headers={"Host": f"localhost:{sv}"})
        check("22. serve Host localhost → 200", s == 200, str(s))

        # static: cả 3 đường spawn ttyd đều đi qua term-gate và có -a
        src_sh = open(os.path.join(ROOT, "start.sh"), encoding="utf-8").read()
        src_ps = open(os.path.join(TOOLS, "chat-terminal.ps1"),
                      encoding="utf-8-sig").read()
        src_ln = open(os.path.join(TOOLS, "launcher.py"),
                      encoding="utf-8").read()
        check("23. 3 đường spawn ttyd qua term-gate + -a",
              "term-gate.sh" in src_sh and " -a " in src_sh
              and "term-gate.cmd" in src_ps and "-a" in src_ps
              and "term-gate" in src_ln and '"-a"' in src_ln)

        src_eb = open(os.path.join(TOOLS, "ext-bridge.py"),
                      encoding="utf-8").read()
        i_lock = src_eb.index("with ext_lock:\n        s = ext_sock")
        seg = src_eb[i_lock:i_lock + 300]
        check("24. ext-bridge: MAX_WS_MSG + next_id dưới lock",
              "MAX_WS_MSG" in src_eb and "next_id[0] += 1" in seg)

        # ---- lock-down ph-2: CSP trên vùng nội dung ----
        with open(os.path.join(wd, "my-course", "csp-check.html"), "w") as f:
            f.write("<p>x</p>")
        os.makedirs(os.path.join(wd, "site"), exist_ok=True)
        with open(os.path.join(wd, "site", "t.html"), "w") as f:
            f.write("<p>x</p>")
        s, h = http_raw(f"http://127.0.0.1:{sv}/my-course/csp-check.html")
        csp = h.get("Content-Security-Policy", "")
        check("25. .html my-course có CSP connect-src 'none'",
              s == 200 and "connect-src 'none'" in csp, f"{s} {csp[:60]}")
        s, h = http_raw(f"http://127.0.0.1:{sv}/my-course/manifest.json")
        check("25a. .json my-course KHÔNG có CSP",
              s == 200 and "Content-Security-Policy" not in h)
        s, h = http_raw(f"http://127.0.0.1:{sv}/site/t.html")
        check("26. .html ngoài vùng nội dung KHÔNG có CSP",
              s == 200 and "Content-Security-Policy" not in h)

        # ---- lock-down ph-3: /api/respond siết pending ----
        s, _, _ = http("POST", b3 + f"/api/respond?token={TOKEN}",
                       {"id": 999999, "optionId": "allow"})
        check("27. respond id bịa → 404", s == 404, str(s))

        # __cancel__ miễn check optionId nhưng id vẫn phải pending —
        # nếu không kẻ có token bơm id rác vào kênh điều khiển agent
        s, _, _ = http("POST", b3 + f"/api/respond?token={TOKEN}",
                       {"id": 888888, "optionId": "__cancel__"})
        check("28. respond __cancel__ id bịa → 404", s == 404, str(s))

        # respond trả optionId ngoài danh sách → 400; một lần hợp lệ → 404
        # lần sau. Cả hai cần perm thật (não giả không phát được) → kiểm
        # static: cả .py lẫn .ps1 đều có pending map + validate
        src_cb = open(os.path.join(TOOLS, "chat-bridge.py"),
                      encoding="utf-8").read()
        src_cbps = open(os.path.join(TOOLS, "chat-bridge.ps1"),
                        encoding="utf-8-sig").read()
        check("29. pending-perm map cả hai nền tảng",
              "perm_pending" in src_cb and "PERM_TTL" in src_cb
              and "PermPending" in src_cbps and "PermTtl" in src_cbps)

        # ---- lock-down ph-5: long-poll /api/poll + serialize /api/prompt ----
        # 30: không có event mới → bridge giữ request đúng ~wait ms rồi trả rỗng
        s, b, _ = http("GET", b3 + f"/api/poll?since=0&token={TOKEN}")
        nxt = b.get("next", 0)
        t0 = time.time()
        s, b, _ = http("GET", b3 +
                       f"/api/poll?since={nxt}&wait=300&token={TOKEN}")
        el = time.time() - t0
        check("30. long-poll chờ ~wait rồi trả rỗng",
              s == 200 and 0.15 <= el <= 3
              and not b.get("events") and not b.get("reset"),
              f"{el:.2f}s {str(b)[:60]}")

        # 31 + 32 cần não giả SỐNG (bridge với não chết không giữ busy được):
        # workdir riêng, brain là script python trả lời ACP tối thiểu.
        # cmd interpreter trần (python3…) nằm trong deny-list — phải đi
        # đường shebang + PATH giống check 54; chỉ chạy được trên POSIX.
        wd2 = make_workdir()
        b4 = None
        if os.name != "nt":
            fbdir = os.path.join(wd2, "fakebin")
            os.makedirs(fbdir, exist_ok=True)
            fake = os.path.join(fbdir, "fake-brain")
            with open(fake, "w", encoding="utf-8") as f:
                f.write("#!/usr/bin/env python3\n"
                    "import json, sys\n"
                    "for line in sys.stdin:\n"
                    "    try: m = json.loads(line)\n"
                    "    except Exception: continue\n"
                    "    mid, meth = m.get('id'), m.get('method')\n"
                    "    if meth == 'initialize':\n"
                    "        print(json.dumps({'jsonrpc':'2.0','id':mid,"
                    "'result':{'protocolVersion':1}}), flush=True)\n"
                    "    elif meth == 'session/new':\n"
                    "        print(json.dumps({'jsonrpc':'2.0','id':mid,"
                    "'result':{'sessionId':'s1'}}), flush=True)\n"
                    "    elif meth == 'session/prompt':\n"
                    "        print(json.dumps({'jsonrpc':'2.0',"
                    "'method':'session/update','params':{'sessionId':'s1',"
                    "'update':{'sessionUpdate':'agent_message_chunk',"
                    "'content':{'type':'text','text':'pong'}}}}), flush=True)\n")
            os.chmod(fake, 0o755)
            json.dump({"id": "fake", "cmd": "fake-brain", "args": []},
                      open(os.path.join(wd2, "brain.json"), "w"))
            cb4 = free_port()
            procs.append(subprocess.Popen(
                [sys.executable, os.path.join(TOOLS, "chat-bridge.py"),
                 str(cb4), wd2],
                env=dict(os.environ,
                         PATH=fbdir + os.pathsep + os.environ["PATH"],
                         TROLY_NO_SANDBOX="1"),
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
            b4 = f"http://127.0.0.1:{cb4}"
        check("31. não giả lên", b4 is not None and
              wait_health(b4 + "/api/health"))

        # chờ session sẵn (ready) rồi lấy cursor mới nhất
        ready, nxt4 = False, 0
        if b4:
            for _ in range(50):
                s, b, _ = http("GET", b4 + f"/api/poll?since=0&token={TOKEN}")
                if any(e.get("t") == "ready" for e in b.get("events", [])):
                    ready, nxt4 = True, b.get("next", 0)
                    break
                time.sleep(0.1)
        check("31a. não giả có session", ready or b4 is None)

        # 31: long-poll đang chờ → prompt tới → event chunk đánh thức sớm
        got = {}
        def _longpoll():
            got["r"] = http("GET", b4 +
                            f"/api/poll?since={nxt4}&wait=3000&token={TOKEN}")
        th = threading.Thread(target=_longpoll, daemon=True)
        t0 = time.time(); th.start(); time.sleep(0.4)
        s, b, _ = http("POST", b4 + f"/api/prompt?token={TOKEN}", {"text": "hi"}) \
            if b4 else (-1, {}, None)
        check("31b. prompt đầu → 200", s == 200 or b4 is None, str(s))
        th.join(timeout=6); el = time.time() - t0
        r = got.get("r") or (-1, {}, {})
        check("31c. long-poll dậy sớm khi có event",
              b4 is None or (r[0] == 200 and el < 2.5
              and any(e.get("text") == "pong" for e in r[1].get("events", []))),
              f"{el:.2f}s {str(r[1])[:60]}")

        # 32: não giả không bao giờ gửi stopReason → lượt vẫn mở → busy
        s, b, _ = http("POST", b4 + f"/api/prompt?token={TOKEN}", {"text": "nữa"}) \
            if b4 else (-1, {}, None)
        check("32. prompt thứ 2 trong lượt → 409", s == 409 or b4 is None, str(s))

        # ---- lock-down ph-6: Seatbelt sandbox (macOS) ----
        # vùng "cấm" trong home — phải tạo TRƯỚC khi gen profile vì
        # deny enumeration là snapshot lúc gen (dir mới sinh sau sẽ đọc
        # được — residual đã ghi trong docs)
        dsecret = os.path.join(os.path.expanduser("~"), "sbtest-deny-zone")
        os.makedirs(dsecret, exist_ok=True)
        open(os.path.join(dsecret, "f"), "w").write("x")

        # sandbox probes cần cwd NGOÀI vùng tmp — mkdtemp mặc định nằm
        # trong TMPDIR (vùng writable theo profile) nên write-probe ở đó
        # pass giả. Tạo workdir riêng trong ROOT (vùng deny-theo-default)
        sbwd = tempfile.mkdtemp(prefix="sbtest-", dir=ROOT)
        for sd in ("tools", "my-course", ".devin", ".devin/skills",
                   ".logs"):
            os.makedirs(os.path.join(sbwd, sd), exist_ok=True)
        open(os.path.join(sbwd, "brain.json"), "w").write("{}")
        open(os.path.join(sbwd, "AGENTS.md"), "w").write("# x")
        open(os.path.join(sbwd, ".devin", "bridge.token"),
             "w").write(TOKEN)
        open(os.path.join(sbwd, ".devin", "secrets.local.json"),
             "w").write("{}")
        open(os.path.join(sbwd, "my-course", "permissions.json"),
             "w").write("{}")
        json.dump({"learner_name": "", "recipes": [], "lessons": []},
                  open(os.path.join(sbwd, "my-course",
                                    "manifest.json"), "w"))

        # 33: profile sinh được + đúng cấu trúc (deny default, bind deny,
        #     carve-out secrets/token, deny enumeration cho home)
        sb_out = subprocess.run(
            [sys.executable, os.path.join(TOOLS, "gen-sandbox.py"), sbwd],
            capture_output=True, text=True)
        sb_fp = os.path.join(sbwd, ".devin", "agent.sb")
        prof = ""
        try:
            prof = open(sb_fp, encoding="utf-8").read()
        except OSError:
            pass
        check("33. gen-sandbox → profile hợp lệ",
              sb_out.returncode == 0
              and "(deny default)" in prof
              and "(deny network-bind network-inbound)" in prof
              and '(literal "' + os.path.join(sbwd, ".devin",
                        "secrets.local.json") + '")' in prof
              and '(deny file-write* (literal "' +
                  os.path.join(sbwd, ".devin", "bridge.token") + '")' in prof
              and '(deny file-write* (literal "' +
                  os.path.join(sbwd, "my-course",
                               "permissions.json") + '")' in prof,
              prof[:120])

        has_sbx = (sys.platform == "darwin"
                   and shutil.which("sandbox-exec"))
        if has_sbx and prof:
            # 34: não trong sandbox đọc được file project
            r = subprocess.run(["sandbox-exec", "-f", sb_fp, "/bin/cat",
                                os.path.join(sbwd, "my-course",
                                             "manifest.json")],
                               capture_output=True, text=True)
            check("34. sandbox: đọc project → được",
                  r.returncode == 0 and "learner_name" in r.stdout,
                  r.stderr[:60])
            # 35: ghi bridge.token bị deny; đọc thì vẫn được
            r = subprocess.run(["sandbox-exec", "-f", sb_fp, "/bin/sh",
                                "-c", "echo x >> '" +
                                os.path.join(sbwd, ".devin",
                                             "bridge.token") + "'"],
                               capture_output=True, text=True)
            r2 = subprocess.run(["sandbox-exec", "-f", sb_fp, "/bin/cat",
                                 os.path.join(sbwd, ".devin",
                                              "bridge.token")],
                                capture_output=True, text=True)
            check("35. sandbox: ghi token deny, đọc vẫn được",
                  r.returncode != 0 and TOKEN in r2.stdout,
                  f"{r.returncode} {r.stderr[:40]}")
            # 36: vùng home ngoài quyền → deny enumeration chặn
            r = subprocess.run(["sandbox-exec", "-f", sb_fp,
                                "/bin/cat",
                                os.path.join(dsecret, "f")],
                               capture_output=True, text=True)
            check("36. sandbox: home ngoài quyền → deny",
                  r.returncode != 0
                  and "not permitted" in (r.stderr or "").lower(),
                  r.stderr[:60])
            # 36b-h: write-allowlist — não chỉ ghi được my-course/,
            # .devin/skills/, .logs/ (audit S1/S2: trước rw=cả cwd → não
            # tự sửa được permissions.json/brain.json/tools = tự cởi còng)
            probes = [
                ("36b. ghi tools/ → deny",
                 os.path.join(sbwd, "tools", "probe-w.txt"), False),
                ("36c. ghi my-course/permissions.json → deny",
                 os.path.join(sbwd, "my-course", "permissions.json"),
                 False),
                ("36d. ghi brain.json → deny",
                 os.path.join(sbwd, "brain.json"), False),
                ("36e. ghi .devin/skills/ → ok",
                 os.path.join(sbwd, ".devin", "skills", "probe-x", "f"),
                 True),
                ("36g. ghi my-course/ → ok (positive control)",
                 os.path.join(sbwd, "my-course", "probe-ok.txt"), True),
                ("36h. ghi .logs/ → ok",
                 os.path.join(sbwd, ".logs", "h.jsonl"), True),
            ]
            for name, fp, should_ok in probes:
                r = subprocess.run(
                    ["sandbox-exec", "-f", sb_fp, "/bin/sh", "-c",
                     "mkdir -p \"$(dirname '" + fp + "')\" && "
                     "echo x >> '" + fp + "'"],
                    capture_output=True, text=True)
                ok = (r.returncode == 0) == should_ok
                check(name, ok, f"{r.returncode} {r.stderr[:40]}")
                if should_ok:
                    if "probe-x" in fp:
                        shutil.rmtree(os.path.dirname(fp),
                                      ignore_errors=True)
                    else:
                        try:
                            os.remove(fp)
                        except OSError:
                            pass
            # 36f: osascript bị chặn (AppleEvents vượt mặt file-sandbox)
            r = subprocess.run(["sandbox-exec", "-f", sb_fp,
                                "/usr/bin/osascript", "-e", "return 1"],
                               capture_output=True, text=True)
            check("36f. sandbox: osascript → deny",
                  r.returncode != 0, r.stderr[:60])
        else:
            check("34-36f. sandbox runtime (chỉ chạy trên macOS)", True,
                  "bỏ qua — không phải darwin")
        shutil.rmtree(dsecret, ignore_errors=True)
        shutil.rmtree(sbwd, ignore_errors=True)

        # 37: /api/permissions giờ qua consent-gate: POST → 202 {pending}
        # → card trong poll → respond thiếu Origin → 403 card còn nguyên
        # → respond đủ Origin → apply + regen profile (audit S1)
        perm_dir = tempfile.mkdtemp(prefix="troly-perm-")
        s, b, _ = http("POST", b3 + f"/api/permissions?token={TOKEN}",
                       {"path": perm_dir, "access": "read"})
        rid = b.get("pending")
        s2, _, _ = http("POST", b3 + f"/api/respond?token={TOKEN}",
                        {"id": rid, "optionId": "ok"})
        s3, _, _ = http("POST", b3 + f"/api/respond?token={TOKEN}",
                        {"id": rid, "optionId": "ok"},
                        headers={"Origin": "http://localhost:8080"})
        s4, _, _ = http("POST", b3 + f"/api/respond?token={TOKEN}",
                        {"id": rid, "optionId": "ok"},
                        headers={"Origin": "http://localhost:8080"})
        prof2 = ""
        try:
            prof2 = open(os.path.join(wd, ".devin", "agent.sb"),
                         encoding="utf-8").read()
        except OSError:
            pass
        check("37. permissions → 202 → no-Origin 403 → Origin 200 → regen",
              s == 202 and bool(rid) and s2 == 403 and s3 == 200
              and s4 == 404     # one-shot — respond lại phải hết hiệu lực
              # regen profile Seatbelt chỉ có trên darwin
              and (sys.platform != "darwin"
                   or os.path.realpath(perm_dir) in prof2),
              f"{s}/{s2}/{s3}/{s4}")
        shutil.rmtree(perm_dir, ignore_errors=True)

        # 38: escape hatch + wrap spawn — kiểm static hai nền tảng
        check("38. sandbox wrap + escape hatch trong code",
              "_sandbox_wrap" in src_cb and "TROLY_NO_SANDBOX" in src_cb
              and "sandbox-exec" in src_cb
              and "agent.sb" in open(os.path.join(
                  TOOLS, "term-gate.sh"), encoding="utf-8").read())
        # 38b: load_brain chặn cmd/terminal không phải tên trần (brain.json
        # sửa tay không spawn lệnh lạ — audit S2)
        check("38b. load_brain validate cmd/terminal",
              're.fullmatch(r"[A-Za-z0-9_.-]+", str(out["cmd"]))' in src_cb)

        # 39: batch permissions — nhiều folder = MỘT card 202; folder không
        # tồn tại đi vào "skipped" chứ không làm hỏng cả batch (audit N5)
        pd1 = tempfile.mkdtemp(prefix="troly-p1-")
        pd2 = tempfile.mkdtemp(prefix="troly-p2-")
        s, b, _ = http("POST", b3 + f"/api/permissions?token={TOKEN}",
                       {"paths": [pd1, pd2, "/nonexistent-xyz-123"],
                        "access": "read"})
        rid39 = b.get("pending")
        s39, _, _ = http("POST", b3 + f"/api/respond?token={TOKEN}",
                         {"id": rid39, "optionId": "ok"},
                         headers={"Origin": "http://localhost:8080"})
        perm39 = {}
        s39b, perm39, _ = http("GET", b3 + f"/api/permissions?token={TOKEN}")
        got39 = {os.path.realpath(os.path.expanduser(f.get("path", "")))
                 for f in (perm39.get("folders") or [])}
        check("39. batch permissions → 1 card → cả hai folder vào",
              s == 202 and bool(rid39) and s39 == 200
              and "/nonexistent-xyz-123" in (b.get("skipped") or [])
              and os.path.realpath(pd1) in got39
              and os.path.realpath(pd2) in got39,
              f"{s}/{s39} {b}")
        shutil.rmtree(pd1, ignore_errors=True)
        shutil.rmtree(pd2, ignore_errors=True)

        # 40: folder nhạy cảm bị từ chối NGAY, không tạo card (card bấm đại
        # "Đồng ý" vẫn mở ~/.ssh nếu chỉ gate — audit S6)
        home = os.path.expanduser("~")
        for sp in ("/", home, os.path.join(home, ".ssh")):
            if not os.path.isdir(os.path.expanduser(sp)):
                continue
            s, b, _ = http("POST", b3 + f"/api/permissions?token={TOKEN}",
                           {"path": sp, "access": "read"})
            check(f"40. sensitive path {sp!r} → 400, no pending",
                  s == 400 and not b.get("pending"), f"{s} {b}")
            break
        # trong batch cũng phải chặn
        s, b, _ = http("POST", b3 + f"/api/permissions?token={TOKEN}",
                       {"paths": [home], "access": "read"})
        check("40b. batch chứa home → 400, no pending",
              s == 400 and not b.get("pending"), f"{s} {b}")

        # 41: GET /api/check-path — onboarding kiểm folder trước khi thêm
        s, b, _ = http("GET", b3 + "/api/check-path?token=" + TOKEN
                       + "&path=" + urllib.parse.quote(wd))
        s2, b2, _ = http("GET", b3 + "/api/check-path?token=" + TOKEN
                         + "&path=/nonexistent-xyz-123")
        check("41. check-path → isdir true/false",
              s == 200 and b.get("isdir") is True
              and s2 == 200 and b2.get("isdir") is False,
              f"{b} {b2}")

        # 42: open_url javascript:/data: bị từ chối ở /api/connections
        # (nút "Mở trang" chạy script trong origin portal — audit S5);
        # open_url https MỚI → 202 consent gate (audit v6 — test 52)
        s, _, _ = http("POST", b3 + f"/api/connections?token={TOKEN}",
                       {"app": {"id": "evil", "open_url": "javascript:alert(1)"}})
        s2, b42, _ = http("POST", b3 + f"/api/connections?token={TOKEN}",
                          {"app": {"id": "okapp", "open_url": "https://x.com"}})
        check("42. open_url javascript: → 400, https mới → 202 gate",
              s == 400 and s2 == 202 and bool(b42.get("pending")),
              f"{s}/{s2}")

        # 43: /api/setup gọi lại khi config đã có language → 202 card
        # (re-setup đè skill pack = đáng ngờ — audit S5). First-run chạy luôn.
        # Cần workdir RIÊNG — b3 chia wd với test 16 đã setup rồi.
        wd4 = make_workdir()
        cb4 = free_port()
        procs.append(spawn("chat-bridge.py", cb4, wd4))
        b4 = f"http://127.0.0.1:{cb4}"
        ok43 = wait_health(b4 + "/api/health")
        s, b, _ = http("POST", b4 + f"/api/setup?token={TOKEN}",
                       {"language": "vi", "learner_name": "t"})
        s2, b2, _ = http("POST", b4 + f"/api/setup?token={TOKEN}",
                         {"language": "vi", "learner_name": "t"})
        rid43 = b2.get("pending")
        s3, _, _ = http("POST", b4 + f"/api/respond?token={TOKEN}",
                        {"id": rid43, "optionId": "ok"},
                        headers={"Origin": "http://localhost:8080"})
        check("43. setup lần đầu → ok; lần 2 → 202 → respond → 200",
              ok43 and s == 200 and s2 == 202 and bool(rid43) and s3 == 200,
              f"{s}/{s2}/{s3}")
        shutil.rmtree(wd4, ignore_errors=True)

        # 44: serve.py trả CSP sandbox cho /my-course/ + /intro/ — trang
        # không tin chạy ở opaque origin, không đọc được localStorage/DOM
        # portal (audit N1). Không có allow-same-origin (đặt vào là hỏng).
        csp44 = ""
        for line in open(os.path.join(TOOLS, "serve.py"),
                         encoding="utf-8").read().splitlines():
            if "sandbox" in line:
                csp44 += line
        check("44. CSP sandbox my-course/intro (không same-origin)",
              "sandbox allow-scripts" in csp44
              and "allow-same-origin" not in csp44, csp44[:80])

        # 45: bridge-token chỉ gắn vào port bridge — không gắn cho :8080
        # (request tới /my-course/ kèm token → service worker ăn — audit N2)
        bt = open(os.path.join(ROOT, "web", "bridge-token.js"),
                  encoding="utf-8").read()
        check("45. bfetch chỉ gắn token cho 7682/7684",
              "BRIDGE_PORTS" in bt and "7682" in bt and "7684" in bt)

        # ---- audit v6 ----
        # 46: grant trên folder CHỨA folder nhạy cảm (~/Library chứa
        # Keychains/Cookies/profile trình duyệt) — chỉ so một chiều thì
        # deny-list con bị vô hiệu hết
        anc = os.path.expanduser("~/Library")
        if os.path.isdir(anc):
            s, b, _ = http("POST", b3 + f"/api/permissions?token={TOKEN}",
                           {"path": anc})
            check("46. permissions ~/Library (chứa Keychains) → 400",
                  s == 400, f"{s} {str(b)[:60]}")
            la = os.path.join(anc, "LaunchAgents")
            if os.path.isdir(la):   # folder persistence — có thể chưa tồn tại
                s, b, _ = http("POST",
                               b3 + f"/api/permissions?token={TOKEN}",
                               {"path": la, "access": "read-write"})
                check("46b. permissions LaunchAgents → 400", s == 400, str(s))
        else:
            src = open(os.path.join(TOOLS, "chat-bridge.py"),
                       encoding="utf-8").read()
            check("46. path_sensitive so 2 chiều (ancestor)",
                  "s.startswith(rpl + os.sep)" in src)

        # 47: read-write trên folder chứa/trong mã nguồn → 400 (ghi được
        # tools/*.py = code chạy NGOÀI sandbox ở spawn kế); bên trong
        # my-course (writable sẵn) → 202 qua card như thường
        os.makedirs(os.path.join(wd, "tools"), exist_ok=True)
        r47 = True
        for p47, want in ((os.path.dirname(wd), 400), (wd, 400),
                          (os.path.join(wd, "tools"), 400),
                          (os.path.join(wd, "my-course"), 202)):
            s, b, _ = http("POST", b3 + f"/api/permissions?token={TOKEN}",
                           {"path": p47, "access": "read-write"})
            if s != want:
                r47 = False
                print(f"    ✗ RW {p47} → {s} (muốn {want}) {str(b)[:60]}")
        check("47. RW grant trên/trong mã nguồn → 400, my-course → 202", r47)

        # 48: deny-list mở rộng (exec-qua-args) + terminal cũng qua deny
        r48 = True
        for cmd48 in ("git", "awk", "vim"):
            s, b, _ = http("POST", b3 + f"/api/brain?token={TOKEN}",
                           {"cmd": cmd48})
            if s != 400:
                r48 = False
                print(f"    ✗ brain cmd {cmd48} → {s}")
        s, b, _ = http("POST", b3 + f"/api/brain?token={TOKEN}",
                       {"cmd": "somecli", "terminal": "sh"})
        check("48. brain cmd git/awk/vim → 400; terminal=sh → 400",
              r48 and s == 400, str(s))

        # 49: brain.json sửa tay terminal:"sh" → load_brain rơi về an toàn
        bf = os.path.join(wd, "brain.json")
        orig49 = open(bf).read()
        json.dump({"cmd": "__no_such_brain__", "terminal": "sh"},
                  open(bf, "w"))
        s, b, _ = http("GET", b3 + f"/api/brain?token={TOKEN}")
        check("49. terminal sh trong file → load_brain không dùng",
              s == 200 and b.get("current", {}).get("terminal") != "sh",
              str(b.get("current", {})))
        open(bf, "w").write(orig49)

        # 50: profile Seatbelt deny-write vùng mã nguồn kể cả khi
        # permissions.json (sửa tay) grant RW trên folder cha
        spec = importlib.util.spec_from_file_location(
            "gen_sandbox", os.path.join(TOOLS, "gen-sandbox.py"))
        gs = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gs)
        json.dump({"folders": [{"path": os.path.dirname(wd),
                                "access": "read-write"}]},
                  open(os.path.join(wd, "my-course",
                                    "permissions.json"), "w"))
        prof50 = gs.build_profile(wd)
        check("50. profile deny-write tools/ + brain.json dù RW grant cha",
              f'(deny file-write* (subpath "{os.path.join(wd, "tools")}")' in prof50
              and f'(deny file-write* (literal "{os.path.join(wd, "brain.json")}")' in prof50)

        # 51: /api/secrets qua consent gate — POST → 202, file CHƯA ghi;
        # approve đúng Origin → mới ghi (audit v6: agent tự gọi url mới =
        # xoá creds thật theo cơ chế wipe-khi-đổi-url)
        sfp = os.path.join(wd, ".devin", "secrets.local.json")
        s, b, _ = http("POST", b3 + f"/api/secrets?token={TOKEN}",
                       {"app": "wordpress",
                        "fields": {"url": "https://site.test", "pw": "x"}})
        rid51 = b.get("pending")
        # file đã tồn tại từ test 15e/15f (cùng wd) → "chưa ghi" kiểm bằng
        # giá trị: url mới chưa được vào file trước khi approve
        creds_pre = {}
        try:
            creds_pre = json.load(open(sfp))
        except OSError:
            pass
        s51, _, _ = http("POST", b3 + f"/api/respond?token={TOKEN}",
                         {"id": rid51, "optionId": "ok"},
                         headers={"Origin": "http://localhost:8080"})
        creds51 = json.load(open(sfp))
        check("51. secrets → 202 (chưa ghi) → approve → ghi",
              s == 202 and bool(rid51) and s51 == 200
              and creds_pre.get("wordpress", {}).get("url")
              != "https://site.test"
              and creds51.get("wordpress", {}).get("url")
              == "https://site.test",
              f"{s}/{s51} {b}")

        # 51b: đổi url trên creds đã có → sau approve chỉ còn field mới
        s, b, _ = http("POST", b3 + f"/api/secrets?token={TOKEN}",
                       {"app": "wordpress",
                        "fields": {"url": "https://khac.test"}})
        rid51b = b.get("pending")
        s51b, _, _ = http("POST", b3 + f"/api/respond?token={TOKEN}",
                          {"id": rid51b, "optionId": "ok"},
                          headers={"Origin": "http://localhost:8080"})
        creds51b = json.load(open(sfp))
        check("51b. secrets đổi url → wipe sau approve",
              s == 202 and s51b == 200
              and creds51b.get("wordpress") == {"url": "https://khac.test"},
              f"{s}/{s51b} {creds51b.get('wordpress')}")

        # 51c: secrets thiếu fields → 400 ngay, không tạo card
        s, b, _ = http("POST", b3 + f"/api/secrets?token={TOKEN}",
                       {"app": "wordpress"})
        check("51c. secrets thiếu fields → 400", s == 400, str(s))

        # 52: /api/connections — upsert status thường → 200 thẳng; đặt/đổi
        # open_url → 202 card (audit v6: nút "Mở trang" quen-thuộc trỏ
        # site lạ = phishing — học viên phải thấy đích trước khi tin)
        connfp = os.path.join(wd, "my-course", "connections.json")
        s52a, _, _ = http("POST", b3 + f"/api/connections?token={TOKEN}",
                          {"app": {"id": "t52", "name": "T52",
                                   "status": "ok"}})
        s52b, b52, _ = http("POST", b3 + f"/api/connections?token={TOKEN}",
                            {"app": {"id": "t52", "name": "T52",
                                     "status": "ok",
                                     "open_url": "https://ok.test"}})
        rid52 = b52.get("pending")
        s52c, _, _ = http("POST", b3 + f"/api/respond?token={TOKEN}",
                          {"id": rid52, "optionId": "ok"},
                          headers={"Origin": "http://localhost:8080"})
        apps52 = {a.get("id"): a for a in
                  json.load(open(connfp)).get("apps", [])}
        # upsert lại CÙNG open_url → không card (portal cập nhật thường)
        s52d, _, _ = http("POST", b3 + f"/api/connections?token={TOKEN}",
                          {"app": {"id": "t52", "name": "T52",
                                   "status": "ok2",
                                   "open_url": "https://ok.test"}})
        apps52b = {a.get("id"): a for a in
                   json.load(open(connfp)).get("apps", [])}
        check("52. connections: status→200; open_url mới→202→apply; giữ→200",
              s52a == 200 and s52b == 202 and bool(rid52) and s52c == 200
              and apps52.get("t52", {}).get("open_url") == "https://ok.test"
              and s52d == 200
              and apps52b.get("t52", {}).get("status") == "ok2",
              f"{s52a}/{s52b}/{s52c}/{s52d}")

        # 53: /api/remove-connection → 202 card; approve → app biến mất
        s, b, _ = http("POST", b3 + f"/api/remove-connection?token={TOKEN}",
                       {"id": "t52"})
        rid53 = b.get("pending")
        s53, _, _ = http("POST", b3 + f"/api/respond?token={TOKEN}",
                         {"id": rid53, "optionId": "ok"},
                         headers={"Origin": "http://localhost:8080"})
        gone53 = all(a.get("id") != "t52"
                     for a in json.load(open(connfp)).get("apps", []))
        check("53. remove-connection → 202 → approve → gỡ",
              s == 202 and bool(rid53) and s53 == 200 and gone53,
              f"{s}/{s53}")

        # 54: watchdog lượt treo — não trả handshake rồi im với prompt.
        # Không watchdog thì prompt_lock kẹt 409 vĩnh viễn. Shebang chỉ
        # chạy trên POSIX; Windows skip (CI test job là ubuntu).
        if os.name != "nt":
            fbdir = os.path.join(wd, "fakebin")
            os.makedirs(fbdir, exist_ok=True)
            fake = os.path.join(fbdir, "fake-brain")
            with open(fake, "w") as f:
                f.write("#!/usr/bin/env python3\n"
                        "import sys, json, time\n"
                        "for line in sys.stdin:\n"
                        "    m = json.loads(line)\n"
                        "    r = {'jsonrpc': '2.0', 'id': m.get('id')}\n"
                        "    if m.get('method') == 'initialize':\n"
                        "        r['result'] = {}; print(json.dumps(r), flush=True)\n"
                        "    elif m.get('method') == 'session/new':\n"
                        "        r['result'] = {'sessionId': 's1'}; print(json.dumps(r), flush=True)\n"
                        "    elif m.get('method'):\n"
                        "        time.sleep(3600)\n")
            os.chmod(fake, 0o755)
            json.dump({"id": "fake", "cmd": "fake-brain", "args": []},
                      open(os.path.join(wd, "brain.json"), "w"))
            env = dict(os.environ,
                       PATH=fbdir + os.pathsep + os.environ["PATH"],
                       TROLY_TURN_TIMEOUT="2",
                       # test đang nhắm watchdog, không nhắm Seatbelt —
                       # tắt để kết quả không phụ thuộc macOS sandbox
                       TROLY_NO_SANDBOX="1")
            cb4 = free_port()
            p4 = subprocess.Popen([sys.executable,
                                   os.path.join(TOOLS, "chat-bridge.py"),
                                   str(cb4), wd], env=env,
                                  stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL)
            procs.append(p4)
            b4 = f"http://127.0.0.1:{cb4}"
            check("54. bridge fake-brain lên", wait_health(b4 + "/api/health"))
            ready = False
            for _ in range(50):
                s, b, _ = http("GET", b4 + f"/api/poll?since=0", token=TOKEN)
                if any(e.get("t") == "ready"
                       for e in (b or {}).get("events", [])):
                    ready = True
                    break
                time.sleep(0.2)
            check("54a. session sẵn sàng", ready)
            s, b, _ = http("POST", b4 + "/api/prompt", {"text": "hi"}, token=TOKEN)
            check("54b. prompt đầu ok", s == 200 and b.get("ok"), str(s))
            s, _, _ = http("POST", b4 + "/api/prompt", {"text": "nữa"}, token=TOKEN)
            check("54c. prompt thứ 2 → 409 khi busy", s == 409, str(s))
            time.sleep(3.5)      # TROLY_TURN_TIMEOUT=2 → watchdog đã chạy
            s, _, _ = http("POST", b4 + "/api/prompt", {"text": "nữa"}, token=TOKEN)
            check("54d. sau timeout → 503 self-heal (không kẹt 409)",
                  s == 503, str(s))
            s, b, _ = http("GET", b4 + f"/api/poll?since=0", token=TOKEN)
            msgs = [e.get("msg", "") for e in (b or {}).get("events", [])
                    if e.get("t") == "err"]
            check("54e. err báo 'kẹt' cho học viên",
                  any("kẹt" in m for m in msgs), str(msgs))

        # 55: delete-lesson → bài vào my-course/.trash/ chứ không mất hẳn
        # (bấm nhầm Đồng ý vẫn khôi phục được), manifest bỏ entry.
        # Dùng b3: base/b2 bị test restart giết sớm; b3 sống tới cuối, cùng wd.
        les = os.path.join(wd, "my-course", "lesson-99-rac")
        os.makedirs(les, exist_ok=True)
        open(os.path.join(les, "lesson.md"), "w").write("# bài test")
        mfp = os.path.join(wd, "my-course", "manifest.json")
        m55 = json.load(open(mfp))
        m55.setdefault("lessons", []).append({"folder": "lesson-99-rac",
                                              "title": "t"})
        json.dump(m55, open(mfp, "w"))
        s, b, _ = http("POST", b3 + f"/api/delete-lesson?token={TOKEN}",
                       {"folder": "lesson-99-rac"},
                       headers={"Origin": "http://localhost:8080"})
        rid55 = b.get("pending")
        s55, b55, _ = http("POST", b3 + f"/api/respond?token={TOKEN}",
                           {"id": rid55, "optionId": "ok"},
                           headers={"Origin": "http://localhost:8080"})
        trash_dir = os.path.join(wd, "my-course", ".trash")
        trashed = [d for d in os.listdir(trash_dir)
                   if d.startswith("lesson-99-rac-")] \
            if os.path.isdir(trash_dir) else []
        m55b = json.load(open(mfp))
        check("55. delete-lesson → .trash, khôi phục được",
              s == 202 and s55 == 200
              and not os.path.exists(les)
              and len(trashed) == 1
              and os.path.exists(os.path.join(trash_dir, trashed[0],
                                              "lesson.md"))
              and all(b.get("folder") != "lesson-99-rac"
                      for b in m55b.get("lessons", [])),
              f"{s}/{s55}/{trashed}/{str(b)[:60]}/{str(b55)[:60]}")
    finally:
        for p in procs:
            try:
                p.terminate()
            except Exception:
                pass
        shutil.rmtree(wd, ignore_errors=True)
        if wd2:
            shutil.rmtree(wd2, ignore_errors=True)

    print(f"\n{'PASS' if not fails else 'FAIL'} — "
          f"{len(passed)} xanh, {len(fails)} đỏ")
    if fails:
        print("  đỏ:", ", ".join(fails))
    sys.exit(1 if fails else 0)

if __name__ == "__main__":
    main()
