# Phase 1 — Khoá các cửa đang mở (ttyd gate, Host check, ext-bridge)

## Mục tiêu

Đóng các vector đã chứng minh bằng test trực tiếp: shell qua ttyd từ
trang `localhost:*` lạ; đọc file qua DNS rebinding trên :8080 (macOS);
race `next_id` + frame WS không cap trong ext-bridge; extension giữ
token rác gây DoS.

## ĐÃ KIỂM CHỨNG — `-O` không vá được

Test trực tiếp ttyd 1.7.7 trên máy dev: với `-O`, WS handshake từ
`Origin: http://localhost:3000` vẫn `101`. Cơ chế `-O` chỉ so sánh
**hostname (không so port)** giữa Origin và Host → mọi trang
`localhost:*` đều "hợp lệ", rebinding cũng qua (origin==host sau
rebind). `-O` chỉ chặn cross-domain thật — vô dụng với threat model
loopback. **Không dùng `-O`.**

## File động

| File | Action | Việc |
|---|---|---|
| `tools/term-gate.sh` | create | wrapper check mã rồi exec não (POSIX) |
| `tools/term-gate.cmd` | create | bản Windows (cmd) — không BOM cần thiết, ASCII only |
| `start.sh` | modify | ttyd chạy qua `term-gate.sh` + `-a` |
| `tools/chat-terminal.ps1` | modify | ttyd chạy qua `term-gate.cmd` + `-a` — **giữ BOM**, giữ nguyên các `-t` theme |
| `tools/launcher.py` | modify | **đường spawn ttyd thứ 3** — binary đóng gói `troly run` spawn `ttyd -W <não>` trực tiếp (dòng ~134), không qua start script nào; phải qua gate + `-a` y hệt, nếu không bản đóng gói vẫn mở shell trần |
| `web/app.js` | modify | `termFrame.src` kèm `?arg=<BRIDGE_TOKEN>` |
| `tools/serve.py` | modify | reject Host lạ (rebinding), parse đúng `[::1]` |
| `tools/ext-bridge.py` | modify | `next_id` vào trong lock + cap payload WS |
| `extension/background.js` | modify | chỉ persist `bridge_token` sau khi WS open thành công |
| `tools/test-bridges.py` | modify | case 19–22 |
| `docs/SECURITY.md` | modify | cập nhật boundary ttyd + residual |

## Chi tiết

### 1a. Gate ngay trong shell — cửa ttyd cũng khoá bằng "chìa khoá nhà"

Nguyên tắc: đừng nhờ ttyd xác thực (nó yếu) — **mỗi kết nối spawn một
shell, shell tự kiểm mã trước khi chạy não**. Hoạt động với mọi bản
ttyd, không phụ thuộc flag nào:

```sh
#!/bin/sh
# tools/term-gate.sh — $1 = arg từ ?arg= (ttyd -a append CUỐI argv);
# não lấy từ env BRAIN_TERM (start.sh export), không truyền argv.
t="$1"
if [ -z "$t" ]; then
  printf "Ma ket noi (xem trong portal > Cai dat): "
  read -r -t 90 t || exit 1        # treo 90s cho kẻ lạ, rồi tự thoát
fi
[ "$t" = "$BRIDGE_TOKEN" ] || { echo "Sai ma ket noi."; sleep 2; exit 1; }
exec "${BRAIN_TERM:-devin}"
```

```bat
@echo off
:: tools/term-gate.cmd — %1 = ?arg= từ URL; não từ %BRAIN_TERM%
:: (@echo off phải là dòng đầu — nếu không dòng comment bị echo ra màn hình)
set "t=%~1"
if "%t%"=="" set /p "t=Ma ket noi (xem trong portal > Cai dat): "
if not "%t%"=="%BRIDGE_TOKEN%" (echo Sai ma ket noi.& exit /b 1)
%BRAIN_TERM%
```

Launch (cả hai nền tảng):

```sh
# start.sh — export cả hai để ttyd → gate kế thừa env
# (start.sh đã cd về project root ở đầu file nên path tương đối OK)
export BRAIN_TERM
ttyd -p 7681 -i 127.0.0.1 -W -a sh tools/term-gate.sh
# với ?arg=X → argv: sh term-gate.sh X  (arg append CUỐI)
```

```powershell
# chat-terminal.ps1 — sau khi đọc $brain; GIỮ NGUYÊN các -t theme
# (theme sáng + fontSize=17 + lineHeight đã chỉnh cho học viên —
# bản draft đầu làm mất hết, nhét lại đúng vị trí trước command)
$env:BRAIN_TERM = $brain
ttyd -p 7681 -i 127.0.0.1 -W -a `
  -t $theme `
  -t fontSize=17 `
  -t lineHeight=1.45 `
  cmd /c "$PSScriptRoot\term-gate.cmd"
# (path tuyệt đối qua $PSScriptRoot — CWD của ttyd không chắc là project root)
```

