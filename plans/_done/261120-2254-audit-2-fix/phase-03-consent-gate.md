# Phase 03 — Consent gate: write API đặc quyền phải qua thẻ xác nhận của học viên

## Vá

**S1 (phần API) + S7 (custom brain) + `/api/delete-lesson`** — root cause:
API không phân biệt được "học viên bấm trên portal" vs "agent tự gọi".
Cả hai đều có token → mọi write đặc quyền phải qua xác nhận mà agent KHÔNG
tự trả lời được (nó có thể gọi /api/respond nhưng card phải do người bấm —
đó là mục đích của gate).

Thiết kế: tái dùng cơ chế `perm` card + `/api/respond` đã có — thêm
`local_pending` cho các hành động do bridge tự phát (không phải agent
xin phép qua ACP).

## Cơ chế `local_pending` (chat-bridge.py)

```python
local_pending = {}   # id(str hex) -> {"action": fn, "args": {...}, "ts": epoch}
```

- `gate_local(title, apply_fn)` → tạo id (`secrets.token_hex(8)`), lưu vào
  `local_pending`, `broadcast({"t":"perm","id":id,"title":title,
  "options":[{"optionId":"ok","name":"Đồng ý"},{"optionId":"__cancel__",
  "name":"Không"}]})` → trả id.
- `/api/respond`: kiểm `perm_pending` (ACP) trước; không khớp thì kiểm
  `local_pending` — hợp lệ + optionId `ok` → chạy `apply_fn` → `{ok}`;
  `__cancel__` → bỏ → `{ok, cancelled}`. One-shot + TTL 600s y hệt.
- `perm` card KHÔNG persist history (đã có sẵn) → restart không tự duyệt.
- Trả API gọi: `202 {"pending": id, "msg": "đã gửi thẻ xác nhận vào chat"}`.

## Áp gate

| Endpoint | Điều kiện gate |
|---|---|
| `POST /api/permissions` | luôn — title `Thêm quyền <access> cho folder X` |
| `POST /api/remove-permission` | luôn — `Gỡ quyền folder X` |
| `POST /api/brain` custom cmd (không preset) | luôn — `Đổi não sang lệnh tự nhập "cmd args…"`; preset `id` → trực tiếp (preset = whitelist an toàn) |
| `POST /api/delete-lesson` | luôn — `Xoá bài học X` → portal bỏ confirm riêng (card chat là confirm duy nhất) |

Không gate: `/api/secrets` (S3a fix đã chặn exfil; secrets ghi rác chỉ
phá chính mình), `/api/connections` upsert (probe đã validate schema
phase-02 — còn lại metadata), `/api/setup`, `/api/prompt`, `/api/bot*`
(import đã có preview UI).

## Portal (`web/app.js`, `web/onboarding.html`)

- `folder-save`: `res.pending` → toast "đã gửi thẻ xác nhận — mở tab Hỏi
  trợ lý để duyệt" + không coi là lỗi.
- `deleteLesson`: bỏ `uiConfirm` riêng, gọi thẳng API → toast như trên.
- `renderBrain` sel.onchange: preset vẫn như cũ; onboarding custom-cmd
  flow → `pending` → hiển thị "vào tab chat bấm Đồng ý để hoàn tất".
- Onboarding folder step: các POST permissions giờ trả `pending` → UI
  note "quyền hiệu lực sau khi xác nhận trong tab chat" (không chặn
  onboarding — các card xếp hàng, học viên duyệt sau).
- `chat.html`: card perm từ local_pending dùng đúng UI sẵn có — options
  `{optionId:"ok"}` map nút Đồng ý; `__cancel__` đã xử lý sẵn.

## Port `chat-bridge.ps1`

Port `local_pending` + nhánh trong `/api/respond` + gate 4 endpoint
(denylist/regex brain từ phase-02 cũng port chung ở đây cho gọn). Cấu
trúc: hashtable `$script:LocalPending`, `Push-Event` broadcast
perm card — `Push-Event` đã bỏ persist perm sẵn.

## Test

- `POST /api/permissions` → 202 + card `perm` xuất hiện trong poll;
  `respond {id, optionId:"ok"}` → quyền được ghi + regen sandbox;
  `respond` lần 2 → 404 (one-shot).
- `__cancel__` → không ghi gì.
- Respond với id trong `local_pending` nhưng optionId rác → 400, card
  còn nguyên.
- `POST /api/brain {"id":"devin"}` → 200 trực tiếp (preset không gate);
  `{"cmd":"somecli"}` → 202.
- `/api/delete-lesson` → 202 → respond ok → folder mất.

## Done khi

Agent tự gọi `POST /api/permissions "/" read-write` chỉ tạo được card
chờ — không đổi được profile; học viên thấy card đáng ngờ → bấm Không.
