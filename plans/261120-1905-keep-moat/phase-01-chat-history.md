# Phase 1 — Chat history persist

## Mục tiêu

Restart bridge (tắt máy, crash, đổi não) không mất lịch sử chat —
portal mở lại thấy đủ ngữ cảnh cuộc trò chuyện trước.

## File động

| File | Action | Việc |
|---|---|---|
| `tools/chat-bridge.py` | modify | `broadcast()` append JSONL; startup replay; rotate; skip `perm` |
| `tools/chat-bridge.ps1` | — | KHÔNG port (đã frozen theo ship-learner phase 5 — nếu chưa freeze thì port nguyên tắc này) |
| `docs/SECURITY.md` | modify | ghi chú history file + quyền + cách xoá |
| `tools/test-bridges.py` | modify | test persist: ghi event → respawn → poll thấy replay |

## Chi tiết

### File

`.logs/chat-history.jsonl` — mỗi dòng = một event JSON y hệt object
trong `event_store`. `.logs/` đã gitignore sẵn.

### `broadcast()` — append

```python
HIST_FP = os.path.join(CWD, ".logs", "chat-history.jsonl")
# .logs/ chỉ được launcher tạo — chạy chat-bridge trực tiếp (start.sh)
# thì chưa chắc có; thiếu makedirs thì open("a") OSError → history
# âm thầm không bao giờ ghi trên máy cài mới
os.makedirs(os.path.dirname(HIST_FP), exist_ok=True)

def broadcast(ev):
    global event_base
    with store_lock:
        event_store.append(ev)
        excess = len(event_store) - MAX_EVENTS
        if excess > 0:
            del event_store[:excess]
            event_base += excess
    # ghi ngoài lock — IO chậm không chặn stream
    try:
        with open(HIST_FP, "a", encoding="utf-8") as f:
            f.write(json.dumps(ev, ensure_ascii=False) + "\n")
    except OSError:
        pass
```

### Startup — replay trong `spawn_brain()` hoặc `main` trước serve

```python
def replay_history():
    global event_base
    try:
        with open(HIST_FP, encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if ev.get("t") == "perm":
                    continue          # card xin phép là transient — bỏ
                with store_lock:
                    event_store.append(ev)
    except OSError:
        return
    with store_lock:
        excess = len(event_store) - MAX_EVENTS
        if excess > 0:
            del event_store[:excess]
            event_base += excess
```

Client `poll` đã xử lý `reset` (cursor lạ → replay toàn bộ) nên không
cần đổi phía web — restart xong portal reload là thấy lại history.

### Rotate

Khi file > 2 MB: ghi lại chỉ MAX_EVENTS dòng cuối (truncate ghi đè,
không để file phình mãi trên máy học viên). Chạy ở startup, trước
replay.

### Quyền file

`os.chmod(HIST_FP, 0o600)` sau khi tạo — history chứa nội dung agent
đã nói (có thể là tóm tắt tin nhắn); SECURITY.md ghi rõ "xoá `.logs/`
= xoá sạch lịch sử".

## Acceptance

- Chat vài lượt → kill bridge → chạy lại → portal reload hiện đủ lượt
  trước (không mất chữ)
- File history có event `perm` → sau restart KHÔNG có card xin phép
  treo
- `test-bridges.py` có case: spawn → prompt giả lập → kill → respawn
  → `/api/poll?since=0` chứa event cũ
- File > 2 MB được truncate về tail, bridge vẫn replay được

## Rủi ro

- Replay toàn bộ vào RAM khi file lớn — cap bằng cùng `MAX_EVENTS`
  (3000) như store hiện tại.
- Đổi não (`/api/brain`) → history não cũ còn hiện — chấp nhận v1
  (history là "cuộc trò chuyện với trợ lý", không phân biệt não; thêm
  marker `{"t":"brain","id":...}` vào event đổi não để UI gạch ngang
  nếu cần sau).
