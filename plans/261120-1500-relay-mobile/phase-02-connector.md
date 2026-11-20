# Phase 2 — `tools/connector.py`: đường dây từ desktop ra VPS

Desktop chủ động nối RA (outbound) nên qua được mọi NAT. Connector là một
**child process thường trực** trong supervisor `troly` (đợt 2) — chỉ chạy
khi user bật "truy cập điện thoại".

## Luồng

```
troly run → connector.py (LUÔN trong jobs — xem mục 3)
   remote.json absent/disabled → sleep loop re-check, không thoát
   enabled → nối wss://vps.example/ws/desktop?mid=X
             + header X-Relay-Auth: X:<ts>:HMAC(X:ts, secret)
   ngay sau handshake → gửi {"type":"hello","bridge_token":<token>}
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

- Header `X-Relay-Auth: <mid>:<ts>:<hmac>` với
  `hmac = HMAC-SHA256(mid + ":" + ts, secret)` — timestamp ngăn replay
  (relay chấp |now−ts| < 5'). **KHÔNG đặt trong `?s=`** — query rớt vào
  access log Caddy/relay. Secret là chìa khoá của CẢ cặp desktop↔relay,
  cất ở `.devin/remote.json` cùng một bản ghi `relay.secret` trên VPS —
  sinh 1 lần lúc setup, `scp` lên.
- WS handshake: nối TCP+TLS (`ssl.create_default_context()`), gửi GET upgrade
  với `Sec-WebSocket-Key` ngẫu nhiên — tái dùng pattern frame/parse đã có.
- **Client frame phải mask** (chuẩn WS, relay check đúng).

### 2. Forward request → localhost

```python
def forward(msg):
    port = next(p for pre, p in PORT_MAP if msg["path"].startswith(pre))
    # /ext-api/browser/status → /api/browser/status (ext-bridge chỉ biết /api/*)
    path = "/api" + msg["path"][len("/ext-api"):] if port == 7684 else msg["path"]
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

### 3. Bổ sung supervisor `troly` — API THẬT trong `launcher.py`

Supervisor hiện tại: `jobs = [("serve",8080),("chat-bridge",7682),
("ext-bridge",7684)]` + ttyd có điều kiện; `child_cmd(name, port)` sinh
`[sys.executable, name, str(port), DATA]` khi FROZEN. Thêm connector:

```python
jobs.append(("connector", 7685))   # LUÔN append — xem dưới
```

- **`child_cmd("connector", 7685)`** → `troly connector 7685 <DATA>` —
  argv[1] chính là port listener pair-code (mục 4), khỏi hardcode.
- **Luôn trong `jobs`, connector TỰ idle khi disabled**: remote.json
  absent hoặc `enabled:false` → connector `sleep 5` + re-check file,
  KHÔNG thoát. Lý do: (a) thoát sớm <10s bị supervisor tính crash-loop;
  (b) `jobs` chỉ đọc lúc boot → toggle `enabled` trong portal (mục
  `/api/remote/config`) có hiệu lực ngay mà không cần restart troly —
  connector tự thấy file đổi và nối/ngắt WS.
- Log prefix `[connector]` → `.logs/connector.log` (theo pattern
  `spawn` hiện có: `os.path.join(LOGDIR, n + ".log")`).

### 4. Pairing UX từ phía desktop

`GET /api/remote/pair-code` trên chat-bridge (endpoint nhỏ, phase 5 plan
trước đã có auth): bridge cần nhờ connector xin mã từ relay — **nhưng
connector chỉ có WS outbound, không có cửa nghe local** → phải thêm một
kenh IPC:

**Chọn: connector mở HTTP listener `127.0.0.1:7685`** (bắt token như mọi
bridge khác), expose `GET /pair-code` → nhắn `{"type":"pair-request"}` qua
WS lên relay → relay trả mã → connector trả về bridge → bridge trả portal.
Một socket listen thêm ~30 dòng, giữ đúng nguyên tắc "mọi giao tiếp relay
nằm trong connector". Portal ⚙ hiện mã 6 số + đếm ngược 5:00.

*(Phương án thay thế đã cân: chat-bridge tự `POST https://relay/pair-request`
kèm HMAC — bỏ được IPC nhưng phá luật "bridge không biết VPS tồn tại".)*

(Đường đi hơi dài nhưng giữ **mọi giao tiếp relay nằm trong connector** —
không process nào khác nói chuyện ra ngoài. Đây là điểm audit được khi rà
lại: bridge không biết VPS tồn tại.)

### 5. `.devin/remote.json` — cấu hình cửa nhà

```json
{
  "enabled": true,
  "relay": "wss://relay.example.com/ws/desktop",
  "machine_id": "a3f8…",          // sinh 1 lần, gắn với máy
  "secret": "9d41…"               // HMAC key — KHÔNG commit, chmod 600
}
```

URL KHÔNG kèm `:4443` — Caddy terminate TLS ở 443 rồi proxy về
127.0.0.1:4443 nội bộ; connector chỉ thấy cổng ngoài 443.

- Ghi bởi `POST /api/remote/config` (portal ⚙ — phase 3; endpoint mới
  trong chat-bridge.py cùng nhánh `/api/remote/*` với pair-code) hoặc
  thủ công.
- `.gitignore` thêm `.devin/remote.json` (cùng nhóm bridge.token —
  hiện `.gitignore` CHƯA có dòng này, bắt buộc thêm).
- `enabled: false` → connector idle trong sleep-loop (mục 3), không
  mở đường ra ngoài; WS cũ nếu đang mở thì đóng.

### 6. Hai lỗi môi trường cần phòng sẵn

- **Port 7685 chiếm** → connector log rõ "port 7685 đang bị chiếm,
  pair-code sẽ không hoạt động" rồi vẫn chạy phần WS (listener chỉ
  phục vụ nút lấy mã — không nên vì nó mà chết cả connector).
- **Redirect lộ port nội bộ**: response local có `Location:
  http://127.0.0.1:8080/...` (VD `/web` → `/web/`) sẽ đưa phone về
  localhost của CHÍNH NÓ → connector phải rewrite mọi `Location`
  trỏ `127.0.0.1:*`/`localhost:*` thành path tương đối trước khi trả.
- `test-parity.py` regex `"(/api/[a-z-]+)"` KHÔNG thấy endpoint lồng
  (`/api/remote/pair-code`) → nới thành `[a-z/-]+` khi thêm endpoint
  này, kẻo parity test mù với chính route mới. Và nếu plan này chạy
  TRƯỚC khi `.ps1` frozen (ship-learner ph-5): endpoint `/api/remote/*`
  chỉ có trong `.py` sẽ làm test-parity FAIL — hoặc port stub sang
  `.ps1` (trả 501), hoặc ghi rõ thứ tự "relay sau khi ps1 frozen".

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
