---
name: tao-cong-cu
description: Gói một việc lặp lại thành công cụ riêng — sinh skill /command mới kèm walkthrough.json (hướng dẫn tương tác từng-bước trong portal) + guide.md bản đọc trong workspace/, cập nhật manifest. Dùng khi học viên mô tả một việc muốn trợ lý làm sẵn công thức, hoặc muốn "biến việc vừa làm thành công cụ cho lần sau".
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
3. **Viết walkthrough.json** theo `templates/walkthrough.json` — màn
   hướng dẫn TƯƠNG TÁC trong portal (modal từng bước, nhiều bước làm
   được luôn trong đó). Đây là sản phẩm chính. Tư duy theo chuỗi hành
   động CỦA HỌC VIÊN (không phải của agent): việc nào họ phải chuẩn bị/
   gõ/duyệt thì thành step tương ứng —
   - cần app mở sẵn (Zalo, Canva, web đăng nhập) → `open-url`
   - cần thông tin riêng của họ (tên shop, link, số) → `input` lưu biến
   - cần chỉ file/folder nguồn → `pick-file` lưu biến
   - gõ lệnh/trả lời trợ lý → `prompt` (prefill điền sẵn chạy được)
   - hộp thoại xin phép sẽ hiện → `wait-perm`
   - cần họ bấm đúng chỗ trên portal → `spotlight` + `click_target`
   - mở file/folder kết quả → `open`
   - kiểm kết quả trước khi xong → `check` (kỳ vọng + nút "Chưa thấy —
     nhờ trợ lý")
   **Sau MỖI prompt/wait-run luôn xếp một `prompt` optional "Trả lời trợ
   lý" rồi một `wait-run`** — trợ lý hay hỏi lẻ giữa run (xác nhận, hỏi
   nghĩa dữ liệu) và không đoán được bao nhiêu lượt; vòng này gánh hết.
   Mở đầu bằng `say` giới thiệu, kết thúc bằng `done` chốt "lần sau gõ
   lệnh gì". Đặt trong `workspace/tool-XX-<slug>/` (XX = số tiếp theo
   trong manifest).
4. **Viết guide.md** theo `templates/lesson.md` — bản đọc của chính
   walkthrough đó (cùng các bước, dạng trang để đọc lại nhanh / in ra).
5. **Tự soát trước khi xong**:
   - chạy `python3 tools/test-walkthrough.py` — phải PASS
   - mỗi step đúng MỘT hành động; `prefill`/`placeholder` chạy được
   - `{{bien}}` trong prefill phải khớp `var` của step input/pick-file
     đứng trước
   - guide.md: mỗi `### Bước` có 1 thao tác + 1 dòng ✅, không từ cấm
   Sai chỗ nào sửa chỗ đó rồi mới qua bước 6.
6. **Cập nhật `workspace/manifest.json`**: thêm entry lesson với
   `"has_slides": false, "has_video": false, "has_exercise": false,
   "has_walkthrough": true`; nếu là skill mới thì thêm vào `recipes`:
   `{"command": "/<ten>", "meaning": "<ý nghĩa một dòng>"}`.
7. **Báo học viên** (câu ngắn, lời thường): công cụ tên gì, gõ `/command`
   ở đâu, guide nằm ở mục nào trên portal. Kèm: *"lần sau quên thì mở
   lại guide, hoặc gõ `/huong-dan` để mình dẫn từng bước"*.

## Không làm

- Không sinh slide, video, bài tập, file mẫu.
- Không ghi đè skill có sẵn — trùng tên thì hỏi học viên muốn đổi tên
  hay cập nhật.
- Không tạo skill cho việc chỉ làm MỘT lần rồi thôi — guide là đủ.
