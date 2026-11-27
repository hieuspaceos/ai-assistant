# Phase 01 — start.bat/start.sh tôn trọng `config.terminal`

## Lý do

`launcher.py` (đường đóng gói `troly.exe`) đã đúng: `terminal_enabled()`
đọc `workspace/config.json` → `terminal`, mặc định TẮT, không spawn
ttyd. Nhưng đường dev/zip (`start.bat`, `start.sh`) vẫn chạy như bản
cũ:

- `start.bat`: `where ttyd` → thiếu thì **`winget install tsl0922.ttyd`
  tự động** → spawn `chat-terminal.ps1` luôn.
- `start.sh`: `command -v ttyd` → có là spawn, không hỏi config.

Kết quả: máy mới cài qua `start.bat` vẫn bị kéo ttyd về + cửa sổ
PowerShell thứ hai, trong khi portal đã giấu nút Terminal (toggle TẮT)
→ dịch vụ chạy vô ích.

## Thay đổi

### `start.sh`

Trước block "--- 4. ttyd":

```bash
# Terminal trong portal là tuỳ chọn (Cài đặt → Hiện chế độ Terminal).
# Mặc định TẮT — đọc config giống launcher.py:terminal_enabled().
TERM_ON="$(python3 -c "import json;print(json.load(open('$ROOT/workspace/config.json')).get('terminal', False))" 2>/dev/null || echo False)"
if [ "$TERM_ON" = "True" ] && command -v ttyd >/dev/null 2>&1; then
  ttyd -p 7681 -i 127.0.0.1 -W -a -O sh tools/term-gate.sh >"$LOGDIR/ttyd.log" 2>&1 &
elif [ "$TERM_ON" = "True" ]; then
  echo "  [!] Terminal bat nhung chua co ttyd - cai: brew install ttyd"
fi
# TERM_ON != True → không nhắc gì: đó là trạng thái bình thường.
```

### `start.bat`

- Đọc `workspace/config.json` qua `read-brain.ps1`-style hoặc một
  one-liner PowerShell an toàn (config là file tin cậy — học viên tự
  sửa trong portal, nhưng vẫn parse qua `ConvertFrom-Json`, không
  `for /f` thô để tránh injection qua giá trị lạ).
- **Bỏ block `winget install ttyd` tự động.** Chỉ khi `terminal=true`
  mà thiếu ttyd → echo gợi ý cài tay. Cài đặt im lặng phần mềm ngoài
  ý muốn là vi phạm niềm tin, không chỉ là UX xấu.
- `terminal=true` + có ttyd → spawn `chat-terminal.ps1` như cũ.

### Parity

- `serve.ps1`/`chat-bridge.ps1` không đụng.
- `test-parity.py`: hai hành vi phải giống nhau giữa .bat/.sh — thêm
  case "config.terminal=false → không spawn", "true + thiếu ttyd →
  cảnh báo, vẫn boot".

## Edge cases

- `workspace/config.json` chưa tồn tại (máy mới) → default `false` —
  khớp onboarding (Terminal tắt cho tới khi bật trong Cài đặt).
- Người bật Terminal trong portal rồi `start.bat` lại → ttyd spawn
  bình thường.
- `warnCli` trong portal hiện nói "chạy lại start.bat" — sau phase
  này vẫn đúng (bật toggle → restart script → có ttyd).

## Test

- Tay: `config.terminal` false → `bash start.sh` → `lsof -i :7681`
  rỗng; đổi true → có ttyd.
- `test-bridges.py`/`test-parity.py` thêm case trên; chạy trên VM
  Win11 cho đường .bat.
