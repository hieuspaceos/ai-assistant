# ai-assistant — System Architecture

**Bản chất:** không có backend tập trung. Hệ thống là 4 process local do
`start.sh`/`start.bat` dựng lên + một MV3 extension trong trình duyệt
thật của học viên + Devin CLI làm não.

## Architecture Overview

```
+---------------------------------------------------------------+
|                    Máy học viên (local only)                   |
|                                                               |
|   Trình duyệt thật (Chrome/Brave/Edge)                        |
|   +-- Portal tab  http://localhost:8080/web/                  |
|   |     |                                                     |
|   |     +--> Chat mode   POST :7682/api/prompt  (chat-bridge) |
|   |     +--> Term mode   ws    :7681            (ttyd+devin)  |
|   |     +--> Static      GET   :8080/...        (serve.py)    |
|   |                                                           |
|   +-- Tab web thường (Zalo, Outlook, site bất kỳ)             |
|         ^                                                     |
|         |  MV3 extension "Trợ Lý AI"                          |
|         |  ws://localhost:7684/ws/ext                         |
|         v                                                     |
|   ext-bridge :7684  <--- POST /api/browser {"action":...} ---+|
|   (tools/ext-bridge.py)                                      ||
|                                                              ||
|   chat-bridge :7682  --->  devin acp  (Agent Client Protocol)||
|   (tools/chat-bridge.py)        |                            ||
|                                 v                            ||
|                            Devin CLI  <======================++
|                            (đọc .devin/skills, gọi API
|                             /api/browser để lái trình duyệt) |
|                                                               |
|   Đĩa: my-course/ (bài học, config, permissions, clone)       |
+---------------------------------------------------------------+
```

Vai trò: **Devin CLI = não** · portal = mặt hiển thị · chat-bridge = cổng
chat · ttyd = cổng terminal · ext-bridge + extension = cánh tay trên
trình duyệt · serve.py = file tĩnh.

## Các thành phần

### 1. Portal tĩnh — `tools/serve.py` / `serve.ps1` :8080
- **Mục đích:** phục vụ `web/` (portal), `my-course/` (bài học, file clone),
  `intro/`, `templates/` — mọi thứ hiển thị được trong browser.
- **Chặn dotfiles**: không phục vụ đường dẫn chứa `.devin`/`.git` (trong
  `.devin/` có secrets của học viên).
- Không build step — HTML/CSS/JS thuần.

### 2. chat-bridge — `tools/chat-bridge.py` / `.ps1` :7682
- **Mục đích:** chế độ Chat của portal — biến `devin acp` thành API tin
  nhắn cho `web/chat.html`.
- Gửi prompt vào session ACP, poll output, quản lý permissions/
  connections/config/secrets, lưu trang clone (`/api/save-page`).
- Sandbox ghi file: chỉ `.html` dưới `my-course/`; tự tạo `.bak` trước
  khi ghi đè. Chi tiết endpoint: `api-reference.md`.

### 3. ttyd — :7681 (tuỳ chọn)
- **Mục đích:** chế độ Terminal — `ttyd -p 7681 -W devin` nhúng CLI Devin
  thật vào portal. Windows dùng `tools/chat-terminal.ps1` (theme sáng,
  font lớn cho người mới).
- Thiếu ttyd thì portal vẫn chạy chế độ Chat bình thường.

### 4. ext-bridge — `tools/ext-bridge.py` :7684
- **Mục đích:** cầu nối hai chiều giữa agent và extension.
  - Agent → `POST /api/browser {"action":"...", ...}` → bridge forward
    qua WebSocket tới extension → extension thực thi trong browser →
    trả kết quả ngược lại.
  - Extension kết nối `ws://localhost:7684/ws/ext`, giữ 1 WS duy nhất.
- ~25 action: tab management, snapshot/click/type/scroll, `dom`,
  `styles` (computed style), `assets`, `css`, `screenshot`, nhóm `t*`
  (input THẬT qua CDP cho app chặn event giả — Zalo, Google Sheets).
- Danh sách đầy đủ: `api-reference.md` + docstring đầu `ext-bridge.py`.

### 5. Extension — `extension/` (MV3, "Trợ Lý AI")
- **background.js**: giữ WS tới bridge, nhận action, điều khiển tab
  (chrome.tabs/debugger), trả kết quả.
- **content.js**: chạy trong trang — snapshot cây phần tử, click/type/
  scroll, trích DOM/styles/assets/css.
- Chạy trong trình duyệt THẬT → thừa hưởng mọi phiên đăng nhập của học
  viên; đây là lý do đọc được Zalo/Outlook không cần mật khẩu.

### 6. Devin CLI
- `devin` (terminal mode) và `devin acp` (chat mode) — cùng một agent.
- Đọc `AGENTS.md` (persona + an toàn) và `.devin/skills/` (công thức).
- Gọi `POST :7684/api/browser` khi skill cần lái trình duyệt; gọi
  `POST :7682/api/save-page` khi viewer lưu trang clone.

## Luồng dữ liệu chính

| Luồng | Đường đi |
|---|---|
| Học viên chat | chat.html → :7682/api/prompt → devin acp → poll /api/poll → render |
| Agent đọc Zalo | agent → :7684/api/browser {snapshot} → WS → content.js → cây phần tử → agent |
| Clone trang | agent → open/dom/styles/css/assets/screenshot (7684) → ref-* trong clone-work/<site>/ → dựng .html → portal viewer |
| Viewer lưu trang | clone-view.html → :7682/api/save-page → .bak + ghi file |
| Onboarding | onboarding.html → :7682/api/setup (config, permissions, skill pack) |

## Điểm neo deployment

- Tất cả bind `127.0.0.1` — không lộ ra LAN.
- Không process nào tự khởi động lại — chết thì `start.sh`/`start.bat`
  chạy lại; health check ngay trong launcher (portal + chat-bridge).
- Log: `<root>/.logs/{portal,chat-bridge,ext-bridge,ttyd}.log`.
