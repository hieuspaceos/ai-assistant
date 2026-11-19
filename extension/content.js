// Trợ Lý AI — content script: chạy trong từng trang, đọc DOM và thao tác.
// Nhận lệnh từ background.js (service worker nhận từ ext-bridge localhost).
// Nạp lại (ensureContent) thì THAY listener cũ — code mới có hiệu lực ngay
// trên tab đang mở mà không cần tải lại trang, đồng thời tự phục hồi sau
// khi extension reload (listener cũ đã chết theo context cũ).
if (window.__troLyAI_handler) {
  try { chrome.runtime.onMessage.removeListener(window.__troLyAI_handler); } catch (e) {}
}

const ATTR = 'data-tlai';

function scrollableEls() {
  return [...document.querySelectorAll('body *')]
    .filter(el => el.scrollHeight - el.clientHeight > 50 && el.clientHeight > 60);
}

function visible(el) {
  const r = el.getBoundingClientRect();
  const s = getComputedStyle(el);
  return r.width > 2 && r.height > 2 &&
         s.visibility !== 'hidden' && s.display !== 'none' && +s.opacity > 0.05;
}

function labelOf(el) {
  const t = (el.getAttribute('aria-label') ||
             el.getAttribute('placeholder') ||
             el.innerText || el.value || el.name || el.title || '');
  return String(t).replace(/\s+/g, ' ').trim().slice(0, 80);
}

// Tạo "cây phần tử" rút gọn — mỗi phần tử tương tác được một ref (e1, e2...)
// để trợ lý chỉ cần nói "bấm e7" thay vì hiểu cả trang.
function snapshot() {
  const SEL = 'a,button,input,textarea,select,[role="button"],[role="link"],' +
              '[role="textbox"],[role="tab"],[role="menuitem"],[role="checkbox"],' +
              '[role="radio"],[role="combobox"],[contenteditable="true"],' +
              'h1,h2,h3,summary,label';
  const out = [];
  let i = 0;
  for (const el of document.querySelectorAll(SEL)) {
    if (i >= 300) break;
    if (!visible(el)) continue;
    const ref = 'e' + (++i);
    el.setAttribute(ATTR, ref);
    const tag = el.tagName.toLowerCase();
    const role = el.getAttribute('role');
    const type = el.getAttribute('type');
    let desc = tag;
    if (role) desc += ':' + role;
    if (type && tag === 'input') desc += '(' + type + ')';
    const lb = labelOf(el);
    const href = el.tagName === 'A' && el.href ? ' → ' + el.href.slice(0, 80) : '';
    out.push(`${ref} ${desc}${lb ? ' "' + lb + '"' : ''}${href}`);
  }
  return {
    ok: true, url: location.href, title: document.title,
    count: i, tree: out.join('\n')
  };
}

function byRef(ref) {
  return document.querySelector(`[${ATTR}="${ref}"]`);
}

function actClick(p) {
  let el;
  if (p.text) {
    // Bấm theo chữ hiển thị — cho site dùng div không ngữ nghĩa (Zalo, FB).
    // Ưu tiên khớp chính xác; không có thì lấy phần tử NHỎ NHẤT chứa chữ
    // (vd tên hội thoại nằm chung hàng với giờ + xem trước).
    const want = String(p.text).trim().toLowerCase();
    const cands = [...document.querySelectorAll('a,button,div,span,li,[role]')]
      .filter(e => visible(e));
    el = cands.filter(e => (e.innerText || '').trim().toLowerCase() === want &&
                           e.children.length <= 3)
              .sort((a, b) => a.innerText.length - b.innerText.length)[0];
    if (!el) {
      el = cands.filter(e => (e.innerText || '').toLowerCase().includes(want))
                .sort((a, b) => a.innerText.length - b.innerText.length)[0];
    }
    if (!el) return { ok: false, err: 'không thấy phần tử chữ "' + p.text + '"' };
  } else if (p.sel) {
    el = document.querySelector(p.sel);
    if (!el) return { ok: false, err: 'không thấy ' + p.sel };
  } else {
    el = byRef(p.ref);
    if (!el) return { ok: false, err: 'không thấy ' + p.ref + ' — trang đổi rồi, chụp snapshot lại' };
  }
  el.scrollIntoView({ block: 'center', behavior: 'instant' });
  // Chuỗi sự kiện chuột đầy đủ — nhiều app (Zalo, FB) bật editor trên
  // mousedown/focus chứ không phải click.
  for (const t of ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click']) {
    el.dispatchEvent(new MouseEvent(t, { bubbles: true, cancelable: true }));
  }
  el.focus();
  return { ok: true };
}

