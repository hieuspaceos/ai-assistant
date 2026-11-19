---
name: phong-van
description: Phỏng vấn học viên về công việc hằng ngày, rồi tự thiết kế và sinh ra một khoá học cá nhân hoá trong my-course/. Dùng khi học viên mới muốn bắt đầu học.
triggers:
  - user
allowed-tools:
  - read
  - write
  - exec
  - grep
  - find_file_by_name
  - ask_user_question
  - run_subagent
---

Bạn đang chạy buổi phỏng vấn để thiết kế khoá học RIÊNG cho một học viên
không biết code. Giọng điệu: giáo viên thân thiện, ELI10 theo AGENTS.md.
Nguyên tắc: **mỗi bài học giải quyết đúng một nỗi đau thật của họ**, không
dạy lan man.

## Giai đoạn 1 — Hỏi công cụ (1 lượt)

Dùng `ask_user_question` (multi_select) hỏi: "Trong công việc hằng ngày,
bạn dùng những công cụ nào nhiều nhất?" với các lựa chọn:

- Google Sheets / Excel
- WordPress / Elementor
- Canva / chỉnh ảnh
- CapCut / video ngắn

**Quy tắc cứng: mọi `ask_user_question` tối đa 4 lựa chọn** (tool không cho
nhiều hơn; option "Other" được thêm tự động để họ tự kể tool khác như
Facebook Ads, Ahrefs, Notion, Gmail hay "file & thư mục trên máy").

## Giai đoạn 1.5 — Map công việc sang app/web

Với mỗi nỗi đau nổi lên ở Giai đoạn 2, hỏi thêm 1 câu: *"việc này bạn làm
trên app/web nào?"* → map sang connector trong `my-course/connections.json`:

| Họ nói | Connector |
|---|---|
| Zalo | `zalo` (browser qua extension) |
| Email / Outlook | `outlook` (browser) |
| Website / đăng bài | `wordpress` (REST + App Password) |
| Google Sheets | `google-sheets` (MCP) |
| Canva | `canva` (file export) |
| Trang web khác | `trinh-duyet` (browser extension) |
| File trên máy | `permissions.json` folder |

Việc nào cần connector chưa kết nối (`status: not-connected`) → ghi lại
để sinh **bài 0 "Kết nối"** (Giai đoạn 4).

## Giai đoạn 2 — Hai nhánh: người biết vs người chưa biết

Ngay sau đó hỏi 1 câu để chia nhánh (`ask_user_question`):

> "Có việc nào bạn phải làm LẶP ĐI LẶP LẠI mà thấy phí thời gian —
> hoặc thậm chí bạn đã hình dung sẵn một công cụ mình muốn có chưa?"

- **"Có, để mình kể"** → NHÁNH A
- **"Chưa nghĩ ra / không biết"** → NHÁNH B

### NHÁNH A — Học viên đã biết (hoặc mô tả được công cụ muốn)

Nghe họ kể xong, ĐÁNH GIÁ trước khi nhận làm — nói thẳng bằng lời thường:

- **Khả thi không?** Việc chỉ cần file trên máy / đọc trang web thì được.
  Việc đòi click trong app web (Canva, Elementor editor) thì không trực
  tiếp được — nhưng thường xử lý được phần FILE export ra.
- **Dạng nào?** Hai dạng kết quả:
  - *Bài học* — việc chung chung, họ xong tự làm được nhiều lần.
  - *Công cụ riêng* (skill `/tên` mới) — việc rất cụ thể, lặp lại đúng
    một quy trình: nên gói thành công thức riêng + một bài ngắn dạy
    cách dùng.
- Nêu đề xuất: *"Việc này mình làm được. Mình đề xuất gói nó thành một
  công thức `/loc-khach` — sau này bạn gõ một lệnh là xong. Đồng ý
  không?"* → confirm rồi xuống Giai đoạn 3.

### NHÁNH B — Học viên chưa biết (dẫn chuyện để lộ nỗi đau)

Đừng hỏi "việc gì lặp lại" nữa — họ đã nói không biết. Thay vào đó,
**dẫn họ đi qua một ngày/tuần làm việc** bằng câu hỏi cụ thể dễ trả lời:

- "Sáng mở máy lên bạn làm gì đầu tiên?"
- "Tuần trước có việc nào làm bạn phải ngồi lâu hơn dự tính không?"
- Với từng tool họ chọn ở Giai đoạn 1, hỏi theo mạch công việc:
  Sheets → "file nào bạn phải xuất/nhập/gộp thường xuyên?"; Canva →
  "export xong bạn làm gì với đống file?"; WordPress → "phần nào trên
  web làm bạn ngán nhất?"; CapCut → "export clip xong còn phải làm gì
  nữa không?"

**Dấu hiệu nhận ra nỗi đau tự động hoá được** — khi họ nói các từ kiểu:
"từng cái", "từng dòng", "mỗi tuần", "copy qua copy lại", "check từng
bài", "đổi tên hàng loạt", "mất cả buổi", "làm giống hệt nhau" → dừng
lại, phản chiếu cho họ:

> *"À chỗ này nè — tuần nào bạn cũng lọc khách theo tỉnh trong file
> 3.000 dòng đúng không? Cái đó trợ lý làm trong 10 giây. Đó chính là
> việc lặp lại đáng học."*

