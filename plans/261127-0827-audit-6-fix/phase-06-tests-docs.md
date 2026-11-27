# Phase 06 — test parity deny-list + docs (F12, F13, residual)

## F12 — test bắt drift deny-list 4 nơi

`BRAIN_CMD_DENY` sống ở 4 file: `cmd_deny.py` (canonical),
`term-gate.sh` (glob case), `term-gate.ps1` + `read-brain.ps1`
(array + regex). Đã so tay: hiện khớp — nhưng không test nào bắt
drift; một PR sửa `cmd_deny.py` quên mirror = mở exec-path.

Thêm `tools/test-deny-parity.py`:

- Extract `BRAIN_CMD_DENY` từ `cmd_deny.py` (regex set literal).
- Extract `$deny`/`$Deny` array từ `term-gate.ps1` + `read-brain.ps1`
  (parse `'name',` entries giữa marker).
- Extract list từ `term-gate.sh` case-pattern (mệnh `|` trước dòng
  `echo "Lenh terminal khong hop le"`) — phần exact-names bỏ glob
  (`*sh[0-9]*`, `python*`… là nhánh glob-equivalent của
  `_BRAIN_CMD_DENY_RE`, không so với set).
- FAIL khi: name ∈ deny-set chính mà thiếu ở một trong 3 file kia
  (trừ name Windows-only `rundll32`/`mshta`… — khai allowlist
  `WIN_ONLY`/`POSIX_ONLY` trong test nếu cần; so trước bằng tay để
  biết có cần hay không — spot-check cho thấy cả 3 file đều chứa đủ
  nên có thể không cần ngoại lệ).
- Tương tự so `_BRAIN_CMD_DENY_RE` ↔ `$DenyRe`/`$denyRe` (2 file
  ps1) — extract regex string, so token từng alternative.

Chạy cùng suite test-parity.

## F13 — note `onMessageExternal` port cứng

`background.js:86` check `u.port !== '8080'`. Nếu sau này serve.py
đổi port mặc định hoặc multi-instance, auto-pair chết ngầm → user
dán tay qua options (đã có đường dự phòng). Không vá — chỉ ghi note
trong `docs/` hoặc comment extension: "đổi PORT 8080 → sửa check
này". LOW, chấp nhận.

## SECURITY.md cập nhật

Thêm/sửa mục residual:

- **F11 accepted-risk**: máy Windows source-mode không cài Python
  không tự áp update/pack — beacon báo `tool_fail` ngược (phase-04),
  admin thấy trên dashboard thay vì im lặng; vá gốc = port
  update/apply-pack sang ps1 hoặc chuẩn bị frozen troly.exe — ghi
  là known-limitation.
- **F8**: `pack_applied`/`update_applied` đã xoá khỏi whitelist
  emit-event (không caller nào — mặt tấn công chết). Nếu sau này
  cần báo rollout từ máy: đi kênh beacon/collector hoặc thêm
  internal-token lúc đó — ghi decision log thay vì residual.
- **F5**: ghi quyết định cuối (port vs feature-gate) + lý do.
- **F6**: walkthrough `open-url` đã siết — ghi rằng renderer +
  validator là 2 lớp; URL chứa `{{var}}` chỉ enforce lúc chạy.
- **F12**: deny-list parity test tồn tại → drift tương lai bị CI bắt.

## Cập nhật test-parity.py

- Xoá `/api/config` khỏi `PY_ONLY_OK` (ps1 đã có — list sai).
- `pick-folder`/`reveal`: đổi từ `PY_ONLY_OK` sang bucket riêng
  `DARWIN_ONLY` (py trả "không hỗ trợ" trên non-mac — ps1 không cần
  port, chỉ cần stub hoặc marker để list không nhiễu).
- Cập nhật comment "đóng băng" thành trạng thái thật theo quyết
  định F5 (5 endpoint: bots/bot/bot-import/bot-import-confirm/
  install-brain).

## Done khi

- Toàn bộ suite test pass + `test-deny-parity.py` mới xanh.
- SECURITY.md có đủ 4 mục residual trên.
- PY_ONLY_OK phản ánh đúng trạng thái sau quyết định F5.
