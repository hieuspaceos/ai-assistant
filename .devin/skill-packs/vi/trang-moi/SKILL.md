---
name: trang-moi
description: Thêm một trang chi tiết mới (bài blog, tour, sản phẩm…) vào site đã clone — nhân bản trang mẫu data-cs-template, đổ nội dung của học viên vào, tự gắn card lên trang danh sách. Dùng khi học viên muốn "viết thêm bài", "thêm tour", "thêm sản phẩm" vào trang clone.
triggers:
  - user
  - model
allowed-tools:
  - read
  - exec
  - write
  - ask_user_question
---

Site clone (do `/clone-trang` sinh) đã có sẵn "khuôn" trang chi tiết —
`<div data-cs-page="/blog/<slug>" data-cs-template="post">`. Skill này
nhân bản khuôn đó thành trang mới chứa nội dung của học viên. Nói với
họ kiểu: *"trang mẫu đã có sẵn, mình chỉ cần nhân bản nó ra rồi thay
chữ của bạn vào"*. Toàn bộ thao tác là đọc/ghi file `.html` — dùng
python qua exec cho chính xác.

## Các bước

### 1. Hỏi đủ, không đoán

Hỏi (gom một lần, dùng ask_user_question nếu được):

- **Site nào**: quét mọi `my-course/*.html`, đếm file có
  `data-cs-template`. Chỉ 1 file → dùng luôn, không cần hỏi. NHIỀU
  file (học viên clone nhiều site) → **bắt buộc hỏi** "thêm vào site
  nào?" kèm danh sách tên site — tuyệt đối không đoán, vì nhầm site
  là hỏng bài của site khác. Nếu lời nhờ đã nói rõ tên site thì khớp
  theo tên, khỏi hỏi. Không file nào có template → báo thẳng, gợi ý
  clone lại bằng `/clone-trang` chuẩn mới.
- **Loại trang**: mở file trước, liệt kê các `data-cs-template` hiện
  có (`post`, `tour`, `product`, `recipe`… — từ vựng mở, tùy site).
  Nhiều loại → hỏi họ muốn thêm loại nào; không có loại họ cần →
  báo thẳng và gợi ý clone thêm trang mẫu loại đó trước.
- **Tiêu đề** trang mới → suy slug: chữ thường không dấu, nối bằng
  `-` (bỏ dấu tiếng Việt, ký tự lạ → `-`). Cho họ xác nhận slug.
- **Nội dung chính**: mô tả ngắn (excerpt), thân bài (vài đoạn), ảnh
  (link hoặc file trong `my-course/` — họ gửi sau cũng được, để
  placeholder).

### 2. Nhân bản trang mẫu

- Đọc file clone. Tìm `<div data-cs-page="…" data-cs-template="LOẠI">`.
  Không có → báo học viên file này chưa clone theo chuẩn mới, gợi ý
  clone lại hoặc nhân bản tay trang gần giống nhất.
- Copy nguyên khối `<div data-cs-page>` đó (đến `</div>` khớp —
  đếm thẻ div lồng nếu cần), **bỏ `data-cs-template`**, đổi
  `data-cs-page` thành `<tiền tố route>/<slug>` — tiền tố là phần
  route cha của trang mẫu (`/ban-can-biet/x` → `/ban-can-biet`).
- Chèn bản mới ngay SAU khối mẫu (trước khi trang kế tiếp bắt đầu).

### 3. Đổ nội dung vào bản mới

Trong KHỐI MỚI (không đụng template):

- `data-cs-text` trên `h1/h2/h3` → tiêu đề mới; trên `p` đầu →
  excerpt; các `p` thân → thân bài.
- `data-cs-img` / khối `.media` caption → ảnh + caption mới (chưa có
  ảnh thì giữ placeholder + nhắc họ thay).
- Ngày tháng (`.tac-card-body .tac-small` hoặc tương đương) → hôm nay.
- Câu nào không map được marker → sửa thẳng text node trong khối
  mới, giữ nguyên class/style.

### 4. Gắn card lên trang danh sách

- Tìm `data-cs-page` của trang cha (route tiền tố). Trong grid danh
  sách, copy `<a class="card…">` (hoặc `tac-card--link`) đầu tiên.
- Sửa bản copy: `href` → `#<data-cs-page mới>` (định dạng link y hệt
  site: `#/route/slug`), caption/title → tiêu đề, date → hôm nay,
  excerpt → mô tả ngắn.
- Chèn card ĐỨNG ĐẦU grid (bài mới nhất lên trước), trừ khi họ nói khác.

### 5. Kiểm chứng tĩnh TRƯỚC khi giao

Chèn xong, kiểm ngay bằng script — không tin mắt:

- Đếm `data-cs-template="<loại>"` trong file → vẫn đúng SỐ CŨ (bản
  mới không được mang marker).
- `data-cs-page="<route-mới>"` tồn tại đúng 1 lần.
- Card đầu tiên của grid trang cha trỏ đúng route mới (trừ khi họ
  nói chèn chỗ khác).
- Route mới khớp router: nằm trong `<main>`, có `hidden` ban đầu
  nếu không phải trang mặc định.

### 6. Giao

- Mở viewer:
  `http://localhost:8080/web/clone-view.html?src=/my-course/<file>.html`
  → bấm route mới trong menu (hoặc gõ hash `#/route/slug`) → thấy
  trang mới render đúng khung.
- Báo ngắn: *"xong — bài mới đã có trang riêng và card trên trang
  Tin tức. Bấm Sửa nội dung để chỉnh tiếp nhé."*

## Giới hạn

- Không đụng `data-cs-template` của trang mẫu — mất khuôn thì lần
  sau không nhân bản được nữa.
- Form/route đặc biệt của site (vd đặt tour có ngày giá) thì clone
  đúng khối form của template, nội dung hỏi học viên.
