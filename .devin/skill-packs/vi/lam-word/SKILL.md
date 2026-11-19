---
name: lam-word
description: Điền template và format file Word .docx bằng python-docx — thay placeholder, điền bảng, hàng loạt từ dữ liệu. File gốc giữ nguyên, kết quả ra file mới.
triggers:
  - user
  - model
allowed-tools:
  - read
  - exec
  - ask_user_question
---

Tạo/sửa file `.docx` cho người không biết kỹ thuật bằng Python
`python-docx`. Quy tắc vàng: **KHÔNG ghi đè file gốc/template** — kết quả
luôn ra file mới.

## Kiểm tra tool (lần đầu)

```bash
python3 -c "import docx"  # Windows: py -c "import docx"
```

Thiếu → `pip install -r requirements.txt` (đã kèm `python-docx`).

## Việc chính: điền template hàng loạt

Kịch bản thật: học viên có mẫu hợp đồng/thư mời `.docx` với chỗ trống
kiểu `{{ten}}`, `{{ngay}}` + một file Excel danh sách người nhận → sinh
hàng loạt file `.docx` điền sẵn.

1. Hỏi: file mẫu ở đâu, dữ liệu điền ở đâu (Excel/CSV), tên file kết quả
   đặt kiểu gì (gợi ý: theo tên người nhận `thu-moi-<ten>.docx`).
2. Đọc template: duyệt `doc.paragraphs` + `doc.tables` (mỗi `table.rows`
   → `row.cells` → `cell.paragraphs`) tìm placeholder `{{...}}`. **Liệt kê
   placeholder tìm được cho học viên xác nhận** — thường có chỗ gõ nhầm.
3. Đọc dữ liệu (Excel qua openpyxl, CSV qua `csv` stdlib).
4. Với mỗi dòng dữ liệu: load template mới → replace text trong từng
   `run` (placeholder nằm trong một run thì thay trực tiếp; bị cắt qua
   nhiều run thì gom paragraph text, thay, gán lại run đầu).
5. Ghi `output/<ten>.docx` cho từng dòng — folder mới, không đụng mẫu.
6. Báo: *"xong — 25 file thư mời trong folder `thu-moi`, mỗi file điền
   đúng tên/ngày"*. Mở folder cho họ xem.

## Việc khác

- **Đọc nội dung**: duyệt paragraphs + tables → text (hỗ trợ `/tom-tat-file`
  cho .docx).
- **Format**: `run.bold`, `font.size`, `paragraph.alignment`, style
  `Heading 1`... — chỉnh format theo mẫu học viên đưa.
- **Tạo bảng**: `doc.add_table(rows, cols)` + điền cell.

## Lưu ý

- `.doc` cũ (không phải `.docx`): `python-docx` không đọc — nhờ học viên
  Save As .docx một lần.
- Textbox, header/footer, comment: `python-docx` hỗ trợ hạn chế — nếu
  template có, kiểm tra kết quả trên bản copy và báo học viên phần không
  điền được.
- Ảnh trong template được giữ nguyên; chèn ảnh mới dùng
  `doc.add_picture(path, width=Cm(n))`.
