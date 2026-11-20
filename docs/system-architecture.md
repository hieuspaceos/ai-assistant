# ai-assistant — System Architecture

**Bản chất:** không có backend tập trung. Hệ thống là 4 process local do
`start.sh`/`start.bat` dựng lên + một MV3 extension trong trình duyệt
thật của học viên + một agent CLI nói chuẩn ACP làm não (mặc định Devin,
đổi được qua `brain.json`).

## Architecture Overview

```
+---------------------------------------------------------------+
|                    Máy học viên (local only)                   |
|                                                               |
|   Trình duyệt thật (Chrome/Brave/Edge)                        |
|   +-- Portal tab  http://localhost:8080/web/                  |
|   |     |                                                     |
|   |     +--> Chat mode   POST :7682/api/prompt  (chat-bridge) |
|   |     +--> Term mode   ws    :7681            (ttyd+não)    |
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
|   chat-bridge :7682  --->  não ACP  (Agent Client Protocol)  ||
|   (tools/chat-bridge.py)        |                            ||
|                                 v                            ||
|                            Agent CLI  <======================++
|                            (đọc .devin/skills, gọi API
|                             /api/browser để lái trình duyệt) |
|                                                               |
|   Đĩa: my-course/ (bài học, config, permissions, clone)       |
+---------------------------------------------------------------+
```

Vai trò: **agent CLI = não** (đổi được — xem mục 6) · portal = mặt hiển
thị · chat-bridge = cổng chat · ttyd = cổng terminal · ext-bridge +
extension = cánh tay trên trình duyệt · serve.py = file tĩnh.

## Các thành phần

### 1. Portal tĩnh — `tools/serve.py` / `serve.ps1` :8080
- **Mục đích:** phục vụ `web/` (portal), `my-course/` (bài học, file clone),
  `intro/`, `templates/` — mọi thứ hiển thị được trong browser.
- **Chặn dotfiles**: không phục vụ đường dẫn chứa `.devin`/`.git` (trong
  `.devin/` có secrets của học viên).
- **Host check** chống DNS rebinding: chỉ `localhost`/`127.0.0.1`/`[::1]`.
- **CSP `connect-src 'none'`** trên `.html` dưới `/my-course/`+`/intro/` —
  nội dung clone/bài học không exfil được ra net. Slide trong portal nhúng
  qua iframe `sandbox="allow-scripts"` (opaque origin).
- HTTP/1.1 keep-alive + `Range` (video bài học tua được); `/web/vendor/*`
  cache 1h.
- Không build step — HTML/CSS/JS thuần.

### 2. chat-bridge — `tools/chat-bridge.py` / `.ps1` :7682
- **Mục đích:** chế độ Chat của portal — spawn "não" (agent CLI nói ACP,
  JSON-RPC qua stdin/stdout) rồi biến nó thành API tin nhắn cho
  `web/chat.html`.
- Não nào chạy đọc từ `brain.json` ở gốc project; `GET /api/brain`
  liệt kê preset + cờ đã cài, `POST /api/brain` đổi não (ghi file +
  khởi động lại agent nóng, không cần chạy lại start).
- Agent chết/chưa cài: bridge không chết theo — báo lỗi về UI và tự
  thử bật lại ở prompt kế tiếp.
- Gửi prompt vào session ACP (`prompt_lock` — một lượt tại một thời
  điểm, tranh chấp → 409), long-poll output, quản lý permissions/
  connections/config/secrets, lưu trang clone (`/api/save-page`).
- `/api/respond` chỉ nhận `id` còn pending trong map (TTL 600s,
  one-shot) — không trả lời được câu hỏi của session cũ.
- Sandbox ghi file: chỉ `.html` dưới `my-course/`; tự tạo `.bak` trước
  khi ghi đè. Chi tiết endpoint: `api-reference.md`.

