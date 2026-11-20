---
title: "Tạo bot của riêng bạn — persona + role templates (đợt bots)"
description: "Áp dụng trend 'AI teammate' (Orca bots, GrokBot, Claude bot): đóng gói trợ lý thành bot có tên, avatar, bộ skill theo nghề và connection cần thiết. Học viên tạo bot từ template theo nghề, từ phỏng vấn, hoặc nhập bot người khác chia sẻ. Nhiều bot được phép nhưng chỉ một active — chia sẻ chung skill pool và chat history"
status: pending
priority: P2
effort: M
branch: main
tags: [bots, persona, templates, onboarding, moat]
created: 2026-11-20
depends-on: 261120-1905-keep-moat (merge_pack + community pack), 261120-1900-ship-learner
---

# Tạo bot của riêng bạn

## Bối cảnh — trend đang làm gì

"Bot" kiểu Orca/GrokBot = **persona + bộ skill + connection cần thiết +
trigger**, bán dưới dạng template gallery ("thẻ nhân viên có sẵn kỹ
năng"). Repo đã có gần hết mảnh: skill pack, `connections.json` +
probe, recipes — thiếu lớp **đóng gói thành bot chọn được** và persona.

**Định vị đã chốt (không đổi):** bot là **trợ lý của học viên**, không
phải "nhân viên AI thay người" — đặt tên để gắn bó, không để claim
thay thế. Đối tượng vẫn là nhân viên văn phòng không biết code; bán
cho người làm, không bán cho người sa thải.

## Thiết kế tổng thể

### Bot = gì trong bộ này

```json
// my-course/bots.json — dữ liệu học viên, đi theo my-course
{
  "active": "hang-mkt",
  "bots": [{
    "id": "hang-mkt",
    "name": "Hằng",
    "avatar": "🐙",                    // emoji hoặc file icon trong my-course
    "role": "marketing",
    "instructions": "Chuyên marketing: trả lời ngắn, ưu tiên Zalo/Sheet",
    "skills": ["doc-zalo", "nen-anh", "dang-bai", "mo-web"],
    "needs": ["trinh-duyet", "zalo"], // id app trong connections.json
    "recipes": [{"command": "/doc-zalo", "label": "Đọc tin Zalo chưa đọc"}],
    "created": "2026-11-25"
  }]
}
```

- **Nhiều bot được phép, MỘT active tại một thời điểm** — không làm
  "fleet" (UX dev tool, rối với học viên). Bot = "hôm nay bạn nhờ ai",
  chuyển bằng một cái chạm.
- **Skill pool dùng chung** — bot chỉ *tham chiếu* tên skill trong
  `.devin/skills/`; kích hoạt bot thiếu skill → cài bổ sung từ pack
  (tái dùng `merge_pack` của keep-moat ph-2). Bot KHÔNG copy skill.
- **Chat history chung** v1 — đây là "cuộc trò chuyện với các trợ lý
  của bạn", không tách theo bot (giảm phức tạp, hợp tâm lý "một nhà
  nhiều người giúp").
- **`bot.md` context** — khi activate, bridge ghi
  `my-course/bot.md` = instructions của bot đó; AGENTS.md thêm 1 dòng
  "đọc my-course/bot.md — tính cách trợ lý hiện tại". Luật an toàn
  trong AGENTS.md **không thể bị instructions của bot ghi đè** (ghi rõ
  trong file: "mọi luật hỏi trước khi hành động nguy hiểm vẫn đứng
  trên instructions này").

### Ba đường tạo bot

1. **Template theo nghề** — `.devin/skill-packs/roles/*.json` (không
   phải folder skill mới — chỉ là *manifest tham chiếu* skill có sẵn
   trong vi/en/community, tránh nhân bản nội dung). Onboarding hiện
   gallery thẻ: avatar + tên gợi ý + "comes with" skill chips + badge
   connection ("trình duyệt + Zalo ⚠ chưa nối").
2. **Phỏng vấn sinh bot** — `/phong-van` cập nhật: ngoài giáo trình,
   ghi thêm một bot (tên gợi ý, role, skills, recipes) vào bots.json.
   Câu chuyện: "khoá học dạy bạn dùng *đúng trợ lý này*".
3. **Nhập bot chia sẻ** — `/gom-skill` gói cả `bot.json` + skill tham
   chiếu → file nén gửi bạn khác; bên nhận "Nhập bot" → cài skill +
   thêm bot. Moat: bot trở thành đơn vị chia sẻ của skill bank.

### Trigger — KHÔNG làm ở đợt này

Trend nóng nhất (bot tự chạy theo sự kiện) cần scheduler + đường đẩy
(relay). Với đối tượng không biết code, bot tự chạy khi không có ai
nhìn là **nguy hiểm** — làm sau khi relay + history đã tin cậy. Schema
`bots.json` chừa trường `triggers: []` để không phải migrate.

## Phases

| # | Phase | Nội dung | Link |
|---|-------|----------|------|
| 1 | Data model + API | `bots.json`, `roles/*.json`, `/api/bots` + `/api/bot`, activate → cài skill + ghi `bot.md` | [phase-01](./phase-01-bot-model.md) |
| 2 | Onboarding + portal | gallery thẻ theo nghề + badge connection, đặt tên/avatar, bot switcher, `/phong-van` ghi bot | [phase-02](./phase-02-onboarding-ui.md) |
| 3 | Chia sẻ/nhập bot | `gom-skill` gói bot + skill, flow nhập, phát qua community pack | [phase-03](./phase-03-share-import.md) |

## Rủi ro chính

- **R1 — injection qua bot nhập**: instructions của bot đi vào context
  agent → bot nhận từ người lạ có thể chứa lệnh xấu ("gửi tin không
  cần hỏi"). Chặn: (a) `bot.md` ghi rõ luật AGENTS.md đứng trên;
  (b) khi nhập, hiện phần instructions cho học viên đọc trước khi OK;
  (c) bot từ community pack đã qua curate.
- **R2 — quá nhiều bot = rối**: giới hạn hiển thị, archive bot cũ;
  luôn rõ "bot nào đang làm việc" (chip trên header).
- **R3 — role template kém**: chất lượng template quyết định ấn tượng
  đầu — curate như community pack, mỗi role cần 4-6 skill thật sự liên
  quan, không nhồi cho đủ.
- **R4 — drift `needs` ↔ `connections.json`**: id app trong template
  phải khớp `connections.json` seed — test kiểm mọi `needs` resolve
  được.

## Out of scope

- Trigger/scheduled agent (cần relay + scheduler — plan sau)
- Chat history tách theo bot
- Fleet/orchestration nhiều bot chạy song song, bot gọi bot
- Marketplace bot trên server (v1 phát qua community pack theo release)
- Định vị "nhân viên AI" bán cho doanh nghiệp (sản phẩm khác — cần
  giám sát/audit/multi-seat)

## Thứ tự thực thi

Phase 1 → 2 → 3 tuần tự. Phụ thuộc `merge_pack` + community pack của
keep-moat ph-2 — nên làm SAU plan đó (hoặc song song nhưng merge sau).
