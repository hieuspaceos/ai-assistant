# Phase 01 — Extension: cửa sổ agent + thao tác nền

## Phase 00 trước — spike (điều kiện vào)

Bốn thí nghiệm, mỗi cái < 30 phút, ghi kết quả vào `findings.md`:

| # | Thí nghiệm | Cách | Pass khi |
|---|---|---|---|
| 00a | CDP input trên tab nền | Attach debugger vào tab KHÔNG active → `Emulation.setFocusEmulationEnabled{enabled:true}` → `Input.dispatchMouseEvent` + `Input.insertText` + `dispatchKeyEvent` (char mode) trên Zalo Web `#richInput` và Google Sheets grid | Tin/ô nhận chữ, `isTrusted` ok, không cần activate |
| 00b | Screenshot tab nền | `Page.captureScreenshot{format:'png',fromSurface:true}` trên tab nền | PNG đúng nội dung, không rỗng/đen |
| 00c | Window không focus | `chrome.windows.create({focused:false})` → kiểm: window có lên trước không; `tabs.update(active)` trong window nền có raise không (thử cả mac + Win11 VM); nếu raise → `windows.update({focused:false})` đẩy lại có kéo xuống không | Cửa sổ user không bị đổi z-order |
| 00d | Coverage nút nền | Win11 VM (UTM): `uiautomation` đọc tree Notepad, dialog Save/Open, Zalo desktop, Chrome dialog → thử `InvokePattern.Invoke` + `ValuePattern.SetValue`. macOS: pyobjc AX đọc TextEdit, Finder dialog, Safari, Zalo macOS → thử `AXPress` + set `AXValue` | Biết rõ app nào "thấy"/"mù" → whitelist + danh sách no_pattern |
| 00e | Throttling tab nền | Tab trong cửa sổ bị che kín (occluded)/không active: (1) scroll virtualized list Zalo Web có nạp item không; (2) timer/rAF của trang có khựng; (3) thử `Page.setWebLifecycleState{state:'active'}` | Biết được có cần "để cửa sổ agent lộ một dải" / Space riêng không |

Nếu 00a FAIL: t* vẫn cần activate → giữ cửa sổ agent nhưng chấp nhận nó
nhảy lên khi t* chạy (vẫn tốt hơn giật tab trong cửa sổ user); hạ mục
tiêu xuống "DOM-actions nền, t* trong cửa sổ riêng".

## Thay đổi `extension/background.js`

### 1. Agent window

