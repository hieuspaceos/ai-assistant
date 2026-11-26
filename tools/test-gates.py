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
    "/api/install-brain":     "chỉ khi máy đã onboard/fleet — cài phần mềm lên máy; máy chưa onboard chưa có agent nào giả nút bấm nên chạy luôn (y hệt setup lần đầu)",
}

# OPEN_OK: đã xét kỹ — không cần gate. Khai endpoint POST mới vào đây
# thì BẮT BUỘC ghi lý do — "vì sao agent tự gọi được mà không sao".
OPEN_OK = {
    "/api/prompt":           "chức năng chính — gửi tin cho não",
    "/api/respond":          "tự vệ: pending-id + optionId + Origin + one-shot",
    "/api/save-page":        "ghi .html dưới workspace/; CSP sandbox đè lên",
    "/api/check-connection": "chỉ ghi status probe vào connections.json",
    "/api/bot-import":       "stage zip vào temp + trả preview; ghi thật ở -confirm",
    "/api/emit-event":       "append-only, whitelist event type — chỉ inflate được đếm dashboard",
    "/api/pick-folder":      "mở hộp chọn folder native (dialog macOS) — chỉ trả path user tự chọn; serialized + 1 dialog/lần, không ghi gì",
    "/api/reveal":           "`open -R` = chỉ highlight trong Finder, không thực thi file; path giới hạn dưới ~ + deny-list nhạy cảm như check-path",
    "/api/config":           "whitelist merge — chỉ key `terminal` (bool); spawn ttyd đi qua term-gate đòi mã kết nối, agent đã có mã nên không leo thang; reversible",
}

fail = False
found = set()

# --- chat-bridge.py: enumerate POST_ROUTES dict → quét source của method
# đích cho gate_local(. Chính xác hơn parse elif chain cũ: gate trong
# helper (_apply closure…) vẫn match, không bị nhiễu code endpoint kề.
src_py = open(os.path.join(ROOT, "tools", "chat-bridge.py"),
              encoding="utf-8-sig").read()
rt = re.search(r'POST_ROUTES = \{(.*?)\}', src_py, re.S)
assert rt, "không thấy POST_ROUTES dict trong chat-bridge.py"
routes = dict(re.findall(r'"(/api/[^"]+)":\s*"(_h_[a-z_]+)"', rt.group(1)))
def _method_src(name):
    i = src_py.index(f"    def {name}(")
    j = src_py.find("\n    def ", i + 1)
    k = src_py.find("\ndef ", i + 1)          # method cuối của class
    end = min(x for x in (j, k) if x > 0)
    return src_py[i:end]
for ep, mn in sorted(routes.items()):
    found.add(ep)
    blk = _method_src(mn)
    if ep in GATED:
        if "gate_local(" not in blk:
            print(f"FAIL — chat-bridge.py: {ep} khai GATED nhưng {mn} "
                  f"không gọi gate_local(")
            fail = True
    elif ep not in OPEN_OK:
        print(f"FAIL — chat-bridge.py: endpoint POST mới {ep} chưa khai "
              f"GATED hay OPEN_OK trong tools/test-gates.py")
        fail = True

# --- chat-bridge.ps1: vẫn elif-style, pattern đã tự lọc POST ---
src_ps = open(os.path.join(ROOT, "tools", "chat-bridge.ps1"),
              encoding="utf-8-sig").read()
ms = list(re.finditer(
    r'HttpMethod -eq "POST" -and \$path -eq "(/api/[^"]+)"', src_ps))
blocks = {m.group(1): src_ps[m.start():ms[i+1].start()
                            if i+1 < len(ms) else len(src_ps)]
          for i, m in enumerate(ms)}
for ep, blk in sorted(blocks.items()):
    found.add(ep)
    if ep in GATED:
        if "New-Gate" not in blk:
            print(f"FAIL — chat-bridge.ps1: {ep} khai GATED nhưng handler "
                  f"không gọi New-Gate")
            fail = True
    elif ep not in OPEN_OK:
        print(f"FAIL — chat-bridge.ps1: endpoint POST mới {ep} chưa khai "
              f"GATED hay OPEN_OK trong tools/test-gates.py")
        fail = True

# ngược chiều: endpoint đã xoá mà khai còn → nhắc dọn (không fail —
# /api/bot* chỉ có .py nên hợp lệ vắng mặt trong .ps1)
for ep in sorted((set(GATED) | set(OPEN_OK)) - found):
    print(f"  warn — {ep} khai trong test-gates.py nhưng không còn "
          f"endpoint nào mang tên đó")

if fail:
    sys.exit(1)
print(f"PASS — {len(found)} endpoint POST đều đã khai "
      f"({sum(1 for e in found if e in GATED)} GATED, "
      f"{sum(1 for e in found if e in OPEN_OK)} OPEN_OK)")
