# Phase 03 — `doc-zalo`: xác minh đúng người trước khi gửi + xác nhận Đã gửi

## Lý do

Skill `doc-zalo` hiện: soạn → đọc lại bản nháp qua screenshot → hỏi
học viên → bấm Gửi. Hai lỗ hổng còn lại:

1. **Gửi nhầm hội thoại**: click theo chữ trong list ảo hoá có thể
   trượt (Zalo render lại giữa chừng) — hội thoại mở ra không phải
   người định gửi mà vẫn hỏi "gửi tin này tới X?" → học viên tin
   bản nháp, không nhìn header.
2. **Bấm Gửi xong không kiểm**: Zalo nuốt click (isTrusted), tin vẫn
   nằm trong ô soạn — báo "đã gửi xong" là nói sai.

Cả hai đều là lỗi **không undo được** — phải chặn trước, không phải
sửa sau.

## Thay đổi `.devin/skills/doc-zalo/SKILL.md`

### Bước mới trong mục "Soạn và gửi tin trả lời"

Chèn TRƯỚC bước "Được đồng ý → bấm Gửi" (giữa soạn-nháp và gửi):

```markdown
3b. **Kiểm đúng người nhận — bắt buộc, không bỏ qua.** Trước khi
    hỏi học viên duyệt gửi, đọc tên trên header khung chat:
    `query` với `sel` = `[class*=header]`/`[class*=title]` (vùng đầu
    khung hội thoại) → so sánh với tên học viên yêu cầu:
    - Khớp → tiếp bước hỏi duyệt như cũ.
    - KHÔNG khớp → DỪNG, đóng/thoát soạn thảo, báo: *"khung chat đang
      mở là <tên khác>, không phải <tên bạn yêu cầu> — mình chưa gửi
      gì, mở lại đúng hội thoại nhé"* rồi làm lại từ bước chọn hội
      thoại.
    - Không đọc được header → `screenshot` kiểm bằng mắt; vẫn không
      chắc → báo học viên, KHÔNG gửi.
```

Và sau bước bấm Gửi:

```markdown
4b. **Kiểm tin đã đi thật.** Sau khi bấm Gửi (click/tclick):
    - `query` ô `#richInput` → phải RỖNG (tin đã đi, soạn thảo dọn
      sạch); và/hoặc `query [class*=chat-message]` cuối → tin cuối
      đúng nội dung vừa gửi, kèm trạng thái gửi (icon tick/đã gửi)
      nếu DOM expose.
    - Ô nhập vẫn còn chữ → tin CHƯA đi (Zalo nuốt click) → thử
      `tclick` lại một lần; vẫn còn → báo học viên *"mình bấm Gửi
      nhưng Zalo chưa nhận — bạn bấm tay giúp mình nút mũi tên nhé"*,
      KHÔNG báo "đã gửi xong".
```

### Cập nhật "Luật an toàn Zalo"

Thêm dòng:

```markdown
- **Không bấm Gửi khi header khung chat không khớp tên người/nhóm
  học viên chỉ định** — kể cả khi đã được đồng ý nội dung; duyệt cho
  đúng nội dung + đúng người, không phải duyệt mù.
```

## (Optional) primitive hỗ trợ ở `tools/ext-bridge.py` + extension

Nếu `query` selector `[class*=header]` hay trượt vì Zalo đổi class —
thêm action nhỏ `chat_header` (đọc `aria-label`/text vùng header bằng
semantic anchor: `role=banner`/`heading` + vị trí top của khung chat).
**Chỉ làm nếu đường query thường trượt trong thực tế** — không viết
primitive cứng trước (đúng bài học "class ngẫu nhiên" của chính báo
cáo).

## Test

- Tay trên VM/dev: mở hội thoại A, cố gửi cho B → skill phải dừng ở
  3b với card "khung chat đang mở là B".
- Nuốt click giả lập: chặn `tclick` → 4b phải báo "chưa gửi được",
  không được nói "đã gửi xong".
- Review lại SKILL.md sau sửa: luồng cũ (search → chọn → đọc → soạn
  → hỏi → gửi) vẫn nguyên, chỉ thêm 2 gate.
