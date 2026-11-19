---
name: tom-tat-file
description: Đọc một file (CSV, Excel export, TXT, MD, JSON...) và tóm tắt nội dung bằng lời thường — có gì trong file, bao nhiêu dòng, điểm đáng chú ý.
triggers:
  - user
  - model
allowed-tools:
  - read
  - exec
  - ask_user_question
---

Tóm tắt file cho người không biết kỹ thuật. Họ muốn biết "trong file này
có gì" mà không phải mở lên đọc từng dòng.

## Các bước

1. Nếu học viên chưa chỉ file, hỏi: file nào, nằm đâu? (nhắc họ gõ @ để
   chọn file hoặc kéo thả).
2. Đọc file. Với CSV lớn, đọc mẫu + đếm dòng bằng lệnh thay vì đọc hết.
3. Trả lời theo khung này, bằng tiếng Việt lời thường:
   - **File này là gì**: một câu, VD "danh sách 3.412 khách hàng kèm email
     và tỉnh thành".
   - **Trong đó có gì**: liệt kê cột/mục chính, dịch tên cột Anh → Việt.
   - **Đáng chú ý**: dòng trùng, ô trống, con số bất thường nếu thấy.
   - Kết bằng: "bạn muốn mình lọc/gom/tìm gì trong file này không?"
4. Nếu file là định dạng đọc khó (xlsx, pdf): tự tìm cách chuyển sang dạng
   đọc được (csv, text) vào folder tạm, nói trước với học viên.
