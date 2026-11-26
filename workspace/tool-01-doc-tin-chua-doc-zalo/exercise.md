# Bài tập — Bài 1: Đọc hết tin chưa đọc trên Zalo

## Tình huống

Sáng vào việc, Zalo sáng đèn chấm đỏ. Trước khi pha cà phê, bạn muốn biết:
có bao nhiêu người đang chờ, ai là khách cần trả lời gấp, ai để sau được.

## Bạn cần làm

1. Nhờ trợ lý liệt kê hết hội thoại có tin chưa đọc trên Zalo Web của bạn
   (hoặc file mô phỏng nếu Zalo chưa sẵn sàng).
2. Chọn MỘT hội thoại đáng chú ý nhất, nhờ trợ lý đọc và tóm tắt họ cần gì.
3. Nói lại được bằng miệng: bạn sẽ trả lời ai trước, vì sao.

File đầu vào (nếu luyện mô phỏng): `sample-files/zalo-hop-thu-demo.txt`
(12 hội thoại giả lập, trong đó 6 cái có tin chưa đọc)

## Làm bằng cách nhờ Devin

Tự viết lời nhờ của bạn trước. Kẹt quá mới xem gợi ý dưới:

<details>
<summary>Gợi ý prompt (bấm để xem)</summary>

Với Zalo thật:

```
/doc-zalo — liệt kê hết hội thoại có tin chưa đọc, kèm xem trước nội dung.
```

Với file mô phỏng:

```
Đọc file workspace/tool-01-doc-tin-chua-doc-zalo/sample-files/zalo-hop-thu-demo.txt, liệt kê các hội thoại có tin chưa đọc kèm xem trước nội dung, rồi gợi ý em nên trả lời ai trước.
```

</details>

## Tự chấm — tích đủ là xong

- [ ] Trợ lý liệt kê được các hội thoại chưa đọc (bản mô phỏng: **6 hội
  thoại** — chị Hương, nhóm Marketing, khách Minh, khách Loan, nhóm KH VIP,
  khách Phúc)
- [ ] Mỗi hội thoại có kèm xem trước nội dung, không chỉ tên
- [ ] Bạn đọc sâu được một hội thoại và biết người đó cần gì
- [ ] Bạn tự nói được ai nên trả lời trước (gợi ý: khách Phúc đang khiếu
  nại đơn 3 ngày chưa thấy — thường là ưu tiên)

Không biết chấm bằng mắt? Hỏi Devin: *"kiểm tra giúp em kết quả đạt chưa"*

## Đáp án tham khảo

<details>
<summary>Xem đáp án</summary>

Bản mô phỏng có 6 hội thoại chưa đọc. Hai cái đáng trả lời trước là
**khách Phúc** (khiếu nại đơn 3 ngày chưa thấy — khách đang bực) và
**khách Loan** (xin đổi lịch xem sang thứ 7 — cần xác nhận trước cuối
tuần). Các hội thoại còn lại: chị Hương hỏi giá, khách Minh hỏi ship tỉnh,
nhóm Marketing và nhóm KH VIP thì đọc sau cũng được.

</details>

## Làm xong rồi?

Thử biến tấu: nhờ trợ lý "soạn giúp em tin trả lời cho một người trong
danh sách" — nhớ nó sẽ hỏi bạn trước khi gửi, bạn cứ bảo "chỉ soạn nháp
thôi" nếu chưa muốn gửi.
