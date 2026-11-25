#!/usr/bin/env python3
"""apply-pack.py — áp config-pack của cty lên máy.

Nguyên tắc "KHÔNG fork, chỉ pack": 100% khác biệt giữa các cty là dữ
liệu — pack mang skills/bots/connections/workflows/rules/exec_allowlist
của org; code đi qua release channel (update.py).

Chạy khi beacon ghi `.devin/fleet-inbox.json` có {"pack": {...}}, hoặc
tay với --file pack.json (IT test pack trước khi phát).

Pack đi qua rào:
  1. org trong pack phải khớp fleet.json (pack của cty khác → abort).
  2. lint `exec_allowlist` — pattern nguy hiểm (pipe-to-shell, redirect,
     `rm `, `sudo`, `curl`, `* ` trần) → reject cả pack.
  3. sha256 file khớp inbox khi tải qua mạng.
  4. backup.py chụp state trước khi ghi đè — pack sai revert được.

Luật ghi:
  - skills/ → ghi đè `.devin/skills/<id>/` (pack là nguồn sự thật cty;
    skill user tự tạo có id khác thì giữ).
  - bots → merge theo `id` vào my-course/bots.json — update hoặc
    append; KHÔNG xoá bot user tự tạo.
  - connections → merge theo `id`, giữ `status`/probe hiện có.
  - workflows → `my-course/workflows/`.
  - rules.local.md → `.devin/rules.local.md` (AGENTS.md đọc nếu có).
  - permissions_template + exec_allowlist → CHỈ áp máy chưa onboard
    (learner_name rỗng) — không đè consent máy đang chạy.

  python3 tools/apply-pack.py [DATA_DIR] [--file pack.json]
"""
import hashlib, json, os, shutil, subprocess, sys, time
import urllib.parse, urllib.request, zipfile   # noqa: F401 — zip unused
import urllib.error                             # noqa: F401

ROOT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1
                       and not sys.argv[1].startswith("-") else
                       os.environ.get("TROLY_DATA") or os.getcwd())
DEVIN = os.path.join(ROOT, ".devin")
MYC = os.path.join(ROOT, "my-course")
TOOLS = os.path.dirname(os.path.abspath(__file__))
FLEET_FP = os.path.join(DEVIN, "fleet.json")
MKEY_FP = os.path.join(DEVIN, "machine.key")
INBOX_FP = os.path.join(DEVIN, "fleet-inbox.json")
PACKV_FP = os.path.join(DEVIN, "pack-version")
CONFIG_FP = os.path.join(MYC, "config.json")
PERM_FP = os.path.join(MYC, "permissions.json")
CONN_FP = os.path.join(MYC, "connections.json")
BOTS_FP = os.path.join(MYC, "bots.json")

# exec_allowlist lint — pack mang allowlist exec là quyền lớn; pattern
# có mấy dấu này biến allowlist thành kênh chạy code tuỳ ý
ALLOWLIST_DENY = ("|", ">", "<", ";", "&&", "`", "$(", "sudo", "rm ",
                  "curl", "wget", "certutil", "powershell", "bash",
                  "python", "node ", "sh ", "eval")


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


