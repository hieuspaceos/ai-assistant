# ai-assistant — Project Overview & Product Development Requirements

## Executive Summary

ai-assistant là **trợ lý AI làm việc thật trên máy học viên**: đọc
Zalo/Outlook, cập nhật Google Sheets, đăng WordPress, xử lý Excel/Word/ảnh,
và **clone một trang web thành trang của học viên** (`/clone-trang`).

Điểm khác biệt: nó là trợ lý duy nhất **tự dạy người dùng dùng nó** — lần
đầu chạy, hệ thống phỏng vấn về công việc thật → agent đóng gói **công cụ**
(skill `/command`) giải đúng pain của học viên → kèm **walkthrough tương
tác từng-bước** trong portal (mỗi bước làm được thật: gõ lệnh, duyệt quyền,
mở kết quả) + guide.md bản đọc → hiển thị qua portal web local có nhúng
chat/terminal.

## Business Context

**Đối tượng:** nhân viên văn phòng KHÔNG biết code — marketing, content,
SEO, design. Dùng Google Sheets, WordPress, Canva, CapCut hằng ngày nhưng
chưa mở terminal bao giờ.

**Nền tảng:** Windows là chính (`start.bat`, `tools/*.ps1`); macOS/Linux
chạy bằng `start.sh` + `tools/*.py`.

**Ngôn ngữ:** tiếng Việt + English — onboarding hỏi lần đầu, ghi vào
`workspace/config.json` → `language`. Skill đang dùng được cài từ
`.devin/skill-packs/<language>/`.

**Runtime:** Devin CLI (`devin`, `devin acp`) — agent chính là Devin,
portal/bridge chỉ là lớp hiển thị và điều khiển.

## Core Requirements

### 1. Onboarding một lần
Chọn ngôn ngữ → điền tên → chọn folder trợ lý được đọc → chọn app kết nối.
Ghi `config.json` + `permissions.json` + `connections.json`; cài skill pack
đúng ngôn ngữ (`/phong-van` cho vi, `/interview` cho en).

### 2. Sinh công cụ cá nhân (không phải giáo trình)
`/phong-van` → agent hỏi về công việc thật → với mỗi pain, đóng gói qua
`/tao-cong-cu`: skill `/command` (mới hoặc có sẵn) +
`workspace/tool-XX-*/` chứa `walkthrough.json` (modal từng-bước làm
thật trong portal — nút "▶ Dùng ngay") + `guide.md` (bản đọc) → cập
nhật `manifest.json` (`has_walkthrough: true`) → portal hiển thị.
KHÔNG sinh slide/video/bài tập — slide-builder/video-builder vẫn giữ
nhưng không được gọi mặc định.

### 3. Hai chế độ tương tác
- **Chat** (mặc định): bong bóng tin nhắn, markdown — qua `chat-bridge`
  :7682 → `devin acp`.
- **Terminal**: ttyd :7681 → `devin` CLI thật nhúng trong portal.

### 4. Trợ lý làm việc thật
Extension MV3 "Trợ Lý AI" điều khiển **trình duyệt thật** của học viên qua
`ext-bridge` :7684 — đọc trang đang đăng nhập (Zalo, Outlook, Sheets,
WordPress admin), bấm/gõ/chụp. Kỹ năng đóng gói thành skill trong
`.devin/skills/`.

### 5. Clone trang web (`/clone-trang` + `/trang-moi`)
Đo trên trang sống → dựng file `.html` giống khung nguồn (nội dung của
học viên, không mang bản quyền người khác) → mở trong `web/clone-view.html`
sửa tại chỗ → lưu về file. Chi tiết: `docs/clone-pipeline.md`.

## Non-goals

- **Không phải SaaS** — chạy hoàn toàn local trên máy học viên; không có
  tài khoản, không có server trung tâm, không telemetry.
- **Không thay thế Devin** — portal là vỏ hiển thị; mọi suy luận do agent.
- **Không clone backend** — bản clone chỉ tái hiện phần nhìn thấy; form,
  giỏ hàng, đăng nhập là khung giả lập.
- **Không dạy lý thuyết chung** — công cụ sinh ra từ nỗi đau thật học viên
  kể, không phải giáo trình có sẵn.

## Durable Constraints

- Agent là **lớp bảo vệ cuối** trước mọi hành động đụng file/secret —
  học viên không đọc được lệnh (xem `SECURITY.md`, `AGENTS.md`).
- File cho học viên chỉ nằm trong `workspace/` hoặc folder được cấp quyền
  trong `permissions.json`.
- Mọi file mới phải chạy được **không cần cài thêm** trên máy học viên
  (Python chuẩn, PowerShell thuần, HTML/CSS/JS không build step).
