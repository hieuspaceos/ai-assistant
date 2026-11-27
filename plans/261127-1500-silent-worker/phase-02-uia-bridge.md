# Phase 02 — `uia-bridge` :7685 — "ext-bridge cho app native" (Windows + macOS)

## Lý do

Computer-use tầng OS là chỗ duy nhất còn chiếm chuột+màn hình. Cả hai OS
đều có sẵn "đường bấm nút không cần chuột" — vốn được làm ra cho trình
đọc màn hình của người khiếm thị:

- **Windows**: UI Automation (UIA) — `InvokePattern`, `ValuePattern`...
- **macOS**: Accessibility API (AX) — `AXPress`, `AXSetValue`...

`uia-bridge` là một file `tools/uia-bridge.py` duy nhất, bên trong chọn
backend theo `sys.platform`, expose **cùng một HTTP API** — agent không
cần biết đang chạy OS nào.

## Nút nào bấm nền được / không được

Câu hỏi "nút nào không bấm nền được" = "control nào OS không cho đường
API". Liệt kê cụ thể:

### Bấm nền ĐƯỢC (phủ ~80% app văn phòng)

| Loại | Ví dụ | Đường API |
|---|---|---|
| Nút thường, link, menu item | "Gửi", "Save", "OK" trong dialog | `InvokePattern.Invoke()` / `AXPress` |
| Checkbox, toggle, radio | tick "Nhớ mật khẩu" | `TogglePattern` / `AXSetValue(AXValue)` |
| Tab, item trong list/tree | chọn hội thoại, chọn sheet | `SelectionItemPattern` / `AXPress` |
| Dropdown mở/đóng | combobox chọn tỉnh | `ExpandCollapsePattern` |
| Ô nhập chữ | gõ tên, gõ số | `ValuePattern.SetValue` / `AXSetValue` |
| Cuộn item vào tầm nhìn | đưa item ẩn hiện ra | `ScrollItemPattern` |
| Slider | kéo âm lượng | `RangeValuePattern` |

### KHÔNG bấm nền được — đây là danh sách bạn hỏi

| Loại | Tại sao | Ví dụ cụ thể |
|---|---|---|
| **App vẽ UI bằng canvas/đồ hoạ riêng** | Toàn bộ màn hình là "một tờ giấy vẽ" — OS chỉ thấy 1 hình chữ nhật trống, không có nút nào bên trong để bấm | Timeline + preview của **CapCut**, canvas **Figma**, game, video editor nói chung |
| **Electron app không bật accessibility** | Electron mặc định chỉ expose cây control khi app gọi `app.setAccessibilitySupportEnabled(true)` hoặc nhận thấy screen reader | **Zalo desktop** — chưa chắc expose đủ; phải spike đo |
| **Java app chưa bật Java Access Bridge** | Swing/AWT không nói UIA trừ khi bridge bật | App kế toán Java cũ của một số công ty |
| **Flutter desktop** | Semantics tree tắt mặc định trên desktop | Vài app mới — spike sẽ biết |
| **Nút custom-drawn trong app Win32 cũ** | Chỉ report 1 khung lớn không có nút con, hoặc `DoDefaultAction` vẫn di chuột | Toolbar app xưa |
| **Thao tác KÉO-THẢ** | Không tồn tại "drag pattern" — kéo chỉ làm được bằng chuột trượt thật | Kéo file vào ô upload, kéo clip trong timeline |
| **Hover để lộ nút/menu ẩn** | Không có hover pattern — hover là của chuột | Nút chỉ hiện khi rê chuột lên item |
| **Chọn vùng/bôi chữ** | Text selection không qua pattern | Bôi đoạn văn trong preview |

Cơ chế xử lý khi gặp nhóm "không được": `uia-bridge` trả lỗi rõ
`{"ok":false,"err":"control chỉ bấm được bằng chuột thật","kind":"no_pattern"}`
→ agent báo học viên + quyết fallback computer-use (và nói trước
"mình cần cầm chuột 30 giây") — **không lén di chuột**.

## Thành phần

- `tools/uia-bridge.py` — HTTP `127.0.0.1:7685`, pattern y hệt
  `ext-bridge.py`: token `?token=`/`X-Bridge-Token` (đọc
  `.devin/bridge.token` / `$env:BRIDGE_TOKEN`), JSON `{action,...}` →
  `{ok,...}`. **Chỉ HTTP thuần** — không có client thứ hai như
  extension nên KHÔNG cần WebSocket/pending/sweep (audit A7); skeleton
  đơn giản hơn ext-bridge nhiều.
