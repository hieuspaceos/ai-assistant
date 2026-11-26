---
name: phong-van
description: Phỏng vấn học viên về công việc hằng ngày, rồi sinh bộ công cụ riêng (skill) kèm hướng dẫn dùng từng-bước trong workspace/. Dùng khi học viên mới muốn bắt đầu học.
triggers:
  - user
allowed-tools:
  - read
  - write
  - exec
  - grep
  - find_file_by_name
  - ask_user_question
---

Bạn đang chạy buổi phỏng vấn để làm ra CÔNG CỤ giải quyết việc thật cho
một học viên không biết code. Giọng điệu: giáo viên thân thiện, ELI10
theo AGENTS.md.

Nguyên tắc: **đầu ra của buổi phỏng vấn là công cụ dùng được ngay, không
phải bài giảng**. Mỗi mục sinh ra gồm đúng hai thứ: một công cụ (skill
`/lệnh` hoặc quy trình portal) + một `guide.md` hướng dẫn dùng từng-bước
(bấm đâu, gõ gì). KHÔNG tạo slide, video, bài tập, file mẫu — học viên
là người đi làm, không có thời gian ngồi học giáo trình.

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
trên app/web nào?"* → map sang connector trong `workspace/connections.json`:

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

## Giai đoạn 4 — Sinh công cụ + hướng dẫn từng-bước

**Bài 0 "Kết nối" (tool-00)**: nếu Giai đoạn 1.5 ghi nhận connector
chưa kết nối mà các công cụ cần → sinh `workspace/tool-00-ket-noi/`
dạy setup đúng một lần:
- trình duyệt → cài extension Trợ Lý AI (SETUP Bước 5)
- wordpress → tạo App Password → ghi `.devin/secrets.local.json` → nút
  Kiểm tra trong portal
- google-sheets → cài MCP + OAuth
- outlook/zalo → đăng nhập web sẵn trên browser
Bài này theo `templates/lesson.md`, đặt đầu manifest (`tool-00`), và
skill sinh ra cho các mục sau phải tự kiểm tra `connections.json` trước —
chưa kết nối thì dẫn học viên qua bài 0 trước.

Với MỖI mục đã chốt (đánh số tool-01, tool-02...), sinh đúng HAI thứ:
một công cụ (skill riêng / skill có sẵn / nhờ tự do) + một `guide.md`
guideial từng-bước trong `workspace/tool-XX-<slug>/`.

**Quy trình sinh chi tiết nằm trong `/tao-cong-cu`** — đọc
`.devin/skills/tao-cong-cu/SKILL.md` và làm theo đúng quy trình đó cho
từng mục (chọn hình thức công cụ, viết SKILL.md, viết guide theo
`templates/lesson.md`, cập nhật manifest).

KHÔNG tạo `exercise.md`, `video-script.md`, `sample-files/`, `slides.html`,
`video.mp4`, không spawn subagent dựng slide/video.

## Giai đoạn 5 — Cập nhật portal + chào

Sau khi đi hết các bài, GHI `workspace/manifest.json` theo đúng schema:

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
      "id": "tool-01",
      "title": "<tên theo kết quả>",
      "description": "<1 câu nỗi đau nó giải quyết>",
      "folder": "tool-01-<slug>",
      "has_slides": false,
      "has_video": false,
      "has_exercise": false
    }
  ]
}
```

Bài mới chỉ có `guide.md` — cứ để cả ba cờ `false` để portal ẩn tab
Slide/Bài tập và mở thẳng phần hướng dẫn.

## Giai đoạn 6 — Tạo "trợ lý" riêng cho học viên

Khoá học xong rồi thì giới thiệu thêm một việc nữa: **đặt tên và chọn nghề
cho trợ lý** — như thuê một nhân viên đã biết sẵn một nhóm việc.

1. `GET /api/bots` → đọc `templates` (các nghề có sẵn: marketing, sales,
   office, content) — nhớ kèm `?token=` hoặc header `X-Bridge-Token`.
2. Chọn template có `skills` gần nhất với công việc học viên đã kể. Không
   cái nào hợp → bỏ qua bước này, trợ lý chung vẫn đủ dùng.
3. Hỏi học viên một câu: *"Đặt tên cho trợ lý nhé — ví dụ `<suggested_bot_name>`,
   bạn thích tên gì?"* (họ không trả lời thì dùng luôn tên gợi ý).
4. `POST /api/bot` hai lần:
   - `{action:"create", name, role:<id template>, avatar, skills, needs,
     recipes, instructions:<instructions theo ngôn ngữ>}`
   - `{action:"activate", id:<id vừa tạo>}` — bridge tự cài skill còn
     thiếu và ghi `workspace/bot.md`.
5. Báo học viên: *"Khoá học này sẽ dạy bạn dùng đúng trợ lý <tên> vừa
   tạo — từ giờ bạn nhắn cho <tên> là được."*

Đừng tự đặt tên hay tự chọn nghề nếu chưa hỏi — tên trợ lý là chuyện cá
nhân. `needs` của bot chỉ là gợi ý kết nối, không bắt học viên nối ngay.

Cuối cùng, nhắn cho học viên (giọng vui, ngắn):

- Công cụ của bạn xong rồi — X mục, đúng các việc bạn kể.
- Mở trang web khoá học (refresh portal) để xem: mỗi mục có hướng dẫn
  từng bước — bấm vào là làm theo được ngay.
- Kẹt chỗ nào quay lại chat hỏi mình — hoặc gõ `/huong-dan` để mình dẫn
  từng bước ngay trong chat.

## Nếu học viên quay lại sau (đã có manifest)

Đừng phỏng vấn lại từ đầu. Hỏi họ muốn thêm bài mới về việc gì, rồi chạy
lại Giai đoạn 4-5 cho riêng bài đó.
