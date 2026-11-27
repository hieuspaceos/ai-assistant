# Phase 05 — Đánh bóng khung chat: khoảng trống chết, nút Dừng, dán ảnh, đọc lại

## Lý do

Soi lại toàn bộ màn chat sau khi Terminal ẩn mặc định — một số dấu vết
và gap còn sót, tất cả đều chạm `web/chat.html` + vùng `#pane-chat`:

1. **Khoảng trống chết dưới input** (ảnh chủ gửi 27-11): `chat.html`
   `body { padding-bottom: 52px }` chừa chỗ cho `#chat-modebar` nổi,
   nhưng khi `config.terminal=false` cả hai nút đã `hidden` — pill rỗng
   vẫn render (chấm nhỏ ở đáy) + padding vẫn chiếm 52px.
2. **Không có nút Dừng** — `send` disabled trong lúc não chạy; trợ lý
   đi sai hướng thì chỉ có cách chờ hết hoặc restart app. ACP có
   `session/cancel` nhưng bridge chưa nối.
3. **Không dán được ảnh** — AGENTS.md hướng dẫn học viên "chụp màn
   hình dán vào chat" nhưng textarea không nhận ảnh; không có đường
   đưa ảnh vào prompt.
4. **Card xin phép replay vẫn sống** — reload trang → lịch sử phát
   lại card perm cũ y hệt card thật; bấm vào chỉ được "hết hạn".
   Học viên không phân biệt được card đang chờ vs card đã xử lý.
5. **Cuộn bị giật đáy** — `msgs.scrollTop = scrollHeight` mỗi chunk
   text; đang đọc lại tin cũ thì tin mới kéo xuống luôn.
6. **`/` không gợi ý skill** — học viên phải nhớ tên lệnh; gõ `/`
   nên mở menu công cụ có sẵn (manifest đã có danh sách).
7. **Đường dẫn file trong tin nhắn không bấm được** — não báo "đã lưu
   vào `workspace/output/x.xlsx`", học viên tự mò folder; `/api/reveal`
   đã có sẵn chỉ chưa được nối vào bubble.

## Thay đổi

### `web/index.html` + `web/styles.css` + `web/app.js` — hết khoảng trống

- `applyTerminalUI()`: khi `terminalOn=false` → **`hidden` cả
  `#chat-modebar`** (không chỉ 2 nút). `#terminal-status` chỉ chứa cảnh
  báo `warnChat`/`warnCli` — khi status có text mới bật bar lại:
  - Trong `setChatMode`: sau khi set `status.innerHTML`, toggle
    `modebar.hidden = !terminalOn && !status.textContent.trim()`.
- `chat.html` `body`: bỏ `padding-bottom:52px` mặc định → đổi thành
  `body.has-modebar { padding-bottom: 52px }`. Cha con cùng origin
  (:8080) → `app.js` gõ thẳng vào iframe:
  `chatFrame.contentDocument.body.classList.toggle('has-modebar',
   !modebar.hidden)` — gọi trong `applyTerminalUI`, `setChatMode`,
  và `chatFrame.onload` (iframe load sau khi state đã biết).

### `tools/chat-bridge.py` + `web/chat.html` — nút "Dừng"

- `POST /api/cancel`: chỉ khi `prompt_lock` đang held → gửi
  `session/cancel` notification (JSON-RPC, không id — notification
  chuẩn ACP). Không có lượt chạy → 200 `{ok:true}` luôn (idempotent,
  nút bấm dư không hại).
- UI: trong lúc busy, nút **Gửi** đổi thành **■ Dừng** (hoặc nút nhỏ
  cạnh status) → POST → hiện "Đang dừng…"; não trả done/err bình
  thường qua event.
- **Fallback nếu não phớt lờ cancel**: vẫn chạy tiếp — chấp nhận,
  đường kill process chỉ là lựa chọn cuối (không tự ý kill; ghi vào
  bẫy). Kiểm trên não chính: `devin acp` tôn trọng `session/cancel`?
  → ghi findings; não nào bơ thì nút vẫn gửi, UI báo "trợ lý không
  dừng được — đợi nó làm xong".
- `test-gates.py`: thêm route.

### `web/chat.html` — dán ảnh + slash menu + reveal link

