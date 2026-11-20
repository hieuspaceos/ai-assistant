# ai-assistant — Skills System

Skill = "cuốn sổ công thức": file `SKILL.md` viết sẵn quy trình cho một
việc lặp lại. Không có skill agent vẫn làm được — có skill thì kết quả
ổn định và nhanh hơn.

## Vị trí và vòng đời

```
.devin/skill-packs/vi/   18 skill tiếng Việt   (kho mẫu)
.devin/skill-packs/en/   17 skill English      (kho mẫu)
        │ onboarding (/api/setup) copy đúng pack theo config.language
        ▼
.devin/skills/<tên>/SKILL.md   ← skill ACTIVE, agent đọc thư mục này
```

- **Sửa skill → sửa ở `.devin/skills/`** (bản active). `skill-packs/` là
  kho gốc để onboard máy mới — sửa cả hai nếu muốn thay đổi lan ra.
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
| phong-van | interview | Phỏng vấn → giáo trình cá nhân |
| hoc-bai | tutor | Chế độ gia sư dẫn từng bài |
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

Skill **không nằm trong pack** (cài trực tiếp, có ở cả hai ngôn ngữ):
`clone-trang`, `trang-moi` — xem `clone-pipeline.md`.

## Contract dữ liệu xuyên skill

- **Manifest**: `my-course/manifest.json` — `/phong-van` sinh bài, portal
  đọc hiển thị. Format: danh sách `{id, title, folder, ...}`.
- **`data-cs-*` markers** — contract giữa `clone-trang` (sinh),
  `clone-view.html` (sửa), `trang-moi` (nhân bản): `data-cs`,
  `data-cs-type`, `data-cs-text/img/link/bg`, `data-cs-page`,
  `data-cs-template`, `data-cs-ref`. Bảng đầy đủ: `clone-pipeline.md`.
- **permissions.json** — mọi skill đụng folder ngoài `my-course/` phải
  kiểm tra trước (xem `SECURITY.md`).
