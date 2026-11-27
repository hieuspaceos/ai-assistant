# Phase 01 — Checkpoint theo turn + nút "Hoàn tác"

## Lý do

Báo cáo nâng cấp đề "copy-on-write trước khi agent sửa file". Nhưng
kiến trúc thật: file write nằm **trong process não** — bridge chỉ thấy
thông báo `tool_call` trên dây ACP, không chặn được trước write (race
không tránh). Bản thiết kế đúng với kiến trúc: **chụp trạng thái ở biên
turn** — thời điểm bridge chắc chắn kiểm soát (trước khi forward
prompt, sau khi nhận `done`).

## Thiết kế

```
turn N bắt đầu (POST /api/prompt)
   └─ snapshot workspace/ + folder read-write → .trash/checkpoints/<turn_id>/
        (incremental: chỉ copy file mtime/size đổi; phần còn lại trỏ
         bản cùng nội dung của checkpoint trước bằng hardlink)
turn N kết thúc (done)
   └─ so cây file ↔ checkpoint <turn_id> → danh sách file đổi
        → gắn vào tin nhắn assistant: "Đã sửa 3 file" + nút Hoàn tác
bấm Hoàn tác → POST /api/undo/<turn_id>
   → copy ngược file về đúng path gốc; file turn N TẠO MỚI → move vào
     .trash/ (không xoá hẳn); file turn N XOÁ → khôi phục lại
```

- `<turn_id>`: tăng dần, lưu mapping `turn_id → {checkpoint_dir,
  changed:[], created:[], deleted:[]}` trong
  `.trash/checkpoints/index.json`.
- Giữ **20 checkpoint gần nhất**, prune cũ hơn (kèm guard: không prune
  checkpoint đang pinned).
- **Vùng chụp**: `workspace/` toàn bộ (trừ `.trash`, `.logs`,
  `__pycache__` — cùng danh sách skip của launcher) + các folder trong
  `permissions.json` có `access:"read-write"`. Folder `read` không
  chụp — não không ghi được vào đó.
- File lớn: cap mỗi file 50MB + cap tổng checkpoint 500MB; vượt →
  bỏ file đó khỏi snapshot + ghi `skipped` vào index, báo rõ khi undo.

## Thay đổi

### `tools/chat-bridge.py`

- `_checkpoint_begin(turn_id)` gọi trước khi `acp.call("session/prompt")`.
- `_checkpoint_end(turn_id)` trên event `done`: diff cây → điền index.
  **Phải broadcast `{"t":"checkpoint","turn":N,"changed":[...]}` sau
  đó** — UI chỉ biết render nút Hoàn tác khi có event này (không có
  event, manifest nằm im trên disk, chip không bao giờ hiện).
- `POST /api/undo?turn=<turn_id>` (query param — `POST_ROUTES` là
  dict exact-match, không hỗ trợ path-param `/api/undo/<id>`):
  - `409` nếu `prompt_lock` đang held (đang có việc chạy).
  - Restore từ manifest (không quét lại), trả danh sách
    `{restored, removed_new, recovered_deleted, skipped}`.
  - Undo xong **đánh dấu checkpoint đã-dùng** — bấm lại lần nữa báo
    "đã hoàn tác rồi", tránh trả đè file người vừa sửa tay.
  - Ghi event `{"t":"undone","turn":N}` vào broadcast + history.
- `test-gates.py`: thêm `/api/undo` (token bắt buộc, POST only).
- `.gitignore`: **`.trash/` CHƯA có** (audit 27-11: file chỉ có
  `.logs/` + `workspace/.shots/`) — phải thêm `workspace/.trash/`
  (hoặc `.trash/` tuỳ vị trí chốt ở dưới).
- **Vị trí checkpoint**: chốt `workspace/.trash/checkpoints/<turn>/` —
  cùng convention `.trash` của delete-lesson (hiện `course/.trash`
  nằm trong từng bài, đây mở rộng ra gốc workspace) và nằm trong
  vùng allow-write sẵn có. Snapshot PHẢI exclude `.trash` chính nó.

### `web/chat.html` + `web/app.js`

- Tin nhắn assistant kèm `files_changed` → chip nhỏ: *"🗂 Đã sửa N
  file — Hoàn tác"* → confirm *"Trả N file về trước việc này?"* →
  `POST /api/undo/<id>` → toast kết quả.
- i18n đủ `vi`/`en`.
- Event `undone` → chip đổi thành "Đã hoàn tác ✓", không bấm lại được.

## Bẫy đã biết

- **Race với write của não khi bắt turn**: prompt đã forward nhưng
  snapshot chưa xong → não đã sửa → checkpoint mang bản "đã sửa".
  Vá: `_checkpoint_begin` chạy **trước** `acp.call(prompt)` trong
  cùng handler, đồng bộ (không thread) — chậm nhất vài trăm ms cho
  workspace văn phòng, chấp nhận được.
- Folder `read-write` ngoài workspace có thể to (ảnh, video) → cap
  file + `skipped` rõ ràng trong index; không im lặng bỏ qua.
- Hardlink không có trên mọi FS Windows (FAT32/exFAT): fallback copy.
- Path đệ quy: `.trash` nằm trong `workspace/` — PHẢI loại khỏi
  snapshot (không thì checkpoint chứa checkpoint → phình mũ).
- Symlink trong vùng chụp: copy theo manifest, KHÔNG deref ra ngoài
  (path_guard parity).

## Test

- `test-bridges.py`: turn tạo file mới → undo → file vào `.trash`;
  turn sửa file → undo → nội dung về bản cũ; turn xoá file → undo →
  file quay lại; undo hai lần → lần hai báo đã-dùng.
- Snapshot với folder 5.000 file nhỏ: `_checkpoint_begin` < 500ms.
- Prune: tạo 25 turn → `.trash/checkpoints/` còn 20.
