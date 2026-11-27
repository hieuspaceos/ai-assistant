# Audit plan silent-worker (2026-11-27)

Đối chiếu plan với code thật: `ext-bridge.py`, `extension/background.js`,
`chat-bridge.py`, `web/app.js`, `web/chat.html`.

## Xác nhận đúng

- Nguồn giật tab đúng như chẩn đoán: `chrome.tabs.update(active:true)`
  trong tclick/tright/tmove/ttype/tkey + `captureVisibleTab` chỉ chụp
  tab active (background.js:283-401). Sửa được bằng code, không phải
  giới hạn platform.
- ext-bridge `handle_api` chỉ `d.pop("action")` rồi forward phần còn
  lại — **không có allowlist action/param** → thêm `scope:"agent"` không
  cần sửa bridge (claim trong phase-01 đúng).
- Kênh event portal tồn tại: `/api/poll?since=N&wait=25000` long-poll
  (chat.html:432) + `emit_event()`/`new_event` (chat-bridge.py:830) →
  `/api/notify` chỉ cần `emit_event({"t":"notify",...})`, không cần
  kênh mới.
- `chrome.windows.create/update` hỗ trợ `focused:false` hợp lệ API.
- `CONTENT_ACTIONS` bọc UNTRUSTED đã đúng chỗ — notify không thuộc
  nhóm đó (nó là action ghi, trả status).

## Lỗ hổng / thiếu sót cần vá vào plan

### A1 (CAO) — Tab nền bị throttle, plan chưa xét

Chrome throttle JS của tab ẩn/occluded: `requestAnimationFrame` dừng
hẳn, `setTimeout` clamp ~1s (sau 5 phút ẩn còn ~1 lần/phút, trừ trang
có websocket/audio). Chrome 88+ còn "native window occlusion" trên
Windows — cửa sổ agent bị che kín (user maximize cửa sổ mình) = coi
như hidden → throttle y hệt minimized.

Hệ quả thật: Zalo Web virtualized list re-render bằng rAF/scroll
handler → cuộn trong tab nền có thể khựng/không nạp item; Sheets grid
tương tự. DOM query vẫn chạy được (layout tính on-demand) nhưng các
flow dựa vào timer/rAF của trang sẽ chậm.

Vá:
- Thêm spike **00e**: scroll virtualized list Zalo Web trong tab của
  cửa sổ occluded → đo có nạp item không; thử
  `Page.setWebLifecycleState{state:'active'}` (unfreeze) như một nút
  vặn.
- Mitigation ghi sẵn: để cửa sổ agent **lộ một dải nhỏ** (không che
  kín) hoặc đặt trên Space/virtual desktop riêng; chấp nhận lag cho
  việc đọc, chỉ cần đo trước khi commit.

### A2 (CAO) — MV3 service worker mất `agentWinId`

background.js là service worker — Chrome giết nó bất cứ lúc nào → biến
`agentWinId` mất → lần `open scope=agent` sau tạo cửa sổ thứ hai →
cửa sổ agent chồng lên mãi.

Vá: persist `agentWinId` vào `chrome.storage.session` (sống qua SW
restart, chết khi browser tắt — đúng ý đồ) + tab đầu của cửa sổ agent
là extension page `agent-home.html` ("Cửa sổ làm việc của Trợ Lý AI —
đừng đóng") — vừa là marker để re-discover bằng `windows.getAll` khi
storage mất (browser restart + session restore), vừa giải thích cho
học viên đây là cửa sổ gì.

### A3 (TRUNG) — uia-bridge là "screen reader cho cả máy" chưa có consent

`attach` + `snapshot`/`read` đọc được nội dung UI của BẤT KỲ app nào —
tương đương đọc file ngoài permissions. Hệ thống có sẵn mô hình
`permissions.json` cho folder — app native nên theo mô hình tương tự.

Vá: `attach` app ngoài whitelist → trả `{"ok":false,"kind":"need_consent"}`
→ agent hỏi học viên trong chat → confirm → ghi vào
`workspace/permissions.json` dạng `{"type":"app","name":...}` (hoặc
`apps.json` riêng). Whitelist hệ thống (dialog, Notepad...) không cần
hỏi. Ghi vào AGENTS.md: app native = "ngăn tủ" cần xin phép.

### A4 (TRUNG) — Không có guard chống bấm nhầm cửa sổ học viên

Mọi action ghi khi không truyền `tabId` default `activeTabId()` = tab
học viên đang nhìn. Trong silent-mode, agent quên truyền tabId =
bấm/gõ vào cửa sổ user.

Vá: khi `scope:"agent"`, sau `pickTab` verify
`tab.windowId === agentWinId` — tab ngoài → `{"ok":false,"err":...}`.
Skill quy định action ghi luôn truyền `tabId` hoặc `scope:"agent"`.

## Minor notes

- A5: Zalo Web lần đầu trong cửa sổ agent có thể cần quét QR một lần
  (nếu học viên chưa đăng nhập web) — ghi vào onboarding/skill.
- A6: `Page.captureScreenshot` nên `Page.enable` trước cho chắc; focus
  emulation tự reset khi detach (vẫn disable tay cho rõ).
- A7: uia-bridge chỉ cần HTTP, KHÔNG cần WebSocket (không có client
  thứ hai như extension) — skeleton đơn giản hơn ext-bridge, đừng copy
  phần WS/pending.
- A8: `emit_event` từ `/api/notify` là server-side path — không đụng
  whitelist `/api/emit-event` (audit-6 F8). Portal cần handler render
  event type `notify` (toast) — hiện app.js chưa có.
- A9: `tinsert mode=char` không gõ được dấu tiếng Việt ghép — hạn chế
  có sẵn, silent-mode không làm nó tệ hơn; dùng `insertText` cho text
  Việt, char-mode chỉ cho Sheets grid.
- A10: File tải trong cửa sổ agent hiện trong download shelf của user —
  chấp nhận, note.
- A11: Kiểm tra port 7685 trống khi implement (chưa ai dùng).
- A12: Học viên mở DevTools trên tab agent → attach debugger fail →
  trả lỗi rõ "đang bật devtools".

## Kết luận audit

Kiến trúc plan đứng; 2 CAO là vận hành (throttling, SW state) chứ không
đổi hướng. Vá A1–A4 vào phase files rồi mới bắt tay.
