# Phase 03 — background.js + manifest.json + handler content.js

## Vá

Năm vá nhỏ trong background/manifest + một dòng trong content handler.
Cùng theme: kênh lệnh phải báo thật khi gãy, và resource (debugger,
token) phải tự hồi.

## 2.6 — `r || {ok:true}` nuốt sự cố + `__proto__` (`background.js:179-186`, `content.js:423`)

Hai đầu:

```js
// content.js:423 — tra own property, không inherited
const fn = Object.hasOwn(ACTIONS, msg.action) ? ACTIONS[msg.action] : null;
```

```js
// background.js:180,186 — content script không trả lời ≠ thành công
const r = await sendToTab(id, { ...params, action });
return r || { ok: false, err: 'content script không trả lời' };
```

## 2.7 — `{action, ...params}` → `{...params, action}` (`background.js:179,185`)

Latent bypass: params có key `action` sẽ đè action allowlist. Đảo thứ
tự — `action` luôn thắng:

```js
const r = await sendToTab(id, { ...params, action });
```

## 2.4 — debugger không tự detach (`background.js:113-163, 317-321`)

Idle-detach qua timestamp + alarm keepalive sẵn có (chu kỳ 0.5 phút):

```js
const dbgLast = {};   // tabId -> ts lệnh dbg cuối

function dbgCmd(tabId, method, params) {
  dbgLast[tabId] = Date.now();
  return chrome.debugger.sendCommand({ tabId }, method, params || {});
}
```

Trong `chrome.alarms.onAlarm` (dòng 74) thêm quét:

```js
const now = Date.now();
for (const [id, ts] of Object.entries(dbgLast)) {
  if (now - ts > 120_000) {          // 2 phút idle → thả banner
    try { chrome.debugger.detach({ tabId: +id }); } catch (e) {}
    delete dbgLast[id];
  }
}
```

`chrome.debugger.onDetach` listener xoá `dbgLast[tabId]` khi user/devtools
detach ngoài ý muốn. SW ngủ thì alarm đánh thức — không cần timer riêng.

## 2.5 — URL assertion (`background.js:166-188`, các case t*)

⚠ Đã audit lại: **KHÔNG đặt check trong `inTab`** — các case t* gọi
`inTab(id,'rect',{ sel: p.sel, ref: p.ref })` với params MỚI, không mang
`p.expectUrl` → check đặt trong inTab sẽ không chạy cho tclick/ttype
(trùng bug "validate ở chỗ không tới được" của audit-3).

Hai lớp:

1. Mọi response kèm `url` hiện tại — agent tự kiểm trang đổi. Gắn ở CẢ
   HAI nhánh return của `inTab` (dòng 180 và 186) — hoặc gom về một
   exit:

```js
try { r.url = (await chrome.tabs.get(id)).url; } catch (e) {}
```

2. `expectUrl` tuỳ chọn — check ở ĐẦU `handle()`, một chỗ phủ hết mọi
   action kể cả x,y thuần:

```js
async function handle(action, p) {
  try {
    if (p.expectUrl) {
      const id0 = p.tabId || await activeTabId();
      const t0 = await chrome.tabs.get(id0).catch(() => null);
      if (!t0 || !(t0.url || '').startsWith(p.expectUrl))
        return { ok: false, err: 'tab không còn đúng trang',
                 url: t0 && t0.url };
    }
    switch (action) { ... }
```

Không strip `expectUrl` khỏi params gửi vào content script — actions
bỏ qua key lạ, vô hại.

## S3 — `externally_connectable` siết port (`manifest.json:10`)

Portal pin cứng `:8080` (`launcher.py:237` `jobs=[("serve",8080)…]`).
Mọi port khác host trang lạ → không cần connect được:

```json
"matches": ["*://localhost:8080/*", "*://127.0.0.1:8080/*"]
```

## S4 — token sai → reconnect loop vô hạn (`background.js:30-36,51-60`)

Token rác ghi đè `extToken` trong RAM → WS 401 → close → 3s retry mãi.
Đếm close-chưa-mở; sau 3 lần nạp lại token đúng từ storage:

```js
// trong connect(), sau ws = new WebSocket(...):
const sock = ws;                 // ⚠ bắt buộc capture — onclose đọc
                                 // biến global `ws` tại LÚC FIRE, lúc đó
                                 // ws có thể đã là socket MỚI → check
                                 // _opened nhầm socket
sock.onopen = () => {
  sock._opened = true;
  badTokenFails = 0;             // reset — mở được = token đúng
  ...
};
sock.onclose = sock.onerror = () => {
  if (!sock._opened) {
    badTokenFails++;
    if (badTokenFails >= 3) {
      badTokenFails = 0;
      // token RAM có thể là rác do trang lạ đẩy — nạp lại token đã
      // persist (storage chỉ ghi sau onopen thành công → luôn đúng)
      chrome.storage.local.get('bridge_token', d => {
        if (d.bridge_token && d.bridge_token !== extToken) {
          extToken = d.bridge_token;
        }
      });
    }
  }
  ...
};
```

`let badTokenFails = 0;` cạnh `reconnectTimer`. Cạnh đã kiểm:

- Manual `ws.close()` khi set-token mới: ws cũ chưa mở → tính 1 fail —
  3 lần mới trigger, và lúc đó extToken đã là token mới → storage reload
  chỉ đè khi `!== extToken` → vô hại (thật ra có lợi: spam set-token rác
  tự khôi phục token đúng).
- Bridge CHẾT (không phải token sai): close-chưa-mở cũng tính fail →
  sau 3 lần reload token — `d.bridge_token === extToken` → skip, vô hại.
- `sock.onopen` đặt flag trên instance, KHÔNG dùng `ws._opened` toàn
  cục — đúng socket nào check socket đó.

## Test

- `handle('__proto__')` qua WS giả → `{ok:false}` không phải `ok:true`.
- `sendToTab` resolve undefined (kill listener) → agent thấy `ok:false
  err 'content script không trả lời'`.
- tclick xong → đợi ~2.5 phút (hoặc giảm ngưỡng khi test) → banner
  "gỡ lỗi" tự hết, `chrome.debugger` detach.
- Snapshot tab A → navigate tab A sang trang khác → `click` kèm
  `expectUrl` cũ → `ok:false` + url mới trong err response.
- `onMessageExternal` từ trang `localhost:9999` → Chrome chặn hẳn
  (manifest) — `localhost:8080` vẫn pair được.
- Đẩy token rác → WS retry ~3 lần → tự nạp token đúng → connect lại
  được (badge ON).

## Done khi

Action thất bại không bao giờ báo `ok:true`; debugger tự thả sau idle;
response action nào cũng kèm url; chỉ portal :8080 gọi được extension.
