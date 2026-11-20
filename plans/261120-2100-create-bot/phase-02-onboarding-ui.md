# Phase 2 — Onboarding gallery + portal bot UI

> **Status: ✅ DONE** — bước gallery sau stepName (7 dots, card theo
> nghề + badge need, pre-open "office", create+activate trong `finish`
> SAU setup để có `config.language`); chip bot trên header + dropdown
> (activate/deactivate/"Tạo trợ lý mới" → overlay gallery); `chat.html`
> chào bằng tên bot; `phong-van`/`interview` Phase 6 sinh bot. Lưu ý
> sai khác plan: create KHÔNG gọi ngay trong gallery (lang chưa ghi).
> Test: 28 xanh, parity warn-only đúng gate, packs xanh.

## Mục tiêu

Học viên nhìn thấy và chọn được "trợ lý theo nghề" ngay onboarding —
mỗi thẻ bot là một nhân viên có sẵn kỹ năng, kèm cảnh báo connection
cần nối. Portal có bot switcher + hiện persona đang làm việc.

## File động

| File | Action | Việc |
|---|---|---|
| `web/onboarding.html` | modify | bước mới sau chọn ngôn ngữ/tên: gallery template theo nghề + đặt tên/avatar |
| `web/app.js` + `web/index.html` | modify | header hiện chip bot active (avatar + tên); dropdown đổi bot / "Tạo bot mới" |
| `web/chat.html` | modify | hiện tên bot trong lời chào đầu phiên ("Hằng nghe đây — bạn cần gì?") — đọc `GET /api/bots` lấy `active` (bot.md là file cho agent, portal không đọc) |
| `web/styles.css` | modify | card gallery, chip persona, badge connection — theo design system hiện có |
| `.devin/skills/phong-van/SKILL.md` (+ bản en `interview`) | modify | cuối phỏng vấn: đề xuất tên/role → `POST /api/bot` create+activate thay vì chỉ sinh khoá học |
| `my-course/connections.json` (seed) | check | `needs` trong roles dùng đúng id thật (`trinh-duyet`, `zalo`, `google-sheets`, `outlook`, `wordpress`…) — đã map sẵn ở phase 1 |

## Chi tiết

### 2a. Bước "Chọn trợ lý của bạn" trong onboarding

Sau bước ngôn ngữ + tên, TRƯỚC bước chọn não (hoặc gộp thành một
màn): `GET /api/bots` → render card mỗi template:

```
┌──────────────────────┐
│ 📣 Trợ lý Marketing  │
│ "Đọc Zalo, nén ảnh,  │
│  đăng bài, sheet"    │
│ [doc-zalo] [nen-anh] │
│ [dang-bai] [mo-web]  │
│ Cần: 🌐trình duyệt ✓ │
│      💬Zalo ⚠ chưa nối │
│ Tên bot: [Hằng____]  │
└──────────────────────┘
```

- Badge connection: đọc `GET /api/connections`, map `needs` → status;
  `connected` → ✓ xanh, khác → ⚠ xám + tooltip "kết nối sau trong ⚙
  cũng được" (KHÔNG chặn chọn — onboarding không bắt nối ngay).
- "Bỏ qua — dùng trợ lý chung" luôn có sẵn dưới gallery.
- Bấm chọn → `POST /api/bot {create}` với `suggested_bot_name`
  (editable) → `activate` → chuyển bước tiếp.

### 2b. Bot switcher trong portal

- Header (cạnh chip não/extension): chip `avatar + tên` bot active;
  không có → chip "Trợ lý" mặc định.
- Dropdown: danh sách bot (radio chọn → `activate`), divider, "Tạo
  bot mới" → mở lại gallery template (component tái dùng, render vào
  modal) + "Nhập bot" (phase 3), "Trợ lý chung" (deactivate).
- Đổi bot → `POST /api/bot activate` → reload manifest (recipes đổi
  theo bot).

### 2c. `/phong-van` sinh bot

Skill phỏng vấn hiện sinh giáo trình + manifest. Thêm bước cuối:
dựa trên nghề học viên khai → chọn role template gần nhất (hoặc
role "custom" chỉ gồm skill phỏng vấn gợi ý) → đề xuất tên bot
(hỏi học viên: "đặt tên trợ lý là gì? gợi ý: Hằng") →
`POST /api/bot` create + activate. Câu chuyện thành:
"khoá học này dạy bạn dùng đúng trợ lý <tên> vừa tạo".

### 2d. i18n

Mọi chuỗi mới vào khối STR hiện có của từng trang (vi + en) — giọng
ELI10: "trợ lý", "người giúp việc"; KHÔNG dùng chữ "bot" trong UI
học viên (bot là tên gọi kỹ thuật — UI gọi "trợ lý").

## Acceptance

- Máy sạch: onboarding có bước gallery, chọn "Marketing" → portal
  header hiện "📣 Hằng", sidebar có recipes của bot, `.devin/skills/`
  có đủ skill role đó
- Chưa kết nối Zalo → badge ⚠ trên card nhưng vẫn chọn được
- Đổi sang "Trợ lý chung" → chip mất tên, `bot.md` xoá
- `/phong-van` chạy xong → bot mới active + hiện trên header
- Không chỗ nào trong UI học viên ghi "bot"

## Rủi ro

- Gallery render chậm vì `check-connection` probe từng app → dùng
  `status` đã cache trong `connections.json`, chỉ probe khi học viên
  bấm "kiểm tra lại".
- Onboarding thêm một bước = thêm rớt → cho phép skip một chạm, và
  role "office" gợi ý sẵn nếu không biết chọn gì.