async function actType(p) {
  const el = p.sel ? document.querySelector(p.sel) : byRef(p.ref);
  if (!el) return { ok: false, err: 'không thấy ' + (p.sel || p.ref) };
  el.scrollIntoView({ block: 'center', behavior: 'instant' });
  // Với ô chưa editable (Zalo bật contenteditable sau click thật): bắn chuỗi
  // sự kiện chuột vào CHÍNH ô đó và chờ nó bật lên.
  if (!el.isContentEditable && el.getAttribute('contenteditable') !== null) {
    for (const t of ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click']) {
      el.dispatchEvent(new MouseEvent(t, { bubbles: true, cancelable: true }));
    }
    for (let i = 0; i < 10 && !el.isContentEditable; i++) {
      await new Promise(r => setTimeout(r, 60));
    }
  }
  el.focus();
  if (el.isContentEditable) {
    // Editor tự viết (Zalo, Slate, Draft.js...) đè lại mọi gán innerText —
    // chỉ execCommand mới bắn đúng chuỗi beforeinput/input như gõ thật.
    document.execCommand('selectAll', false, null);
    if (p.text) {
      document.execCommand('insertText', false, p.text);
    } else {
      document.execCommand('delete', false, null);
    }
  } else if ('value' in el) {
    el.value = p.text;
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  } else {
    return { ok: false, err: 'không gõ được vào phần tử này — cần click chuột thật trước' };
  }
  return { ok: true };
}

function actRead(p) {
  // Nội dung trang gọn gàng — bỏ script/style, giới hạn độ dài.
  // p.sel: chỉ đọc trong vùng chọn (vd '#sidebar'); mặc định cả trang.
  const root = p.sel ? document.querySelector(p.sel) : document.body;
  if (!root) return { ok: false, err: 'không thấy vùng ' + p.sel };
  const clone = root.cloneNode(true);
  clone.querySelectorAll('script,style,noscript,svg')
       .forEach(n => n.remove());
  const text = clone.innerText.replace(/\n{3,}/g, '\n\n').trim();
  return { ok: true, url: location.href, title: document.title,
           text: text.slice(0, 8000), truncated: text.length > 8000 };
}

