---
title: "Giữ chân & moat: chat history + skill bank hai chiều + publish skills.sh"
description: "Sau khi ship được (261120-1900-ship-learner), đợt này làm trợ lý 'đáng quay lại': không mất lịch sử chat khi restart, kho công thức cộng đồng chảy hai chiều (gom về + phát ra), và skill pack được publish lên registry Agent Skills để vừa marketing vừa chống lock-in"
status: pending
priority: P2
effort: M
branch: main
tags: [retention, skills, moat, community]
created: 2026-11-20
depends-on: 261120-1900-ship-learner (đợt ship)
---

# Giữ chân & moat

## Bối cảnh — tại sao làm

Đợt ship giải quyết "cài được, dùng được". Đợt này giải quyết câu hỏi
tiếp theo: **tại sao học viên quay lại ngày mai, và moat nằm ở đâu khi
Claude/ChatGPT làm browser-control tốt hơn?**

Ba mảnh:

| # | Việc | Trả lời cho |
|---|------|------------|
| A | Chat history persist — `event_store` hiện mất khi restart bridge | trợ lý dùng hàng ngày không thể mất trí nhớ mỗi lần tắt máy |
| B | Skill bank hai chiều — `/gom-skill` chỉ gom về kho, chưa có đường phát lại cho học viên khác | moat duy nhất có network effect: cộng đồng công thức VN |
| C | Publish pack lên registry Agent Skills (skills.sh) | marketing miễn phí + chống "bộ này chết thì skill mất" — pack theo chuẩn `SKILL.md` chạy được trên 70+ agent khác |

## Thiết kế tổng thể

1. **History**: `broadcast()` ghi thêm JSONL vào `.logs/chat-history.jsonl`;
   bridge khởi động replay file vào `event_store` — client poll nhận
   `reset` đã dựng lại toàn bộ UI (cơ chế sẵn có). Event `perm` là
   transient → không replay. Rotate file khi quá lớn.
2. **Skill bank**: v1 bundle `.devin/skill-packs/community/` vào `troly`
   (cập nhật theo release — zero network, đúng triết lý) + merge an
   toàn khi `/api/setup` (skill học viên tự tạo không bị đè — tái dùng
   logic merge `skills.bak` hiện có). Đường fetch-on-demand qua mạng
   để v2.
3. **skills.sh**: pack vi/en đã đúng format `SKILL.md` — verify khớp
   spec Agent Skills (AAIF), mở repo public `troly-skills`, submit
   listing. Extra frontmatter (`triggers`, `allowed-tools`) giữ nguyên
   — spec cho phép field mở rộng, agent khác bỏ qua.

## Phases

| # | Phase | Nội dung | Link |
|---|-------|----------|------|
| 1 | Chat history | JSONL persist + replay + rotate + skip perm events | [phase-01](./phase-01-chat-history.md) |
| 2 | Skill bank pull | pack `community/` bundle vào troly + merge trong `/api/setup` + skill `gom-skill` ghi vào đúng chỗ | [phase-02](./phase-02-skill-bank-pull.md) |
| 3 | Publish skills.sh | verify spec + repo public + submit registry | [phase-03](./phase-03-skills-sh.md) |

## Rủi ro chính

- **R1**: history chứa nội dung nhạy cảm (agent kể lại tin Zalo) — file
  nằm `.logs/` đã gitignore + `chmod 600` khi ghi, ghi chú rõ vào
  SECURITY.md: history là "những gì agent đã nói", học viên xoá `.logs/`
  là mất sạch.
- **R2**: replay event `perm` cũ → card xin phép zombie — bắt buộc lọc
  khi replay (đã thiết kế).
- **R3**: community pack chất lượng kéo xuống nếu nhận mọi skill gửi về
  — kho do chủ dự án curate (review trước khi vào release), không mở
  quyền ghi trực tiếp.
- **R4**: publish pack public → lộ thông tin riêng trong skill? —
  review trước khi public (skills chỉ chứa quy trình, không secret —
  nhưng phải kiểm một vòng).

## Out of scope

- Relay/mobile (`261120-1500-relay-mobile` — plan riêng, độc lập với
  đợt này, ưu tiên ngang hoặc sau tuỳ nguồn lực)
- Fetch-on-demand skill bank qua mạng (v2 — khi có >vài chục học viên)
- Skill rating/feedback trong portal
- Sync history giữa nhiều máy (trái triết lý local-first)

## Thứ tự thực thi

Phase 1 độc lập, làm ngay được. Phase 2 và 3 cùng chủ đề "kho skill" —
làm liền nhau; phase 3 cần quyết định mở repo public (việc người dùng).
