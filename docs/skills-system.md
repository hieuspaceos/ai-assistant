# ai-assistant — Skills System

Skill = "cuốn sổ công thức": file `SKILL.md` viết sẵn quy trình cho một
việc lặp lại. Không có skill agent vẫn làm được — có skill thì kết quả
ổn định và nhanh hơn.

## Vị trí và vòng đời

```
.devin/skill-packs/vi/   20 skill tiếng Việt   (kho mẫu)
.devin/skill-packs/en/   20 skill English      (kho mẫu)
.devin/skill-packs/recipes/<lang>.json   recipes sidebar theo ngôn ngữ
        │ onboarding (/api/setup) copy đúng pack theo config.language
        │        + ghi recipes vào manifest.json
        ▼
.devin/skills/<tên>/SKILL.md   ← skill ACTIVE, agent đọc thư mục này
```

- **Sửa skill → sửa ở `.devin/skills/` rồi đồng bộ sang pack vi** —
  `test-packs.py` bắt buộc hai bản giống nhau, quên đồng bộ = test đỏ.
  Bản en là dịch thuật, không cần giống chữ với vi.
- **Skill mới muốn phát cho học viên → copy vào CẢ HAI pack.** Skill chỉ
  nằm ở `.devin/skills/` sẽ KHÔNG có trong bản đóng gói `troly`
  (launcher chỉ bundle `skill-packs/`) — đã từng mất `/clone-trang`
  vì lỗi này. `tests/test-packs.py` kiểm tự động.
- Skill mới do agent tự viết khi học viên lặp một lời nhờ nhiều lần —
  đặt thẳng vào `.devin/skills/`, không cần đăng ký thêm.
- `/gom-skill` (`pack-skill` en) nén skill tự sinh để chia sẻ cho người
  khác cài vào `skill-packs` của họ.

## SKILL.md contract

```yaml
---
name: ten-skill            # = tên folder, lệnh học viên gõ /ten-skill
description: >-            # một đoạn — agent dùng để quyết định invoke
  làm gì, khi nào dùng, giới hạn
triggers: [user, model]    # user = học viên gõ /ten; model = agent tự nhận
allowed-tools: [read, exec, write, webfetch, ask_user_question]
---
```

Phần thân = hướng dẫn theo phong cách "checklist + bẫy đã gặp":

- Viết **hành động cụ thể** (lệnh extension nào, lưu file nào), không
  viết nguyên tắc chung chung.
- Ghi rõ **bẫy thật đã xảy ra** và cách tránh — đây là phần giá trị
  nhất của skill (VD: "đo DOM tĩnh chỉ thấy panel accordion đang mở").
- Văn phong theo `AGENTS.md`: tiếng Việt, ELI10 khi nói với học viên,
  không "đơn giản/chỉ cần/dễ".

## Danh mục skill (pack vi ↔ en)

| vi | en | Việc |
|---|---|---|
| phong-van | interview | Phỏng vấn → công cụ cá nhân (skill + walkthrough + guide) |
| tao-cong-cu | make-tool | Gói việc lặp lại → skill /command + walkthrough.json + guide.md |
| huong-dan | guide | Chế độ gia sư dẫn dùng công cụ theo guide |
| mo-web | open-web | Lái trình duyệt thật qua extension |
| doc-zalo | read-zalo | Đọc/trả lời Zalo Web |
| doc-outlook | read-outlook | Đọc Outlook Web |
| cap-nhat-sheet | update-sheet | Đọc/ghi Google Sheets |
| dang-bai | publish-post | Đăng bài WordPress (nháp trước) |
| seo-meta | seo-meta | Sửa meta bài WP qua REST |
| lam-excel | work-excel | openpyxl: đọc/ghi/lọc .xlsx |
| lam-word | work-word | python-docx: điền template .docx |
| tom-tat-file | summarize-file | Tóm tắt nội dung file |
| loc-khach | split-customers | Tách danh sách khách theo tỉnh |
| gom-file | gather-files | Dọn Downloads/Desktop |
| nen-anh | compress-images | Nén + đổi kích thước ảnh |
| anh-web | web-images | Đổi tên + nén ảnh export Canva |
| xuat-canva | export-canva | Dẫn học viên export đúng từ Canva |
| zalo-oa | zalo-oa | Gửi tin Zalo OA qua API chính thức |
| gom-skill | pack-skill | Đóng gói skill tự sinh chia sẻ |
| clone-trang | clone-page | Clone trang mẫu → HTML của học viên |
| trang-moi | new-page | Thêm trang chi tiết vào site clone |

Pipeline clone (`data-cs-*` markers): xem `clone-pipeline.md`.

## Contract dữ liệu xuyên skill

- **Manifest**: `workspace/manifest.json` — `/phong-van`/`/tao-cong-cu`
  sinh bài, portal đọc hiển thị. Format: danh sách `{id, title, folder,
  has_slides, has_video, has_exercise, has_walkthrough, ...}` — tab
  portal hiện/ẩn theo cờ; `has_walkthrough` → nút "▶ Dùng ngay".
  Tool mới chỉ `has_walkthrough:true` (ba cờ media false — chuẩn
  guide + walkthrough, không slide/video/bài tập).
- **Walkthrough**: `tool-XX/walkthrough.json` — schema trong
  `templates/walkthrough.json` (16 kinds + cond/optional/then_probe/
  media); runner `web/app.js`, validator `tests/test-walkthrough.py`.
- **`data-cs-*` markers** — contract giữa `clone-trang` (sinh),
  `clone-view.html` (sửa), `trang-moi` (nhân bản): `data-cs`,
  `data-cs-type`, `data-cs-text/img/link/bg`, `data-cs-page`,
  `data-cs-template`, `data-cs-ref`. Bảng đầy đủ: `clone-pipeline.md`.
- **permissions.json** — mọi skill đụng folder ngoài `workspace/` phải
  kiểm tra trước (xem `SECURITY.md`).

## Bot bundle — đơn vị chia sẻ "cả trợ lý"

`gom-skill` (vi) / `pack-skill` (en) có mode gói bot: một bot trong
`workspace/bots.json` + các skill nó tham chiếu → `bot-<slug>.zip`:

```
bot-hang.zip
├── bot.json    # {name, avatar, role, skills[], needs[], recipes[],
│               #  instructions} — KHÔNG kèm id, triggers
├── README.txt  # 3 dòng: làm gì, cần nối gì, nhắc đọc instructions
└── skills/<tên>/   # thư mục skill đầy đủ
```

Nhập qua portal: menu chip trợ lý → "Nhập trợ lý từ file" →
`POST /api/bot-import` (preview instructions trước) →
`POST /api/bot-import-confirm` (ghi thật, KHÔNG tự activate).
Bot hay sau curate → thêm `skill-packs/roles/<id>.json` để phát cho mọi
máy như role template (xem `SECURITY.md` mục "Bot / skill nhập").