def _jwrite(fp, obj):
    os.makedirs(os.path.dirname(fp), exist_ok=True)
    with open(fp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def fetch_pack(hint, base, key):
    url = urllib.parse.urljoin(base + "/", hint["url"])
    if urllib.parse.urlparse(url).netloc != \
            urllib.parse.urlparse(base).netloc:
        raise ValueError("pack url host khác collector")
    req = urllib.request.Request(url)
    req.add_header("X-Beacon-Key", key)
    with urllib.request.urlopen(req, timeout=15) as r:
        data = r.read()
    if hint.get("sha256") and \
            hashlib.sha256(data).hexdigest() != hint["sha256"]:
        raise ValueError("sha256 pack không khớp")
    return json.loads(data)


def lint(pack):
    if not isinstance(pack.get("pack_version"), int):
        raise ValueError("pack_version phải là số nguyên")
    for pat in pack.get("exec_allowlist") or []:
        low = str(pat).lower()
        if any(d in low for d in ALLOWLIST_DENY):
            raise ValueError(f"exec_allowlist pattern nguy hiểm: {pat}")
        # pattern phải bắt đầu bằng tên lệnh — `*`/`?` trần khớp mọi
        # lệnh = tắt consent gate chứ không allowlist
        pl = str(pat).strip()
        if pl and not pl[0].isalnum() and pl[0] not in "._-":
            raise ValueError(
                f"exec_allowlist pattern không bắt đầu tên lệnh: {pat}")
    for sid, files in (pack.get("skills") or {}).items():
        if "/" in sid or "\\" in sid or sid in (".", ".."):
            raise ValueError(f"skill id lạ: {sid}")
        for fn in files:
            if fn.startswith("/") or ".." in fn.split("/") \
                    or "\\" in fn:
                raise ValueError(f"skill {sid}: path lạ {fn}")
    for wf in (pack.get("workflows") or {}):
        if wf.startswith("/") or ".." in wf or "\\" in wf:
            raise ValueError(f"workflow path lạ: {wf}")
    # devin_files — whitelist cứng: pack được đặt config vào .devin/ cho
    # não + probe (mcp), KHÔNG được đụng state máy (token, key, license,
    # allowlist exec — cái đó đi kênh exec_allowlist/new-machine riêng)
    # env-allowlist.json CỐ Ý không trong whitelist: file đó mở lại
    # env đã scrub (não kế thừa secrets) — là quyết định machine-local
    # của chủ máy, pack không được đẩy từ xa.
    DEVIN_FILES_OK = {"mcp_config.json", "mcp_config.local.json"}
    for fn in (pack.get("devin_files") or {}):
        if fn not in DEVIN_FILES_OK:
            raise ValueError(f"devin_files tên không được phép: {fn}")
    for fn in (pack.get("mycourse_files") or {}):
        if "/" in fn or "\\" in fn or ".." in fn or fn.startswith("."):
            raise ValueError(f"mycourse_files path lạ: {fn}")
        if not fn.endswith((".md", ".json", ".jsonl", ".txt")):
            raise ValueError(f"mycourse_files loại không cho: {fn}")


def apply(pack):
    new_machine = not ((_jload(CONFIG_FP) or {}).get("learner_name"))
    # skills — ghi đè dir của từng skill trong pack (pack là sự thật)
    for sid, files in (pack.get("skills") or {}).items():
        d = os.path.join(DEVIN, "skills", sid)
        shutil.rmtree(d, ignore_errors=True)
        for fn, content in files.items():
            fp = os.path.join(d, fn)
            os.makedirs(os.path.dirname(fp), exist_ok=True)
            with open(fp, "w", encoding="utf-8") as f:
                f.write(content)
    # bots — merge theo id, giữ bot user tự tạo + active hiện tại
    if pack.get("bots"):
        bj = _jload(BOTS_FP) or {"active": None, "bots": []}
        have = {b.get("id"): b for b in bj.get("bots") or []}
        for b in pack["bots"]:
            if b.get("id"):
                have[b["id"]] = b
        bj["bots"] = list(have.values())
        _jwrite(BOTS_FP, bj)
    # connections — merge theo id, giữ status/probe của bản máy
    if pack.get("connections"):
        cj = _jload(CONN_FP) or {"apps": []}
        have = {c.get("id"): c for c in cj.get("apps") or []}
        for c in pack["connections"]:
            cid = c.get("id")
            if not cid:
                continue
            old = have.get(cid) or {}
            merged = dict(c)
            for k in ("status", "check_message", "checked_at"):
                if k in old:
                    merged[k] = old[k]
            have[cid] = merged
        cj["apps"] = list(have.values())
        _jwrite(CONN_FP, cj)
    # workflows → my-course/workflows/
    for name, wf in (pack.get("workflows") or {}).items():
        wdir = os.path.join(MYC, "workflows")
        os.makedirs(wdir, exist_ok=True)
        _jwrite(os.path.join(wdir, name), wf)
    # devin_files → .devin/ (whitelist đã lint — mcp config cho não/probe)
    for fn, content in (pack.get("devin_files") or {}).items():
        with open(os.path.join(DEVIN, fn), "w", encoding="utf-8") as f:
            f.write(content if isinstance(content, str)
                    else json.dumps(content, ensure_ascii=False, indent=2))
    # mycourse_files → my-course/ CHỈ máy mới — file cá nhân (rules của
    # tôi, feedback log) là của user, pack không đè lần hai
    if new_machine:
        for fn, content in (pack.get("mycourse_files") or {}).items():
            fp = os.path.join(MYC, fn)
            if os.path.exists(fp):
                continue
            with open(fp, "w", encoding="utf-8") as f:
                f.write(content if isinstance(content, str)
                        else json.dumps(content, ensure_ascii=False,
                                        indent=2))
    # rules cty
    if pack.get("rules_local_md"):
        with open(os.path.join(DEVIN, "rules.local.md"), "w",
                  encoding="utf-8") as f:
            f.write(pack["rules_local_md"])
    # permissions_template + exec_allowlist — CHỈ máy mới (consent đã
    # duyệt của máy đang chạy là của user, pack không được đè)
    if new_machine and pack.get("permissions_template"):
        pj = _jload(PERM_FP) or {"folders": []}
        have = {f.get("path") for f in pj.get("folders") or []}
        for f in pack["permissions_template"]:
            if f.get("path") and f["path"] not in have:
                pj.setdefault("folders", []).append(
                    {"path": f["path"],
                     "access": f.get("access", "read"),
                     "note": "pack " + str(pack.get("org") or "")})
        _jwrite(PERM_FP, pj)
    if new_machine and pack.get("exec_allowlist"):
        _jwrite(os.path.join(DEVIN, "exec-allowlist.json"),
                {"patterns": pack["exec_allowlist"]})


def main():
    if "--file" in sys.argv:
        pack = json.load(open(
            sys.argv[sys.argv.index("--file") + 1], encoding="utf-8"))
    else:
        hint = (_jload(INBOX_FP) or {}).get("pack")
        if not hint or not hint.get("version"):
            return                                # không có pack mới
        cur = int(_read(PACKV_FP, "0") or 0)
        if int(hint["version"]) <= cur:
            return                                # đã áp rồi
        fleet = _jload(FLEET_FP) or {}
        base = (fleet.get("collector") or "").rstrip("/")
        try:
            pack = fetch_pack(hint, base, _read(MKEY_FP))
        except Exception as e:
            print(f"apply-pack: tải pack lỗi — {e}", flush=True)
            return
    fleet = _jload(FLEET_FP) or {}
    if pack.get("org") and fleet.get("org") \
            and pack["org"] != fleet["org"]:
        print(f"apply-pack: pack org={pack['org']} nhưng máy thuộc "
              f"{fleet['org']} — abort", flush=True)
        return
    try:
        lint(pack)
    except ValueError as e:
        print(f"apply-pack: pack không hợp lệ — {e}", flush=True)
        return
    # frozen (troly.exe): gọi vai con `troly <tool>` — exe không chạy
    # được path .py, argv lạ rơi vào `troly run`
    FROZEN = getattr(sys, "frozen", False)
    def tool_cmd(name, args):
        return [sys.executable, name] + args if FROZEN else \
            [sys.executable, os.path.join(TOOLS, name + ".py")] + args
    try:
        subprocess.run(tool_cmd("backup", [ROOT, "--why", "pack"]),
                       timeout=300)
    except Exception:
        pass
    apply(pack)
    with open(PACKV_FP, "w") as f:
        f.write(str(pack["pack_version"]))
    # skills mới → regen sandbox profile (skill dir mới cần đọc được);
    # lỗi thì thôi — profile cũ vẫn chạy
    try:
        subprocess.run(tool_cmd("gen-sandbox", [ROOT]), timeout=30)
    except Exception:
        pass
    print(f"apply-pack: đã áp pack v{pack['pack_version']} "
          f"org={pack.get('org')}", flush=True)


if __name__ == "__main__":
    main()
