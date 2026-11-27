---
title: "Trust harness — trợ lý làm xong phải chứng minh được và lùi được: checkpoint hoàn tác 1 chạm, verify contract cho skill, gửi Zalo kiểm 2 bước, quyền theo tác vụ"
description: "Hiện workflows đã có verify {dir,glob,min_count} nhưng skill không có; không có cơ chế undo file bị não sửa; doc-zalo hỏi trước khi gửi nhưng chưa kiểm đúng người nhận; quyền chỉ có allow_once hoặc allowlist vĩnh viễn. Plan biến 4 chỗ hở đó thành tầng 'tin cậy': mọi thay đổi có checkpoint, mọi tác vụ có kiểm chứng, mọi quyền có thời hạn."
status: draft
priority: P1
effort: L
branch: main
tags: [safety, undo, verify, permissions, zalo]
created: 2026-11-27
---

# Trust harness — chứng minh được & lùi được

## Bối cảnh

Audit so với báo cáo nâng cấp bên ngoài: phần "kiểm chứng" dự án đã có
một mảng (`workflows[].verify` + `/api/count-glob` + checklist người
tick + verify đỏ tự nhờ não sửa), nhưng ba chỗ còn hở:

1. **Không undo được.** `.trash` chỉ che `delete-lesson`; não sửa/xoá
   file trong `workspace/` hay folder được cấp quyền thì không có
   đường lùi. Đây là nỗi sợ số 1 của người dùng cá nhân.
2. **Skill không có hợp đồng kiểm chứng** — pattern verify của
   workflow chưa lan sang `.devin/skills/`.
3. **Gửi Zalo chưa kiểm đúng người** — skill `doc-zalo` hỏi học viên
   trước khi gửi, nhưng không đối chiếu header khung chat với đích
   danh; gửi nhầm hội thoại là lỗi không cứu được.
4. **Quyền chỉ hai cực**: `allow_once` lắt nhắt (audit-3 M1 cố tình
   chặn "đồng ý = cho mãi") hoặc `exec-allowlist.json` vĩnh viễn.
   Thiếu vùng giữa "cho phép trong tác vụ này".

## Mục tiêu

- Mọi file bị đụng trong một turn đều có bản trước-đó để khôi phục;
  tin nhắn của trợ lý có nút **Hoàn tác**.
- Skill hành động khai `verify` giống workflow — portal tự check và
  báo xanh/đỏ.
- Không gửi nhầm tin Zalo: khớp `header_title == target` trước khi
  bấm Gửi, kiểm "Đã gửi" sau khi bấm.
- Xin quyền có lựa chọn thứ ba: **trong tác vụ này (~15 phút)** —
  tự thu hồi, không ghi vào allowlist bền.

## Phase

| Phase | Việc | Phụ thuộc |
|---|---|---|
| 01 | Checkpoint theo turn vào `.trash/checkpoints/<turn_id>/` + nút Hoàn tác trong chat | — |
| 02 | `verify` contract cho skill (định dạng + đọc ở portal/agent) | 01 (không bắt buộc, nhưng undo có sẵn làm verify-đỏ-sửa-lại an toàn hơn) |
| 03 | `doc-zalo`: xác minh người nhận 2 bước + xác nhận Đã gửi | — |
| 04 | Quyền theo tác vụ 15 phút (memory-only, tự thu hồi) | 01, 02 — làm cuối, cần đối chiếu kỹ audit-3 M1 |

Chi tiết: `phase-01-checkpoint-undo.md`, `phase-02-skill-verify.md`,
`phase-03-zalo-send-verify.md`, `phase-04-task-grant.md`.

## Quyết định thiết kế (đề xuất — chờ chủ chốt)

1. **Checkpoint theo biên turn, không theo từng file-write.** Bridge
   không thấy write của não trước khi nó xảy ra (write nằm trong
   process não). Snapshot trạng thái `workspace/` + folder được cấp
   `read-write` ở **đầu mỗi turn** (trước khi forward prompt) —
   "Hoàn tác" = trả cây file về snapshot của turn đó. Đảm bảo đúng
   100%, đánh đổi là mức chụp cả cây chứ không chỉ file bị sửa.
2. **Skill verify v1 chạy ở portal** giống workflow (đã có
   `/api/count-glob`), không đụng SKILL.md parser phức tạp —
   skill khai khối `verify:` trong frontmatter.
3. **Quyền 15 phút chỉ trong memory**, hết hạn tự mất, KHÔNG ghi
   `exec-allowlist.json` — giữ nguyên tinh thần audit-3 M1.

## Rủi ro chính

| Rủi ro | Giảm |
|---|---|
| Snapshot cả cây mỗi turn tốn IO/disk | Chỉ copy file **đổi** so với snapshot trước (mtime+size), hardlink phần còn lại; prune giữ N checkpoint gần nhất; folder `read` không chụp |
| "Hoàn tác" trả file trong khi não vẫn đang giữ handle/mở file | Undo chỉ khi không có prompt đang chạy (409 như new-task); báo rõ file nào được trả |
| Quyền 15 phút bị lạm dụng thành "always ngầm" | Memory-only + hiển thị đếm ngược trên portal; không persist; audit log vào `.logs/` |
| Verify skill làm dev nản phải viết thêm block | Optional — skill không khai thì chạy như cũ; chỉ skill "hành động" mới nên khai |

## Ra ngoài phạm vi

- Undo cho thao tác web/Zalo (không undo được message đã gửi — chỉ
  kiểm trước khi gửi, đó là phase 03).
- Versioning đầy đủ kiểu git — checkpoint chỉ phục vụ "lùi 1 turn".
