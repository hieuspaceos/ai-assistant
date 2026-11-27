# Bài 2: Làm một trang web giống trang mẫu bạn thích — với nội dung của mình

> Bài này dạy bạn cách nhờ trợ lý dựng một trang web (landing page) theo
> đúng khuôn của một trang đẹp bạn thấy — việc mà trước giờ phải thuê
> người làm hoặc ngồi vật với Elementor cả ngày.

---

## 1. Tình huống thật

Bạn lướt web thấy landing page của đối thủ — ảnh to, khẩu hiệu bắt, ba ô
ưu điểm gọn gàng, giá nhảy số, nút "Mua ngay" vàng chóe. Nghĩ bụng: *"giá
mà sản phẩm mình cũng có một trang thế này"*. Thuê người làm thì vài triệu
và chờ cả tuần; tự làm thì không biết bắt đầu từ đâu. Sau bài này: bạn đưa
trợ lý cái link trang mẫu + nội dung sản phẩm của bạn, ngồi chờ một lúc là
có trang mở lên xem thử ngay.

## 2. Bạn sẽ có gì sau bài này

- Một file trang web chạy được ngay trên máy bạn, giống trang mẫu về bố
  cục và phong cách — nhưng nội dung là của bạn.
- Biết cách nhờ trợ lý chỉnh tiếp: đổi màu, đổi chữ, thêm mục.
- Biết công thức `/clone-trang` để lần sau thấy trang đẹp là "bắt chước"
  được luôn.

Thời gian: khoảng 15 phút.

## 3. Chuẩn bị

- Một trang mẫu bạn thích: dán link web, hoặc dùng file mẫu đi kèm bài
  `sample-files/trang-mau.html` (landing page của một hãng mỹ phẩm bịa —
  bấm mở xem trước cho quen).
- Nội dung CỦA BẠN — viết nháp sẵn mấy dòng này vào đâu đó:
  - Tên sản phẩm/dịch vụ
  - Một câu giới thiệu ngắn (khẩu hiệu)
  - 2-3 ưu điểm
  - Giá hoặc ưu đãi
  - Chữ trên nút kêu gọi (VD "Đặt ngay", "Gọi tư vấn")

## 4. Nhờ Devin làm — từng bước

### Bước 1: Đưa trang mẫu + nội dung của bạn

Gõ vào khung chat (sửa phần nội dung thành của bạn):

```
Đọc trang workspace/tool-02-trang-giong-trang-mau/sample-files/trang-mau.html rồi dựng cho em một trang web giống về bố cục và phong cách — nhưng nội dung của em: sản phẩm "Trà thảo mộc Thanh Lọc", khẩu hiệu "Ngủ ngon mỗi đêm", ưu điểm là nguyên liệu tự nhiên, không caffeine, đóng gói túi lọc tiện dụng, giá ưu đãi 149.000đ (gạch giá cũ 220.000đ), nút "ĐẶT NGAY". Lưu ra file workspace/trang-cua-em.html rồi mở cho em xem.
```

Điều sẽ xảy ra: trợ lý đọc trang mẫu, phân tích nhịp trình bày (ảnh lớn +
khẩu hiệu → ưu điểm → giá → nút kêu gọi), rồi dựng file trang mới và mở
trên trình duyệt cho bạn xem.

> **Về bản quyền — nói thẳng luôn:** trợ lý chỉ học *khuôn* của trang mẫu
> (cách bày bài, màu sắc, nhịp). Chữ, hình, logo trên trang kết quả là của
> bạn — không mang của họ sang. Copy nguyên trang người khác để đăng lại
> là đụng bản quyền, việc đó mình không làm.

### Bước 2: Chỉnh tới khi vừa ý

Xem trang xong, cứ nhờ tiếp bằng lời thường:

```
Đổi màu chủ đạo thành xanh lá, đổi nút thành "Gọi tư vấn miễn phí", và thêm một mục cảm nhận khách hàng.
```

Trợ lý sửa file và bạn tải lại trang (F5) là thấy bản mới.

### Bước 3 (tuỳ chọn): Dùng trang mẫu trên web thật

Thấy trang đẹp trên mạng? Dán link vào:

```
/clone-trang — trang mẫu là https://link-trang-dep.com, nội dung của em như sau: ...
```

### Cách nhanh — công thức `/clone-trang`

Nhà mình có sẵn công thức cho việc này: gõ `/clone-trang` — trợ lý tự hỏi
bạn trang mẫu ở đâu, nội dung của bạn là gì, rồi làm đúng quy trình: học
khuôn → dựng trang → mở cho xem.

## 5. Kiểm tra kết quả — thấy gì là đúng

- File `trang-cua-em.html` mở trên trình duyệt hiện một trang hoàn chỉnh:
  phần đầu ấn tượng, các ô ưu điểm, giá, nút kêu gọi.
- **Toàn bộ chữ là của bạn** — tìm trong trang không thấy tên/chữ của
  trang mẫu (VD "LUMI Serum").
- Nhịp trình bày giống trang mẫu: cùng trình tự các phần.

Nếu trang trông "xương" không màu mè — kiểm tra file mở đúng chưa, hoặc gõ:
*"trang trông thiếu định dạng, kiểm tra lại giúp em"*

## 6. Kẹt ở đâu thì sao

| Bạn thấy | Nghĩa là | Làm gì |
|---|---|---|
| "không đọc được trang mẫu" | trang đó cần đăng nhập hoặc chặn tải | mở trang trong trình duyệt → Ctrl+S lưu thành file .html → đưa trợ lý file đó |
| nút "Đặt ngay" bấm không được | trang mới chỉ là khung nhìn — chưa có chức năng thật | bình thường — muốn bấm thật thì hỏi mình về bước đưa lên web |
| trang giống mẫu quá, chưa ra bản sắc mình | thiếu nội dung riêng | bổ sung câu chuyện/hình của bạn rồi nhờ trợ lý đưa vào |

Còn nữa thì chụp màn hình dán vào chat (Alt+V trên Windows) và hỏi:
*"bị gì vậy bạn?"*

## 7. Từ mới gặp trong bài

| Từ | Nghĩa theo lời thường |
|---|---|
| landing page | một trang web duy nhất làm cho một mục đích — bán hàng, thu email — như tờ rơi quảng cáo trên mạng |
| bố cục / khuôn trang | cách các phần xếp trên trang: ảnh lớn trước, ưu điểm sau, giá cuối — như khung nhà, còn chữ và hình là nội thất của bạn |
| file .html | tệp trang web — bấm đúp là trình duyệt mở ra xem được |

## 8. Học xong rồi — biết thêm

- Trang làm xong đang nằm trên máy bạn. Muốn người khác vào được bằng link
  thật thì cần đưa lên web — khi sẵn sàng hỏi mình "làm sao đưa trang này
  lên internet".
- Cách này dùng được cho nhiều thứ: trang bán hàng, trang sự kiện, trang
  giới thiệu công ty — cứ thấy khuôn đẹp là "học" được.
