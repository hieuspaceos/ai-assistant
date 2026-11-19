---
name: gom-skill
description: Gói các skill tự sinh trong .devin/skills/ thành file nén để gửi lại cho người quản kho — skill bank. Dùng khi học viên muốn chia sẻ "công thức" trợ lý vừa tạo cho đồng nghiệp khác.
triggers:
  - user
  - model
allowed-tools:
  - exec
  - read
  - ask_user_question
---

Skill hay sinh ra trên máy học viên nằm trong `.devin/skills/<tên>/`.
Để lan ra kho chung: gói thành file nén → học viên gửi cho người quản kho
(qua mail/Zalo), người quản kho merge vào `.devin/skill-packs/<lang>/`.

## Các bước

1. Liệt kê skill trong `.devin/skills/` kèm mô tả (dòng `description:`
   trong mỗi SKILL.md) → hỏi học viên chọn cái nào muốn chia sẻ
   (`ask_user_question`, multi_select — tối đa 4 lần chọn nếu nhiều).
   **Bỏ qua** các skill mặc định của hệ thống (đã có sẵn trong
   skill-packs) — chỉ gói skill MỚI sinh ra.
2. Nói trước: *"mình sẽ gói 2 skill bạn chọn vào file
   `my-course/skill-exports/skills-<ngày>.zip` để bạn gửi cho người quản
   kho. Gốc trong `.devin/skills/` không động vào. Nhé?"*
3. Gói:
   ```bash
   mkdir -p my-course/skill-exports
   cd .devin/skills && zip -r ../../my-course/skill-exports/skills-$(date +%Y%m%d).zip <skill1> <skill2>
   # Windows PowerShell:
   # Compress-Archive .devin\skills\<skill1>,.devin\skills\<skill2> my-course\skill-exports\skills-<ngày>.zip
   ```
4. Báo đường dẫn file nén + hướng dẫn gửi: *"gửi file này cho người quản
   kho (mình không tự gửi)"*.
5. Người quản kho: giải nén vào `.devin/skill-packs/<vi|en>/` → các
   learner cài lại qua `/api/setup` hoặc copy sang `.devin/skills/`.
