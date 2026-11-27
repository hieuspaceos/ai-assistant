# Phase 02 — Phát hiện việc lặp → gợi ý "Lưu thành công cụ"

## Lý do

`tao-cong-cu` đã biến "việc vừa làm" thành skill + walkthrough +
manifest — nhưng chỉ khi học viên *chủ động* nhờ. Người dùng cá nhân
không biết tính năng đó tồn tại; cứ nhờ trợ lý nén ảnh lần thứ 4 bằng
lời mới gõ. Bridge cần tự nói: *"việc này bạn làm 3 lần rồi — lưu
thành công cụ bấm-là-chạy không?"*

## Thiết kế

### Đếm lặp — đơn giản, không ML

**Tiền đề BẮT BUỘC (audit 27-11 phát hiện):** `chat-history.jsonl`
hiện KHÔNG ghi prompt của user — bridge chỉ broadcast event phía não
(text/tool/done/err/warn/ready/perm_done). `_h_prompt` forward thẳng
cho não, không broadcast `{"t":"user_msg"}`. Hệ quả phụ: **reload
chat mất hết tin nhắn của học viên** — chỉ replay phía trợ lý (gap
UX cần vá luôn, xin vào phase này vì cùng một dòng code):

- Trong `_h_prompt`, trước/sau `acp.call`: `broadcast({"t":"user_msg",
  "text": <prompt>})` — `hist_write` ghi tự động (chỉ skip `perm`).
- `chat.html`: render `user_msg` thành bubble user khi replay — sửa
  luôn lỗi history một chiều.
- Nếu không muốn lộ prompt trong history → vẫn phải ghi
  `{"t":"user_msg","key":<hash/normalized>}` tối thiểu để đếm lặp.

Thuật toán (sau khi prompt đã được ghi):

- Chuẩn hoá prompt: lowercase, trim, collapse khoảng trắng, **bỏ phần
  biến động** (đường dẫn, tên file, số) → `prompt_key`.
- Đếm `prompt_key` trong **30 ngày gần nhất**: ≥3 → candidate.
- Workflow cũng đếm: cùng `workflow_id` chạy ≥3 lần (ghi event khi
  portal chạy workflow → history record).
- Lưu bảng đếm vào `workspace/connections.json`? — KHÔNG, đó là file
  trạng thái kết nối. Để `workspace/.repeat-stats.json` (hoặc trong
  `.logs/` nếu coi là ephemeral — chọn `.logs/` vì stats mất cũng
  không sao, chỉ làm lại đếm chậm).

### Surface gợi ý — thụ động, không popup

- Endpoint `GET /api/repeat-suggest` → `[{key, count, sample_prompt,
  kind: "prompt"|"workflow"}]` (top 3).
- Portal: chip nhỏ trên `welcome`/đầu panel tools: *"💡 'nén ảnh cho
  web' bạn làm 3 lần rồi — **Lưu thành công cụ** | Để sau"*.
- Bấm **Lưu**: gửi prompt mở luồng `tao-cong-cu` (prompt dựng sẵn:
  *"Dùng công thức /tao-cong-cu: gói việc '<sample_prompt>' thành công
  cụ — hỏi mình từng tham số cần thiết"*) → não dẫn từng bước như
  bình thường.
- Bấm **Để sau**: ghi `dismissed[key]=true` → không gợi lại key đó
  nữa (persist trong `workspace/config.json`? — nhẹ hơn: file riêng
  `.logs/repeat-dismissed.json`, cùng chỗ stats).
- Skill tương tự đã tồn tại (manifest có) → không gợi ý nữa — check
  `workspace/manifest.json` trước khi trả list.

## Thay đổi

### `tools/chat-bridge.py`

- Thêm broadcast `user_msg` trong `_h_prompt` (tiền đề ở trên) →
  đếm lazy khi `GET /api/repeat-suggest`: parse jsonl tail →
  normalize → count → lọc dismissed + lọc đã-có-skill → top 3
  (không thêm IO vào đường prompt nóng, file 30 ngày đọc vài
  trăm KB là nhanh).
- `GET /api/repeat-suggest`: parse jsonl tail → normalize → count →
  lọc dismissed + lọc đã-có-skill → top 3.
- `test-gates.py`: GET mới, token.

### `web/app.js`

- `renderSuggest()` gọi khi boot + sau mỗi `done` (throttle 5 phút).
- Chip → hành động như trên; i18n vi/en.

## Bẫy đã biết

- Normalize quá tay → mọi prompt thành cùng một key ("gửi tin" match
  hết). Quy tắc: giữ **động từ + skill-name + loại file**; chỉ cắt
  path/number/quoted string. Test với history thật của máy dev.
- `chat-history.jsonl` đã rotate (tail 256KB) → đếm chỉ đúng trong
  cửa sổ dữ liệu còn lại — chấp nhận (repeat gần mới đáng gợi ý).
- `/api/prompt` từ workflow có nội dung prompt dài — key phải bóc
  `workflow_id` chứ không đếm text dài ấy.
- Không đếm prompt của chính `tao-cong-cu`/skillify-flow → tránh gợi
  ý "lưu công cụ lưu công cụ".

## Test

- `test-bridges.py`: ghi 3 prompt giống nhau (khác tên file) → GET
  trả candidate; dismiss → không còn; manifest đã có skill → lọc.
- UI: chip hiện, bấm Lưu → prompt tao-cong-cu đi vào chat; Để sau →
  chip biến mất và không quay lại sau reload.
