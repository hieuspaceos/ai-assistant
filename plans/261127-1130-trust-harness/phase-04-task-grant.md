# Phase 04 — Quyền theo tác vụ: "cho phép trong ~15 phút"

## Lý do

Hai cực hiện có đều khó chịu:

- `allow_once` (mặc định cố tình — audit-3 M1): tác vụ 20 thao tác
  nhỏ = bấm duyệt 20 lần.
- `exec-allowlist.json`: duyệt một lần → bền mãi, rộng hơn ý định.

Cần vùng giữa: **cho phép trong phạm vi tác vụ này, tự thu hồi**.

## Ràng buộc từ audit-3 M1 — KHÔNG được phá

- Một cú bấm "Đồng ý" không được biến thành quyền vĩnh viễn —
  grant 15 phút vẫn là "nhiều lần", phải hiển thị rõ đó là lựa chọn
  khác (nút/label riêng: *"Cho phép trong tác vụ này"* chứ không gộp
  vào "Đồng ý").
- KHÔNG ghi vào `exec-allowlist.json` — file đó = quyết định bền của
  chủ máy. Grant tác vụ sống **chỉ trong memory** của bridge; restart
  bridge = mất sạch.
- Mặc định vẫn là allow_once — grant tác vụ là opt-in tường minh.

## Thiết kế

```
perm card có 2 nút:
  [Đồng ý lần này]            → trả optionId allow_once (y như cũ)
  [Cho phép trong tác vụ]     → allow_once + ghi grant vào task_grants

task_grants = {pattern_key: expires_epoch}   # memory dict, ~15 phút

Khi não xin quyền lần sau với tool_call tương đương:
  _allow_match() → trúng task_grants còn hạn → tự trả allow_once,
  KHÔNG hiện card, KHÔNG spawn dialog native.
```

- **Scope của grant**: match theo *loại thao tác + đích*, không phải
  "cho hết mọi thứ" — VD `exec:python3 *.py` hoặc `fs:write:<folder>`.
  Tái dùng pattern-extract của `_allow_match`/`exec-allowlist` nhưng
  key đi vào dict memory.
- **Hết hạn**: `time.time()` + 900; sweep khi match (lazy) + thread
  dọn — không cần timer phức tạp.
- **Hiển thị**: chip nhỏ trên portal "⚡ Đang cho phép tự động —
  còn 12 phút" + nút **Thu hồi** (xoá hết grant ngay). Học viên phải
  NHÌN THẤY mình đang cho phép gì — đây là điểm khác then chốt với
  allowlist vô hình.
- Turn mới (`/api/new-task` từ plan ux-polish) → clear `task_grants`
  — "tác vụ" kết thúc khi hội thoại kết thúc.

## Thay đổi

### `tools/chat-bridge.py`

- `task_grants` dict + `GRANT_TTL = 900`.
- `_perm_title`/extract candidates đã có — thêm `_grant_key(tc)`:
  chuẩn hoá thành key ổn định (kind + nhị phân thay vì full argv?
  full argv có arg đổi liên tục → match trượt. Quyết trong phase:
  key = tool kind + executable + folder đích).
- Hook trong đường xin quyền ACP (`session/request_permission`
  handler): check grant trước khi tạo card.
- `POST /api/grants/revoke` (token bắt buộc) + `GET /api/grants`
  (đếm + TTL) cho chip portal.
- Audit: mỗi auto-allow ghi `.logs/` `{"t":"grant_hit",...}` —
  dashboard/điều tra sau này thấy được.

### `web/chat.html` + `web/app.js`

- Nút thứ hai trên perm card + i18n.
- Chip đếm ngược + revoke button, poll `/api/grants` mỗi 30s
  (đủ — không cần đếm giây chính xác).
- Confirm lần đầu dùng tính năng: *"Trong 15 phút tới, thao tác kiểu
  này không hỏi lại — vẫn dừng ngay nếu bạn bấm Thu hồi."*

## Bẫy đã biết

- **Key match quá rộng** = grant vô hình 15 phút → dùng pattern
  hẹp nhất có thể (kind+exe+dir), KHÔNG `*` toàn cục. Tool kind
  `edit`/`write` vào folder ngoài `permissions.json` → grant KHÔNG
  áp (path_guard vẫn chặn như cũ — grant chỉ gộp card, không nới
  quyền folder).
- Dialog native (macOS osascript) không có nút thứ hai → grant chỉ
  chọn được trên **card trong chat**; dialog native giữ allow_once.
- `prompt_lock` đang held mà grant vẫn hit → đúng ý đồ (đó là tác vụ
  đang chạy).
- Không auto-allow tool `delete`/exec pattern trong `cmd_deny` — grant
  match TRƯỚC nhưng deny-list vẫn chạy trước match (thứ tự trong
  `_allow_match` giữ nguyên).

## Test

- `test-bridges.py`/`test-deny-parity.py`: duyệt grant → lần 2 cùng
  pattern không card; pattern khác vẫn hỏi; đổi TTL ngắn → hết hạn hỏi
  lại; revoke → hỏi lại; `/api/new-task` → grant mất; pattern khớp
  cmd_deny → vẫn bị chặn dù có grant.
- Không ghi gì vào `exec-allowlist.json` (assert file mtime đứng).
