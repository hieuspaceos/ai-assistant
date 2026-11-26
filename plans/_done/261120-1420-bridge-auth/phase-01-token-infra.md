# Phase 1 — Token infra + chat-bridge.py

## Mục tiêu

Có `.devin/bridge.token` dùng chung + `chat-bridge.py` bắt token trên mọi
endpoint (trừ health + OPTIONS) mà không vỡ CORS.

## File động

| File | Action | Việc |
|---|---|---|
| `.gitignore` | modify | thêm `.devin/bridge.token` |
| `start.sh` | modify | sinh token nếu thiếu TRƯỚC khi launch; mở URL kèm `?t=` |
| `start.bat` | modify | tương đương PowerShell |
| `tools/chat-bridge.py` | modify | load token, `_authed()`, sửa CORS, export env |

## Chi tiết

### 1a. Sinh token — `start.sh`

Trước khi launch các bridge:

```bash
TOKEN_FILE="$DIR/.devin/bridge.token"
mkdir -p "$DIR/.devin"
if [ ! -f "$TOKEN_FILE" ]; then
  (umask 077; openssl rand -hex 24 > "$TOKEN_FILE")
fi
BRIDGE_TOKEN="$(cat "$TOKEN_FILE")"
open "http://localhost:8080/web/?t=$BRIDGE_TOKEN"
```

`start.bat` tương đương:

```bat
if not exist .devin\bridge.token (
  powershell -NoProfile -Command ^
    "[IO.File]::WriteAllText('.devin\bridge.token', -join ((1..48) | %% { '{0:x}' -f (Get-Random -Max 16) }))"
)
for /f "delims=" %%i in (.devin\bridge.token) do set "BRIDGE_TOKEN=%%i"
```

### 1b. `tools/chat-bridge.py`

Gần đầu file (sau `BRAIN_FP`):

```python
TOKEN_FP = os.path.join(CWD, ".devin", "bridge.token")

def load_token():
    # fallback: tự sinh atomic nếu start script chưa chạy (O_EXCL chống race)
    try:
        with open(TOKEN_FP) as f:
            return f.read().strip()
    except OSError:
        import secrets as _s
        t = _s.token_hex(24)
        try:
            fd = os.open(TOKEN_FP, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.write(fd, t.encode()); os.close(fd)
            return t
        except FileExistsError:
            return load_token()   # thằng khác thắng race → đọc của nó

BRIDGE_TOKEN = load_token()
os.environ.setdefault("BRIDGE_TOKEN", BRIDGE_TOKEN)  # cho process não kế thừa
```

Helper trong `Handler`:

```python
import hmac

def _authed(self):
    q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
    tok = self.headers.get("X-Bridge-Token") or (q.get("token") or [""])[0]
    return hmac.compare_digest(tok, BRIDGE_TOKEN)
```

Áp vào `do_GET`/`do_POST` ngay sau `path = ...`:

```python
if path != "/api/health" and not self._authed():
    return self._json({"err": "thiếu hoặc sai mã kết nối"}, 401)
```

`do_OPTIONS` — giữ nguyên (KHÔNG check token) nhưng sửa header:

```
Access-Control-Allow-Headers: Content-Type, X-Bridge-Token
```

(`send_json`/`_json` nếu có CORS header ở response thường cũng thêm
`X-Bridge-Token` vào Allow-Headers.)

`/api/health` trả thêm `"version"` (đọc file `VERSION` — tạo trong phase 7,
fallback `"0"`).

## Acceptance

- `curl :7682/api/poll` không token → `401 {"err":...}`
- `?token=sai` → 401; `?token=<đúng>` → 200
- `X-Bridge-Token: <đúng>` → 200
- `OPTIONS` preflight không token → 204 kèm `Access-Control-Allow-Headers`
  chứa `X-Bridge-Token`
- `GET /api/health` không token → 200
- Process não spawn ra: `env | grep BRIDGE_TOKEN` (nếu kế thừa được — không
  bắt buộc, fallback đọc file)

## Rủi ro

- OPTIONS check token → vỡ CORS: test case đầu tiên
- `parse_qs` trên mọi request — rẻ, OK
