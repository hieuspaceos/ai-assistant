# Phase 2 — `tools/connector.py`: đường dây từ desktop ra VPS

Desktop chủ động nối RA (outbound) nên qua được mọi NAT. Connector là một
**child process thường trực** trong supervisor `troly` (đợt 2) — chỉ chạy
khi user bật "truy cập điện thoại".

## Luồng

```
troly run → (nếu .devin/remote.json bật) → connector.py
   nối wss://vps.example/ws/desktop?mid=X&s=HMAC(X, secret)
   loop: đọc frame {id, method, path, headers, body64}
         → HTTP request nội bộ đúng port theo bảng map
         → gửi lại {id, status, headers, body64}
   mất kết nối → backoff 2s→60s → nối lại (giống pattern reconnect
   của extension/background.js)
```

## File mới — `tools/connector.py` (~200 dòng)

```python
#!/usr/bin/env python3
# connector.py — giữ đường dây ra VPS relay, chuyển request về localhost.
# Stdlib only. Đọc cấu hình .devin/remote.json:
#   {"enabled": true, "relay": "wss://relay.example.com/ws/desktop",
#    "machine_id": "<uuid>", "secret": "<hex>"}
import json, socket, base64, hashlib, hmac as hmaclib, os, sys, time
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

CONF = os.path.join(".devin", "remote.json")
PORT_MAP = [                      # theo thứ tự khớp đầu path
    ("/api/",        7682),       # chat-bridge — trừ /api/health? KHÔNG: mọi /api đều đúng 7682
    ("/ext-api/",    7684),       # prefix giả → ext-bridge (strip prefix khi forward)
    ("/",            8080),       # serve.py — fallback cuối
]
```

### 1. Auth + handshake

- `s = hmac.new(secret, machine_id, sha256).hexdigest()` — chuẩn client-side,
  không phải token trong file user đọc được (khác `.devin/bridge.token`:
  cái này là chìa khoá của CẢ cặp desktop↔relay, cất ở `.devin/remote.json`
  cùng một bản ghi `relay.secret` trên VPS — sinh 1 lần lúc setup, `scp` lên).
- WS handshake: nối TCP+TLS (`ssl.create_default_context()`), gửi GET upgrade
  với `Sec-WebSocket-Key` ngẫu nhiên — tái dùng pattern frame/parse đã có.
- **Client frame phải mask** (chuẩn WS, relay check đúng).

### 2. Forward request → localhost

```python
def forward(msg):
    port = next(p for pre, p in PORT_MAP if msg["path"].startswith(pre))
    path = msg["path"][len("/ext-api"):] if port == 7684 else msg["path"]
    req = Request(f"http://127.0.0.1:{port}{path}", data=body or None,
                  headers={k: v for k, v in msg["headers"].items()
                           if k.lower() not in ("host", "cookie", "content-length")},
                  method=msg["method"])
    try:
        r = urlopen(req, timeout=25)
        return {"id": msg["id"], "status": r.status,
                "headers": dict(r.headers), "body64": b64(r.read())}
    except HTTPError as e:
        return {"id": msg["id"], "status": e.code,
                "headers": dict(e.headers), "body64": b64(e.read())}
    except URLError:
        return {"id": msg["id"], "status": 502, "body64": b64(b"local service down")}
```

- **Strip `cookie`** — session của relay ở cookie, KHÔNG chuyển xuống bridge
  local (bridge không hiểu, và tránh lẫn chuyện auth).
- **`X-Bridge-Token` đi xuyên**: phone đã có token (qua pairing — phase 3),
  header đến đúng bridge :7682 → auth nội bộ giữ nguyên. Connector không
  thêm, không bớt — chỉ là đường ống.

### 3. Bổ sung supervisor `troly` (đợt 2 đã có khung)

Trong code `troly run` (phase 8 plan trước), thêm child thứ 5 **có điều kiện**:

```python
if remote_conf.get("enabled") and remote_conf.get("relay"):
    child("connector", [SELF, "connector"])
```

`connector` cũng là một role của binary (`troly connector`) — kế thừa
watchdog/restart/log giống 4 child kia. Log prefix `[connector]` trong
`.logs/troly.log`.

### 4. Pairing UX từ phía desktop

`GET /api/remote/pair-code` trên chat-bridge (endpoint nhỏ, phase 5 plan
trước đã có auth): bridge forward `{"type": "pair-request"}` xuống connector
local → connector nhắn qua WS lên relay → relay trả mã → bridge trả về
portal. Portal ⚙ hiện mã 6 số + đồng hồ đếm ngược 5 phút.

(Đường đi hơi dài nhưng giữ **mọi giao tiếp relay nằm trong connector** —
không process nào khác nói chuyện ra ngoài. Đây là điểm audit được khi rà
lại: bridge không biết VPS tồn tại.)

### 5. `.devin/remote.json` — cấu hình cửa nhà

```json
{
  "enabled": true,
  "relay": "wss://relay.example.com:4443/ws/desktop",
  "machine_id": "a3f8…",          // sinh 1 lần, gắn với máy
  "secret": "9d41…"               // HMAC key — KHÔNG commit, chmod 600
}
```

- Sinh bởi `GET /api/remote/setup` (phase 3 portal gọi) hoặc thủ công.
- `.gitignore` thêm `.devin/remote.json` (cùng nhóm bridge.token).
- `enabled: false` → troly không spawn connector, không có cửa ra ngoài.

## Acceptance criteria

- Giả relay (ws server echo local): connector nối được, gửi request ảo →
  response về đúng `id`.
- Kill process `serve.py` giả → request `/x` về qua connector trả 502 chứ
  không nứt connector.
- Rút mạng 30s → connector reconnect, request sau đó đi qua bình thường.
- `machine_id`+`secret` sai → relay close → connector backoff và log rõ.
- Cookie của phone không lọt xuống bridge local (test bằng cách log header
  thấy không có `Cookie: s=`).

## Rủi ro

- WS client write tay → ping/pong keepalive (mỗi 30s) để NAT không đóng đường —
  copy từ pattern extension ping.
- Request lớn (upload file qua portal) — body64 phình 1.33x; v1 chấp nhận,
  ghi giới hạn 10MB trong runbook.
- Nhiều desktop cùng `mid` — relay xử "đường mới thắng" (phase 1 đã ghi).
