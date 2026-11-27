#!/usr/bin/env python3
"""test-walkthrough.py — kiểm mọi walkthrough.json trong workspace/.

Runner portal là renderer câm nên file hỏng = màn hướng dẫn hỏng ngay
giữa chừng học viên. Generator (/tao-cong-cu) chạy file này SAU KHI
viết walkthrough.json và trước khi báo xong; CI cũng chạy qua suite.

Cách chạy:  python3 tests/test-walkthrough.py [đường-dẫn-workspace]
Mặc định:   ./workspace

Kiểm:
- JSON parse được, có title + steps là mảng không rỗng
- kind hợp lệ (15 kind) + field bắt buộc theo từng kind
- {{var}} trong prefill/send/text/url/path phải do một step TRƯỚC đó
  với `var` cung cấp — var không định nghĩa render ra chữ "{{var}}"
- cond chỉ một trong conn/var/path (var cần equals)
- media.src / file của download tồn tại trong folder bài
- 'done' nếu có phải là bước cuối; bước đầu nên là 'say' (intro)
- body/title/expect không chứa từ cấm của AGENTS.md
"""

import json
import os
import re
import sys
import tempfile

KINDS = {
    "say", "prompt", "input", "choice", "pick-file", "open-url",
    "wait-perm", "wait-run", "auto", "spotlight",
    "open", "watch", "download", "check", "copy", "done",
}
BANNED = re.compile(r"đơn giản|chỉ cần|hiển nhiên|dễ mà|dễ dàng", re.I)
VAR_REF = re.compile(r"\{\{(\w+)\}\}")

# kind -> (field bắt buộc, field string cần quét {{var}})
REQ = {
    "prompt":   ([], ["prefill", "placeholder"]),
    "input":    (["var"], []),
    "pick-file": (["var"], []),
    "choice":   (["var", "options"], []),
    "open-url": (["url"], ["url"]),
    "auto":     (["send"], ["send"]),
    "spotlight": (["target"], []),
    "open":     (["path"], ["path"]),
    "watch":    ([], []),
    "download": ([], []),
    "check":    (["expect"], ["expect"]),
    "copy":     (["text"], ["text"]),
    "say":      ([], []),
    "wait-perm": ([], []),
    "wait-run": ([], []),
    "done":     ([], []),
}


def fail(errs, where, msg):
    errs.append("  ✗ %s: %s" % (where, msg))


