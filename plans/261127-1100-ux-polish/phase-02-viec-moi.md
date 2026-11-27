# Phase 02 — Nút "Việc mới" — hội thoại sạch một chạm

## Lý do

Hội thoại kéo dài → context phình, trợ lý dễ lẫn việc cũ vào việc mới,
quota chạy nhanh hơn. Người dùng cá nhân quen nút "New chat" của mọi
app AI; ở đây muốn vậy phải restart cả app (kill não → spawn lại) —
thao tác không ai nghĩ ra.

## Mục tiêu

Một nút trong khung chat: bấm → hội thoại mới sạch context, UI xoá
khung tin nhắn cũ, não giữ nguyên (không cần đăng nhập lại).

## Hai đường làm — thử đường nhẹ trước

### Đường A: `session/new` trên process đang sống

ACP cho phép nhiều session trên một agent process. Thử với não mặc
định (`devin acp --process-model in-process`):

```python
mid = acp.call_sync("session/new", {"cwd": CWD, "mcpServers": []})
# result.sessionId mới → acp.session_id = mới → prompt kế vào session sạch
```

**Pass khi**: não trả `sessionId` mới và prompt sau không còn ký ức
turn trước. Ghi kết quả vào `findings.md` theo não — mỗi não một hàng
(devin/gemini/codex-acp/claude-acp/goose/opencode): cái nào nhận, cái
nào trả "Invalid request".

### Đường B (fallback): respawn não

Não không nhận session thứ hai → `spawn_brain()` lại (đường self-heal
có sẵn ở `/api/prompt` — kill proc cũ, Popen mới, handshake +
session/new). Mất 3–8s nhưng chắc chắn sạch. Phải serialize qua
`spawn_lock` có sẵn.

## Thay đổi

### `tools/chat-bridge.py`

- Endpoint mới `POST /api/new-task`:
  - Nếu đang có prompt chạy (`prompt_lock` held) → `409`, không giết
    việc đang làm giữa chừng.
  - Đường A: thử `session/new`; result có `sessionId` → cập nhật
    `acp.session_id`, broadcast `{"t":"ready","sessionId":...}` +
    `{"t":"cleared"}` để UI xoá khung.
  - Đường B: `spawn_brain()` rồi trả khi `ready`.
- **Không** xoá `chat-history.jsonl` — chỉ broadcast
  `{"t":"cleared"}` (một tên duy nhất, đừng tạo `new_task` riêng):
  nó vừa đi qua long-poll để UI xoá khung ngay, vừa tự ghi vào
  history làm ranh giới — `replay_history()` chỉ replay sau marker
  `cleared` gần nhất.
- `test-gates.py`: thêm `/api/new-task` vào bảng gate (yêu cầu token).

### `web/chat.html` + `web/app.js`

- Nút ➕/"Việc mới" cạnh input bar (i18n: `newTask:'Việc mới'` /
  `'New task'`), confirm nhẹ: *"Bắt đầu việc mới? Trợ lý sẽ quên hội
  thoại đang làm."* — đây là hành động huỷ context, phải hỏi.
- Sau `cleared`/`ready`: xoá `#messages`, hiện greeting/hint-chips.
- Long-poll đã có sẵn — `cleared` đi qua kênh broadcast, không cần
  endpoint poll mới.

## Bẫy đã biết

- `perm_pending`/`local_pending` sót lại từ turn cũ → clear cùng
  `cleared` (card xin quyền của việc đã bỏ không được bấm được nữa;
  `_append` đã tự clear chúng khi event `ready` tới — broadcast
  `ready` trước `cleared` là đủ).
- **Race với `/api/prompt`** (audit 27-11): check `prompt_lock`
  rồi `session/new` là hai bước — prompt chen vào giữa sẽ đáp vào
  session CŨ rồi bị quên giữa chừng. Vá: acquire `prompt_lock` ngay
  đầu handler (không lấy được → 409); giữ suốt session/new hoặc
  spawn — `_append` tự release lock khi event `ready` tới, đúng
  timing. Nhớ release tay trong nhánh fail (spawn chết, không
  ready nào tới → lock kẹt → mọi prompt sau 409).
- `turn_gen`/event_store: tăng gen để event turn cũ không lẫn vào —
  cùng pattern khi respawn não.
- Spam nút → debounce + disable khi đang `session/new` in-flight.

## Test

- `test-bridges.py`: prompt → `/api/new-task` → prompt "nhắc lại việc
  vừa rồi" → não không nhớ (kiểm bằng fakebrain nếu có sẵn —
  `test-fakebrain.cs`).
- UI tay: bấm khi đang chạy dở → 409; bấm hai cái liền → một session.