```python
# launcher.py — trong supervisor(), thay nhánh ttyd:
if shutil.which("ttyd"):
    os.environ["BRAIN_TERM"] = brain_terminal()
    if platform.system() == "Windows":
        gate = ["cmd", "/c", os.path.join(DATA, "tools", "term-gate.cmd")]
    else:
        gate = ["sh", os.path.join(DATA, "tools", "term-gate.sh")]
    jobs.append(("ttyd", ["ttyd", "-p", "7681", "-i", "127.0.0.1",
                          "-W", "-a"] + gate))
# term-gate.* nằm trong tools/ → CODE_DIRS đã copy sang DATA khi bootstrap.
# BRIDGE_TOKEN đã có sẵn trong env nhờ ensure_token() — gate kế thừa.
```

Portal tự điền mã (học viên không phải dán):

```js
// app.js — chỗ termFrame.src
termFrame.src = TTYD_URL + '/?arg=' + encodeURIComponent(window.BRIDGE_TOKEN);
```

**Verify bắt buộc khi implement** (vì phụ thuộc hành vi `-a` của ttyd
bản cài): mở portal → tab Terminal vào được não ngay không hỏi mã;
mở `http://localhost:7681/` trực tiếp (không `?arg=`) → hỏi mã, gõ
sai → "Sai ma ket noi". Nếu `-a` không truyền arg (bản ttyd khác):
fallback vẫn an toàn — prompt hỏi mã, UX xấu hơn chút nhưng không hở.

Residual sau fix: kẻ lạ chiếm được WS chỉ thấy prompt mã (đọc token
file đòi quyền user — tới đó thì đã có shell rồi). Token trong
`iframe.src` DOM — cùng mức lộ với localStorage hiện tại, không thêm
bề mặt.

### 1b. `serve.py` — check Host, parse đúng IPv6

Trong `send_head`, trước khi serve:

```python
h = (self.headers.get("Host") or "").strip()
if h.startswith("[") and "]" in h:
    h = h[1:h.index("]")]           # [::1]:8080 → ::1
elif not h.startswith("["):
    h = h.rsplit(":", 1)[0]         # localhost:8080 → localhost
# Host dị dạng ("[", "[]", thiếu hẳn) → h lạ → rơi vào 403 bên dưới
if h not in ("localhost", "127.0.0.1", "::1") and not h.endswith(".localhost"):
    self.send_error(403, "Host không được phép"); return None
```

(Bản draft dùng `split(":")[0]` → `[::1]` thành `"["` — sai, fix.)

Windows không cần đổi: `serve.ps1` prefix `http://localhost:8080/` →
http.sys reject Host lạ ở kernel. Ghi parity note vào test.

### 1c. ext-bridge — race + cap

```python
with ext_lock:
    s = ext_sock
    next_id[0] += 1
    rid = next_id[0]
# ws_recv: n > MAX_WS_MSG (64MB) → raise ConnectionError
# — cap CẢ tổng tích luỹ: len(msg) + n > MAX_WS_MSG → raise, nếu không
# kẻ xấu gửi nhiều continuation frame nhỏ vẫn phình RAM vô hạn
```

### 1d. Extension — token rác không được persist

Hiện `onMessageExternal` ghi `chrome.storage` trước khi chứng minh
token đúng → trang localhost lạ đẩy token rác vào → extension kẹt
reconnect sai mãi cho tới khi portal pair lại. Sửa: token mới chỉ
`chrome.storage.local.set` **sau khi `ws.onopen` với token đó** —
thất bại thì giữ token cũ, badge báo `!`.

## Test bổ sung (tools/test-bridges.py)

| # | Case | Kỳ vọng |
|---|------|---------|
| 19 | serve.py `GET /web/index.html` `Host: evil.example` | 403 |
| 20 | serve.py `Host: [::1]:8080` (nếu bind v6) / `localhost:8080` | 200 |
| 21 | static: `start.sh` + `chat-terminal.ps1` + `launcher.py` đều launch ttyd qua `term-gate` và có `-a` | có cả 3 |
| 22 | static: `ext-bridge.py` có `MAX_WS_MSG`; `next_id` tăng dưới `ext_lock` | có |
| (tay) | `?arg=` đúng → vào não; sai/vắng → prompt → sai mã → exit | — |

(Đã renumber: test-bridges.py hiện chiếm tới case 18 — draft đầu đánh
trùng 17–20.)

## Lưu ý

- `term-gate.sh` phải executable (`chmod +x`) và được git add —
  `.gitignore` có `*.tmp` không đụng nó.
- `read -t` không có trên mọi `sh` POSIX — script chạy bởi `/bin/sh`:
  trên macOS `/bin/sh` là bash 3.2 có `-t`; Windows dùng `set /p`
  (không timeout — chấp nhận, kẻ lạ chỉ treo kết nối của chính nó).