def check_file(path, errs):
    name = os.path.relpath(path)
    try:
        wt = json.load(open(path, encoding="utf-8"))
    except Exception as e:
        return fail(errs, name, "JSON hỏng: %s" % e)
    if not isinstance(wt.get("title"), str) or not wt["title"].strip():
        fail(errs, name, "thiếu title")
    steps = wt.get("steps")
    if not isinstance(steps, list) or not steps:
        return fail(errs, name, "steps phải là mảng không rỗng")

    folder = os.path.dirname(path)
    have_vars = set()
    saw_done = False
    for i, s in enumerate(steps):
        w = "%s bước %d" % (name, i + 1)
        if saw_done:
            fail(errs, w, "có bước sau 'done' — 'done' phải đứng cuối")
        if not isinstance(s, dict):
            fail(errs, w, "step không phải object")
            continue
        k = s.get("kind")
        if k not in KINDS:
            fail(errs, w, "kind lạ: %r" % k)
            continue
        if k == "done":
            saw_done = True
        for f in REQ[k][0]:
            if not s.get(f):
                fail(errs, w, "kind %s thiếu field %s" % (k, f))
        # prompt cần ít nhất prefill HOẶC placeholder — prompt trống
        # trơn không dẫn được học viên
        if k == "prompt" and not (s.get("prefill") or s.get("placeholder")):
            fail(errs, w, "prompt cần prefill hoặc placeholder")
        if k == "choice" and not (
                isinstance(s.get("options"), list) and s["options"]):
            fail(errs, w, "choice cần options là mảng không rỗng")
        if k == "spotlight" and not (
                isinstance(s.get("target"), str) and s["target"].strip()):
            fail(errs, w, "spotlight cần target (CSS selector)")
        # audit-6 F6: open-url chỉ nhận http(s) — javascript: kế thừa
        # origin portal. URL chứa {{biến}} chưa resolve → renderer
        # app.js check lại lúc chạy (defense 2 lớp).
        if k == "open-url":
            u = str(s.get("url") or "")
            if u and "{{" not in u and not re.match(r"^https?://", u, re.I):
                fail(errs, w, "open-url url chỉ nhận http(s): %s" % u[:60])

        # cond — đúng một probe, var cần equals
        c = s.get("cond")
        if c is not None:
            if not isinstance(c, dict) or not c:
                fail(errs, w, "cond phải là object {conn|var|path}")
            else:
                keys = [x for x in ("conn", "var", "path") if x in c]
                if len(keys) != 1:
                    fail(errs, w, "cond chỉ một trong conn/var/path")
                if "var" in c and "equals" not in c:
                    fail(errs, w, "cond.var cần kèm equals")

        # {{var}} trong field string phải được step trước định nghĩa
        for f in REQ[k][1] + ["body"]:
            for v in VAR_REF.findall(str(s.get(f) or "")):
                if v not in have_vars:
                    fail(errs, w, "{{%s}} trong %s chưa có step nào cung cấp"
                         % (v, f))
        if s.get("var"):
            have_vars.add(s["var"])

        # media/download file tồn tại trong folder bài
        m = s.get("media")
        if k == "download" and not (m and m.get("src")):
            fail(errs, w, "download cần media.src")
        if m is not None:
            if not isinstance(m, dict) or not m.get("src"):
                fail(errs, w, "media cần {type, src}")
            elif not os.path.exists(os.path.join(folder, str(m["src"]))):
                fail(errs, w, "media.src không thấy file: %s" % m["src"])

        # từ cấm trong chữ học viên đọc
        for f in ("title", "body", "expect", "placeholder"):
            if BANNED.search(str(s.get(f) or "")):
                fail(errs, w, "từ cấm trong %s: %r" % (f, s.get(f)))

    if steps[0].get("kind") != "say":
        fail(errs, name, "bước 1 nên là 'say' (intro)")


def _wt_errs(steps):
    """Ghi steps ra file tạm rồi chạy check_file — self-test validator."""
    fd, fp = tempfile.mkstemp(suffix=".json", prefix="wt-selftest-")
    with os.fdopen(fd, "w") as f:
        json.dump({"title": "selftest", "steps": steps}, f)
    errs = []
    try:
        check_file(fp, errs)
    finally:
        os.unlink(fp)
    return errs


def main():
    # audit-6 F6: validator phải bắt open-url scheme lạ, thả http(s) và
    # URL chứa {{biến}} (biến chỉ check được lúc chạy — renderer soát lại)
    _intro = [{"kind": "say", "body": "x"}]
    if not _wt_errs(_intro + [{"kind": "open-url",
                              "url": "javascript:alert(1)"}]):
        print("FAIL selftest — javascript: lọt validator open-url")
        return 1
    for u in ("https://example.com", "http://x.vn/a?b=1"):
        if _wt_errs(_intro + [{"kind": "open-url", "url": u}]):
            print("FAIL selftest — url hợp lệ bị chặn:", u)
            return 1
    _var_steps = _intro + [{"kind": "input", "var": "u",
                            "body": "nhập link"},
                           {"kind": "open-url", "url": "{{u}}"}]
    if _wt_errs(_var_steps):
        print("FAIL selftest — {{biến}} trong url bị chặn oan")
        return 1

    root = (sys.argv[1] if len(sys.argv) > 1 else "./workspace")
    errs, files = [], []
    if os.path.isdir(root):
        for dp, _, fns in os.walk(root):
            # bỏ templates/ — file schema có {{biến}} minh hoạ, không phải
            # walkthrough thật nên không validate như tool của học viên
            if os.sep + "templates" in dp:
                continue
            for fn in fns:
                if fn == "walkthrough.json":
                    files.append(os.path.join(dp, fn))
    if not files:
        print("walkthrough: không có file nào trong %s — bỏ qua" % root)
        return 0
    for f in sorted(files):
        check_file(f, errs)
    if errs:
        print("walkthrough: %d file, %d lỗi" % (len(files), len(errs)))
        print("\n".join(errs))
        return 1
    print("walkthrough: %d file đều đạt ✓" % len(files))
    return 0


if __name__ == "__main__":
    sys.exit(main())
