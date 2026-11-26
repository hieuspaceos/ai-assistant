#!/usr/bin/env python3
"""test-gates.py — mọi endpoint POST /api/* phải được KHAI TƯỜNG MINH một
trong hai: GATED (handler gọi gate_local/New-Gate → thẻ xác nhận của học
viên), hoặc OPEN_OK (chủ đích không gate — lý do ghi kèm trong dict).

Vì sao: bridge API không phân biệt được "học viên bấm portal" và "agent
tự gọi HTTP" — một write đặc quyền thiếu gate là agent tự sửa trạng thái
âm thầm. Audit đợt 4 bắt được /api/bot activate-delete + /api/bot-import-
confirm mở trần đúng lỗ hổng này. Thêm endpoint POST mới mà quên khai →
test FAIL — ép quyết định bảo mật lúc viết code, không phải lúc audit vớ.

Giới hạn: chỉ soi POST (GET hiện toàn read-only — thêm GET-ghi-state thì
phải tự khai). Không chứng minh được gate ĐÚNG — chỉ chứng minh có lời
gọi gate trong block handler; logic điều kiện vẫn phải tự đọc.

Chạy: python3 tools/test-gates.py"""
import os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# GATED: block handler PHẢI chứa lời gọi gate (được phép đặt trong điều
# kiện — vd /api/connections chỉ gate khi open_url mới/đổi; điều kiện ghi
# trong chú thích để người đọc sau không tưởng là gate mọi request).
GATED = {
    "/api/brain":              "mọi lần — kể cả preset (agent tự kill session/spawn churn)",
    "/api/delete-lesson":      "mọi lần — xoá vào .trash, khôi phục được",
    "/api/permissions":        "mọi lần — đồ chìa khoá",
    "/api/remove-permission":  "mọi lần — mất grant âm thầm",
    "/api/connections":        "chỉ khi open_url mới/đổi (card hiện đích)",
    "/api/remove-connection":  "mọi lần — mất nút âm thầm",
    "/api/secrets":            "mọi lần — credential là payload nhạy nhất",
    "/api/setup":              "chỉ khi config đã tồn tại (re-run cài đè)",
    "/api/bot":                "activate/delete — ghi bots.json (deny-write) + bot.md; create/rename mở (không kích hoạt gì; instructions preview ở card activate — audit-3 M2)",
    "/api/bot-import-confirm": "mọi lần — cài skill + instruction từ ngoài",
}

# OPEN_OK: đã xét kỹ — không cần gate. Khai endpoint POST mới vào đây
# thì BẮT BUỘC ghi lý do — "vì sao agent tự gọi được mà không sao".
OPEN_OK = {
    "/api/prompt":           "chức năng chính — gửi tin cho não",
    "/api/respond":          "tự vệ: pending-id + optionId + Origin + one-shot",
    "/api/save-page":        "ghi .html dưới my-course/; CSP sandbox đè lên",
    "/api/check-connection": "chỉ ghi status probe vào connections.json",
    "/api/bot-import":       "stage zip vào temp + trả preview; ghi thật ở -confirm",
    "/api/emit-event":       "append-only, whitelist event type — chỉ inflate được đếm dashboard",
}

fail = False
for name, fp, pat, gate_tok in (
    ("chat-bridge.py",
     os.path.join(ROOT, "tools", "chat-bridge.py"),
     r'^\s+(?:elif|if) path == "(/api/[^"]+)"',
     "gate_local("),
    ("chat-bridge.ps1",
     os.path.join(ROOT, "tools", "chat-bridge.ps1"),
     r'HttpMethod -eq "POST" -and \$path -eq "(/api/[^"]+)"',
     "New-Gate"),
):
    src = open(fp, encoding="utf-8-sig").read()
    # .py: chỉ vùng do_POST trở đi (do_GET nằm trước, cùng pattern path ==)
    # .ps1: pattern đã tự lọc POST nên quét cả file
    if name.endswith(".py"):
        src = src[src.index("def do_POST"):]
    ms = list(re.finditer(pat, src, re.M))
    blocks = {m.group(1): src[m.start():ms[i+1].start()
                              if i+1 < len(ms) else len(src)]
              for i, m in enumerate(ms)}
    for ep, blk in sorted(blocks.items()):
        if ep in GATED:
            if gate_tok not in blk:
                print(f"FAIL — {name}: {ep} khai GATED nhưng handler "
                      f"không gọi {gate_tok}")
                fail = True
        elif ep not in OPEN_OK:
            print(f"FAIL — {name}: endpoint POST mới {ep} chưa khai "
                  f"GATED hay OPEN_OK trong tools/test-gates.py")
            fail = True

# ngược chiều: endpoint đã xoá mà khai còn → nhắc dọn (không fail —
# /api/bot* chỉ có .py nên hợp lệ vắng mặt trong .ps1)
found = set()
src_py = open(os.path.join(ROOT, "tools", "chat-bridge.py"),
              encoding="utf-8-sig").read()
found |= set(re.findall(r'^\s+(?:elif|if) path == "(/api/[^"]+)"',
                        src_py[src_py.index("def do_POST"):], re.M))
src_ps = open(os.path.join(ROOT, "tools", "chat-bridge.ps1"),
              encoding="utf-8-sig").read()
found |= set(re.findall(
    r'HttpMethod -eq "POST" -and \$path -eq "(/api/[^"]+)"', src_ps))
for ep in sorted((set(GATED) | set(OPEN_OK)) - found):
    print(f"  warn — {ep} khai trong test-gates.py nhưng không còn "
          f"endpoint nào mang tên đó")

if fail:
    sys.exit(1)
print(f"PASS — {len(found)} endpoint POST đều đã khai "
      f"({sum(1 for e in found if e in GATED)} GATED, "
      f"{sum(1 for e in found if e in OPEN_OK)} OPEN_OK)")
