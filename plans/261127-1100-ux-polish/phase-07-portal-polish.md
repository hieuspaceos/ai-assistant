# Phase 07 — Đánh bóng portal: đổi ngôn ngữ sau cài, gửi tin khi busy, trang lỗi êm, gói nhật ký hỗ trợ

## Lý do

Phần nhỏ còn lại sau khi quét `web/` + `serve.py` + onboarding — không
cái nào đủ lớn cho phase riêng, gom một phase "vệ sinh".

## Danh sách

### 1. Đổi ngôn ngữ sau onboarding — Settings thiếu toggle

`config.language` chỉ set ở onboarding bước 1; chọn nhầm / nhà hai
người dùng hai thứ tiếng → không đường đổi. **Audit 27-11: `POST
/api/config` (`_h_config`) là WHITELIST — hiện chỉ nhận key
`terminal`, patch khác ăn 400 "không có key nào được phép"** → phải:

- Thêm `language` vào whitelist của `_h_config`, validate giá trị
  chỉ `vi`|`en` (giữ tinh thần whitelist — không mở patch tự do).
- Settings → dropdown "Ngôn ngữ / Language: Tiếng Việt | English" →
  POST `{language}` → `initI18n()` lại + reload iframe chat (chat.html
  đọc `/api/config` lúc load — reload frame là đủ).
- Rerun onboard giữ nguyên — chỉ đổi chuỗi hiển thị, không reset gì.

### 2. Gửi tin khi não đang busy — Enter bị nuốt êm

`sendBtn.disabled` trong lúc busy → gõ xong bấm Enter, `send()` return
sớm, chữ còn nguyên nhưng **không có dấu hiệu nào** nói "chưa gửi".
**Audit 27-11 — tương tác với phase-05**: sau nút Dừng, nút không còn
`disabled` mà là `dataset.mode='stop'` → check "đang busy" trong
`send()` phải đổi từ `sendBtn.disabled` sang đọc mode (hoặc biến
busy riêng), nếu không Enter lúc busy đi thẳng vào `send()` và vẫn
bị nuốt êm.
Hai hành vi cùng lúc:

- `send()` check `res.ok`: bridge 409 (tab khác đang chạy) → đọc
  `err` từ body → `addErr` thay vì im lặng chờ event không tới.
- Cho phép **xếp 1 tin**: gửi lúc busy → tin nằm chip "⏳ Sẽ gửi khi
  trợ lý xong việc — bấm để huỷ" → event `done` tự POST. Không xếp
  tin thứ hai (chỉnh chip trước khi gửi). Xếp tin là ý định của user,
  không phải agent tự spam — decision-log 427 chỉ cấm queue phía
  bridge không báo, queue ở UI có báo rõ nên hợp tinh thần đó.

### 3. Trang lỗi thô → trang êm tiếng Việt

`serve.py` `send_error` default in "Error response / Error code: 404"
tiếng Anh trần — F-017 từng gặp với bài học 404. Override:

- `error_page(lang)` trả HTML tối giản theo config.language:
  "Không thấy trang này — có thể bài đã xoá hoặc đường dẫn cũ. Bấm
  về trang chính" + link `/web/`.
- Áp cho 404/403/500 của portal (KHÔNG đụng API JSON của bridge —
  đó là domain khác).

### 4. "Gói nhật ký hỗ trợ" trong Settings

B2C báo lỗi = "em chụp màn hình gửi anh". Cho thêm đường chuẩn:

- Settings → nút **"Gói nhật ký lỗi"** → `POST /api/support-bundle`
  → zip `.logs/` (trừ file >5MB, trừ **`chat-history*.jsonl`** —
  nội dung trò chuyện riêng tư không đi theo file gửi người khác)
  + `workspace/config.json` (đã lọc secrets — KHÔNG kèm `.devin/`,
  `bridge.token`, secrets) ra `troly-logs-<date>.zip` → reveal file
  đó (phase 06 làm reveal chạy được trên Windows).
- **Đích lưu trên Windows**: `~/Desktop` có thể KHÔNG tồn tại khi
  OneDrive redirect Desktop (`~/OneDrive/Desktop`) — thử lần lượt
  `~/Desktop` → `~/OneDrive/Desktop` → fallback `~/Downloads`
  (không nhận đích từ client — chống oracle).
- Card confirm trước: "nhật ký có thể chứa tên file bạn đã xử lý —
  chỉ gửi cho người bạn tin".
- `test-gates.py`: POST + token; path cố định Desktop — không nhận
  đích từ client (không oracle).

### 5. (Ghi nhận — quyết định chủ, không code trong phase này)

**Update 1-chạm cho máy cá nhân.** Hiện banner chỉ link GitHub
releases → tải exe tay thay file. `update.py` + launcher đã có cơ chế
staged update cho fleet — có thể tái dùng: banner → `POST /api/update`
tải release signed → stage → "mở lại app là xong". Phạm vi + rủi ro
ký/tải riêng → tách decision, không gộp plan này.

## Bẫy đã biết

- Đổi ngôn ngữ giữa phiên: `chat.html` trong iframe không tự reload
  → parent phải `chatFrame.src` reload (giữ token qua localStorage,
  chat tự nối lại); STR trong chat.html đọc lại từ `/api/config`.
- Queue-1-tin: huỷ queue khi user bấm "Việc mới" (phase 02) hoặc
  bridge chết — tin xếp không được bay vào session mới lặng lẽ.
- Support-bundle: zip trong `workspace/` (allow-write) xong copy ra
  Desktop — Desktop nằm ngoài permissions → đích cố định là `~/Desktop`
  vẫn hợp lệ vì endpoint tự quyết, không theo input client.

## Test

- Đổi `en`→`vi` trong Settings → portal + chat đổi chữ ngay, không
  restart.
- Busy → gõ tin + Enter → chip "⏳ sẽ gửi" → done → tin tự đi; bấm
  huỷ → không gửi; tab 2 prompt → 409 → err hiện không treo.
- Mở `/workspace/khong-co.html` → trang lỗi êm, link về portal.
- Support-bundle → zip trên Desktop, mở ra không chứa `bridge.token`
  hay secrets (grep assert).
