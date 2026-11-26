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
  - bots → merge theo `id` vào workspace/bots.json — update hoặc
    append; KHÔNG xoá bot user tự tạo.
  - connections → merge theo `id`, giữ `status`/probe hiện có.
  - workflows → `workspace/workflows/`.
  - rules.local.md → `.devin/rules.local.md` (AGENTS.md đọc nếu có).
  - permissions_template + exec_allowlist → CHỈ áp máy chưa onboard
    (learner_name rỗng) — không đè consent máy đang chạy.

  python3 tools/apply-pack.py [DATA_DIR] [--file pack.json]
"""
import hashlib, json, os, re, shutil, subprocess, sys, time
import urllib.parse, urllib.request, zipfile   # noqa: F401 — zip unused
import urllib.error                             # noqa: F401

ROOT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1
                       and not sys.argv[1].startswith("-") else
                       os.environ.get("TROLY_DATA") or os.getcwd())
DEVIN = os.path.join(ROOT, ".devin")
MYC = os.path.join(ROOT, "workspace")
TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)
from path_guard import path_sensitive, rw_grant_ok   # noqa: E402
from cmd_deny import pattern_cmd_denied, first_token, brain_cmd_denied   # noqa: E402
FLEET_FP = os.path.join(DEVIN, "fleet.json")
MKEY_FP = os.path.join(DEVIN, "machine.key")
INBOX_FP = os.path.join(DEVIN, "fleet-inbox.json")
PACKV_FP = os.path.join(DEVIN, "pack-version")
BANKV_FP = os.path.join(DEVIN, "bank-version")
BOWN_FP = os.path.join(DEVIN, "bank-skills.json")   # ids do bank sở hữu
CONFIG_FP = os.path.join(MYC, "config.json")
PERM_FP = os.path.join(MYC, "permissions.json")
CONN_FP = os.path.join(MYC, "connections.json")
BOTS_FP = os.path.join(MYC, "bots.json")

# exec_allowlist lint — pack mang allowlist exec là quyền lớn; pattern
# có mấy dấu này biến allowlist thành kênh chạy code tuỳ ý. Substring
# chỉ cho metachar/tool exfil — tên interpreter so qua cmd_deny.first_token
# (tên ngắn r/at/go/env trong deny-set làm substring khớp mọi pattern).
ALLOWLIST_DENY = ("|", ">", "<", ";", "&&", "`", "$(", "sudo", "rm ",
                  "curl", "wget", "certutil", "powershell", "bash",
                  "python", "node ", "sh ", "eval")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Redirect → trả None → urlopen raise HTTPError. Pack chỉ nhận từ
    đúng collector trong fleet.json; bị redirect là dấu hiệu DNS/proxy
    bị chơi — parity chủ đích NoRedirect của update.py (F8)."""
    def redirect_request(self, *a, **k):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def _bad_relpath(fn):
    """Tên file tương đối trong pack — chặn absolute POSIX, `..`,
    backslash, VÀ drive-absolute/drive-relative Windows (`C:/x`,
    `C:x`) vì os.path.join trên Windows resolve chúng ra khỏi dir đích.
    `.`/rỗng cũng chặn — open(dir/.) crash."""
    return (not fn or fn in (".", "..") or fn.startswith("/")
            or ".." in fn.split("/") or "\\" in fn
            or re.match(r"^[A-Za-z]:", fn))


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
    # Cloudflare chặn UA "Python-urllib" (1010) — cần UA riêng
    req.add_header("User-Agent", "TroLyAI-Pack/1")
    req.add_header("X-Beacon-Key", key)
    with _OPENER.open(req, timeout=15) as r:
        data = r.read()
    if hint.get("sha256") and \
            hashlib.sha256(data).hexdigest() != hint["sha256"]:
        raise ValueError("sha256 pack không khớp")
    return json.loads(data)