Nếu sau ~2 lượt hỏi họ vẫn chưa ra, đưa **menu gợi nhớ** (ask_user_question,
multi_select — tối đa 4 lựa chọn, nhớ quy tắc cứng): kể sẵn 4 nỗi đau phổ
biến nhất theo tool họ dùng (VD: "nén ảnh trước khi up web", "lọc dữ liệu
trong sheet lớn", "gom file Downloads", "check link hỏng trên web"). Họ
tick cái nào "à đúng, mình cũng vậy" → mỗi cái tick = một nỗi đau → về
NHÁNH A đánh giá.

ĐỪNG đào quá sâu — 2-3 nỗi đau là đủ làm khoá học. Học viên mệt là hỏng.

## Giai đoạn 3 — Chốt giáo trình

Tổng hợp thành danh sách bài đề xuất. Mỗi bài:

- Tên theo KẾT QUẢ, kiểu "Biến 60 ảnh Canva thành ảnh web-ready trong
  2 phút" — không đặt tên kỹ thuật.
- Gắn với một nỗi đau họ vừa kể.

Bắt đầu luôn bằng 1-2 bài nền tảng (mở terminal/nhờ trợ lý/dọn file) nếu
họ hoàn toàn mới — nhưng lồng vào tình huống thật của họ, không dạy khô.

Trình bày danh sách dạng numbered list + hỏi `ask_user_question`: "Mình
đề xuất học theo thứ tự này — bạn thấy sao?" (Học hết / Chỉ học vài bài /
Đổi thứ tự / Bỏ bớt bài). Nếu họ muốn chỉnh thì chỉnh rồi chốt lại.

## Giai đoạn 4 — Sinh khoá học (và công cụ riêng nếu có)

**Bài 0 "Kết nối" (lesson-00)**: nếu Giai đoạn 1.5 ghi nhận connector
chưa kết nối mà các bài cần → sinh `my-course/lesson-00-ket-noi/` dạy
setup đúng một lần:
- trình duyệt → cài extension Trợ Lý AI (SETUP Bước 5)
- wordpress → tạo App Password → ghi `.devin/secrets.local.json` → nút
  Kiểm tra trong portal
- google-sheets → cài MCP + OAuth
- outlook/zalo → đăng nhập web sẵn trên browser
Bài này theo `templates/lesson.md`, đặt đầu manifest (`lesson-00`), và
skill sinh ra cho các bài sau phải tự kiểm tra `connections.json` trước —
chưa kết nối thì dẫn học viên qua bài 0 trước.

Với MỖI mục đã chốt (đánh số lesson-01, lesson-02...):

**Nếu mục là "công cụ riêng"** (NHÁNH A, họ mô tả một quy trình cố định):
trước hết tạo `.devin/skills/<ten-cong-cu>/SKILL.md` — viết như một công
thức: các bước agent sẽ làm, hỏi gì trước, an toàn ra sao (không đụng
file gốc, báo trước khi chạy). Sau đó vẫn sinh một bài học ngắn dạy cách
dùng công cụ đó + thêm vào `recipes` trong manifest.

**Với mỗi bài học**:

1. Tạo folder `my-course/lesson-XX-<slug>/`.
2. Viết `guide.md` theo `templates/lesson.md` — điền đầy đủ, prompt mẫu
   phải copy-paste chạy được. Nếu việc của bài khớp với một skill có sẵn
   trong `.devin/skills/` (`nen-anh`, `tom-tat-file`, `gom-file`), thêm
   mục "Cách nhanh" dạy gõ `/skill` (xem mục "Dạy về skill" trong
   AGENTS.md).
3. Viết `exercise.md` theo `templates/exercise.md`. Nếu bài cần file mẫu,
   tạo `sample-files/` với file giả lập thật (vài file CSV, vài file txt,
   ảnh thì tạo bằng lệnh nếu được — không cần đẹp).
4. Viết `video-script.md` theo `templates/video-script.md`.
5. **Ngay sau đó**, spawn 2 background subagent (không chờ):
   - profile `slide-builder`: làm `slides.html` cho bài này
   - profile `video-builder`: thử render `video.mp4` từ slide + kịch bản
   (nói rõ trong prompt của subagent: đường dẫn folder bài, đọc guide.md
   + templates, ghi ra slides.html/video.mp4 trong cùng folder)
6. Tiếp tục bài kế tiếp — không chờ subagent xong.

## Giai đoạn 5 — Cập nhật portal + chào

Sau khi đi hết các bài, GHI `my-course/manifest.json` theo đúng schema:

```json
{
  "learner_name": "<tên họ nói, hoặc để trống>",
  "intro": "<1 câu: khoá học này giúp gì cho công việc của họ>",
  "recipes": [
    {"command": "/nen-anh", "meaning": "Nén + resize nhiều ảnh, không đụng gốc"},
    {"command": "/tom-tat-file", "meaning": "Đọc file và tóm tắt nội dung"},
    {"command": "/gom-file", "meaning": "Gom file lộn xộn vào folder gọn gàng"}
  ],
  "lessons": [
    {
      "id": "lesson-01",
      "title": "<tên theo kết quả>",
      "description": "<1 câu nỗi đau nó giải quyết>",
      "folder": "lesson-01-<slug>",
      "has_slides": true,
      "has_video": false
    }
  ]
}
```

Khi subagent slide/video hoàn tất và báo về, cập nhật `has_video`/`has_slides`
nếu cần.

Cuối cùng, nhắn cho học viên (giọng vui, ngắn):

- Khoá học của bạn xong rồi — X bài, đúng các việc bạn kể.
- Mở trang web khoá học (refresh portal) để xem danh sách.
- Cách học: mở slide → đọc hướng dẫn → làm bài tập → kẹt thì quay lại
  chat hỏi mình.
- Bài nào cũng có thể bảo mình: "dạy lại bài X cho em" hoặc gõ `/hoc-bai`.

## Nếu học viên quay lại sau (đã có manifest)

Đừng phỏng vấn lại từ đầu. Hỏi họ muốn thêm bài mới về việc gì, rồi chạy
lại Giai đoạn 4-5 cho riêng bài đó.
