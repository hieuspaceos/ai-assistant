---
name: lam-excel
description: Đọc/ghi/lọc/gộp/format file Excel .xlsx bằng openpyxl — file gốc giữ nguyên, kết quả ra file mới. Dùng khi học viên cần sửa bảng Excel mà không mở Excel tay.
triggers:
  - user
  - model
allowed-tools:
  - read
  - exec
  - ask_user_question
---

Xử lý file `.xlsx` cho người không biết kỹ thuật bằng Python `openpyxl`.
Quy tắc vàng: **KHÔNG ghi đè file gốc** — đọc file gốc, ghi ra file mới
(`<tên>-moi.xlsx` hoặc folder kết quả).

## Kiểm tra tool (lần đầu)

```bash
python3 -c "import openpyxl"  # Windows: py -c "import openpyxl"
```

Thiếu → `pip install -r requirements.txt` (đã kèm `openpyxl` trong repo).
Cần cài thì nói trước: *"mình cần cài một gói Python nhỏ để đọc Excel —
khoảng 30 giây"*.

## Các việc hay làm

| Việc | Cách |
|---|---|
| Đọc/xem nội dung | `load_workbook(file, data_only=True)` → duyệt sheet/row |
| Lọc dòng | duyệt `iter_rows`, giữ dòng khớp điều kiện → ghi workbook mới |
| Gộp nhiều file | đọc từng file → append row vào workbook đích (giữ header lần đầu) |
| Tách theo cột | nhóm theo giá trị cột → mỗi nhóm một file (xem `/loc-khach`) |
| Đổi format | `cell.font`, `cell.fill`, `column_dimensions[w].width`, freeze `freeze_panes` |
| Thêm sheet | `wb.create_sheet(tên)` |

## Các bước chuẩn

1. Hỏi rõ: file nào, làm gì, kết quả mong muốn. File lớn thì đọc mẫu
   vài dòng đầu xác nhận cấu trúc với học viên trước.
2. Nói trước bằng lời thường: *"mình sẽ đọc file X, làm Y, ghi ra file
   mới Z — file gốc không đụng. Nhé?"*
3. Thực hiện bằng script Python trong folder làm việc (không ghi script
   lộn xộn — viết vào `my-course/` hoặc folder bài đang làm).
4. Kiểm tra lại file kết quả (đếm dòng, đọc vài dòng mẫu) trước khi báo.
5. Báo NGẮN kiểu con người: *"xong — 3.000 dòng lọc còn 412 trong
   `khach-ha-noi-moi.xlsx`"*. Mở folder kết quả cho họ xem.

## Lưu ý

- File `.xls` cũ: `openpyxl` không đọc — chuyển qua `pandas + xlrd` hoặc
  nhờ học viên Save As .xlsx một lần.
- Công thức: `data_only=True` lấy giá trị đã tính (file phải từng mở bằng
  Excel để cache giá trị); file chưa mở → giá trị `None`, báo học viên.
- Format phức tạp (merged cells, chart, ảnh nhúng): `openpyxl` giữ phần
  lớn nhưng không tuyệt đối — file quan trọng thì copy gốc rồi thử trên
  bản copy, cho học viên mở kiểm tra.