def lint(pack):
    if not isinstance(pack.get("pack_version"), int):
        raise ValueError("pack_version phải là số nguyên")
    for pat in pack.get("exec_allowlist") or []:
        pl = str(pat).strip()
        # first-token thuộc deny-set (pwsh/cmd/zsh/find/git/tar/docker…) —
        # enforcement chỉ lọc metachar nên "pwsh *" qua là tắt gate (F9).
        # pattern_cmd_denied so cả glob-evasion: "git*"/"g[i]t *" cũng
        # khớp được "git -c …" khi exec nên phải coi là git (audit-lại-3).
        # Check trước ALLOWLIST_DENY để lỗi nói đúng tên — "pwsh *" cũng
        # khớp substring "sh " ở dưới nhưng nguyên nhân thật là pwsh.
        if pl and pattern_cmd_denied(first_token(pl)):
            raise ValueError(
                f"exec_allowlist pattern là interpreter/exec: {pat}")
        low = str(pat).lower()
        if any(d in low for d in ALLOWLIST_DENY):
            raise ValueError(f"exec_allowlist pattern nguy hiểm: {pat}")
        # pattern phải bắt đầu bằng tên lệnh — `*`/`?` trần khớp mọi
        # lệnh = tắt consent gate chứ không allowlist
        if pl and not pl[0].isalnum() and pl[0] not in "._-":
            raise ValueError(
                f"exec_allowlist pattern không bắt đầu tên lệnh: {pat}")
    for sid, files in (pack.get("skills") or {}).items():
        if "/" in sid or "\\" in sid or sid in (".", ".."):
            raise ValueError(f"skill id lạ: {sid}")
        for fn in files:
            if _bad_relpath(fn):
                raise ValueError(f"skill {sid}: path lạ {fn}")
    for wf in (pack.get("workflows") or {}):
        if _bad_relpath(wf):
            raise ValueError(f"workflow path lạ: {wf}")
    # connections merge ghi thẳng vào file, KHÔNG qua _h_connections —
    # lưới open_url phải lặp lại ở đây: javascript:/data: trong nút
    # "Mở trang" của portal chạy script ngay trong origin portal (F2)
    for c in (pack.get("connections") or []):
        if not isinstance(c, dict):
            raise ValueError("connections entry không phải object")
        ou = str(c.get("open_url") or "")
        if ou and not re.match(r"^https?://", ou, re.I):
            raise ValueError(
                f"connections[{c.get('id')}]: open_url chỉ nhận http(s)")
    # permissions_template → permissions.json trần ở máy mới. Lint
    # sensitive ở đây vì Windows grant ACL không re-check như
    # gen-sandbox._grant_ok (F10). `%` env-var (%USERPROFILE%) expand
    # khác nền → chặn luôn (pack legit dùng ~ hoặc absolute).
    for f in (pack.get("permissions_template") or []):
        if not isinstance(f, dict):
            raise ValueError("permissions_template entry không phải object")
        p = str(f.get("path") or "")
        if not p or "%" in p:
            raise ValueError(f"permissions_template path lạ: {p!r}")
        if path_sensitive(p):
            raise ValueError(f"permissions_template nhạy cảm: {p}")
        if str(f.get("access")) == "read-write" \
                and not rw_grant_ok(p, ROOT):
            raise ValueError(f"permissions_template rw vào code: {p}")
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
        if "/" in fn or "\\" in fn or ".." in fn or fn.startswith(".") \
                or re.match(r"^[A-Za-z]:", fn):
            raise ValueError(f"mycourse_files path lạ: {fn}")
        if not fn.endswith((".md", ".json", ".jsonl", ".txt")):
            raise ValueError(f"mycourse_files loại không cho: {fn}")
    # brain — pack chọn sẵn não cho máy mới (ghi brain.json). Validate y
    # hệt POST /api/brain phía bridge: cmd/terminal là tên lệnh trần,
    # không interpreter/exec-helper, args giới hạn.
    br = pack.get("brain")
    if br is not None:
        if not isinstance(br, dict):
            raise ValueError("brain không phải object")
        # cmd bắt buộc; terminal trống thì bridge/apply rơi về cmd (y
        # hệt brain load) nên chỉ validate khi CÓ
        for k in ("cmd", "terminal"):
            v = str(br.get(k) or "")
            if not v:
                if k == "cmd":
                    raise ValueError("brain.cmd trống")
                continue
            if not re.fullmatch(r"[A-Za-z0-9_.-]+", v) \
                    or brain_cmd_denied(v.lower()):
                raise ValueError(f"brain.{k} không hợp lệ: {v!r}")
        args = br.get("args") or []
        if not isinstance(args, list) or len(args) > 20 \
                or not all(isinstance(a, str) and len(a) <= 200
                           for a in args):
            raise ValueError("brain.args không hợp lệ")


def apply_bank(bank):
    """Áp kho công thức của org (gom từ máy nhân viên — bàn giao khi
    nghỉ việc). Luật sở hữu:
      - skill chưa có trên máy → tạo + đánh dấu bank-owned
      - skill bank-owned → ghi đè (kho là nguồn sự thật cho nó)
      - dir tồn tại mà KHÔNG bank-owned → của pack hoặc của user —
        bank không đè, bỏ qua (pack vẫn là sự thật cấp org)
    """
    owned = set((_jload(BOWN_FP) or {}).get("ids") or [])
    sroot = os.path.join(DEVIN, "skills")
    for sid, files in (bank.get("skills") or {}).items():
        if "/" in sid or "\\" in sid or sid in (".", "..") \
                or not isinstance(files, dict):
            continue
        d = os.path.join(sroot, sid)
        if os.path.isdir(d) and sid not in owned:
            continue                          # pack/user sở hữu
        shutil.rmtree(d, ignore_errors=True)
        for fn, content in files.items():
            if _bad_relpath(fn) or not isinstance(content, str):
                continue
            fp = os.path.join(d, fn)
            os.makedirs(os.path.dirname(fp), exist_ok=True)
            with open(fp, "w", encoding="utf-8") as f:
                f.write(content)
        owned.add(sid)
    _jwrite(BOWN_FP, {"ids": sorted(owned)})
    with open(BANKV_FP, "w") as f:
        f.write(str(bank["bank_version"]))


