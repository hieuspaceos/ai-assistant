# Bài 1: Mở Zalo cái là biết ngay ai đang chờ — đọc hết tin chưa đọc trong 30 giây

> Bài này dạy bạn cách nhờ trợ lý lật hết hộp thư Zalo và kể lại ai đang
> nhắn mình — việc mà trước giờ mỗi sáng bạn phải bấm vào từng hội thoại
> một để xem có gì mới.

---

## 1. Tình huống thật

Sáng mở Zalo lên, thấy chấm đỏ khắp nơi — mười mấy hội thoại có tin chưa
đọc. Muốn biết khách nào cần trả lời gấp, bạn phải bấm vào từng cái, đọc,
rồi nhớ trong đầu "cái này gấp, cái kia để sau". Trong đống đó có cả nhóm
chat, tin quảng cáo, tin gia đình — lọc ra khách thật cũng mất một lúc.
Sau bài này: một câu nhờ, trợ lý lật hết hộp thư và kể lại cho bạn nghe
ai đang chờ, mỗi người cần gì — bạn chỉ việc quyết trả lời ai trước.

## 2. Bạn sẽ có gì sau bài này

- Danh sách gọn mọi hội thoại đang có tin chưa đọc, kèm xem trước nội dung.
- Biết ai cần trả lời trước mà không phải bấm từng hội thoại.
- Biết công thức `/doc-zalo` để mỗi sáng gõ một lệnh là xong.

Thời gian: khoảng 10 phút.

## 3. Chuẩn bị

- Zalo Web đã mở và đăng nhập sẵn trên trình duyệt của bạn (nhà mình đã
  kết nối sẵn). Nếu chưa mở, trợ lý sẽ mở giúp — nó hỏi bạn quét mã QR
  bằng Zalo trên điện thoại thì quét, chỉ cần một lần.
- **Chưa có Zalo Web hoặc hôm nay hộp thư trống?** Không sao — bài này có
  file mô phỏng `sample-files/zalo-hop-thu-demo.txt`, luyện trên đó trước
  rồi áp vào Zalo thật sau.

## 4. Nhờ Devin làm — từng bước

### Bước 1: Nhờ trợ lý lật hộp thư

Gõ vào khung chat:

```
Mở Zalo Web của em, liệt kê hết các hội thoại đang có tin chưa đọc — kèm xem trước nội dung mỗi hội thoại.
```

Điều sẽ xảy ra: trợ lý mở Zalo trên trình duyệt của bạn, bấm vào tab
"Chưa đọc", cuộn hết danh sách, rồi kể lại bằng lời thường — kiểu *"có 5
hội thoại đang chờ: chị Hương hỏi giá, nhóm Marketing đang bàn banner,
khách Loan xin đổi lịch..."*

> **Yên tâm: trợ lý chỉ ĐỌC, không tự trả lời ai hết.** Muốn nó soạn và
> gửi tin thì phải nhờ riêng — và nó luôn hỏi bạn trước khi gửi.

**Luyện trên file mô phỏng trước** (nếu Zalo chưa sẵn sàng), gõ:

```
Đọc file workspace/tool-01-doc-tin-chua-doc-zalo/sample-files/zalo-hop-thu-demo.txt rồi liệt kê giúp em những hội thoại nào có tin chưa đọc, kèm xem trước nội dung.
```

### Bước 2: Đào sâu vào một hội thoại

Thấy tên ai đáng chú ý trong danh sách? Hỏi tiếp:

```
Đọc giúp em mấy tin gần nhất của hội thoại với <tên người>, tóm tắt xem họ cần gì.
```

Trợ lý sẽ mở đúng hội thoại đó, đọc tin gần nhất và tóm tắt — kiểu
*"khách Loan muốn đổi lịch xem nhà sang thứ 7, đang chờ bạn xác nhận"*.

### Cách nhanh — công thức `/doc-zalo`

Nhà mình có sẵn công thức cho việc này: gõ `/doc-zalo` — trợ lý tự làm
đúng quy trình: kiểm tra Zalo đã mở chưa → lật tab Chưa đọc → kể lại ai
đang chờ. Sáng nào mở máy cũng gõ một lệnh là biết tình hình hộp thư.

## 5. Kiểm tra kết quả — thấy gì là đúng

- Trợ lý trả lời bằng danh sách ngắn gọn: tên hội thoại + xem trước nội
  dung, bắt đầu kiểu *"có X hội thoại đang chờ..."*
- Số lượng hội thoại nó liệt kê khớp với số chấm đỏ bạn thấy trên Zalo.
- Nó không tự trả lời ai — chỉ đọc và kể lại.

Nếu nó nói "không mở được Zalo", gõ tiếp: *"mở Zalo Web giúp em, xong
nhắc em nếu cần quét mã đăng nhập"*

## 6. Kẹt ở đâu thì sao

| Bạn thấy | Nghĩa là | Làm gì |
|---|---|---|
| "Zalo chưa đăng nhập / có mã QR" | Zalo Web cần đăng nhập | quét mã QR bằng app Zalo trên điện thoại, xong bảo "ok rồi" để trợ lý làm tiếp |
| danh sách ít hơn số tin chưa đọc bạn thấy | Zalo đang hiện mục "Đã ghim" hoặc lọc khác | gõ "kiểm tra lại cả mục Đã ghim nữa giúp em" |
| trợ lý kể sai một hội thoại | tin mới vừa tới trong lúc đọc | gõ "đọc lại hộp thư lần nữa giúp em" |

Còn nữa thì chụp màn hình dán vào chat (Alt+V trên Windows) và hỏi:
*"bị gì vậy bạn?"*

## 7. Từ mới gặp trong bài

| Từ | Nghĩa theo lời thường |
|---|---|
| Zalo Web | Zalo chạy trên trình duyệt máy tính — trợ lý đọc được hộ bạn vì nó "nhìn" được trang này |
| hội thoại chưa đọc | các cuộc chat có chấm đỏ — người ta nhắn mà bạn chưa mở ra xem |
| connector / kết nối | cầu nối sẵn giữa trợ lý và Zalo Web — nhờ nó mà trợ lý mở được trang cho bạn |

## 8. Học xong rồi — biết thêm

- Sau khi biết ai đang chờ, bạn có thể nhờ tiếp: *"soạn giúp em tin trả
  lời khách Loan"* — trợ lý sẽ đọc ngữ cảnh rồi soạn nháp, và LUÔN hỏi
  bạn trước khi gửi.
- Có khách hay gửi file đơn hàng qua Zalo? Trợ lý lấy được luôn file
  đính kèm về máy cho bạn — cứ nhờ.
