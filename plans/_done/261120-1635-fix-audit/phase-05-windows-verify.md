# Phase 5 — Kiểm chứng trên máy Windows thật (manual)

## Mục tiêu

Windows là nền tảng chính nhưng `PLAN.md` ghi "chờ test Windows" ở cả
Phase 0 lẫn Phase 4 — toàn bộ con đường `start.bat` + `chat-bridge.ps1` +
`chat-terminal.ps1` chưa chạy thật lần nào. Phase này là checklist tay
chạy trên một máy Windows (hoặc VM), ghi kết quả vào runbook.

**Không làm được từ macOS** — phase này luôn pending tới khi có máy.

## Điều kiện cần

- Một máy Windows 10/11 (hoặc VM Parallels/UTM) có quyền cài phần mềm.
- File `TroLyAI.exe` từ CI (plan `261120-1900-ship-learner` phase 1) —
  **đường chính, test trước**. Con đường `start.bat`+`.ps1` test sau
  (sắp frozen theo ship-learner phase 5 — chỉ cần xác nhận chạy được
  như cũ, không phải verify đầy đủ).
- *(Audit 261120: checklist này và verify của ship-learner phase 1 là
  một — gộp chạy một lượt trên cùng máy, mục 1-12 dưới đây áp cho
  troly.exe; mục .ps1 chỉ giữ phần smoke.)*

## Checklist

| # | Bước | Kỳ vọng |
|---|---|---|
| 1 | `start.bat` double-click | 4 cửa sổ nền mở (portal, chat, terminal, browser); browser hiện portal |
| 2 | Onboarding lần đầu | chọn ngôn ngữ → tên → não → folder → app → xong vào portal |
| 3 | Tab Chat gõ `/phong-van` | trợ lý trả lời (não ACP qua `.ps1` hoạt động) |
| 4 | Portal ⚙ Cài đặt → thêm folder quyền | `permissions.json` ghi được (test Expand-Path Windows `C:\...`) |
| 5 | Clone một trang nhỏ → sửa trong clone-view → "Lưu lại trang" | **save-page hoạt động** (đây là bug vừa vá ở phase 1) + `.bak` xuất hiện |
| 6 | Extension load unpacked → auto-pair | icon ON xanh, `/api/browser/status` connected |
| 7 | `/doc-zalo` hoặc action `tabs` qua chat | ext-bridge trả danh sách tab |
| 8 | Chế độ Terminal | ttyd hiện CLI não (nếu cài được ttyd qua winget) |
| 9 | Đổi não trong ⚙ | bridge restart agent không cần chạy lại start |
| 10 | `py tools\test-bridges.py` + `test-parity.py` + `test-packs.py` | test từ phase 3 xanh trên Windows |
| 11 | Skill Excel (`/lam-excel`) | `py -m pip install -r requirements.txt` + skill chạy được |
| 12 | Tắt/mở lại `start.bat` | lên lại đủ, token không đổi, portal vào thẳng |

## Ghi kết quả

- Mỗi mục FAIL → mở issue riêng hoặc vá ngay nếu nhỏ; ghi vào
  `docs/troubleshooting-runbook.md` mục "Windows".
- Xong → sửa `PLAN.md`: Phase 0 & 4 gỡ "chờ test Windows" → đánh dấu đã
  kiểm chứng kèm ngày.

## Rủi ro

- PowerShell 5.1 (mặc định Windows) khác pwsh 7 — `chat-bridge.ps1` phải
  chạy trên 5.1; nếu dev test bằng pwsh 7 mà bỏ qua 5.1 sẽ sót lỗi.
- Windows Defender/SmartScreen chặn `start.bat` hoặc `TroLyAI.exe` — ghi
  lại thông báo, quyết định có cần ký code không (đã note trong plan
  bridge-auth: chấp nhận trong pilot).
- Path Unicode/space trong username Windows (`C:\Users\Nguyễn Văn`) —
  test case riêng nếu có thể.
