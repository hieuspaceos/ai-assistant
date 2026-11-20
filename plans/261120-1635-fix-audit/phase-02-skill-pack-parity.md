# Phase 2 — Đưa `clone-trang`/`trang-moi` vào skill-packs + bản English

## Mục tiêu

Hai skill headline chỉ tồn tại trong `.devin/skills/` (active dir của repo
này). `build.sh` + `launcher.py` chỉ bundle `skill-packs/` → học viên cài
`troly` mất `/clone-trang` (tính năng đầu bảng README) và `/trang-moi`.
Pack `en` thiếu hẳn bản clone → học viên English cũng mất.

## File động

| File | Action | Việc |
|---|---|---|
| `.devin/skill-packs/vi/clone-trang/SKILL.md` | create | copy từ `.devin/skills/clone-trang/` |
| `.devin/skill-packs/vi/trang-moi/SKILL.md` | create | copy từ `.devin/skills/trang-moi/` |
| `.devin/skill-packs/en/clone-page/SKILL.md` | create | bản English của clone-trang |
| `.devin/skill-packs/en/new-page/SKILL.md` | create | bản English của trang-moi |
| `docs/skills-system.md` | modify | liệt kê đủ skill trong 2 pack |
| `.devin/skills/` | giữ nguyên | active dir của repo này (vi) không đổi |

## Chi tiết

### 2a. vi pack

```bash
cp -r .devin/skills/clone-trang .devin/skill-packs/vi/
cp -r .devin/skills/trang-moi  .devin/skill-packs/vi/
```

Giữ nguyên nội dung — đây là "bản gốc" mà `/api/setup` copy cho học viên.

### 2b. en pack — dịch, không copy

Tên command en theo quy ước pack en hiện có (verb-noun, tiếng Anh):
`clone-trang` → `/clone-page`, `trang-moi` → `/new-page`. **Chốt lại tên
khi implement** nếu muốn khác (vd `clone-site`).

Nguyên tắc dịch (đúng AGENTS.md — "tên file, folder, key JSON luôn tiếng
Anh; lời dẫn theo ngôn ngữ"):

- `name:` frontmatter đổi thành tên en.
- Toàn bộ lời dẫn/giải thích/ví dụ prompt → English, giọng ELI10 giống
  các skill en hiện có (xem `skill-packs/en/open-web/SKILL.md` làm mẫu
  giọng).
- **Giữ nguyên** mọi contract kỹ thuật: marker `data-cs-ref`/`data-cs-page`/
  `data-cs-template`, đường `my-course/clone-work/<site>/`, tên file
  `ref-*`, endpoint `/api/browser`, `/api/save-page` — dịch sai marker là
  chết pipeline (R2).
- Giữ luật bản quyền: không mang chữ/ảnh/logo site nguồn sang bản giao.

`new-page` dịch từ `trang-moi` — skill này phụ thuộc marker do
`clone-page` tạo → hai file phải tham chiếu nhau đúng tên en.

### 2c. Doc

`docs/skills-system.md`: bảng danh sách skill mỗi pack phải có đủ 20 mục
(vi: 18 cũ + clone-trang + trang-moi; en: 18 cũ + clone-page + new-page)
— sửa luôn số liệu đang sai ("en 17 skill" → thực tế 18, sau phase này
là 20). Ghi rõ quy tắc: **skill mới sinh vào `.devin/skills/` mà muốn
phát cho học viên thì PHẢI copy vào cả 2 pack** — đây là quy trình chống
lỗi B (root cause chính là dòng "Sửa skill → sửa ở `.devin/skills/`"
trong doc này: vi pack trở thành bản cũ sau mỗi lần sửa).

### 2d. `manifest.json` recipes hardcode tiếng Việt (lỗi H)

Seed `my-course/manifest.json` list `/clone-trang`, `/nen-anh`… — học
viên chọn en vẫn thấy lệnh vi trong sidebar cho tới khi `/interview`
sinh lại manifest. Hai cách:

- **A (khuyến nghị)**: sau khi `/api/setup` copy pack, bridge tự sinh
  `recipes` từ frontmatter (`name` + `description`) của các SKILL.md
  vừa cài — một nguồn đúng, đúng ngôn ngữ, không cần file seed riêng.
  Implement ở CẢ `.py` lẫn `.ps1` (~15 dòng mỗi bên).
- **B (chấp nhận)**: để nguyên — `/interview` cuối phỏng vấn viết lại
  manifest anyway; chỉ lộ lỗi trong khoảng trước phỏng vấn. Ghi
  known-limitation vào doc.

Chọn A nếu effort cho phép; B là đáy chấp nhận được.

### 2e. Tại sao không sửa launcher để bundle `.devin/skills/`

`.devin/skills/` là *trạng thái* của máy đang chạy (chứa cả skill học viên
tự tạo), không phải payload. `/api/setup` đã có merge giữ skill tự tạo
khi cài pack. Bundle active dir sẽ trộn trạng thái dev vào bản phát —
không làm.

## Acceptance

- `diff -r .devin/skills/clone-trang .devin/skill-packs/vi/clone-trang` = rỗng.
- Cài mô phỏng: copy `skill-packs/vi` sang dir tạm → có đủ 20 skill.
- Bản en: `name:` đúng, không còn câu tiếng Việt ngoài ví dụ nội dung,
  mọi `data-cs-*`/endpoint nguyên vẹn.
- `/api/setup` en trên máy thật → `.devin/skills/` có `clone-page`+`new-page`.

## Rủi ro

- Dịch en sai marker/tên file kỹ thuật → review diff từng file sau khi viết.
- Sau này sửa skill vi quên sửa en → quy tắc ở 2c ghi trong doc; test
  `test-packs.py` (phase 3) chỉ bắt được skill THIẾU, không bắt được skill
  en lệch nội dung — chấp nhận, note trong doc.
