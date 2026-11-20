# Phase 3 — Siết `/api/respond`: chỉ chủ thẻ xin phép mới được bấm

## Mục tiêu

`/api/respond` hiện nhận `id` + `optionId` tuỳ ý → ai có token cũng tự
duyệt permission card thay học viên (bypass lớp bảo vệ cuối). Thêm
pending-map: bridge nhớ `id → optionIds` lúc broadcast perm, respond
chỉ chấp nhận cặp hợp lệ, one-shot.

## File động

| File | Action | Việc |
|---|---|---|
| `tools/chat-bridge.py` | modify | pending_perm map + validate trong `do_POST /api/respond` (handler thật ở ~dòng 576, không phải 520) |
| `tools/chat-bridge.ps1` | modify | parity — **giữ BOM** (`/api/respond` ở ~dòng 530) |
| `web/chat.html` | modify | handler bấm nút perm: check `res.ok`, 404 → hiện `addErr` "yêu cầu đã hết hạn" (~5 dòng) |
| `tools/test-bridges.py` | modify | case 25–27 |

## Chi tiết chat-bridge.py

```python
perm_pending = {}          # id -> {"options": set(optionId), "ts": time}
PERM_TTL = 600             # perm treo >10 phút coi như chết

# trong Acp._dispatch, nhánh session/request_permission — TRƯỚC khi broadcast:
opts = [o.get("optionId") for o in p.get("options", [])]
with store_lock:
    if len(perm_pending) > 200:      # trần chống phình
        perm_pending.clear()
    perm_pending[m["id"]] = {"options": set(opts), "ts": time.time()}

# dọn theo vòng đời: prompt mới / done / ready → perm cũ hết giá trị
# (broadcast("ready") ở session mới và "done" kết lượt → clear hết)
```

Trong `do_POST /api/respond` — **validate id cho CẢ hai đường**
(không để `__cancel__` lách kiểm tra: id rác gửi thẳng tới agent
cũng là rác trong kênh điều khiển):

```python
rid = data.get("id")
oid = data.get("optionId")
rec = perm_pending.pop(rid, None)
if rec is None or time.time() - rec["ts"] > PERM_TTL:
    self._json({"err": "yêu cầu không còn hiệu lực"}, 404); return
if oid != "__cancel__" and oid not in rec["options"]:
    self._json({"err": "lựa chọn không hợp lệ"}, 400); return
```

Dọn map: `perm_pending.clear()` khi broadcast `ready`, `done`, **hoặc
`err`** (perm treo qua lượt mới/lỗi là trạng thái rác — UI cũng không
còn thẻ). Residual ghi rõ: ai có token đọc `/api/poll` vẫn thấy id
đang pending và duyệt được — không chặn được mà không tách trust; fix
này chặn **id bịa + optionId ngoài danh sách + replay**, còn "token
holder giả làm người dùng" là giới hạn mô hình (giống mọi API khác).

`.ps1`: cùng logic — hashtable `$script:permPending`, validate trong
handler `/api/respond` tương ứng. **Giữ BOM** (R1).

## Hành vi thay đổi (cần biết trước)

- Perm card "treo" từ phiên trước (UI replay event cũ sau reset) → bấm
  giờ trả 404 thay vì im lặng gửi lệnh vô nghĩa — đúng hơn, UI nên
  hiển thị "yêu cầu đã hết hạn" (chat.html: thêm check `res.ok` trong
  handler bấm nút, hiện `addErr` nhẹ — 5 dòng).
- `__cancel__` chỉ miễn kiểm tra **optionId** (option ảo do UI tự thêm
  khi card không có nút) — `id` VẪN phải nằm trong pending map như
  thường. (Draft đầu viết "miễn kiểm tra" không rõ — đọc nhầm là miễn
  validate id thì tạo lại lỗ hổng bơm id rác.)

## Test bổ sung

| # | Case | Kỳ vọng |
|---|------|---------|
| 25 | `POST /api/respond` `{"id": 999999, "optionId": "allow"}` | 404 |
| 26 | respond `optionId` không trong options của perm đang pending | 400 |
| 27 | respond đúng một lần → lần hai cùng id | lần 2 → 404 |

(Perm giả để test: inject thẳng `perm_pending` qua... không có API —
chấp nhận test 25/27 bằng id lạ + dùng lại, 26 cần perm thật từ não →
test tay checklist, hoặc để TODO trong test file ghi rõ cách tạo perm
giả bằng cách mock `Acp`.)
