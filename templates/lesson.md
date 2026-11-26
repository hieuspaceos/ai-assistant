<!--
TEMPLATE HƯỚNG DẪN DÙNG CÔNG CỤ — agent điền vào chỗ {{...}} khi sinh bài mới.
Quy tắc bắt buộc khi điền:
- Ngôn ngữ theo `workspace/config.json` (vi → tiếng Việt, en → English),
  giọng ELI10 theo AGENTS.md của folder này. Tên bước dịch theo ngôn ngữ
  đó nhưng giữ đúng loại trong từ vựng bước bên dưới.
- Bài này là một TUTORIAL TỪNG-BƯỚC để dùng một công cụ — như màn
  onboarding: bước nào cũng ghi rõ BẤM VÀO ĐÂU, GÕ CHỮ GÌ, TICK Ô NÀO.
- Mỗi bước = MỘT hành động. Không gộp hai việc vào một bước.
- Mọi lệnh/prompt mẫu phải copy-paste chạy được ngay, viết bằng lời thường.
- Không được có chữ "đơn giản", "chỉ cần", "hiển nhiên", "dễ".

TỪ VỰNG BƯỚC — mọi bước phải thuộc một trong các loại sau (đặt tên bước
theo loại để học viên quen mặt dù công cụ khác nhau):
- "Gõ lệnh"      → mở khung chat, gõ /command hoặc dán prompt mẫu, bấm Gửi
- "Trả lời trợ lý" → trợ lý hỏi gì thì gõ câu trả lời ngắn tương ứng
- "Duyệt quyền"  → hộp thoại hiện → đọc nó định làm gì → bấm Đồng ý
- "Chọn file/folder" → duyệt tới đúng chỗ khi hộp chọn file hiện
- "Bấm nút trên portal" → bấm nút Chạy trên card workflow
- "Kết nối app"  → đăng nhập sẵn app/web trên trình duyệt
- "Mở kết quả"   → mở file/folder kết quả để kiểm tra
- "Nhờ chỉnh lại" → kết quả chưa ý thì gõ tiếp yêu cầu sửa
Skill tổ hợp (nhiều lệnh nối nhau) = xích các loại bước này lặp lại theo
đúng thứ tự công cụ chạy.
-->

# {{lesson_name_outcome}}

> Bài này dạy bạn dùng công cụ {{tool_name}} để {{outcome_one_liner}} —
> việc mà trước giờ {{pain_one_liner}}.

## Công cụ này làm gì

{{what_tool_does}} — 2-3 câu lời thường, kèm phép so sánh đời thường nếu
khái niệm mới (VD: "giống người giúp việc biết sẵn công thức nấu của nhà").

**Cách gọi:** {{cach_goi}}

- Nếu là công cụ riêng: gõ `/{{command}}` vào khung chat.
- Nếu là quy trình trong portal: bấm nút **Chạy** ở thẻ `{{workflow_name}}`.
- Nếu là nhờ tự do: gõ VD `{{prompt_mau}}`.

## Dùng ngay — từng bước

### Bước 1 — {{ten_buoc_1: hành động cụ thể, VD "Mở khung chat"}}

{{bấm đâu / gõ gì — viết ra thao tác thật:
- "Bấm nút **Hỏi trợ lý** góc trên bên phải trang web."
- "Gõ vào khung chat: `/nen-anh` rồi bấm **Gửi**."
- "Khi hộp thoại hiện lên hỏi, đọc xem nó định làm gì rồi bấm **Đồng ý**."}}

✅ Thấy {{dau_hieu_dung_1}} là đúng.

### Bước 2 — {{ten_buoc_2}}

{{thao_tac}}

✅ Thấy {{dau_hieu_dung_2}} là đúng.

{{extra_steps}}

### Bước cuối — Kiểm tra kết quả

{{cach_mo_file_ket_qua}} — VD: "Mở folder `anh-nho` trong Downloads, bạn
sẽ thấy {{ket_qua_thay}}."

Nếu kết quả không giống ý, gõ tiếp: *"{{prompt_fixed}}"*

## Trợ lý hỏi lại thì trả lời sao

| Trợ lý hỏi | Bạn trả lời kiểu |
|---|---|
| {{cau_hoi_1}} | {{cau_tra_loi_mau_1}} |
| {{cau_hoi_2}} | {{cau_tra_loi_mau_2}} |

## Kẹt chỗ nào thì

| Bạn thấy | Nghĩa là | Làm gì |
|---|---|---|
| {{loi_1}} | {{nghia_1}} | {{cach_sua_1}} |
| {{loi_2}} | {{nghia_2}} | {{cach_sua_2}} |

Còn nữa thì chụp màn hình dán vào chat và hỏi: *"bị gì vậy bạn?"*