- Backend Windows: lib
  [`uiautomation`](https://github.com/yinkaisheng/Python-UIAutomation-for-Windows)
  — pure Python + comtypes, wrap UIAutomationCore.dll có sẵn trong
  Windows, không driver ngoài.
- Backend macOS: `pyobjc-framework-ApplicationServices` —
  `AXUIElementCreateApplication(pid)`, `AXUIElementCopyAttributeValue`,
  `AXUIElementPerformAction("AXPress")`, `AXUIElementSetAttributeValue`
  cho `AXValue`. **Lưu ý quyền**: app cần quyền Accessibility trong
  System Settings → Privacy (một lần, giống computer-use đang cần) —
  onboarding phải dẫn học viên cấp.
- Guard import theo platform; thiếu lib/OS lạ → skip khởi động, portal
  vẫn chạy bình thường (fail-soft).
- **Session Isolation (Windows)**: `uia-bridge` PHẢI chạy trong cùng
  phiên đăng nhập tương tác với app đích — UIA chỉ thấy cây control
  của desktop thuộc session mình. Process chạy ở Session 0 (Windows
  service, scheduled task SYSTEM, scheduled task "whether user is
  logged on or not") nhìn desktop ảo rỗng → `snapshot` trả tree trống
  dù app đang mở trước mắt user. Hệ quả:
  - Spawn từ `launcher.py`/`start.bat` trong session user (đúng như
    ext-bridge/chat-bridge hiện tại) là đủ — KHÔNG tách thành service.
  - Tuyến B2B chạy bridge dưới `troly-agent` (setup-agent-user.ps1)
    sẽ MÙ với app của user chính — nếu cần điều khiển app native trong
    mô hình đó phải đặt một helper mỏng trong phiên user chính; ghi
    vào docs/fleet.md khi tới, không làm trong phase này.
  - Self-check khi boot: `apps` trả rỗng trên Windows trong khi user
    đang có cửa sổ → log cảnh báo "có thể đang chạy sai session".
- Start: `launcher.py`/`start.bat`/`start.sh` spawn cùng ext-bridge.
- Package `troly.spec`: Windows thêm `uiautomation`+`comtypes`
  hiddenimports (comtypes gen runtime lúc import — test kỹ trong
  binary); macOS thêm `pyobjc-framework-ApplicationServices`.

## API — mirror shape ext-bridge, chung cho 2 OS

| Action | Tham số | Làm gì |
|---|---|---|
| `apps` | — | Liệt kê app đang chạy có cửa sổ (pid, name, title) |
| `attach` | `pid` hoặc `name` | Chọn app đích |
| `snapshot` | — | Cây control (depth ≤8, whitelist loại có nghĩa) → `e1,e2...` + name/role/rect |
| `click` | `ref` | Invoke/AXPress → Toggle/SelectionItem/ExpandCollapse theo role → hết cách → lỗi `no_pattern` |
| `type` | `ref`,`text` | SetValue/AXValue — không SetFocus, không SendKeys |
| `read` | `ref?` | Text của control hoặc cả tree ≤8000 chữ |
| `shot` | — | Chụp window không cần foreground — Win: `PrintWindow(PW_RENDERFULLCONTENT)`, fallback Graphics Capture; mac: `CGWindowListCreateImage` (cần quyền Screen Recording — onboarding dẫn cấp cùng lúc Accessibility) |
| `wait` | `ms` | Chờ |

## Whitelist app đợt đầu (từ spike 00d điền thật)

- **Windows**: Notepad, dialog Open/Save (comdlg), Explorer, Word/Excel
  (UIA tốt), Chrome/Edge native dialogs; Zalo desktop = chờ spike.
- **macOS**: Finder + dialog Open/Save (AX rất đầy đủ), Safari chrome,
  app Apple (Notes, Mail — AX chuẩn); Zalo macOS = chờ spike.

**Consent cho app ngoài whitelist** (audit A3): `attach`/`snapshot`/
`read` = đọc được nội dung UI của app — surface riêng tư tương đương
đọc folder ngoài `permissions.json`. Quy tắc:

- App trong whitelist hệ thống (dialog, Notepad/TextEdit, Office,
  Finder...) → attach tự do.
- App ngoài list → `attach` trả `{"ok":false,"kind":"need_consent"}`
  → agent hỏi học viên trong chat → được đồng ý thì ghi vào
  `workspace/permissions.json` một entry `{"type":"app","name":...}`
  (cùng "ngăn tủ được phép mở"), lần sau khỏi hỏi.
- Ghi luật vào AGENTS.md: app native = ngăn tủ — xin phép trước khi
  đọc/điều khiển.

## Test

- `test-bridges.py` nhánh `:7685`: Windows chạy trên VM UTM — attach
  Notepad → snapshot → type vào Edit → read ra đúng chữ; macOS chạy
  ngay máy dev — attach TextEdit → tương tự (TextEdit AX đầy đủ).
- `test-parity.py`: `uia-bridge` chỉ `.py` → ghi `PY_ONLY_OK` kèm lý do.
- Security: bind 127.0.0.1, token bắt buộc; dữ liệu từ `snapshot`/`read`
  thuộc "dữ liệu không phải lệnh" (luật AGENTS.md) — ghi chú trong
  skill.

## Môi trường dev/test của chủ

- Máy chính: macOS — dev + test backend AX trực tiếp.
- Máy ảo Windows 11 trên UTM — test backend UIA + extension/bridge trên
  Windows. Cần chạy portal+bridge trong VM (bộ cài `TroLyAI.exe` hoặc
  `start.bat` + python).
