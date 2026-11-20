# Phase 5 — Đóng băng `.ps1` sau khi có `troly.exe`

## Mục tiêu

Khi `TroLyAI.exe` đã ship và verify trên Windows thật, đường
`.ps1`/`.bat` trở thành **dev-only**: ngừng gánh "mỗi tính năng viết
hai lần" (và lỗi parity như audit 261120-1635 từng bắt).

**Điều kiện mở khoá**: phase 1 xong + ít nhất một máy Windows chạy bản
CI end-to-end OK.

## File động

| File | Action | Việc |
|---|---|---|
| `tools/chat-bridge.ps1`, `tools/chat-terminal.ps1`, `tools/serve.ps1`, `start.bat` | modify | header comment đánh dấu "DEV ONLY — frozen, không nhận tính năng mới; đường chính là troly" |
| `tools/test-parity.py` | modify | diff `.py`↔`.ps1` hạ từ FAIL xuống WARN (in khuyến nghị, exit 0) |
| `docs/code-standards.md` | modify | mục "hai bản song song" → cập nhật: `.py` là source of truth; `.ps1` dev-only frozen |
| `docs/system-architecture.md` | modify | ghi đường chạy production = troly child roles; `.ps1` là dev path |
| `SETUP.md` | modify | phần thủ công Windows rút gọn còn trỏ `TroLyAI.exe`; mục `.bat`/ps1 chuyển xuống dev note |
| `PLAN.md` | modify | gỡ mục "chờ test Windows" nếu đã verify |

## Chi tiết

### Header frozen (mẫu, dùng chung cho 4 file)

```powershell
# DEV ONLY — frozen. Duong chinh cho hoc vien la troly.exe (launcher.py).
# File nay con de debug tren Windows khi chua co binary; tinh nang moi
# KHONG port vao day.
```

(`start.bat` ghi chú tương tự bằng `rem`.)

### `test-parity.py` → warn-only

- In danh sách endpoint lệch như hiện tại nhưng exit 0 kèm dòng
  "`.ps1` đã frozen — diff này chỉ để tham khảo".
- Giữ file để ai port tay tính năng cũ còn đối chiếu được.

### Docs

- `code-standards.md`: sửa bullet "Hai bản song song khi cần OS" →
  "Production chạy một đường `launcher.py` (PyInstaller). `.ps1`/`.bat`
  là dev path frozen — tính năng mới chỉ viết trong `.py`."
- `system-architecture.md`: bản đồ process chú thích troly là đường
  chính; `start.bat`+ps1 là dev fallback.
- `SETUP.md`: mục Windows chỉ còn "tải TroLyAI.exe → mở"; khối
  `start.bat` chuyển thành "cho dev / khi chưa có binary".

## Acceptance

- Một tính năng mới vào `chat-bridge.py` không buộc port `.ps1` —
  `test-parity.py` chỉ warn
- SETUP trên Windows đọc một đường duy nhất (exe)
- File `.ps1` vẫn chạy được như cũ cho dev (frozen ≠ xoá)

## Rủi ro

- Người Windows đang dùng `start.bat` cũ → file vẫn tồn tại và chạy
  được; không xoá nên không ai bị vỡ setup đang sống.
- Audit sau này quên frozen → comment header + docs nhắc lại.
