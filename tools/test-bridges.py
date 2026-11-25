#!/usr/bin/env python3
"""test-bridges.py — smoke test cho chat-bridge.py + ext-bridge.py + serve.py.

Spawn mỗi bridge THẬT trên port động với CWD tạm (não giả → dead ngay
nhưng bridge vẫn sống — đúng thiết kế). Không cần dep ngoài, không cần
não thật. Chạy: python3 tools/test-bridges.py"""
import json, os, secrets, shutil, socket, subprocess, sys, tempfile, threading, time
import urllib.error, urllib.request

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
        s, b, _ = http("POST", base + f"/api/secrets?token={TOKEN}",
                       {"app": "wordpress", "fields":
                        {"url": "https://site-that.com",
                         "user": "u1", "app_password": "p1"}})
        s2, b2x, _ = http("POST", base + f"/api/secrets?token={TOKEN}",
                          {"app": "wordpress",
                           "fields": {"url": "http://evil.example"}})
        creds = json.load(open(os.path.join(wd, ".devin",
                                            "secrets.local.json")))
        wp = creds.get("wordpress") or {}
        check("15e. secrets đổi url → xoá creds cũ",
              s == 200 and s2 == 200
              and wp.get("url") == "http://evil.example"
              and "user" not in wp and "app_password" not in wp
              and bool(b2x.get("note")), str(wp)[:80])
        s, b, _ = http("POST", base + f"/api/secrets?token={TOKEN}",
                       {"app": "wordpress",
                        "fields": {"user": "u2", "app_password": "p2"}})
        creds = json.load(open(os.path.join(wd, ".devin",
                                            "secrets.local.json")))
        wp = creds.get("wordpress") or {}
        check("15f. secrets cùng url → merge giữ",
              s == 200 and wp.get("user") == "u2", str(wp)[:80])

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
        # workdir riêng, brain là script python trả lời ACP tối thiểu
        wd2 = make_workdir()
        fake = os.path.join(wd2, "fake-brain.py")
        with open(fake, "w", encoding="utf-8") as f:
            f.write(
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
        # cmd phải là tên trần (load_brain chặn absolute path — audit S2)
        # → dùng basename của interpreter, PATH lookup lúc spawn
        json.dump({"id": "fake",
                   "cmd": os.path.basename(sys.executable), "args": [fake]},
                  open(os.path.join(wd2, "brain.json"), "w"))
        cb4 = free_port()
        procs.append(spawn("chat-bridge.py", cb4, wd2))
        b4 = f"http://127.0.0.1:{cb4}"
        check("31. não giả lên", wait_health(b4 + "/api/health"))

        # chờ session sẵn (ready) rồi lấy cursor mới nhất
        ready, nxt4 = False, 0
        for _ in range(50):
            s, b, _ = http("GET", b4 + f"/api/poll?since=0&token={TOKEN}")
            if any(e.get("t") == "ready" for e in b.get("events", [])):
                ready, nxt4 = True, b.get("next", 0)
                break
            time.sleep(0.1)
        check("31a. não giả có session", ready)

        # 31: long-poll đang chờ → prompt tới → event chunk đánh thức sớm
        got = {}
        def _longpoll():
            got["r"] = http("GET", b4 +
                            f"/api/poll?since={nxt4}&wait=3000&token={TOKEN}")
        th = threading.Thread(target=_longpoll, daemon=True)
        t0 = time.time(); th.start(); time.sleep(0.4)
        s, b, _ = http("POST", b4 + f"/api/prompt?token={TOKEN}", {"text": "hi"})
        check("31b. prompt đầu → 200", s == 200, str(s))
        th.join(timeout=6); el = time.time() - t0
        r = got.get("r") or (-1, {}, {})
        check("31c. long-poll dậy sớm khi có event",
              r[0] == 200 and el < 2.5
              and any(e.get("text") == "pong" for e in r[1].get("events", [])),
              f"{el:.2f}s {str(r[1])[:60]}")

        # 32: não giả không bao giờ gửi stopReason → lượt vẫn mở → busy
        s, b, _ = http("POST", b4 + f"/api/prompt?token={TOKEN}", {"text": "nữa"})
        check("32. prompt thứ 2 trong lượt → 409", s == 409, str(s))

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
              and os.path.realpath(perm_dir) in prof2,
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
