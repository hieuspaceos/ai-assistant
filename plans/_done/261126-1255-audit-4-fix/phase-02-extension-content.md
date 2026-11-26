# Phase 02 — content.js: ref do trang kiểm soát + snapshot/dom lộ secrets

## Vá

Ba finding cùng một gốc: **nội dung trang là untrusted nhưng agent lại
tin DOM của trang** — cả ở chiều trang→agent (giá trị form lọt vào
snapshot) lẫn agent→trang (ref click trang tự đặt được).

## 2.1 — ref `data-tlai` trong DOM (`content.js:10,54-77`)

Audit đề xuất hai mức: dọn attr cũ trước snapshot (gọn, ~3 dòng) hoặc
Map ref→el (đúng hơn). **Chọn Map** — vì dọn trước snapshot vẫn hở:
page JS chạy song song, gắn `data-tlai="e7"` lên nút mồi TRONG KHOẢNG
giữa snapshot và click → vẫn điều khiển được mục tiêu. Map sống trong
isolated world của content script → page JS không đọc/ghi được, ref giả
bất khả thi.

```js
const ATTR = 'data-tlai';
const refMap = new Map();   // ref -> Element; isolated world, page
                            // JS không chạm được — ref giả bất khả thi

// snapshot(): trong loop, sau el.setAttribute(ATTR, ref):
refMap.set(ref, el);
// (giữ setAttribute — vô hại, giúp debug/định vị bằng mắt; byRef không
// đọc DOM nên attr giả của trang không làm gì được)
// Đầu snapshot(): refMap.clear();

// scrollables: refMap.set('s' + (i + 1), el) bên cạnh setAttribute

function byRef(ref) {
  const el = refMap.get(ref);
  // detached sau re-render → coi như mất, báo chụp lại snapshot
  return el && el.isConnected ? el : null;
}
```

Cạnh cần nhớ:

- `refMap.clear()` ở đầu `snapshot()` — map tích luỹ phần tử cũ giữ
  chúng sống (leak nhẹ) và ref cũ vẫn resolve được (đúng cái audit
  gọi là "bấm nhầm").
- Re-inject (`ensureContent`) tạo script mới → `const refMap` mới →
  ref cũ chết theo context cũ — đúng hướng (mechanism `ping`/`freshTabs`
  đã bảo đảm script mới).
- Attr `s1..sN` trên scrollables giữ nguyên setAttribute + map — fallback
  re-resolve theo index ở `scroll` (`:219-222`) đã có, giữ.

## 2.2 — `labelOf` đọc `el.value` (`content.js:33`)

Ô `input text/tel/select/textarea` không label/placeholder → giá trị
đang gõ (số thẻ, OTP, bản nháp) lọt vào tree → transcript. Bỏ hẳn
`.value` khỏi fallback — ô không label vẫn hiện `input(text)` đủ định
vị; `name`/`title` còn lại phía sau:

```js
const t = (el.getAttribute('aria-label') ||
           el.getAttribute('placeholder') ||
           el.innerText ||
           el.name || el.title || '');
```

Nếu sau này thấy snapshot thiếu gợi ý cho ô không-label, thêm
`verbose`-gated value — nhưng mặc định tắt. (Cập nhật comment dòng
28-29: không chỉ password — mọi value đều là dữ liệu người dùng.)

## 2.3 — `dom` action lộ hidden input + CSRF meta (`content.js:300-308`)

Clone giữ nguyên `<input type=hidden value=…>` (token CSRF của
Django/Rails/WP) và `<meta name=csrf-token content=…>` → secrets phiên
rơi vào transcript. Trên clone, strip `value` của MỌI input (giá trị
đang gõ cũng là user data) + `content` của meta tên nhạy cảm:

```js
const c = root.cloneNode(true);
c.querySelectorAll('script,noscript').forEach(n => n.remove());
// clone chỉ cần layout/style — giá trị form là dữ liệu người dùng,
// hidden input thường là CSRF token của framework
c.querySelectorAll('input').forEach(n => n.removeAttribute('value'));
c.querySelectorAll('meta[name]').forEach(n => {
  if (/csrf|token|nonce|secret/i.test(n.getAttribute('name') || ''))
    n.removeAttribute('content');
});
```

Ghi chú: `actQuery` (`:186-195`) đã có whitelist attr từ audit-3 —
nhất quán hoá comment để hai nơi cùng một threat model.

## Test

- Trang test: `data-tlai="e7"` gắn sẵn trên nút mồi → snapshot →
  `click e7` phải bấm phần tử refMap gán (verify bằng listener log),
  không bấm mồi. Snapshot lần 2 sau khi phần tử bị remove → `click eN`
  trả `không thấy … chụp snapshot lại` thay vì bấm attr cũ sót.
- Form có `input[type=text]` đang gõ "4111..." + hidden input CSRF +
  `meta[name=csrf-token]` → `snapshot` không chứa "4111"; `dom` HTML
  không chứa `value=` của input và không chứa `content=` của meta csrf.
- Ô không-label → tree vẫn có dòng `eN input(text)` (định vị được).
- Snapshot → re-render trang xoá phần tử → ref báo lỗi rõ, không throw.

## Done khi

Page JS không điều khiển được mục tiêu của `click eN`; snapshot/dom
không lộ giá trị form hay token phiên; ref cũ không bấm nhầm.
