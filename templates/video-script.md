<!--
TEMPLATE KỊCH BẢN VIDEO — mỗi bài 1 file, dùng để quay video kiểu Khan
Academy (màn hình + giọng đọc) hoặc cho subagent video-builder tự render.

Cấu trúc mỗi đoạn:
- THOẠI: đúng câu người đọc sẽ nói — viết y chang lời nói, không văn viết.
- MÀN HÌNH: mô tả chính xác cái người xem thấy trên màn hình lúc đó.
- THỜI LƯỢNG gợi ý mỗi đoạn.

Quy tắc: thoại ELI10, câu ngắn. Mỗi khi có thao tác, thoại phải nói TRƯỚC
thao tác xảy ra 1-2 giây để người xem kịp nhìn.
-->

# Kịch bản video — Bài {{lesson_no}}: {{lesson_name}}

**Độ dài mục tiêu:** {{x}} phút · **Format:** quay màn hình + giọng đọc
**Setup quay:** mở sẵn terminal ở folder bài học + folder file bên cạnh (chia
đôi màn hình), zoom chữ to, ẩn desktop lộn xộn.

---

## Đoạn 1 — Mở đầu (~{{t1}} giây)

**THOẠI:**
> "{{greeting}} — VD: Có bao giờ bạn nhận được một cục file mà nhìn vào chỉ
> muốn thở dài không? Hôm nay mình cho Devin lo việc đó trong hai phút."

**MÀN HÌNH:** Slide tiêu đề bài học (`slides.html` trang 1). Chưa gõ gì.

## Đoạn 2 — Nỗi đau (~{{t2}} giây)

**THOẠI:**
> "{{pain_story}}"

**MÀN HÌNH:** Quay folder/file thật đang bừa bộn — {{scene_desc}}. Dùng chuột
chỉ vào thứ đang nói tới.

## Đoạn 3 — Nhờ Devin (phần chính, ~{{t3}} giây)

**THOẠI:**
> "{{pre_typing_note}} Giờ mình gõ câu này..."

**MÀN HÌNH:** Gõ chậm prompt vào Devin:
```
{{prompt_sample}}
```
Để Devin chạy thật trên màn hình — KHÔNG cắt. Khi nó hỏi xác nhận, dừng chuột
lên nút đó và đọc to cho người xem nghe.

**THOẠI (lúc nó hỏi duyệt):**
> "Thấy không — nó hỏi trước khi làm. Mình đọc thử: {{cmd_plain}}.
> Đúng rồi, mình cho phép."

## Đoạn 4 — Kết quả (~{{t4}} giây)

**THOẠI:**
> "{{result_comment}} — so sánh lúc nãy nhé."

**MÀN HÌNH:** Trước/sau cạnh nhau — {{before_after_desc}}.

## Đoạn 5 — Chốt + giao bài tập (~{{t5}} giây)

**THOẠI:**
> "Vậy là xong. Bài tập của bạn nằm trong file exercise.md — thử làm đi, kẹt
> thì hỏi Devin như hỏi mình."

**MÀN HÌNH:** Slide cuối: tóm tắt 3 ý + nhắc file bài tập.

---

## Checklist trước khi quay

- [ ] Chạy thử toàn bộ prompt 1 lần — video không được có lỗi bất ngờ
- [ ] Font terminal to (Ctrl+= vài lần)
- [ ] Thoại đọc thử to — câu nào vướng thì viết lại ngắn hơn
