# PLAN — ai-assistant: từ kit khoá học → bàn làm việc AI cá nhân

Mục tiêu cuối: mỗi học viên copy folder về máy, bấm `start.bat`, phỏng vấn → có khoá học riêng + trợ lý làm việc thật với app/file của họ.

## Phase 0 — Nền tảng quyền & kết nối ✅ ĐÃ XONG (2025-11; chờ test Windows)

Đã hiện thực (schema hơi khác bản nháp): `my-course/permissions.json` +
`my-course/connections.json`; bridge endpoints `/api/permissions`, `/api/remove-permission`,
`/api/connections`, `/api/remove-connection`, `/api/check-connection` (probe http/path/mcp/wp/tabs/zalo-oa);
portal gom 2 mục quyền/kết nối vào panel **Cài đặt** (nút ⚙ cuối sidebar —
sidebar chỉ còn Bài học + Công thức nhanh) + chip trạng thái extension trên
header; AGENTS.md có rule kiểm tra quyền trước khi đụng folder lạ. Secret không lưu trong
connections.json — đúng như thiết kế dưới đây.

Nháp thiết kế gốc:

1. **`permissions.json` — phạm vi folder**
   - Schema: `{ "folders": [{"path": "...", "access": "read|read-write", "note": "..."}] }`
   - Bridge: `GET/POST/DELETE /api/permissions` (port cả `.py` lẫn `.ps1`)
   - Portal: mục "Folder trợ lý được đọc" trong sidebar (thêm/gỡ)
   - Skill `phong-van` + AGENTS rules: agent chỉ đụng folder trong `permissions.json` + `my-course/`; khi cần folder mới → hỏi trong chat → đồng ý thì ghi vào `permissions.json`
   - Xác nhận xoá/ghi file vẫn qua permission card ACP (lớp chặn thứ hai)

2. **`connections.json` — trạng thái kết nối app**
   - Schema: `{ "apps": [{"id": "wordpress", "type": "rest_api", "status": "connected|not-connected", "probe": {...}}] }`
   - Bridge: `GET/POST /api/connections` + `POST /api/check-connection` (probe thật → trả kết quả đọc được)
   - Portal: section "Kết nối ứng dụng" — card per app: tên, loại đường đi (chữ thường), trạng thái, nút Kết nối / Kiểm tra / Ngắt
   - Secret (app password, token) KHÔNG lưu trong file hiển thị portal — lưu `.devin/mcp_config.local.json` hoặc file `.env`-local gitignored; `connections.json` chỉ giữ trạng thái + metadata không nhạy cảm

## Phase 1 — Connector đầu tiên + Office file ✅ ĐÃ XONG (skill + probe; chờ test site thật)

3. **WordPress REST connector** ✅
   - probe `type:"wp"` trong connections.json — đọc `.devin/secrets.local.json`
     (gitignored) → GET `/wp-json/wp/v2/users/me` Basic auth; port `.py` + `.ps1`
   - Skill `/dang-bai` + `/seo-meta` (vi) `/publish-post` + `/seo-meta` (en)
   - Chưa test site thật — cần credentials của một wp site

4. **Skill file-Office** ✅
   - `/lam-excel` `/lam-word` (vi) `/work-excel` `/work-word` (en)
   - `requirements.txt` root (openpyxl + python-docx) + ghi chú trong SETUP Bước 5.5

5. **Extension "Trợ Lý AI" — web không có API (Zalo Web, wp-admin, Outlook web, trích xuất)** ✅
   - Extension MV3 riêng trong `extension/` — cài unpacked, kết nối WS về `ext-bridge` localhost
   - `tools/ext-bridge.py` (:7684): HTTP API cho agent (`/api/browser/*`) + WS cho extension
   - Agent gọi API qua terminal (curl/Invoke-RestMethod) — không cần MCP
   - Dùng browser THẬT của học viên — Zalo/Outlook/wp-admin đang login sẵn, không phải đăng nhập lại
   - Lệnh v1: `tabs / open / activate / close / snapshot / click / type / scroll / scrollables / query / read / screenshot / wait / reload`
   - Skill `/mo-web` (+ các skill dùng chung: `/doc-zalo` `/doc-outlook`); KHÔNG tự gửi tin/mail/đăng — luôn hỏi trước
   - Dự phòng: Playwright MCP nếu site phát hiện automation hoặc cần chạy nền

## Phase 2 — Mở rộng connector ✅ ĐÃ XONG (registry + skill; chờ credentials test)

6. **Google Sheets** ✅ — app `google-sheets` + skill `/cap-nhat-sheet` `/update-sheet`
   (đọc CSV trực tiếp, ghi qua MCP khi đã cài)
7. **Outlook** ✅ — app `outlook` + skill `/doc-outlook` `/read-outlook` (browser
   extension, dùng session đăng nhập sẵn — không cần Playwright/Graph cho v1)
8. **Canva** ✅ — app `canva` + skill `/xuat-canva` `/export-canva` (file-export flow,
   không automation editor)
9. **Zalo OA** ✅ — app `zalo-oa` + skill `/zalo-oa` (API chính thức, secrets trong
   secrets.local.json)

## Phase 3 — Khoá học & phỏng vấn thế hệ mới ✅ ĐÃ XONG

10. **`phong-van` v2** ✅ — Phase 1.5 "việc này bạn làm trên app/web nào?" → map
    connector → **lesson-00 "Kết nối"** tự sinh (cả vi lẫn en)
11. **Skill sinh ra tự kiểm tra `connections.json`** ✅ — mọi skill mới đều check
    connections trước + dẫn qua bài 0
12. **`hoc-bai` cập nhật** — chưa cần (UI portal chưa đổi layout video)

## Phase 4 — Đóng gói & kiểm chứng máy đích 🟡 (code xong, chờ test Windows)

13. **Test `start.bat` + `chat-bridge.ps1` trên Windows thật** — ❌ vẫn chờ máy Windows
14. **Offline fonts** ✅ — `web/vendor/fonts.css` + 10 woff2 (148KB), local trước Google
15. **Skill bank** — 🟡 một phần: `/gom-skill` đã có (gom skill học viên tự tạo về kho chung); còn thiếu bước "pack" ngược lại khi onboard
16. SETUP/README ✅ — onboarding, secrets, requirements, start.sh đã ghi

## Ranh giới giữ nguyên (không làm)

- CapCut: chỉ chuẩn bị nguyên liệu (srt, TTS, thumbnail) — không automation editor
- Gửi tin/mail/đăng bài ra ngoài: luôn xin xác nhận trước
- Elementor layout: browser automation chỉ khi không còn cách
- `devin --sandbox`: để sau — kiểm chứng Windows trước đã