- **Paste ảnh**: `input.addEventListener('paste')` → `clipboardData`
  có `image/*` → POST `/api/upload-paste` (endpoint mới, cap 10MB,
  ghi `workspace/inbox/paste-<ts>.png` — folder trong vùng allow sẵn)
  → chèn vào input: `[ảnh: paste-xxx.png]` + kèm đường dẫn trong text
  gửi đi (`"xem ảnh mình vừa dán: workspace/inbox/paste-xxx.png"`).
  Fallback sang ACP image content-block chỉ khi não chính hỗ trợ —
  đường file trước là đủ và não nào cũng đọc được. `test-gates.py`
  thêm route; path_guard khoá ghi chỉ trong `workspace/inbox/`.
- **Slash menu**: keydown `/` ở đầu input → dropdown lọc theo ký tự
  gõ tiếp, nguồn = `manifest.recipes` + `GET /api/skills` (endpoint
  mới đọc tên `.devin/skills/*/name` — cùng lý do serve chặn dotfile
  ở phase skill-verify, có thể gộp endpoint). Enter/Tab chọn → fill.
  Esc/space đóng.
- **Reveal link**: sau `done`, quét bubble agent mới nhất tìm pattern
  path (`workspace/…`, `~/…`, ổ `X:\…`) → render chip nhỏ 📂 cạnh
  bubble → `POST /api/reveal {path}` (endpoint có sẵn, gate sẵn).
  Guard thực tế của reveal (audit 27-11): chỉ path **dưới `~`**, trừ
  `.devin` và `path_sensitive` — UI cứ gửi, bridge tự 403 path ngoài
  vùng; chip chỉ nên render cho path "có vẻ trong workspace/home" để
  khỏi hiện nút bấm chết.

### `web/chat.html` — replay & cuộn

- Perm card replay (`data.reset` / `replaying`): render class
  `perm stale` — nút `disabled`, chữ mờ + chú thích "(đã xử lý)".
  Biết nhờ flag `replaying` đã có trong poll loop. Chi tiết cơ chế
  (audit 27-11): event `perm` KHÔNG ghi history nhưng VẪN nằm trong
  `event_store` → `/api/poll?since=0` replay được; perm đã trả lời
  thì `perm_done` kế tiếp đóng card. Card chỉ "treo giả" khi bridge
  clear `perm_pending` qua ready/done/err mà không phát `perm_done`
  — vá ở cả hai đầu: UI mờ card khi replay VÀ bridge nên broadcast
  `perm_done` khi clear pending (rẻ, đúng hơn).
- **History một chiều** (gap mới audit 27-11): prompt của user không
  được broadcast → reload chỉ thấy lời trợ lý. Fix chung với
  `user_msg` event — đã giao cho plan `no-llm-macro` phase-02
  (cùng một dòng `broadcast` phục vụ cả đếm-lặp lẫn replay đủ 2
  chiều); nếu làm phase này trước thì kéo mục đó về đây luôn.
- Cuộn: theo dõi `msgs.onscroll` — `nearBottom = scrollHeight -
  scrollTop - clientHeight < 80`. `addText` chỉ auto-scroll khi
  nearBottom; ngược lại hiện pill "↓ Tin mới" bấm là xuống đáy.

## Bẫy đã biết

- `contentDocument` null khi iframe chưa load → set class trong
  `onload` callback + guard null ở mọi chỗ toggle.
- `/api/upload-paste`: file ảnh vào `workspace/` = vùng não đọc
  được — nhưng cũng là vùng "dữ liệu không phải lệnh": tên file
  sanitize (`paste-<ts>.png`, bỏ tên gốc — tên gốc clipboard có thể
  mang path lạ).
- Slash menu phải tắt khi input không bắt đầu bằng `/` (gõ `/` giữa
  câu không mở menu — VD "gửi a/b").
- Cancel: `prompt_lock` release khi `done` — não bơ cancel thì nút
  "vô hiệu" ngầm; UI phải revert về busy nếu 10s sau chưa done.

## Test

- Terminal off → không pill, không padding (đo `body.scrollHeight`
  vs viewport). Bật Terminal trong Cài đặt → pill + padding về đúng.
- Dán ảnh screenshot vào input → file vào `workspace/inbox/` → prompt
  có đường dẫn; não đọc được file (e2e trên não dev).
- Dừng giữa lượt: prompt dài → bấm Dừng → done về sớm, bubble kết
  thúc êm; bấm Dừng khi không busy → không lỗi.
- Replay: reload giữa lúc có perm card → card cũ mờ, không bấm được.
- `/` gõ đầu → menu hiện; gõ `/xyz` lọc còn 0 → menu đóng êm.
