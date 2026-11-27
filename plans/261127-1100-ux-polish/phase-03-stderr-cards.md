# Phase 03 — stderr của não → card lỗi tiếng Việt + im lặng trên Windows

## Lý do

`AcpClient` spawn não với `stderr=subprocess.DEVNULL`. Khi não sống
sai (hết phiên OAuth, config hỏng, crash khởi động), dấu vết duy nhất
văng vào hư không — UI chỉ thấy "não chết", học viên không biết làm
gì. Hai việc cùng một chỗ chạm: **đọc được stderr** + **hiển thị nó
bằng lời thường kèm nút xử lý**.

## Thay đổi `tools/chat-bridge.py`

### 1. Capture stderr thay vì vứt

```python
self.proc = subprocess.Popen(
    _sandbox_wrap([...]),
    cwd=CWD, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
    stderr=subprocess.PIPE, text=True, bufsize=1,
    env=benv,
    **_no_window_flags())          # Windows: CREATE_NO_WINDOW
```

- Thread `_stderr_reader` daemon đọc từng dòng → append
  `.logs/brain-stderr.log` (`rotate_logs` đã quét mọi `*.log`
  trong `.logs/` — không cần thêm pattern gì).
- **Không** đưa stderr vào `chat-history.jsonl` / broadcast thô —
  stderr có thể chứa token, path, stack trace. Chỉ card đã dịch đi
  lên UI.

### 2. Bảng dịch lỗi → card

| Dấu hiệu trong stderr/exit (regex, case-insensitive) | Card tiếng Việt | Nút trên card |
|---|---|---|
| `unauthorized`, `401`, `token expired`, `login required`, `oauth` | "Phiên đăng nhập của não đã hết — đăng nhập lại giúp mình nhé" | **"Đăng nhập lại"** → endpoint login có sẵn (mở terminal OAuth như hiện tại; phase 04 nâng cấp) |
| `ENOENT`/Popen `OSError` (đã có) | "Não chưa cài" | Link Cài đặt đổi não — giữ nguyên |
| Process exit != 0 ngay sau spawn + stderr rỗng | "Não vừa tắt ngay khi mở — mình thử lại được, hoặc bạn đổi não khác trong Cài đặt" | "Thử lại" → `spawn_brain` |
| stderr có `rate limit`, `quota`, `insufficient` | "Não đang bị giới hạn lượt dùng — chờ một lát hoặc đổi não khác" | — |

- Match trên **cửa sổ gộp** ~4KB stderr gần nhất khi process chết /
  khi stdout đóng bất thường (đã có hook `_reader` báo UI khi stdout
  đóng — nối dịch lỗi vào đúng chỗ đó).
- Dedup: cùng loại card trong 60s chỉ hiện một lần (não crash-loop
  qua watchdog spawn → không spam chat).

### 3. Im lặng trên Windows

```python
def _no_window_flags():
    if platform.system() != "Windows":
        return {}
    # không cho con console-subsystem (devin.exe...) pop cửa sổ cmd
    si = subprocess.STARTUPINFO(); si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    return {"creationflags": subprocess.CREATE_NO_WINDOW,
            "startupinfo": si}
```

- Áp cho cả não spawn lẫn `powershell`/`osascript` phụ nếu có.
- `troly.spec`: cân nhắc `console=False` cho app packaged — **nhưng**
  phải kiểm trước `.logs/` đã ghi đủ khi exe crash sớm (boot-fail
  không console = không thấy gì). Nếu thiếu đường xem lỗi → giữ
  `console=True`, ghi decision. Kiểm trên VM Win11.

## Bẫy đã biết

- stderr không phải UTF-8 thuần → `errors="replace"`.
- Pipe đầy mà không ai đọc → con treo: thread reader phải luôn sống
  ngay sau Popen, kể cả khi handshake ACP fail.
- Não in stack trace có prompt token → chỉ ghi file log, không parse
  lung tung — bảng regex là allowlist dấu hiệu, không phải forward.

## Test

- `test-bridges.py`: fakebrain exit 1 in "Error: unauthorized" → card
  đúng loại `auth`; crash-loop → 1 card/60s.
- `.logs/brain-stderr.log` có nội dung, không lọt vào
  `chat-history.jsonl` (grep assert).
- Win11 VM: spawn não → `Get-Process` không thấy console window mới;
  packaged exe boot fail → `.logs` đủ để debug.
