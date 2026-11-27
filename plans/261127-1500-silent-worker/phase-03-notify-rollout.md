# Phase 03 — Kênh `/api/notify` + rollout skills

## 3a. Endpoint notify

`POST http://127.0.0.1:7682/api/notify?token=...`

```json
{"title": "Đọc xong Zalo", "body": "3 hội thoại chưa đọc, đã tóm tắt trong chat", "level": "info"}
```

- `title` ≤80 ký tự, `body` ≤300, `level` ∈ `info|warn|error`; strip
  control chars. Thiếu/sai field → 400.
- Làm **cả `chat-bridge.py` lẫn `chat-bridge.ps1`** (luật parity;
  .ps1 ghi file kèm BOM — bài học audit 1).

## 3b. Hai đầu ra của notify

**Portal toast** (luôn có):
- Đẩy qua kênh event hiện có — chat-bridge đã có `new_event`/long-poll
  phục vụ chat (chat-bridge.py:830, portal poll `/api/poll?wait=25000`
  ở chat.html:432); `/api/notify` chỉ cần `emit_event({"t":"notify",...})`
  — đây là emit phía server, KHÔNG đi qua whitelist `/api/emit-event`
  (audit-6 F8 chỉ chặn agent tự emit).
- Portal `app.js`/`chat.html` thêm **handler cho event type `notify`**
  (hiện chưa có) → toast góc màn hình + badge số trên tab "💬" + (tuỳ
  chọn) âm `ding` nhẹ.
- Render bằng `textContent` — body notify là dữ liệu ngoài, không
  innerHTML (XSS portal = đọc được `bridge_token`).

**OS toast** (khi portal không mở):
- Windows: spawn PowerShell ngắn với toast XML
  `Windows.UI.Notifications` (Win10+, không cần BurntToast module).
  Viết `tools/notify.ps1` nhận `-Title -Body`.
- macOS: `osascript -e 'display notification "..." with title "..."'` —
  `tools/notify.sh` hoặc inline.
- Bridge gọi script qua subprocess, timeout 5s, nuốt lỗi (notify fail
  không được làm chết request — log thôi).

## 3c. Skill/agent dùng notify

Convention ghi vào skill + AGENTS.md:

- Việc < ~10 giây chạy xong trong chat → không cần notify.
- Việc dài (đọc nhiều tin, cập nhật sheet hàng loạt, clone trang) →
  bắt đầu nói "mình làm ngầm nhé, xong báo bạn" → làm trong agent
  window → kết thúc `POST /api/notify` + tóm tắt ngắn trong chat.
- Lỗi → `level:"warn"`/`"error"` với hướng dẫn học viên làm gì tiếp.

## 3d. Cập nhật skill (`.devin/skills` + `.devin/skill-packs` cả hai ngôn ngữ)

| Skill | Đổi |
|---|---|
| `mo-web`/`open-web` | Thêm mục "làm việc im lặng": mọi việc của trợ lý mở bằng `open scope:"agent"`; không `activate`/`screenshot` tab của học viên; `t*` chỉ trong cửa sổ agent; xong việc → notify |
| `doc-zalo`/`read-zalo`, `doc-outlook`/`read-outlook` | Việc đọc (scroll+query) vốn đã nền — chuyển sang chạy trong agent window, thêm notify cuối luồng |
| `cap-nhat-sheet`/`update-sheet` | `tinsert mode=char` chuyển sang tab nền + focus emulation (verify ở 00a) |
| `clone-trang`/`clone-page` | `screenshot`/`dom`/`styles` trên tab nền — đo + so sánh không giật màn hình |
| AGENTS.md cả hai bản | Luật mới: "không activate tab/cửa sổ học viên; việc riêng của trợ lý làm trong cửa sổ agent; xong việc dài → gọi /api/notify; computer-use OS chỉ là fallback cuối và phải báo trước" |

## 3e. Test + tài liệu

- `test-bridges.py`: case notify — POST hợp lệ → 200; thiếu token → 401;
  body quá dài → 400; level lạ → 400.
- `test-parity.py`: thêm `/api/notify` vào danh sách phải có cả hai bên.
- `docs/api-reference.md`: mục notify + phần `scope:"agent"` của
  ext-bridge.
- `docs/system-architecture.md`: thêm uia-bridge :7685 + notify vào sơ
  đồ thành phần.
- `test-gates.py`: notify KHÔNG qua consent gate (chỉ hiện thông báo,
  không side-effect) — nhưng phải check không bị deny list chặn.

## Thứ tự gợi ý khi implement

1. Phase 00 spike → ghi findings.
2. Phase 01 (extension) — độc lập, win nhanh nhất.
3. Phase 03a/3b (notify) — nhỏ, làm song song hoặc ngay sau 01.
4. Phase 02 (uia-bridge) — nặng nhất, chỉ bắt đầu sau khi 00d cho kết
   quả coverage chấp nhận được.
