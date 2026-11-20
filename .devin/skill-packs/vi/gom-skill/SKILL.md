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

## Mode gói BOT — "chia sẻ cả trợ lý"

Ngoài skill lẻ, có thể gói một **bot** trong `my-course/bots.json`
(trợ lý có tên riêng + bộ skill nó dùng). File ra đời mở được trên máy
khác bằng mục "Nhập trợ lý" trong menu chip trợ lý.

1. Đọc `my-course/bots.json` → liệt kê `bots[]` (tên + role) → hỏi học
   viên chọn bot nào muốn chia sẻ.
2. Lấy đúng object bot đó, viết `bot.json` — chỉ các trường schema:
   `name, avatar, role, skills, needs, recipes, instructions`
   (KHÔNG kèm `id`, `triggers`).
3. Viết `README.txt` 3 dòng: bot làm gì, cần nối app nào, và câu nhắc
   "đọc lời dặn (instructions) trước khi nhập".
4. Copy từng skill trong `bot["skills"]` từ `.devin/skills/<tên>/` vào
   `skills/<tên>/` trong bundle (skill hệ thống cũng gói — file nhỏ,
   bên nhận không đè skill đang có).
5. Nén thành `my-course/skill-exports/bot-<slug>.zip` đúng layout:

   ```
   bot-hang.zip
   ├── bot.json
   ├── README.txt
   └── skills/<tên>/SKILL.md (+ file kèm)
   ```

   Dùng python `zipfile` (Windows không chắc có `zip`):
   ```bash
   python3 -c "import zipfile,glob,os
   z=zipfile.ZipFile('my-course/skill-exports/bot-<slug>.zip','w')
   z.write('bot.json'); z.write('README.txt')
   [z.write(f,os.path.relpath(f,'.')) for f in glob.glob('skills/**/*',recursive=True) if os.path.isfile(f)]
   z.close()"
   ```
   (chạy từ một folder tạm đã bung bot.json + README.txt + skills/)
6. Báo đường dẫn file — học viên tự gửi cho bạn bè, mình không tự gửi.
