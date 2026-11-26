# Phase 3 — Portal/web plumbing

## Mục tiêu

Portal nhận token từ URL `?t=`, giữ trong `localStorage`, gắn
`X-Bridge-Token` vào MỌI fetch tới :7682/:7684; hiện "mã kết nối" trong ⚙
để user copy cho extension.

## File động

| File | Action | Việc |
|---|---|---|
| `web/app.js` | modify | bootstrap token + wrapper fetch + dòng Mã kết nối |
| `web/chat.html` | modify | đọc localStorage, gắn header mọi fetch |
| `web/clone-view.html` | modify | gắn token vào `/api/save-page` (SÓT trong bản plan đầu) |
| `web/onboarding.html` | modify | gắn token vào fetch `/api/*` |

## Chi tiết

### Bootstrap — chung cho mọi trang (đoạn đầu mỗi file JS)

```js
const _q = new URLSearchParams(location.search);
if (_q.get('t')) {
  localStorage.setItem('bridge_token', _q.get('t'));
  history.replaceState(null, '', location.pathname + location.hash);
}
const BRIDGE_TOKEN = localStorage.getItem('bridge_token') || '';
const bfetch = (url, o = {}) => {
  o.headers = Object.assign({'X-Bridge-Token': BRIDGE_TOKEN}, o.headers || {});
  return fetch(url, o);
};
```

- `app.js`: thay mọi `fetch(BRIDGE_URL…)` → `bfetch(...)`; khi token rỗng
  → hiện `hintNotReady` ("mở lại bằng file start").
- `chat.html`/`clone-view.html`: iframe cùng origin :8080 → đọc chung
  `localStorage` trực tiếp, KHÔNG cần `?t=` trong src; chỉ cần wrapper.
- `onboarding.html`: mọi `fetch(BRIDGE…)` → `bfetch`.

### "Mã kết nối" trong ⚙ settings (`index.html` + `app.js`)

Dưới `#brain-row`, thêm hàng: `<code>` hiện token (đọc từ localStorage) +
nút copy (`navigator.clipboard.writeText`). i18n: `connCode` /
`connCodeHint` vi+en — giải thích "dán vào extension khi nó hỏi mã".

### Onboarding — auto-pair extension (chuẩn bị cho phase 4)

Chỗ bước extension đã cài: sau khi detect extension → thử
`chrome.runtime.sendMessage(EXT_ID, {t:'set-token', token:BRIDGE_TOKEN})`
trong try/catch (ID cố định nhờ manifest `key` phase 4).

## Acceptance

- Mở `web/?t=<token>` → localStorage có token, URL sạch (replaceState)
- Reload trang (không `?t=`) → vẫn fetch được (token trong localStorage)
- Xoá localStorage → mọi fetch 401 → hint "chạy lại start" hiện
- chat iframe hoạt động bình thường (cùng origin share storage)
- clone-view "Lưu lại trang" vẫn ghi được

## Rủi ro

- Sót `fetch()` nào đó không qua `bfetch` → audit grep `fetch(` mỗi file
  trước khi đóng phase
