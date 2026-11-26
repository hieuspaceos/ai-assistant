---
name: tao-cong-cu
description: Gói một việc lặp lại thành công cụ riêng — sinh skill /command mới kèm guide.md tutorial từng-bước trong my-course/, cập nhật manifest. Dùng khi học viên mô tả một việc muốn trợ lý làm sẵn công thức, hoặc muốn "biến việc vừa làm thành công cụ cho lần sau".
triggers:
  - user
  - model
allowed-tools:
  - read
  - write
  - exec
  - grep
  - find_file_by_name
  - ask_user_question
---

Bạn biến một việc cụ thể của học viên thành một CÔNG CỤ dùng lại được,
kèm hướng dẫn từng-bước. Giống viết món ăn vào sổ công thức của nhà —
lần sau chỉ cần gọi tên món.

## Đầu vào

Học viên mô tả một việc (VD: "mỗi tuần phải nén ảnh Canva, đổi tên, đăng
web"), hoặc chỉ vào việc trợ lý vừa làm xong ("gói việc này thành công cụ
cho lần sau"). Nếu mô tả còn mơ hồ, hỏi TỐI ĐA 2 câu trước khi làm: việc
này làm trên file/app nào? đầu ra mong muốn là gì?

## Quy trình

1. **Chọn hình thức công cụ** — đúng một trong ba:
   - *Skill mới* `.devin/skills/<ten-tool>/SKILL.md` — việc có quy trình
     cố định, lặp lại nhiều lần.
   - *Skill có sẵn* — đã có `/nen-anh`, `/loc-khach`... khớp việc →
     không tạo mới, chỉ sinh guide dạy cách gọi.
   - *Nhờ tự do* — việc đặc thù không đáng làm skill → chỉ sinh guide
     dạy cách diễn đạt lời nhờ.
2. **Viết SKILL.md** (nếu skill mới): frontmatter đủ `name`/`description`/
   `triggers`/`allowed-tools`; thân là công thức — các bước làm, cần hỏi
   gì trước, luật an toàn (không đụng file gốc, báo trước khi chạy). Tên
   skill: chữ thường, gạch ngang, không dấu (VD `nen-anh-facebook`).
   Nếu được, chạy thử một lần trên folder đã được cấp quyền để chắc công
   thức đúng.
3. **Viết guide.md** theo `templates/lesson.md` — tutorial từng-bước
   kiểu onboarding: mỗi `### Bước N` là MỘT thao tác (bấm đâu, gõ gì,
   tick ô nào), sau mỗi bước có dòng "✅ thấy gì là đúng". Đặt trong
   `my-course/lesson-XX-<slug>/` (XX = số tiếp theo trong manifest).
   Tên bước lấy từ "từ vựng bước" trong template (Gõ lệnh, Duyệt quyền,
   Mở kết quả...) để các guide nhìn quen giống nhau.
4. **Tự soát guide trước khi xong** — đọc lại file vừa viết và kiểm:
   - mỗi `### Bước` có đúng MỘT thao tác + MỘT dòng ✅
   - tên bước thuộc từ vựng bước trong template
   - không có từ cấm ("đơn giản", "chỉ cần", "hiển nhiên", "dễ")
   - prompt mẫu copy-paste chạy được
   Sai chỗ nào sửa chỗ đó rồi mới qua bước 5.
5. **Cập nhật `my-course/manifest.json`**: thêm entry lesson với
   `"has_slides": false, "has_video": false, "has_exercise": false`;
   nếu là skill mới thì thêm vào `recipes`:
   `{"command": "/<ten>", "meaning": "<ý nghĩa một dòng>"}`.
6. **Báo học viên** (câu ngắn, lời thường): công cụ tên gì, gõ `/command`
   ở đâu, guide nằm ở mục nào trên portal. Kèm: *"lần sau quên thì mở
   lại guide, hoặc gõ `/hoc-bai` để mình dẫn từng bước"*.

## Không làm

- Không sinh slide, video, bài tập, file mẫu.
- Không ghi đè skill có sẵn — trùng tên thì hỏi học viên muốn đổi tên
  hay cập nhật.
- Không tạo skill cho việc chỉ làm MỘT lần rồi thôi — guide là đủ.