// Lấy text của các phần tử khớp selector — linh hoạt cho site dùng div
// không ngữ nghĩa (Zalo, FB...). Chỉ đọc text hiển thị, không đọc
// thuộc tính nhạy cảm (value của input password bị chặn).
function actQuery(p) {
  const els = document.querySelectorAll(p.sel || '*');
  const out = [];
  for (const el of els) {
    if (out.length >= 100) break;
    if (!visible(el) && el.tagName !== 'IMG') continue;
    if (el.matches('input[type="password"]')) continue;
    // p.attr: lấy thuộc tính (vd 'src' của img, 'href' của a) thay vì chữ.
    // Thuộc tính trống/không có → thử property sống (value, checked của input).
    let t;
    if (p.attr) {
      let v = el.getAttribute(p.attr);
      if ((v === null || v === '') && typeof el[p.attr] !== 'object') v = el[p.attr];
      t = String(v ?? '');
    } else {
      t = String(el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim();
    }
    if (t) out.push(t.slice(0, 300));
  }
  return { ok: true, count: out.length, items: out };
}

const ACTIONS = {
  // background dùng ping để nhận biết content script mới — script cũ
  // không có action này nên trả "action lạ" → bị thay thế.
  ping: () => ({ ok: true, v: 2 }),
  snapshot,
  click: actClick,
  type: actType,
  scroll: p => {
    // p.sel: cuộn một vùng riêng (khung chat Zalo...); mặc định cả trang.
    // dy âm = cuộn lên (nạp tin nhắn cũ hơn).
    const dy = p.dy || 600;
    if (p.sel) {
      let el = document.querySelector(p.sel);
      if (!el || el.scrollHeight <= el.clientHeight) {
        // Ref sN (hoặc [data-tlai=sN]) bị trang render lại làm mất/trượt
        // → giải lại theo thứ tự vùng cuộn hiện tại.
        const m = /(s\d+)/.exec(p.sel);
        if (m) el = scrollableEls()[+m[1].slice(1) - 1] || null;
      }
      if (!el) return { ok: false, err: 'không thấy vùng cuộn ' + p.sel + ' — gọi scrollables lấy ref mới' };
      if (el.scrollHeight <= el.clientHeight)
        return { ok: false, err: 'vùng ' + p.sel + ' không cuộn được — nội dung vừa khung' };
      const before = el.scrollTop;
      el.scrollTop += dy;
      if (el.scrollTop === before)
        el.dispatchEvent(new WheelEvent('wheel', { deltaY: dy, bubbles: true }));
      return { ok: true, top: el.scrollTop, height: el.scrollHeight,
               atBottom: el.scrollTop + el.clientHeight >= el.scrollHeight - 4,
               atTop: el.scrollTop <= 0 };
    }
    scrollBy(0, dy);
    return { ok: true, y: scrollY };
  },
  read: actRead,
  query: actQuery,
  // Toạ độ tâm phần tử — phục vụ click/key THẬT qua chrome.debugger
  // (Input.dispatchMouseEvent) cho app check isTrusted như Zalo.
  rect: p => {
    const el = p.sel ? document.querySelector(p.sel) : byRef(p.ref);
    if (!el) return { ok: false, err: 'không thấy ' + (p.sel || p.ref) };
    el.scrollIntoView({ block: 'center', behavior: 'instant' });
    const r = el.getBoundingClientRect();
    return { ok: true, x: Math.round(r.left + r.width / 2),
             y: Math.round(r.top + r.height / 2),
             w: Math.round(r.width), h: Math.round(r.height) };
  },
  // Gửi phím (Enter, Tab, Escape, Delete, mũi tên) vào phần tử — nhiều
  // app như Google Sheets/Zalo chỉ xử lý khi nhận sự kiện bàn phím.
  key: p => {
    const el = p.sel ? document.querySelector(p.sel)
             : p.ref ? byRef(p.ref)
             : document.activeElement;
    if (!el) return { ok: false, err: 'không thấy phần tử nhận phím' };
    const key = p.key || 'Enter';
    const code = { Enter: 'Enter', Tab: 'Tab', Escape: 'Escape',
                   Delete: 'Delete', Backspace: 'Backspace',
                   ArrowUp: 'ArrowUp', ArrowDown: 'ArrowDown',
                   ArrowLeft: 'ArrowLeft', ArrowRight: 'ArrowRight' }[key] || key;
    for (const t of ['keydown', 'keypress', 'keyup'])
      el.dispatchEvent(new KeyboardEvent(t, { key, code, bubbles: true, cancelable: true }));
    return { ok: true };
  },
  // Dán text (bảng TSV, nhiều dòng) vào vị trí đang chọn — cách ghi
  // nhanh nhất vào Google Sheets: chọn ô đầu bằng name box rồi paste.
  paste: p => {
    const el = p.sel ? document.querySelector(p.sel)
             : document.activeElement || document.body;
    if (!el) return { ok: false, err: 'không thấy phần tử nhận paste' };
    const dt = new DataTransfer();
    dt.setData('text/plain', p.text);
    el.dispatchEvent(new ClipboardEvent('paste',
      { clipboardData: dt, bubbles: true, cancelable: true }));
    return { ok: true };
  },
  // Tải nội dung một URL BẰNG phiên đăng nhập của tab (cookie theo kèm,
  // cùng origin với trang đang mở) — đọc được sheet/file private mà
  // không cần share link hay cài MCP. Chỉ dùng với URL cùng site đang mở.
  fetch: async p => {
    try {
      const r = await fetch(p.url, { credentials: 'include' });
      const text = await r.text();
      return { ok: r.ok, status: r.status, text: text.slice(0, 900000),
               truncated: text.length > 900000 };
    } catch (e) {
      return { ok: false, err: String(e && e.message || e) };
    }
  },
  // Liệt kê các vùng cuộn được (scrollHeight > clientHeight) — để biết
  // khung chat/bảng dữ liệu nằm ở selector nào.
  scrollables: () => {
    const out = scrollableEls().slice(0, 20).map((el, i) => {
      el.setAttribute(ATTR, 's' + (i + 1));
      return `s${i + 1} ${el.tagName.toLowerCase()}${el.id ? '#' + el.id : ''}.${String(el.className).slice(0, 60)} h=${el.clientHeight} scroll=${el.scrollHeight}`;
    });
    return { ok: true, items: out };
  },
  wait: p => new Promise(r => setTimeout(() => r({ ok: true }), Math.min(p.ms || 1000, 5000))),
};

window.__troLyAI_handler = (msg, _s, sendResponse) => {
  const fn = ACTIONS[msg.action];
  if (!fn) { sendResponse({ ok: false, err: 'action lạ' }); return; }
  Promise.resolve(fn(msg)).then(sendResponse);
  return true; // async response
};
chrome.runtime.onMessage.addListener(window.__troLyAI_handler);
