---
name: cap-nhat-sheet
description: Đọc và cập nhật Google Sheets — đọc qua gviz CSV bằng phiên đăng nhập, ghi lẻ qua sự kiện thật (t-insert), ghi hàng loạt qua MCP hoặc export file nộp lại. Dùng khi học viên cần xử lý dữ liệu trên sheet online.
triggers:
  - user
  - model
allowed-tools:
  - read
  - exec
  - ask_user_question
---

Xử lý Google Sheets cho người không biết kỹ thuật. Hai đường, chọn theo
việc:

## Đường A — chỉ ĐỌC

**Sheet "bất kỳ ai có link đều xem"** → tải trực tiếp dạng CSV:

```
curl -sL "https://docs.google.com/spreadsheets/d/<SHEET_ID>/export?format=csv&gid=<GID>" -o sheet.csv
```

**Sheet private (đa số — sheet công ty)** → đọc qua tab trình duyệt đang
đăng nhập Google của học viên, không cần share link:

1. `{"action":"tabs"}` qua ext-bridge :7684 → tìm tab `docs.google.com`;
   chưa có thì `{"action":"open","url":"https://docs.google.com/spreadsheets/"}`
   (học viên đăng nhập sẵn rồi, chỉ đợi trang nạp).
2. Tải CSV của sheet bằng phiên trong tab đó:

```
{"action":"fetch","tabId":ID,
 "url":"https://docs.google.com/spreadsheets/d/<SHEET_ID>/gviz/tq?tqx=out:csv&gid=<GID>"}
```

   Dùng endpoint `gviz` — `/export` redirect sang domain khác bị chặn.
   Kết quả `text` là CSV → ghi ra file rồi xử lý.

Sau đó xử lý như CSV thường (`/tom-tat-file`, `/loc-khach`, `/lam-excel`).
SHEET_ID lấy từ link học viên dán; GID = tab (mặc định 0).

## Đường B — GHI qua sự kiện THẬT (đã kiểm chứng, không cần MCP)

Grid của Sheets render bằng canvas và CHỈ nhận sự kiện thật — synthetic
`type`/`paste`/`key` không commit được. Nhưng nhóm `t*` (CDP trusted
input) GHI ĐƯỢC — đã verify: chữ "troly" commit vào ô Z100.

Quy trình ghi một ô (vd ghi "abc" vào C5):

1. `ttype` `sel='#t-name-box'` `text='C5'` → click thật + gõ địa chỉ.
   (name box là input thường — `ttype` chắc ăn hơn `type` giả.)
2. `tkey` `key=Enter` → grid nhảy tới ô C5. Kiểm chứng:
   `query sel='#t-name-box' attr=value` phải trả `C5`.
3. `tinsert` `text='abc'` `mode='char'` → bắn phím thật từng ký tự —
   grid mở chế độ edit và nhận chữ. KHÔNG dùng mode ime (insertText)
   vì canvas không có editable để nhận.
4. `tkey` `key=Enter` → commit ô (xuống ô dưới). Tab = sang ô phải,
   Escape = hủy nháp.
5. Verify lại bằng đường A: gviz `range=C5:C5&gid=...` — lưu ý range
   phải tường minh dạng `C5:C5`, chỉ `C5` có thể trả rỗng.
6. Xong thì `tdetach` tắt banner gỡ lỗi.

Giới hạn: gõ theo ký tự nên CHẬM (~35ms/chữ + độ trễ mạng) — hợp ghi
vài ô/vài dòng. Ghi hàng loạt (cả bảng) → đường B1/C nhanh và chắc hơn.
Nhóm `t*` đưa tab lên trước — báo học viên trước khi chạy.

### Đường B1 — ghi hàng loạt qua MCP google-sheets

1. Đọc `my-course/connections.json` → app `google-sheets`; hoặc
   `POST /api/check-connection` `{"id":"google-sheets"}`.
2. Chưa kết nối → hướng dẫn: `devin mcp` cài server google-sheets vào
   `.devin/mcp_config.local.json` + OAuth đăng nhập Google (lần đầu trợ
   lý dẫn từng bước, học viên chỉ bấm đồng ý trên trình duyệt).
3. Kết nối rồi thì ghi qua tool MCP tương ứng (đọc/ghi range, append row).

## Đường C — không cài MCP: sửa rồi nộp lại

Đọc CSV (đường A) → xử lý → xuất `.xlsx`/`.csv` mới trong folder kết quả
→ học viên mở sheet dán lại / File → Import. Chậm hơn nhưng không cần
đăng nhập gì.

## Luật

- Sheet công ty thường KHÔNG share public — đường A báo lỗi 403/login
  page → bảo học viên share link "người có link xem được" hoặc đi đường
  B/C. Không hỏi mật khẩu Google.
- Ghi vào sheet dùng chung của cả team: báo trước rõ vùng sẽ ghi
  (sheet nào, range nào), đồng ý mới ghi.
