# Phase 1 — `relay.py`: điểm hẹn trên VPS

Một file duy nhất trên VPS — registry đường dây desktop + phát mã ghép đôi +
bơm request HTTP hai chiều qua WS. Tái dùng mẫu WS server trong
`tools/ext-bridge.py` (ws_handshake/ws_recv/ws_send đã chạy thật).

## Vai trò — bưu điện, không biết nghĩ

```
GET  /                    → serve portal static (từ web/ đã copy lên VPS)
GET  /api/* (+ POST)      → forward xuống connector của desktop → bridge :7682
GET  /assets/...          → forward xuống connector → serve.py :8080
WS   /ws/desktop?mid=&s=  → connector desktop cắm đường dây vào (đăng ký)
GET  /pair (POST code)    → điện thoại đổi mã 6 số lấy cookie session
GET  /health              → {"ok": true, "desktops_online": n}
```

## File mới — `deploy/relay.py` (~350 dòng)

```python
#!/usr/bin/env python3
# relay.py — điểm hẹn giữa điện thoại và desktop ở nhà.
# Stdlib only. Chạy: python3 relay.py --port 4443 --secret-file relay.secret
import json, threading, secrets, time, hmac, base64, os, sys
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.parse import urlparse, parse_qs

DESKTOP_SECRET = open("relay.secret").read().strip()   # sinh 1 lần: secrets.token_hex
DESKS = {}          # mid -> {"sock": ws, "last": ts, "lock": Lock}
PENDING = {}        # req_id -> {"ev": Event, "res": bytes|None}
PAIRS = {}          # code -> {"mid": mid, "exp": ts}
SESSIONS = {}       # sess_token -> {"mid": mid, "exp": ts}
PAIR_TTL, SESS_TTL = 300, 30*86400
```

### 1. WS endpoint `/ws/desktop` — đăng ký đường dây

- Query `mid` (machine id) + `s` = HMAC-SHA256(mid, DESKTOP_SECRET) —
  connector chứng minh nó biết secret chung.
- `Origin`/host: không check Origin (đây là server-initiated WS của
  connector, Origin không có nghĩa ở chiều này — auth bằng HMAC).
- Thành công → `DESKS[mid] = sock`. Nếu mid đã online: **đường mới thắng**,
  close đường cũ (máy khởi động lại sẽ nối lại).
- Loop đọc frame: mỗi frame từ connector = response cho một `PENDING` request
  (id khớp) → `ev.set()`. Connector KHÔNG gửi request chủ động (ngoài
  `pair-request` bên dưới).

### 2. Pairing — phát mã và đổi mã

```python
# connector đẩy qua WS: {"type": "pair-request"} → relay trả mã
{"type": "pair-code", "code": "482913", "exp": ts}
# relay lưu PAIRS["482913"] = {mid, exp}
```

- Code: `f"{secrets.randbelow(1000000):06d}"` — 6 số, TTL 5 phút, một mã dùng
  được **một lần** (pop khi đổi thành công).
- `POST /pair {"code": "482913"}`:
  - Tìm mã còn hạn → tạo `SESSIONS[tok] = {mid}` → `Set-Cookie: s=<tok>;
    HttpOnly; Secure; SameSite=Lax; Max-Age=2592000`
  - **Rate limit**: per-IP tối đa 5 lần/phút (`RATE = {}` — ip → [ts...]).
    Sai mã trả 401 chung, không nói "mã hết hạn" hay "không tồn tại".
  - Điện thoại có cookie → mọi request sau đó resolve `mid` từ session.

### 3. HTTP proxy — bơm request xuống desktop

```python
def forward(self, mid):
    req_id = secrets.token_hex(8)
    body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
    msg = {"id": req_id, "method": self.command, "path": self.path,
           "headers": dict(self.headers), "body": base64.b64encode(body).decode()}
    ev = threading.Event(); PENDING[req_id] = {"ev": ev}
    ws_send(DESKS[mid]["sock"], json.dumps(msg))
    if not ev.wait(timeout=30): return 503
    res = PENDING.pop(req_id)["res"]      # connector gửi frame {id, status, headers, body64}
    ...  # viết status + headers + body về cho điện thoại
```

- Auth request từ phone: check cookie `s` → mid. Không có/sai → redirect về
  trang nhập mã (serve `pair.html` ở `/pair`, GET trả form nhập 6 số).
- `DESKS` không có mid → **503 + trang "trợ lý ở nhà đang nghỉ"** (HTML
  nhỏ inline, tiếng Việt, không stack trace).
- Timeout 30s → 504. PENDING dọn định kỳ (GC entry > 60s — tránh leak).

### 4. Route đích — prefix ánh xạ port (connector quyết định, relay chỉ chuyển)

Relay **không** tách path — chuyển nguyên `path` xuống connector; connector
map sang port local (phase 2). Giữ relay ngu.

**Ngoại lệ BẮT BUỘC ở relay** (lớp lọc thô, trước khi forward):
```python
BLOCK = ("/my-course/.shots", "/.devin", "/.git")
if any(b in self.path for b in BLOCK): return 403
```
(đúng yêu cầu relay trong SECURITY.md của đợt 1 — lọc ở mép, không chờ
connector.)

### 5. Static portal

- `GET /`, `/web/*`, `/pair` (form) → serve từ `./web/` copy sẵn lên VPS
  (deploy step trong phase 4). Không phải forward — portal phải load được
  **kể cả khi desktop offline** (để hiện trạng thái + form nhập mã).

## Acceptance criteria

- Connector giả (wscat hoặc python client) nối `?mid=vm1&s=<hmac>` → online;
  sai `s` → close ngay.
- `pair-request` → nhận 6 số; `POST /pair` đúng mã → cookie; sai mã 6 lần
  trong 1 phút từ một IP → lần 7 bị 429.
- `GET /api/health` qua relay → 200 khi desktop online; rút connector →
  request tới `api/health` trả 503 "đang nghỉ".
- `GET /my-course/.shots/x.png` qua relay → 403 **không chạm** connector.
- ThreadingHTTPServer: 2 request đồng thời (một nhanh một chậm 20s) không
  chặn nhau.

## Rủi ro

- WS frame code port từ ext-bridge — nhớ **connector→relay frame cũng phải
  mask** (client→server đúng chuẩn) và handle fragmentation như bản gốc.
- `DESKS`/`PENDING` chia sẻ giữa thread HTTP và thread WS → mọi truy cập
  qua lock per-mid.
- Pair code 6 số * cần brute-force trong 5 phút = 10⁶ khả năng * — rate
  limit 5 lần/phút/IP là khuyên đủ.
