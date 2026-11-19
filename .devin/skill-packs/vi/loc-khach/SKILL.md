---
name: loc-khach
description: Tách một file danh sách khách hàng lớn (Excel/CSV) thành nhiều file riêng theo tỉnh thành — để gửi cho từng bạn sales phụ trách. File gốc giữ nguyên, kết quả vào folder mới.
triggers:
  - user
  - model
allowed-tools:
  - read
  - exec
  - ask_user_question
---

Bạn sắp tách file danh sách khách hàng theo tỉnh cho một người KHÔNG
biết kỹ thuật — họ tuần nào cũng ngồi filter tay mất cả tiếng.
Quy tắc vàng: **KHÔNG đụng file gốc** — luôn xuất ra folder mới.

## Các bước

1. Hỏi bằng lời thường nếu họ chưa nói rõ (dùng ask_user_question):
   - File khách hàng nằm ở đâu? (gợi ý: kéo file thả vào cửa sổ chat,
     hoặc gõ @ rồi chọn file)
   - Cột nào chứa tỉnh thành? Nếu không chắc, đọc vài dòng đầu của file
     rồi đoán, và xác nhận lại với họ: "Mình thấy cột `tinh` — đúng cột
     bạn hay lọc không?"
   - Gửi cho sales dạng file gì? Excel (.xlsx) hay CSV — nếu họ không
     biết thì chọn định dạng GIỐNG file gốc.

2. Nói trước bằng lời thường, VD: *"Mình sẽ đọc file 3.000 dòng, đếm xem
   có bao nhiêu tỉnh, rồi tách ra mỗi tỉnh một file trong folder mới
   `khach-theo-tinh`. File gốc nằm yên không ai đụng. Nhé?"*

3. Thực hiện (ưu tiên Python + pandas/openpyxl nếu có; không thì
   csvkit/awk cho CSV):
   - Đọc file và đếm trong đầu để TỰ kiểm tra — nhưng báo lại cho họ
     NGẮN theo kiểu "kết luận trước": *"Mình thấy file có 3.000 khách,
     tên tỉnh nằm ở cột `tinh`. Có người gõ tên tỉnh nhiều kiểu ('Hà
     Nội', 'Ha Noi'...) nên mình sẽ gom về đúng tỉnh. Được chưa?"*
     KHÔNG liệt kê số khách từng tỉnh hay số cách ghi — chỉ nói chi
     tiết khi có chỗ cần họ quyết định.
   - Chuẩn hoá tên tỉnh khi gom nhóm (VD: "Hà Nội" vs "Ha Noi" vs
     "hà nội" phải về một file — hỏi họ nếu thấy tên lạ).
   - Tên file kết quả: `khach-<tinh-khong-dau-gach-ngang>.xlsx`, VD
     `khach-ha-noi.xlsx`, `khach-tp-ho-chi-minh.xlsx`. Dòng không có tỉnh
     → gom vào `khach-chua-ro-tinh.xlsx`, báo cho họ biết.
   - Tất cả vào folder mới `khach-theo-tinh/` cạnh file gốc. Tuyệt đối
     không ghi đè file gốc.

4. Báo cáo kiểu con người, NGẮN: *"Xong rồi — 3.000 khách thành 12
   file theo tỉnh trong folder `khach-theo-tinh`. Riêng 37 khách chưa
   ghi tỉnh mình để riêng file `khach-chua-ro-tinh` nhé."* Không kèm
   bảng đếm từng tỉnh trừ khi họ hỏi. Mở folder kết quả cho họ xem
   (`open <folder>` trên macOS, `explorer <folder>` trên Windows).

5. Nhắc nhẹ: *"Tuần sau cứ gõ `/loc-khach` rồi chỉ file mới — mình làm
   y chang."*