def apply(pack):
    new_machine = not ((_jload(CONFIG_FP) or {}).get("learner_name"))
    # skills — ghi đè dir của từng skill trong pack (pack là sự thật);
    # id nào đang bank-owned thì pack chiếm sở hữu — gỡ dấu để lần kéo
    # bank sau không đè lại bản pack
    if pack.get("skills"):
        bj = _jload(BOWN_FP) or {}
        ids = set(bj.get("ids") or [])
        drop = ids & set(pack["skills"])
        if drop:
            bj["ids"] = sorted(ids - drop)
            _jwrite(BOWN_FP, bj)
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
    # workflows → workspace/workflows/
    for name, wf in (pack.get("workflows") or {}).items():
        wdir = os.path.join(MYC, "workflows")
        os.makedirs(wdir, exist_ok=True)
        _jwrite(os.path.join(wdir, name), wf)
    # devin_files → .devin/ (whitelist đã lint — mcp config cho não/probe)
    for fn, content in (pack.get("devin_files") or {}).items():
        with open(os.path.join(DEVIN, fn), "w", encoding="utf-8") as f:
            f.write(content if isinstance(content, str)
                    else json.dumps(content, ensure_ascii=False, indent=2))
    # mycourse_files → workspace/ CHỈ máy mới — file cá nhân (rules của
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
    # brain — pack chọn sẵn não của cty, CHỈ máy mới (não đang dùng của
    # máy đã onboard là lựa chọn của user — pack không đè)
    if new_machine and pack.get("brain"):
        br = pack["brain"]
        _jwrite(os.path.join(ROOT, "brain.json"), {
            "id": str(br.get("id") or br["cmd"])[:40],
            "label": str(br.get("label") or br["cmd"])[:60],
            "cmd": br["cmd"], "args": list(br.get("args") or []),
            "terminal": br.get("terminal") or br["cmd"]})


def _tool_cmd(name, args):
    # frozen (troly.exe): gọi vai con `troly <tool>` — exe không chạy
    # được path .py, argv lạ rơi vào `troly run`
    return [sys.executable, name] + args \
        if getattr(sys, "frozen", False) else \
        [sys.executable, os.path.join(TOOLS, name + ".py")] + args


def _gen_sandbox():
    # skills mới → regen sandbox profile (skill dir mới cần đọc được);
    # lỗi thì thôi — profile cũ vẫn chạy
    try:
        subprocess.run(_tool_cmd("gen-sandbox", [ROOT]), timeout=30)
    except Exception:
        pass


def _apply_pack(pack):
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
    try:
        subprocess.run(_tool_cmd("backup", [ROOT, "--why", "pack"]),
                       timeout=300)
    except Exception:
        pass
    apply(pack)
    with open(PACKV_FP, "w") as f:
        f.write(str(pack["pack_version"]))
    _gen_sandbox()
    print(f"apply-pack: đã áp pack v{pack['pack_version']} "
          f"org={pack.get('org')}", flush=True)


def main():
    if "--file" in sys.argv:
        pack = json.load(open(
            sys.argv[sys.argv.index("--file") + 1], encoding="utf-8"))
        _apply_pack(pack)
        return
    inbox = _jload(INBOX_FP) or {}
    fleet = _jload(FLEET_FP) or {}
    base = (fleet.get("collector") or "").rstrip("/")
    mkey = _read(MKEY_FP)
    hint = inbox.get("pack")
    if hint and hint.get("version") \
            and int(hint["version"]) > int(_read(PACKV_FP, "0") or 0):
        try:
            _apply_pack(fetch_pack(hint, base, mkey))
        except Exception as e:
            print(f"apply-pack: tải pack lỗi — {e}", flush=True)
    # kho công thức của org — beacon resp báo bank.version mới hơn
    # .devin/bank-version local (gom xong từ máy người nghỉ → máy mới
    # vào thay kéo về nhận đủ công thức)
    bhint = inbox.get("bank")
    if bhint and bhint.get("version") \
            and int(bhint["version"]) > int(_read(BANKV_FP, "0") or 0):
        try:
            bank = fetch_pack(bhint, base, mkey)
            if not isinstance(bank.get("skills"), dict) \
                    or not isinstance(bank.get("bank_version"), int):
                raise ValueError("bank thiếu skills/bank_version")
            if bank.get("org") and fleet.get("org") \
                    and bank["org"] != fleet["org"]:
                raise ValueError(
                    f"bank org={bank['org']} khác org máy {fleet['org']}")
            apply_bank(bank)
            _gen_sandbox()
            print(f"apply-pack: đã áp kho công thức "
                  f"v{bank['bank_version']}", flush=True)
        except Exception as e:
            print(f"apply-pack: kéo kho công thức lỗi — {e}", flush=True)


if __name__ == "__main__":
    main()
