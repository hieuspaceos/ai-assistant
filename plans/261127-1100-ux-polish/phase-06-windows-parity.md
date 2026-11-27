# Phase 06 — Windows parity: chọn folder bằng hộp thoại + mở Explorer

## Lý do

Định hướng B2C là **Windows trước**, nhưng hai tính năng UX nhỏ nhất mà
quan trọng nhất hiện là **macOS-only**:

| Endpoint | macOS | Windows |
|---|---|---|
| `/api/pick-folder` | osascript `choose folder` → nút "Chọn bằng cách duyệt…" hiện | probe trả `supported:false` → nút ẩn → **học viên phải gõ path tay** (đúng điểm F-005 từng vá — chỉ vá trên Mac) |
| `/api/reveal` | `open -R` chọn sẵn file trong Finder | trả `{"err":"không hỗ trợ"}` — walkthrough nút "Mở folder" chết êm, phase-05 reveal-chip cũng vô dụng trên Windows |

Gõ path tay là rào cản thật với người không biết `~`/`C:\` là gì —
onboarding có cả bước folder quyền nên đây là màn first-run.

## Thay đổi `tools/chat-bridge.py`

### `/api/pick-folder` — Windows + Linux

```python
def _pick_folder_win():
    # PowerShell FolderBrowserDialog — không cần tkinter (PyInstaller
    # kéo tk nặng). new-shell → dialog thuộc process con, code wait
    # + parse stdout 1 dòng path. Timeout 120s chống dialog mồ côi.
    out = subprocess.run(
        ["powershell", "-NoProfile", "-STA", "-Command",
         "Add-Type -AssemblyName System.Windows.Forms;"
         "$d=New-Object System.Windows.Forms.FolderBrowserDialog;"
         "if($d.ShowDialog() -eq 'OK'){$d.SelectedPath}"],
        capture_output=True, text=True, timeout=120)
    return out.stdout.strip() or None
```

- `-STA` bắt buộc cho WinForms dialog.
- Linux: `zenity --file-selection --directory` nếu có; không →
  `supported:false` (fallback ô gõ tay như hiện).
- `_g_pick_folder_probe`: `supported = darwin(osascript) or
  windows(powershell) or linux(zenity)` — probe đã có sẵn shape này.
- Vẫn `_pick_folder_lock` + anti-oracle y nguyên (dialog chỉ trả path,
  không tự hỏi ở đâu — chọn vẫn do NGƯỜI bấm trong hộp OS).

### `/api/reveal` — explorer.exe /select

```python
if sys.platform == "darwin":
    subprocess.Popen(["open", "-R", p], ...)
elif sys.platform == "win32":
    # explorer /select, = chọn sẵn item (parity `open -R`), không
    # thực thi file. Folder thì mở luôn folder đó.
    if os.path.isfile(p):
        subprocess.Popen(["explorer", "/select,", p])
    else:
        subprocess.Popen(["explorer", p])
else:
    # Linux: xdg-open folder chứa — không có "select" chuẩn
    subprocess.Popen(["xdg-open", p if os.path.isdir(p) else
                     os.path.dirname(p)])
```

- Giữ nguyên guard: chỉ dưới `~`, không `.devin`, không `path_sensitive`.
- `explorer /select,` trả exit code 1 kể cả khi thành công (quirk đã
  biết của explorer) → dùng `Popen` không check return code.

## Cross-ref — KHÔNG làm lại việc của plan khác

- **`chat-bridge.ps1` thiếu 5 endpoint** (`/api/bots`, `/api/bot`,
  bot-import×2, `/api/install-brain`) → onboarding "cài não 1-click"
  chết ngầm trên Windows first-run qua đường `start.bat`. Đã là F5 của
  `plans/261127-0827-audit-6-fix` phase 05 — theo dõi ở đó; phase này
  chỉ vá `.py` (đường `troly.exe` packaged). Nếu định hướng là phát
  exe cho B2C thì .ps1 chỉ còn đường dev.
- Dialog xin phép native (osascript) cũng macOS-only — trên Windows
  mọi xin phép đi qua **card trong chat**, vốn là đường an toàn hơn
  (không forge được nút). Ghi nhận là divergent-by-design, không vá.

## Bẫy đã biết

- `explorer` spawn từ service/hidden context vẫn mở cửa sổ trên
  desktop user — bridge chạy trong session user nên ok (liên quan
  Session Isolation ở silent-worker phase-02).
- FolderBrowserDialog trong PowerShell hidden-window: dialog con
  không tự raise → thêm `-WindowStyle Normal` hoặc `TopMost` nếu
  thực tế bị chìm sau browser — kiểm trên VM Win11.
- Path trả về có `\` + khoảng trắng (OneDrive "Documents - Cty") →
  strip + validate `isdir` trước khi ghi permissions (đã có flow
  `/api/permissions`).

## Test

- VM Win11: onboarding bước folder → nút "Chọn bằng cách duyệt…"
  hiện → chọn Downloads → path đúng vào list; cancel dialog → không
  lỗi, ô gõ tay vẫn hoạt động.
- Walkthrough nút "Mở folder" trên Windows → Explorer mở đúng file
  chọn sẵn; path ngoài `~` / `.devin` / sensitive → 403 như cũ.
- `test-bridges.py`: probe `supported:true` trên Windows; reveal
  path dính `..`/`C:\Windows` → từ chối.
