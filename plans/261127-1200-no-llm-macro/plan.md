---
title: "No-LLM macro — việc lặp lại chạy thẳng qua bridge không tốn não: workflow steps trực tiếp + tự phát hiện thao tác lặp gợi ý lưu công cụ"
description: "Workflows hiện chỉ là prompt template gửi qua /api/prompt — vẫn đi qua LLM dù chuỗi bước cố định. Và phát hiện 'việc này lặp rồi' đang để mắt người đo. Plan thêm: (1) macro engine chạy chuỗi bước trực tiếp qua bridge endpoints, chỉ gọi não khi bước cần nội dung; (2) đếm prompt/tool lặp ≥3 lần → chip gợi ý 'lưu thành công cụ' mở sẵn luồng tao-cong-cu."
status: draft
priority: P2
effort: M
branch: main
tags: [workflow, macro, token-saving, skillify]
created: 2026-11-27
---

# No-LLM macro — việc lặp lại không tốn não

## Bối cảnh

Audit so với báo cáo nâng cấp bên ngoài:

- **"Macro thực thi thẳng"**: đúng là chưa có — `workflows/*.json`
  hiện chỉ chứa `prompt` + `checklist`, bấm nút là POST `/api/prompt`
  → não xử lý toàn bộ. Chuỗi bước cố định (copy folder, nén ảnh, đổi
  tên) tốn một lượt LLM mỗi lần chạy dù kết quả luôn giống nhau.
- **"1-click Skillify"**: `tao-cong-cu` skill đã gói được việc lặp
  thành công cụ — nhưng phải ai đó *chủ động* gọi. Chưa có bộ đếm
  "bạn làm việc này 3 lần rồi".

Cả hai đều nằm ở tầng bridge/portal — khả thi, nhưng macro mở surface
ghi file mới vào bridge → phải thiết kế kỹ phần guard.

## Mục tiêu

- Workflow có thể khai `steps:` — chạy tuần tự qua endpoint bridge,
  trăm mili-giây, **không gọi não**; step nào cần nội dung/ngữ cảnh
  mới rơi về prompt.
- Portal tự hiện gợi ý "lưu thành công cụ" khi cùng một việc lặp
  ≥3 lần → bấm là mở luồng `tao-cong-cu` có sẵn.

## Phase

| Phase | Việc | Phụ thuộc |
|---|---|---|
| 01 | `steps:` trong workflow JSON + macro runner (portal gọi endpoint có sẵn; fs-ops qua endpoint guard mới giới hạn trong permissions.json) | — |
| 02 | Đếm lặp trong `chat-history.jsonl` → chip "Lưu thành công cụ" → mở luồng `tao-cong-cu` | 01 (macro là "thứ để lưu thành" tự nhiên; nhưng có thể chạy độc lập) |

Chi tiết: `phase-01-macro-steps.md`, `phase-02-repeat-suggest.md`.

## Quyết định thiết kế (đề xuất — chờ chủ chốt)

1. **Macro runner chạy ở portal (JS) gọi endpoint**, không viết
   runner trong bridge — engine nhỏ, dễ audit, step-fail dừng ngay
   báo lỗi. Endpoint fs mới (`/api/fs-op`: copy/move/delete) vẫn đi
   qua `path_guard` + `permissions.json` như mọi đường khác.
2. **Không tự sinh macro.** Macro là do dev đóng gói sẵn trong
   workflow JSON (hoặc `tao-cong-cu` sinh có người duyệt) — portal
   chỉ chạy, không compose lệnh.
3. Đếm lặp chỉ trên **prompt text chuẩn hoá** + workflow id —
   không phân tích tool-call stream (phức tạp, ít lợi).

## Rủi ro chính

| Rủi ro | Giảm |
|---|---|
| `/api/fs-op` mới = surface ghi/xoá mới trên bridge | Giới hạn chặt: chỉ op {copy,move,delete→.trash}, chỉ trong `permissions.json` read-write, deny qua `cmd_deny`/`path_guard`; test-gates + test-deny-parity bắt buộc |
| Step macro fail giữa chừng → trạng thái nửa vời | Mỗi step ghi kết quả; fail → dừng + báo step nào; checkpoint của trust-harness (nếu đã có) che phần fs |
| Gợi ý skillify phiền (popup spam) | Chỉ chip thụ động trong panel, không modal; đã bấm "để sau" → không gợi ý lại prompt đó |

## Ra ngoài phạm vi

- Macro cho thao tác web/extension (chuỗi click/type) — giai đoạn sau,
  cần kết hợp silent-worker trước.
- Skillify phức tạp có điều kiện/vòng lặp — `tao-cong-cu` lo phần soạn
  skill, plan này chỉ lo phát hiện + đường chạy.