MV3 service worker bị Chrome giết bất cứ lúc nào → `agentWinId` trong
biến thường sẽ mất → cửa sổ trùng. Vì vậy: persist vào
`chrome.storage.session` + tab đầu là **marker page**
`agent-home.html` (extension page: "Cửa sổ làm việc của Trợ Lý AI —
đừng đóng nhé") — vừa là dấu nhận diện để re-discover khi storage mất
(browser restart + session restore), vừa giải thích cho học viên.

```js
const AGENT_HOME = chrome.runtime.getURL('agent-home.html');
let agentWinId = null;   // cache; nguồn thật: chrome.storage.session

async function agentWindow() {
  if (agentWinId == null) {
    const s = await chrome.storage.session.get('agentWinId');
    agentWinId = s.agentWinId ?? null;
  }
  if (agentWinId != null) {
    try { return await chrome.windows.get(agentWinId); } catch (e) {}
    agentWinId = null;
  }
  // mất id (SW restart / restore) — tìm cửa sổ có tab marker còn sống
  const wins = await chrome.windows.getAll({ populate: true });
  const found = wins.find(w => (w.tabs || []).some(t => t.url === AGENT_HOME));
  if (found) {
    agentWinId = found.id;
  } else {
    const w = await chrome.windows.create({
      url: AGENT_HOME, focused: false,
      width: 1100, height: 750, type: 'normal',
      // vị trí né giữa màn hình; spike 00e quyết: giữ lộ một dải
      // chống occlusion-throttle hay để Space riêng
      left: 60, top: 60,
    });
    agentWinId = w.id;
  }
  await chrome.storage.session.set({ agentWinId });
  return await chrome.windows.get(agentWinId);
}
chrome.windows.onRemoved.addListener(id => {
  if (id === agentWinId) agentWinId = null;
});
```

### 2. Action `open` — thêm `scope`

`{"action":"open","url":...,"scope":"agent"}` → tạo tab trong
`agentWindow()` (`chrome.tabs.create{windowId, active:true}` — activate
trong cửa sổ riêng, không đụng cửa sổ user). `scope` mặc định `user` =
hành vi cũ, không phá back-compat.

### 3. `tabs` — trả thêm `windowId` + cờ `agent`

Để agent biết tab nào thuộc cửa sổ mình mà thao tác nền.

### 4. `activeTabId()` — tách `agentTabId()`

```js
async function agentTabId() {
  const w = await agentWindow();           // tự tạo nếu chưa có
  const [t] = await chrome.tabs.query({ windowId: w.id, active: true });
  return t && t.id;
}
```

Quy tắc chọn tab mặc định: `p.tabId` → dùng; `p.scope==='agent'` →
`agentTabId()`; không gì → `activeTabId()` (hành vi cũ). Một helper
`pickTab(p)` thay `p.tabId || await activeTabId()` ở mọi handler t*.

**Guard chống bấm nhầm cửa sổ học viên** (A4): mọi action GHI
(`click`/`type`/`key`/`paste`/`scroll`/nhóm `t*`/`close`) khi có
`scope:'agent'` phải verify `tab.windowId === agentWinId` — tab ngoài
→ `{"ok":false,"err":"tab không thuộc cửa sổ của trợ lý"}`. Skill quy
định: action ghi luôn truyền `tabId` hoặc `scope:"agent"`.

### 5. Silent `t*`

Sau `dbgEnsure(id)` thêm một lần (idempotent):

```js
await dbgCmd(id, 'Emulation.setFocusEmulationEnabled', { enabled: true });
```

Rồi bỏ `chrome.tabs.update(id,{active:true})` **khi `t.windowId === agentWinId`**.
Tab ngoài cửa sổ agent giữ activate như cũ (back-compat) nhưng skill mới
sẽ khuyên không làm vậy.

Nếu spike 00c thấy activate-tab-trong-window-nền vẫn raise window: sau
mỗi activate trong agent window gọi
`chrome.windows.update(agentWinId, {focused:false})`.

### 6. Silent `screenshot`

Đổi sang CDP — không cần tab active (gọi `Page.enable` một lần sau
`dbgEnsure` cho chắc; capture force BeginFrame nên tab nền vẫn ra ảnh):

```js
case 'screenshot': {
  const id = p.tabId || (p.scope === 'agent' ? await agentTabId() : await activeTabId());
  await dbgEnsure(id);
  const shot = await dbgCmd(id, 'Page.captureScreenshot', { format: 'png' });
  return { ok: true, png_b64: shot.data };
}
```

Giữ `captureVisibleTab` làm fallback khi `p.legacy===true`.

### 7. `tdetach` + alarm sweep

Đã có auto-detach sau 2 phút idle — giữ. `tdetach` thêm
`Emulation.setFocusEmulationEnabled{enabled:false}` trước khi detach
(sạch sẽ, tránh tab "ảo focus" sót lại).

## ext-bridge.py

Không đổi code — action mới (`scope`) chỉ là field forward qua WS. Chỉ
cập nhật docstring + `docs/api-reference.md` cho `scope:"agent"`,
`agentTabId`, screenshot nền.

## Acceptance

- `open scope=agent` → tab mở trong cửa sổ riêng, cửa sổ user không đổi
  z-order (đo bằng tay trên Windows + macOS).
- `tclick`/`ttype` vào tab trong agent window: viewport user không giật,
  `document.hasFocus()` của tab đó trả true (nhờ emulation).
- `screenshot` của tab nền trả ảnh đúng, không activate.
- Mọi action cũ (không `scope`) hành vi y hệt — regression `test-bridges.py`
  phần ext không cần sửa expectation.