### 3. ttyd — :7681 (tuỳ chọn)
- **Mục đích:** chế độ Terminal — `ttyd -p 7681 -W -a <gate>` nhúng CLI
  thật vào portal; `<não>` = trường `terminal` trong `brain.json`.
  Windows dùng `tools/chat-terminal.ps1` (theme sáng, font lớn cho
  người mới).
- **term-gate** (`term-gate.sh`/`.cmd`) đứng giữa ttyd và não ở mọi
  đường spawn (start.sh, chat-terminal.ps1, launcher.py — bản đóng
  gói): ttyd `-a` truyền `?arg=<mã kết nối>` từ URL iframe, gate đòi
  đúng mã trong shell (sai 3 lần/timeout 90s → thoát) rồi mới `exec
  <não>` — ai mở được WS ttyd cũng chỉ gặp prompt mã, không chạm shell.
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

### 6. Não — agent CLI qua ACP (đổi được)
- Não là **bất kỳ agent CLI nào nói chuẩn ACP** — không gắn chết Devin.
  Cấu hình trong `brain.json` ở gốc: `{"id","label","cmd","args","terminal"}`
  — `cmd`+`args` là lệnh mở chế độ ACP, `terminal` là lệnh cho chế độ
  Terminal (ttyd).
- Preset có sẵn trong bridge (`GET /api/brain`): Devin `devin acp`,
  Gemini `gemini --acp`, OpenCode `opencode acp`, Goose `goose acp`
  (ACP native); Codex và Claude Code qua adapter `npx -y
  @agentclientprotocol/codex-acp` / `claude-agent-acp` (vẫn cần CLI
  gốc để đăng nhập). Onboarding có bước chọn não — chỉ preset "đã cài"
  mới chọn được, còn có ô nhập lệnh tự do cho não khác.
- Học viên dùng Devin: `devin` (terminal) và `devin acp` (chat) — cùng
  một agent.
- Agent đọc `AGENTS.md` (persona + an toàn) và `.devin/skills/` (công
  thức) — skill nằm trong file nên não nào đọc AGENTS.md cũng dùng được.
- **macOS: não chạy trong Seatbelt** — `tools/gen-sandbox.py` sinh
  `.devin/agent.sb` từ `permissions.json` rồi chat-bridge spawn qua
  `sandbox-exec -f`. Đọc = allow `/` trừ sibling bị deny-enumerate
  (quirk compiler Darwin: `process*` chỉ compile khi `file-read*` phủ
  `/`); ghi = whitelist CWD + folder `read-write`. `bridge.token`
  đọc-được-không-ghi; `secrets*.json` deny-read. Windows chưa có
  enforcement tương đương (`tools/setup-agent-user.ps1` là khung).
- Agent gọi `POST :7684/api/browser` khi skill cần lái trình duyệt; gọi
  `POST :7682/api/save-page` khi viewer lưu trang clone.

## Luồng dữ liệu chính

| Luồng | Đường đi |
|---|---|
| Học viên chat | chat.html → :7682/api/prompt → não ACP → long-poll /api/poll?wait= → render |
| Đổi não | onboarding/Cài đặt → :7682/api/brain → brain.json + restart agent |
| Agent đọc Zalo | agent → :7684/api/browser {snapshot} → WS → content.js → cây phần tử → agent |
| Clone trang | agent → open/dom/styles/css/assets/screenshot (7684) → ref-* trong clone-work/<site>/ → dựng .html → portal viewer |
| Viewer lưu trang | clone-view.html → :7682/api/save-page → .bak + ghi file |
| Onboarding | onboarding.html → :7682/api/setup (config, permissions, skill pack) |

## Điểm neo deployment

- Tất cả bind `127.0.0.1` — không lộ ra LAN.
- Không process nào tự khởi động lại — chết thì `start.sh`/`start.bat`
  chạy lại; health check ngay trong launcher (portal + chat-bridge).
- Log: `<root>/.logs/{portal,chat-bridge,ext-bridge,ttyd}.log`.
