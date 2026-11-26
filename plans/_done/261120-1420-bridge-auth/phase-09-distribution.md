# Phase 9 — Distribution: extension store + brain auto-install + installer

## Mục tiêu

Xoá 2 blocker còn lại của "user không biết code tự cài": extension qua
Chrome Web Store (không dev-mode) + não tự cài từ onboarding. Installer
đóng gói là tuỳ chọn vì phase 8 đã cho "1 file chạy".

## File động

| File | Action | Việc |
|---|---|---|
| `web/onboarding.html` | modify | bước não: `installHint` per preset + "Cài ngay"; bước extension: link store (fallback unpacked) |
| `tools/chat-bridge.py` | modify | `BRAIN_PRESETS` thêm `install` (url + hint vi/en) |
| `extension/` | modify | icon/screenshot/store listing assets + giảm quyền nếu review khó |
| `tools/installer.nsi` | create (tuỳ chọn) | NSIS: shortcut Start Menu/Desktop + chạy exe |
| `SETUP.md`, `README.md` | modify | hướng dẫn mới: tải file → chạy → onboarding |

## Chi tiết

### Extension → Chrome Web Store

- Việc cần: tài khoản dev ($5), listing vi+en, screenshot, privacy note
  ("mọi dữ liệu ở máy bạn").
- **Rủi ro review lớn nhất: quyền `debugger`** (CDP cho nhóm t*) — Google
  soi kỳ quyền này. Chuẩn bị: justification rõ trong listing; nếu bị từ
  chối → đường B2B là Chrome enterprise policy cài sẵn (cho fleet sales).
- Khi lên store: bước extension trong onboarding = mở link store; giữ
  hướng dẫn unpacked cho dev. Extension ID từ store KHÁC ID unpacked →
  `externally_connectable` + `key` vẫn đảm bảo auto-pair (ID store ổn định
  theo public key Google cấp — kiểm chứng ID thật khi submit, cập nhật
  EXT_ID trong onboarding).

### Brain auto-install trong onboarding

`BRAIN_PRESETS` thêm field `install` (không ghi vào brain.json):

```python
{"id":"devin", ..., "install": {
    "url": "https://cli.devin.ai (hoặc trang cài chính thức)",
    "hint": {"vi": "Bấm nút để mở trang cài của Devin — tải về, mở file, bấm Next",
             "en": "Opens Devin's install page — download, open, click Next"}}}
```

Onboarding bước não: preset `installed:false` → nút **"Cài não này"** mở
`install.url` + hướng dẫn theo `hint` + nút "Đã cài xong — kiểm tra lại"
(re-fetch `/api/brain` → installed lật). KHÔNG tự chạy lệnh cài hộ
(cài hãng thường cần quyền/UAC — dẫn đúng chỗ an toàn hơn chạy hộ).
`GET /api/brain` trả thêm `install` cho preset chưa cài.

### Installer (tuỳ chọn — NSIS)

Vì `troly.exe` đã self-contained + self-install payload, installer chỉ cần:
copy exe vào `%LOCALAPPDATA%\TroLyAI`, tạo shortcut Start Menu/Desktop,
tuỳ chọn "chạy cùng Windows". Làm SAU khi có pilot feedback — file exe
kép vẫn xài được ngay.

### Update path (đơn giản, đủ dùng)

- `VERSION` trong binary vs `~/TroLyAI/VERSION` → phase 8 đã cho update-đè-code.
- Phát hành = phát exe mới. Portal kiểm `version` trong `/api/health`,
  settings hiện số version; muốn "có bản mới" thì so với URL release
  (để phase sau, không bắt buộc).

## Acceptance

- Onboarding: preset chưa cài hiện nút "Cài não này" mở đúng trang hãng
- "Kiểm tra lại" sau khi cài → installed:true, chọn được
- Extension trên store (hoặc chuẩn bị xong hồ sơ submit nếu review chậm)
- `troly.exe` double-click trên máy Windows sạch → portal mở

## Rủi ro

- Review store kéo dài/từ chối quyền debugger → fallback: enterprise
  policy (B2B) hoặc unpacked có hướng dẫn (giữ lối cũ)
- Trang cài CLI hãng thay đổi → `install.url` cập nhật theo release
