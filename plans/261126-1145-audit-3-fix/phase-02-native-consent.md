# Phase 02 — CAO-1: nút Không/Esc trên dialog native không được downgrade card (+ M4/L8 flood)

## Vá

**CAO-1 — consent bypass hoàn chỉnh trên macOS.** `_native_confirm`
(card `local_pending` — /api/secrets, /api/permissions…) khai
`cancel button "Không"` (chat-bridge.py:433). Bấm Không/Esc → osascript
error -128, stdout rỗng → `gui_failed=True` → `_native_fallback()` phát
lại card KHÔNG cờ native → `POST /api/respond {id, optionId:"ok"}` chỉ
cần token+Origin — agent tự set được → `apply()` chạy **ngay sau khi
học viên từ chối**.

`_perm_native_confirm` (card ACP, ~487–560) đã vá đúng mô-típ này — có
comment giải thích sẵn. Port nguyên pattern sang `_native_confirm`:

```python
# KHÔNG khai "cancel button": Esc/bấm Không = error -128 stdout rỗng
# → không phân biệt được "người từ chối" với "dialog hỏng". Bỏ cancel
# button thì "Không" trả về stdout bình thường (button returned:Không).
script = ("display dialog " + _asq(title) +
          ' with title "Trợ Lý AI — xin phép" with icon note '
          'buttons {"Không", "Đồng ý"} default button "Không" '
          'giving up after ' + str(int(PERM_TTL)))
...
out, _ = p.communicate(timeout=PERM_TTL + 60)
approved = "button returned:Đồng ý" in out
declined = "button returned:Không" in out or "gave up:true" in out
gui_failed = p.returncode != 0 and not approved and not declined
```

Hành vi sau đó đã đúng sẵn: `gui_failed` mới `_native_fallback`;
`declined` → pop rec + `perm_done`, **không apply, không fallback**.

Kiểm Esc sau khi bỏ cancel button: Esc không dismiss được dialog (không
có nút nào map cancel) — người dùng chỉ đóng được bằng "Không" hoặc chờ
TTL → cả hai đều ra `declined`/gave-up, không còn đường xuống fallback.

**Ngoại lệ còn lại (accept):** Popen lỗi (resource exhaustion) vẫn
`_native_fallback` — escape hatch có chủ đích cho máy headless; ghi
nhận, không vá trong phase này.

**Đã verify — không cần vá thêm:** agent trong Seatbelt KHÔNG kill được
dialog để ép fallback: profile `(deny default)` + `(allow process*)`
không cấp op `signal` (signal là op riêng, không nằm dưới `process*`)
→ kill osascript bị chặn ở kernel; `process-info` cũng bị deny nên
không tìm pid được. Đường `gui_failed` chỉ còn GUI hỏng thật — residual
không còn attacker-controlled.

## M4 + L8 — dialog flood + proc mồ côi (cùng vùng code)

Eviction/pop KHÔNG kill proc hiện ở **3 chỗ** — vá cả ba bằng helper
`_kill_proc(rec)` (`rec["proc"].terminate()` nếu còn sống):

1. `gate_local` evict — `local_pending.pop(next(iter(...))` (~401).
2. `broadcast()` — `perm_pending.clear()` trên `ready`/`done`/`err`
   (~619): duyệt dict terminate từng rec trước clear (L8: card ACP mồ
   côi giữ dialog treo tới TTL 10').
3. `session/request_permission` evict — `perm_pending.clear()` khi
   `>= PERM_MAX` (~805).

(Cancel-từ-chat đã terminate đúng ~441 — không đụng.)

**Cap dialog native đồng thời** `NATIVE_MAX = 2`, đếm qua **CẢ HAI**
`local_pending` + `perm_pending` (rec nào cũng có key `native`/`proc`):

- `gate_local`: đạt cap → KHÔNG tạo card, trả 409 `{"err": "đang có thẻ
  xác nhận chờ — duyệt hoặc huỷ trước đã"}`.
- `session/request_permission`: check trong cùng `store_lock` block
  registration (~804) → đạt cap thì gửi JSON-RPC error cho não ngay
  (y nhánh `dup` hiện có) — card không được đăng ký. KHÔNG downgrade
  card vì đó là kênh attack mới.

## `chat-bridge.ps1` — ĐÃ KIỂM: không có bug tương đương

ps1 `New-Gate` (~184) là Origin-based thuần — không có native dialog,
không có fallback path → không có downgrade surface. CAO-1 là
macOS-only. Phase-05 chỉ cần ghi nhận trong SECURITY.md.

## Test

- Tay trên macOS: `POST /api/permissions` → dialog hiện → **bấm Không**
  → card biến mất khỏi poll (`perm_done`), `POST /api/respond
  {id, optionId:"ok"}` Origin+token đúng → 404; permissions.json không
  đổi. Lặp với Esc (dialog không đóng — phải bấm Không).
- `POST /api/secrets` → bấm Không → secrets.local.json không đổi,
  respond forge → 404.
- Dialog hiện mà restart/kill bridge → card không tự duyệt sau boot
  (perm không persist — invariant cũ).
- Flood: spam 10 `POST /api/permissions` hợp lệ → ≤2 osascript process
  (`pgrep -f "display dialog"` chờ ≤2), request thứ 3+ → 409; duyệt xong
  1 cái → request mới spawn được. Evict → `pgrep osascript` giảm.
- `python3 tools/test-bridges.py` PASS (không đổi giao diện HTTP hợp
  lệ).

## Done khi

Mọi cách từ chối card local trên macOS (Không/Esc/TTL) đều kết thúc ở
`declined` — `_native_fallback` chỉ còn chạy khi Popen lỗi hoặc
osascript chết mà không output (GUI thật sự hỏng); `pgrep osascript`
không bao giờ vượt `NATIVE_MAX`.
