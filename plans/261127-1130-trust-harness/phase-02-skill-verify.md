# Phase 02 — `verify` contract cho skill hành động

## Lý do

Workflow đã có `verify {dir, glob, min_count}` + checklist → portal
tự check sau `done` và nhờ não sửa nếu đỏ. Skill trong `.devin/skills/`
thì không có gì — não bảo "xong" là tin luôn. Phase này đưa cùng một
hợp đồng kiểm chứng sang skill, tái dùng hẳn cơ chế workflow.

## Định dạng

Thêm khối optional vào frontmatter `SKILL.md` (vẫn YAML thuần, không
đổi parser):

```yaml
---
name: lam-excel
description: ...
verify:
  - dir: "{{output_dir}}"      # tái dùng cú pháp của workflows
    glob: "*.xlsx"
    min_count: 1
  - hint: "Mở file đầu tiên — số dòng khớp báo cáo"   # checklist người
---
```

- `verify` là **list**: mỗi phần tử hoặc `check máy` (`dir`/`glob`/
  `min_count`, `file_exists`) hoặc `hint` (dòng checklist người tick).
- Giữ nguyên engine `/api/count-glob` + UI chip của workflow — không
  endpoint mới.

## Thay đổi

### `tools/chat-bridge.py` hoặc `tools/serve.py` (chọn một, ghi decision)

- Endpoint đọc verify của skill: `GET /api/skill-verify?name=<skill>`
  → parse frontmatter `SKILL.md` → trả list verify (file nằm trong
  `.devin/skills/` — **serve phải cho phép đọc file này**; kiểm
  dotfile-guard hiện tại — `.devin` bị chặn → cần endpoint qua
  chat-bridge thay vì serve tĩnh. Ghi decision: bridge đọc file,
  serve không động vào `.devin`.)

### `web/app.js`

- Sau event `done`, nếu prompt bắt đầu bằng `/<skill>` hoặc manifest
  gắn skill → fetch `/api/skill-verify` → chạy check máy → chip
  xanh/đỏ + phần `hint` hiện checklist người tick — **y hệt luồng
  workflow** (tái dùng `wf-checklist` UI, đổi tên hàm chung).
- Verify đỏ → tự gửi prompt sửa (pattern `wfIssueFix` có sẵn, i18n sẵn).

### Skill cần khai `verify:` đợt đầu (sủa SKILL.md)

| Skill | Check máy |
|---|---|
| `lam-excel` | output_dir có `*.xlsx` ≥1 |
| `lam-word` | output_dir có `*.docx` ≥1 |
| `nen-anh` | folder `*-web/` có ảnh ≥ số ảnh gốc |
| `gom-file` | folder đích có file ≥1 + folder nguồn còn ≥0 (file gốc giữ nguyên = `hint`) |
| `loc-khach` | folder đích có `*.xlsx` ≥2 |
| `anh-web` | folder kết quả có ảnh ≥1 |

## Bẫy đã biết

- `{{placeholder}}` trong skill không có ngữ cảnh fill sẵn như
  workflow (không có form inputs) → v1: chỉ hỗ trợ `dir` dạng tương
  đối so với `workspace/` hoặc placeholder `{{output_dir}}` do agent
  tự quyết — **thành thật: đây là phần mờ nhất**. Phương án gọn hơn:
  skill khai `verify` với đường **literal** tương đối, agent ghi file
  kết quả vào đúng chỗ đó theo convention (VD mọi skill output ra
  `workspace/output/`). Chốt convention trong phase này rồi mới viết
  verify cho 6 skill.
- `.devin/` bị serve chặn (dotfile) → phải đi qua bridge; không mở
  exception trong serve.

## Test

- `test-bridges.py`: `/api/skill-verify?name=lam-excel` trả đúng list;
  name lạ → 404; name có `../` → 400.
- UI tay: chạy `/nen-anh` xong → chip verify xanh; xoá output → đỏ →
  prompt sửa tự gửi.
