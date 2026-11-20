# Phase 3 — Publish skill pack lên registry Agent Skills (skills.sh)

## Mục tiêu

Pack vi/en của Trợ Lý AI có mặt trên registry Agent Skills mở
(skills.sh — ~1 triệu skill, dùng được trên 70+ agent platform): vừa
là kênh marketing miễn phí cho sản phẩm, vừa chứng minh pack không
lock vào bộ trợ lý này.

## File động

| File/repo | Action | Việc |
|---|---|---|
| repo public mới `troly-skills` (GitHub) | create | bản public của `skill-packs/vi` + `skill-packs/en` (+ `community` khi phase 2 xong), README giới thiệu |
| `.devin/skill-packs/*/SKILL.md` | modify | verify/sửa frontmatter khớp spec Agent Skills: `name` + `description` bắt buộc; field mở rộng giữ nguyên |
| `docs/skills-system.md` | modify | ghi đường publish + luật "field mở rộng Devin không làm vỡ spec" |
| `tools/test-packs.py` | modify | kiểm mọi SKILL.md có đủ `name` + `description` hợp lệ theo spec (name = `^[a-z0-9-]+$` khớp folder) |

## Chi tiết

### 3a. Kiểm khớp spec trước khi publish

Spec Agent Skills (AAIF): bắt buộc `name` + `description` trong
frontmatter YAML; `name` khớp tên folder, charset `a-z0-9-`, ≤64 ký
tự. Field thêm (`triggers`, `allowed-tools` của Devin) là mở rộng hợp
lệ — agent khác bỏ qua.

Điểm cần săn trong pack hiện tại:

- Một số skill tham chiếu đường dẫn riêng của bộ này
  (`my-course/permissions.json`, `bridge.token`, port 7684…) — giữ
  nguyên (skill viết cho đúng môi trường là bình thường); nhưng rà để
  chắc không chứa secret/đường dẫn máy cá nhân.
- Skill phụ thuộc extension Trợ Lý AI (`mo-web`, `doc-zalo`…) — mô tả
  ghi rõ "cần extension đi kèm" để người ngoài không hiểu nhầm.

### 3b. Repo public `troly-skills`

```
troly-skills/
├── README.md          # giới thiệu bộ skill VN cho dân văn phòng + link troly
├── vi/<skill>/SKILL.md
├── en/<skill>/SKILL.md
└── community/<skill>/SKILL.md   (khi phase 2 có)
```

Sync tay từ repo chính lúc release (script `tools/export-skills.sh`
copy `skill-packs/` ra folder export, git init/commit — đủ cho nhịp
release hiện tại; chưa cần CI hai chiều).

### 3b2. Submit registry

- Theo hướng dẫn submit của skills.sh tại thời điểm làm (PR thêm entry
  trỏ repo). Yêu cầu repo public + license — thêm `LICENSE` (MIT/CC-BY
  cho nội dung skill).
- README repo ghi đường về `troly.hieuspace.com` — đây là phần
  "marketing miễn phí".

## Acceptance

- `test-packs.py` kiểm spec pass cho mọi SKILL.md trong 3 pack
- Repo `troly-skills` public, clone về dùng được với một agent khác
  (verify nhanh bằng cách trỏ một não khác vào folder skills)
- Listing trên skills.sh được chấp nhận (hoặc có lý do từ chối cụ thể
  để vá)

## Rủi ro

- Rà soát thiếu sót → lộ thông tin riêng: checklist review từng
  SKILL.md trước khi push lần đầu (không token, không path cá nhân,
  không tên học viên thật).
- Duy trì hai repo lệch nhau → export là một chiều từ repo chính, ghi
  rõ "source of truth = ai-assistant".
