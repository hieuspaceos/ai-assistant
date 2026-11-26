# Phase 2 — ext-bridge.py auth

## Mục tiêu

`ext-bridge.py` bắt token trên `/api/*` + WS `/ext`, đồng thời vá lỗ hổng
thật: WS không gửi Origin hiện connect được và chiếm slot extension.

## File động

| File | Action | Việc |
|---|---|---|
| `tools/ext-bridge.py` | modify | token load + check HTTP + check WS path |

## Chi tiết

### Token load

Giống phase 1 (copy `TOKEN_FP` + `load_token()` — đọc `.devin/bridge.token`,
fallback `O_EXCL` sinh). KHÔNG cần export env (ext-bridge không spawn não).

### HTTP API

Trong `serve_conn`, sau khi parse `method`/`path` và TRƯỚC origin check:

```python
q = urllib.parse.parse_qs(urllib.parse.urlparse(path).query)
tok = (re.search(r"^x-bridge-token:\s*(\S+)", head, re.I | re.M) or [None,""])[1] \
      if False else None
# đơn giản hơn: lấy header bằng regex như origin
mo_t = re.search(r"^x-bridge-token:\s*(\S+)", head, re.I | re.M)
tok = (mo_t.group(1).strip() if mo_t else None) or (q.get("token") or [""])[0]
authed = hmac.compare_digest(tok, BRIDGE_TOKEN)
```

Áp: `OPTIONS` miễn; mọi path `/api/*` còn lại bắt `authed` → `401`.

CORS: `send_json` + `OPTIONS` response thêm `X-Bridge-Token` vào
`Access-Control-Allow-Headers`.

### WS `/ext`

Request line hiện so `path == "/ext"` — sửa thành parse:

```python
p = urllib.parse.urlparse(path)
if method == "GET" and p.path == "/ext" and "upgrade: websocket" in head.lower():
    tok = (urllib.parse.parse_qs(p.query).get("token") or [""])[0]
    if not hmac.compare_digest(tok, BRIDGE_TOKEN):
        sock.sendall(b"HTTP/1.1 401 Unauthorized\r\nContent-Length:0\r\n\r\n")
        sock.close(); return
    if ws_handshake(sock, head): ...
```

→ đóng được lỗ hổng "no-Origin chiếm slot": process local không có token
không vào được nữa (extension có token từ phase 4).

## Acceptance

- `POST /api/browser` không token → 401; đúng token → chạy
- `/api/browser/status` không token → 401 (nó lộ trạng thái — khoá luôn)
- `GET /ext` không `?token=` → 401, không chiếm được slot
- `GET /ext?token=<đúng>` + Origin extension → handshake OK
- `OPTIONS` → 204 với Allow-Headers đầy đủ

## Rủi ro

- Extension chưa có token (phase 4) → flap reconnect — chấp nhận trong dev,
  test phase này bằng client WS giả
