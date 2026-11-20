# Phase 1 — Khoá ba cửa đang mở (ttyd origin, Host header, ext-bridge)

## Mục tiêu

Đóng các vector đã chứng minh bằng test trực tiếp: shell qua ttyd từ
trang `localhost:*` lạ; đọc file qua DNS rebinding trên :8080 (macOS);
race `next_id` + frame WS không cap trong ext-bridge.

## File động

| File | Action | Việc |
|---|---|---|
| `start.sh` | modify | thêm `-O` vào dòng launch ttyd (l.57) |
| `tools/chat-terminal.ps1` | modify | thêm `-O` vào lệnh ttyd (cuối file) — **giữ BOM** |
| `tools/serve.py` | modify | reject Host lạ (rebinding) |
| `tools/ext-bridge.py` | modify | `next_id` vào trong lock + cap payload WS |
| `tools/test-bridges.py` | modify | test case 17–20 (Host check, flags, WS cap khó test động → test tĩnh) |
| `docs/SECURITY.md` | modify | cập nhật trust boundary + residual rebinding của ttyd |

## Chi tiết

### 1a. ttyd `-O` — một ký tự, đóng shell mở trần

```diff
# start.sh
- ttyd -p 7681 -i 127.0.0.1 -W "$BRAIN_TERM" ...
+ ttyd -p 7681 -i 127.0.0.1 -W -O "$BRAIN_TERM" ...

# tools/chat-terminal.ps1
- ttyd -p 7681 -i 127.0.0.1 -W ` -t $theme ... $brain
+ ttyd -p 7681 -i 127.0.0.1 -W -O ` -t $theme ... $brain
```

Vì sao `-O` đủ cho vector chính: WS hợp lệ phát từ document ttyd trên
`localhost:7681` (portal iframe trỏ thẳng `:7681`) → Origin
`http://localhost:7681` khớp. Trang lạ trên `localhost:3000` có Origin
khác → 403. **Không** dùng `-c` vì iframe không nhúng được credential.

Residual (ghi vào SECURITY.md): rebinding giữ Origin==Host → vẫn qua
được; giảm rủi ro vì Chrome PNA + yêu cầu attacker đoán port/timing;
nếu sau này cần chặt hơn → chat-bridge proxy ttyd hoặc chạy ttyd
on-demand khi mở tab Terminal.

### 1b. `serve.py` — check Host

Trong `send_head`, trước khi serve:

```python
host = (self.headers.get("Host") or "").split(":")[0].lower()
if host not in ("localhost", "127.0.0.1", "::1", "[::1]") \
        and not host.endswith(".localhost"):
    self.send_error(403, "Host không được phép"); return None
```

Windows không cần đổi: `serve.ps1` đăng ký prefix `http://localhost:8080/`
→ http.sys tự reject Host lạ ở kernel (bản Windows vốn đã an toàn hơn —
ghi chú parity vào test để không ai "sửa" ngược).

### 1c. ext-bridge — race + cap

```python
# ext_call: đưa id vào cùng lock với lấy socket
with ext_lock:
    s = ext_sock
    next_id[0] += 1
    rid = next_id[0]

# ws_recv: sau khi giải n — frame > 64MB là lỗi/tấn công
MAX_WS_MSG = 64 * 1024 * 1024
if n > MAX_WS_MSG:
    raise ConnectionError("frame quá lớn")
```

64MB đủ cho screenshot 4K base64 (~vài chục MB). `pending` đã tự dọn
qua timeout/pop — không đụng.

## Test bổ sung (tools/test-bridges.py)

| # | Case | Kỳ vọng |
|---|------|---------|
| 17 | serve.py `GET /web/index.html` `Host: evil.example` | 403 |
| 18 | serve.py cùng request `Host: localhost:8080` | 200 |
| 19 | static: `grep -q ' -O '` trong start.sh và chat-terminal.ps1 dòng ttyd | có flag |
| 20 | static: `ext-bridge.py` chứa `MAX_WS_MSG` và `next_id` tăng dưới `ext_lock` | có |

## Lưu ý

- 19/20 là test tĩnh (đọc file) — chấp nhận vì WS race/DoS test động tốn
  công hơn giá trị; mục tiêu chặn "ai đó gỡ flag/fix sau này".
- Chạy tay sau phase: mở portal → tab Terminal vẫn nhúng ttyd bình
  thường (verify `-O` không phá iframe hợp lệ — đây là case dễ hỏng
  nhất của phase, test trên cả Brave/Chrome).
