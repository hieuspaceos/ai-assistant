# Phase 5 — Mở rộng rẻ tiền + kiểm chứng + doc

## Mục tiêu

Hai thay đổi mở rộng có ích ngay không cần viết lại kiến trúc
(long-poll, serialize prompt), chốt test cho các phase trước, cập nhật
doc để audit sau không phải tìm lại.

## File động

| File | Action | Việc |
|---|---|---|
| `tools/chat-bridge.py` | modify | `/api/poll?wait=` long-poll + busy flag cho `/api/prompt` |
| `tools/chat-bridge.ps1` | modify | parity (xem R6 — chấp nhận `.py` trước nếu HttpListener vướng) |
| `web/chat.html` | modify | poll dùng `wait=25000`, reconnect nhanh khi done |
| `tools/test-bridges.py` | modify | case long-poll + busy; tổng hợp mọi case phase 1–3 |
| `docs/SECURITY.md` | modify | boundary mới (CSP, pending-perm, ttyd -O, Host); sửa mục permissions.json gọi đúng "policy không phải boundary" |
| `docs/decision-log.md` | modify | entry: vì sao chọn CSP thay tách port, `-O` thay `-c` |
| `PLAN.md` / `docs/codebase-summary.md` | modify | cập nhật mô tả nếu có chỗ lệch |

## Chi tiết

### 5a. Long-poll `/api/poll`

```python
new_event = threading.Condition(store_lock)   # broadcast() notify_all

# GET /api/poll?since=N&wait=25000
wait_ms = min(int(qs.get("wait", ["0"])[0] or 0), 30000)
if wait_ms:
    with store_lock:
        if not events_new_for(since):
            new_event.wait(wait_ms / 1000)
```

Client: `bfetch('/api/poll?since='+since+'&wait=25000')` → response về
ngay khi có event hoặc sau 25s trả rỗng → poll lại. Giảm ~97% request
(1 req/25s thay vì ~1 req/s) và độ trễ hiển thị ~0ms. Giữ hành vi cũ
khi không có `wait` (compat agent/script khác).

Cạm bẫy implementation: `new_event.wait()` phải nằm TRONG `with
store_lock:` (Condition tự release khi chờ, reacquire khi dậy); sau khi
dậy phải **tính lại** `reset`/`evs` — không được trả evs đã đọc trước
wait. `broadcast()` phải `new_event.notify_all()` trong `store_lock`.

`.ps1`: HttpListener async phức tạp hơn — nếu triển khai vướng trong
phase này thì `.py` ship trước, ghi nợ parity (client tự fallback vì
`wait` chỉ là hint; `.ps1` bỏ qua param vẫn đúng protocol).

### 5b. Serialize `/api/prompt`

```python
prompt_busy = threading.Event()

# /api/prompt: 
if prompt_busy.is_set():
    self._json({"err": "trợ lý đang xử lý câu trước"}, 409); return
prompt_busy.set()
# clear trong broadcast() khi {"t":"done"} hoặc {"t":"err"},
# VÀ trong spawn_brain()/_reader đặt dead — não chết giữa chừng
# không được kẹt busy mãi (giống bug "sendBtn disabled" đã từng vá ở UI)
```

Chặn 2 tab/2 client đan prompt vào một session ACP — event interleave
làm UI rối và agent nhận context lẫn. 409 để UI hiện "đang bận" thay
vì mất prompt (chat.html đã disable nút khi busy — cờ server là lớp
thứ hai cho client khác).

### 5c. Doc

- SECURITY.md: thêm hàng `Nội dung my-course → bridge | CSP connect-src
  'none'`; `WS ttyd → origin lạ | term-gate đòi mã trong shell`;
  `Host lạ → serve | reject 403 (py) / http.sys prefix (ps1)`; sửa rõ
  `permissions.json` là **policy cho agent, không phải technical
  boundary** (agent chạy shell full quyền user).
- decision-log: "CSP > tách port vì blast radius"; "term-gate >
  `-O`/`-c` vì `-O` chỉ so hostname bỏ port (đã test: `localhost:*` vẫn
  qua) còn `-c` không nhúng credential vào iframe được — gate ở shell
  độc lập mọi flag ttyd".

## Test bổ sung

| # | Case | Kỳ vọng |
|---|------|---------|
| 28 | `/api/poll?since=X&wait=300` không event | trả sau ~300ms, `events:[]` |
| 29 | poll `wait` + POST prompt song song | poll trả sớm với event text (không đợi hết wait) |
| 30 | 2× `POST /api/prompt` cạnh tranh | cái sau → 409 |

## Checklist kiểm chứng tay (Windows + macOS)

- [ ] `start.sh`/`start.bat`/`troly run` (launcher.py) mở đủ dịch vụ,
  tab Terminal nhúng được và vào thẳng não nhờ `?arg=`
- [ ] Trang `localhost:*` lạ (serve thử 1 file html port khác) mở
  `http://localhost:7681/` → WS vẫn nối nhưng chỉ thấy prompt "Ma ket
  noi", gõ sai → exit (gate không phải từ chối ở tầng WS — đừng nhầm
  là hở)
- [ ] `Host: evil` vào :8080 → 403 (mac); Windows kiểm vẫn 200 vì đã
  an toàn sẵn — verify đúng hành vi hiện tại
- [ ] Clone-view sửa+lưu được; slide chuyển trang được (CSP không giết)
- [ ] DevTools trong trang clone: fetch :7682 → CSP refused
- [ ] Perm card thật bấm Đồng ý vẫn chạy; respond id bịa → 404
- [ ] Chat 2 tab: gửi tab 1, tab 2 thấy "đang bận"/409 không đan xen
- [ ] `/doc-zalo` end-to-end trên Zalo Web thật (regression perf phase 4)

## Chốt

Sau phase này: 3 lỗ hổng chứng minh được đều đóng hoặc có biện pháp đo
được, perf hot-path giảm layout-thrash + parse O(n²), nợ mở rộng còn
lại là architectural (multi-session, sandbox agent) — ghi rõ là quyết
định có chủ đích, không phải lỗ quên.
