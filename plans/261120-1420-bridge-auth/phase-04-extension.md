# Phase 4 — Extension pairing

## Mục tiêu

Extension nối `ws://127.0.0.1:7684/ext?token=…`. Hai đường nạp token:
auto-pair từ trang portal (đường chính, zero-paste) + options page (fallback).

## File động

| File | Action | Việc |
|---|---|---|
| `extension/manifest.json` | modify | `key` cố định + `externally_connectable` + `options_ui` |
| `extension/background.js` | modify | đọc token từ `chrome.storage`, nối `?token=`, onMessage pair |
| `extension/options.html` | create | ô dán mã fallback + lưu chrome.storage |

## Chi tiết

### manifest.json

```json
{
  "key": "<base64 public key — sinh một lần bằng openssl, embed cố định>",
  "externally_connectable": {
    "matches": ["*://localhost:*/*", "*://127.0.0.1:*/*"]
  },
  "options_ui": { "page": "options.html", "open_in_tab": false },
  "permissions": ["tabs", "debugger", "scripting", "storage", ...]
}
```

- `key` cố định → extension ID ổn định giữa mọi máy → onboarding biết ID
  để `sendMessage`. Sinh key một lần trong khi implement, commit vào manifest
  (key public, ID không phải secret).
- `externally_connectable.matches` giới hạn localhost → trang web khác
  không gửi message được. Message duy nhất nhận: `{t:'set-token'}` — kẻ lạ
  overwrite token chỉ gây DoS reconnect, không đánh cắp gì.

### background.js

```js
const WS_BASE = 'ws://127.0.0.1:7684/ext';
let extToken = null;
chrome.storage.local.get('bridge_token', d => { extToken = d.bridge_token; connect(); });
chrome.runtime.onMessageExternal.addListener((m, sender, reply) => {
  if (m && m.t === 'set-token' && typeof m.token === 'string') {
    extToken = m.token;
    chrome.storage.local.set({bridge_token: m.token});
    try { ws && ws.close(); } catch(e) {}
    connect();
  }
});
function connect() {
  if (!extToken) return;   // chưa pair — chờ, badge hiện "cần mã"
  ws = new WebSocket(WS_BASE + '?token=' + encodeURIComponent(extToken));
  ...
}
```

Badge: `chrome.action.setBadgeText` "!" khi chưa pair.

### options.html (fallback)

Ô text + nút Lưu → `chrome.storage.local.set({bridge_token})` + báo đã lưu.
Onboarding/⚙ settings chỉ user vào options khi auto-pair thất bại.

## Acceptance

- Extension chưa pair → không spam connect, badge "!"
- Onboarding auto-pair → `chrome.storage` có token, WS nối `/ext?token=` →
  `{"action":"status"}` trả connected (qua ext-bridge có token)
- Token sai → bị 401, reconnect giữ nguyên (không crash)
- Options paste → reload, connect OK

## Rủi ro

- `key` trong manifest đổi extension ID → user đã cài bản cũ phải remove +
  load unpacked lại (ghi vào SETUP.md + onboarding nhắc)
