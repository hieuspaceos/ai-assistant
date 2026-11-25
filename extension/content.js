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
  // Chỉ quét container có khả năng cuộn — leaf (span/a/img...) không bao
  // giờ là vùng cuộn; 'body *' trước đây quét cả cây (nghìn node, ép reflow).
  return [...document.querySelectorAll('main,section,article,aside,nav,div,ul,ol')]
    .slice(0, 4000)
    .filter(el => el.scrollHeight - el.clientHeight > 50 && el.clientHeight > 60);
}

function visible(el) {
  const r = el.getBoundingClientRect();
  const s = getComputedStyle(el);
  return r.width > 2 && r.height > 2 &&
         s.visibility !== 'hidden' && s.display !== 'none' && +s.opacity > 0.05;
}

function labelOf(el) {
  // KHÔNG đọc .value của ô password — mật khẩu đang gõ sẽ lọt vào
  // snapshot gửi về agent (actQuery đã chặn; đây là lỗ hổng còn lại).
  const t = (el.getAttribute('aria-label') ||
             el.getAttribute('placeholder') ||
             el.innerText ||
             (el.matches('input[type="password"]') ? '' : el.value) ||
             el.name || el.title || '');
  return String(t).replace(/\s+/g, ' ').trim().slice(0, 80);
}

// Khung hình chữ nhật của phần tử — clone cần biết kích thước/vị trí thật
function boxOf(el) {
  const r = el.getBoundingClientRect();
  return { x: Math.round(r.x), y: Math.round(r.y),
           w: Math.round(r.width), h: Math.round(r.height) };
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
    // Đọc innerText MỘT lần mỗi ứng viên (một layout flush) — trước đây đọc
    // lại trong filter rồi lại trong sort comparator → hàng chục nghìn reflow
    // trên trang nặng (Zalo/Sheets). Giữ nguyên ưu tiên: khớp chính xác
    // (children<=3, chuỗi ngắn nhất) → chứa chữ (chuỗi ngắn nhất).
    const cands = [...document.querySelectorAll('a,button,div,span,li,[role]')]
      .slice(0, 6000)                        // trần chống trang khổng lồ
      .filter(visible);
    // Prefilter bằng textContent (KHÔNG reflow) — chỉ đọc innerText (1
    // layout flush mỗi node) của ứng viên có khả năng khớp. Trước đây đọc
    // innerText cả 6000 node. Prefilter rỗng → fallback scan hết: innerText
    // có thể khác textContent (CSS text-transform, \n từ <br>).
    let pool = cands.filter(e => (e.textContent || '').toLowerCase().includes(want));
    if (!pool.length) pool = cands;
    const mapped = pool.map(e => ({ e, t: (e.innerText || '').toLowerCase() }));
    let hit = mapped.filter(c => c.t.trim() === want && c.e.children.length <= 3)
                    .sort((a, b) => a.t.length - b.t.length)[0];
    if (!hit) {
      hit = mapped.filter(c => c.t.includes(want))
                  .sort((a, b) => a.t.length - b.t.length)[0];
    }
    el = hit && hit.e;
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
      // Chỉ cùng origin trang đang mở — URL tuỳ ý + credentials:'include'
      // là kênh đọc session của site khác qua phiên đăng nhập học viên.
      const u = new URL(p.url, location.href);
      if (u.origin !== location.origin)
        return { ok: false, err: 'chỉ tải URL cùng trang đang mở' };
      const r = await fetch(u.href, { credentials: 'include' });
      const text = await r.text();
      return { ok: r.ok, status: r.status, text: text.slice(0, 900000),
               truncated: text.length > 900000 };
    } catch (e) {
      return { ok: false, err: String(e && e.message || e) };
    }
  },
  // ── Trích xuất phục vụ /clone-trang ─────────────────────────────
  // dom: HTML sống của trang (đã render xong JS) — bỏ script, giới hạn
  // kích thước. read chỉ lấy text; clone cần cấu trúc + class + inline svg.
  dom: p => {
    const root = p.sel ? document.querySelector(p.sel) : document.documentElement;
    if (!root) return { ok: false, err: 'không thấy vùng ' + p.sel };
    const c = root.cloneNode(true);
    c.querySelectorAll('script,noscript').forEach(n => n.remove());
    const html = c.outerHTML;
    const cap = p.max || 300000;
    return { ok: true, html: html.slice(0, cap), truncated: html.length > cap };
  },
  // styles: computed style THẬT của các phần tử khớp selector (hoặc các
  // phần tử con trong vùng sel khi deep=true). Đây là số liệu clone chuẩn —
  // màu/font/khoảng cách/cỡ đều lấy từ đây, không phỏng đoán.
  styles: p => {
    const PROPS = ['color', 'background-color', 'font-family', 'font-size',
      'font-weight', 'line-height', 'letter-spacing', 'text-transform',
      'padding', 'margin', 'border', 'border-radius', 'box-shadow',
      'display', 'gap', 'width', 'height', 'max-width',
      'justify-content', 'align-items', 'text-align', 'background-image'];
    const pick = el => {
      const s = getComputedStyle(el);
      const o = {};
      for (const k of PROPS) {
        const v = s.getPropertyValue(k);
        if (v && v !== 'none' && v !== 'normal' && v !== '0px'
            && v !== 'auto' && v !== 'rgba(0, 0, 0, 0)') o[k] = v;
      }
      return o;
    };
    const idOf = el => {
      let s = el.tagName.toLowerCase();
      if (el.id) s += '#' + el.id;
      const cls = String(el.className && el.className.baseVal !== undefined
        ? el.className.baseVal : el.className).trim();
      if (cls) s += '.' + cls.split(/\s+/).slice(0, 2).join('.');
      return s.slice(0, 80);
    };
    if (p.deep) {
      const root = p.sel ? document.querySelector(p.sel) : document.body;
      if (!root) return { ok: false, err: 'không thấy vùng ' + p.sel };
      const out = [];
      const walk = (el, depth) => {
        if (out.length >= 120 || depth > (p.depth || 3)) return;
        if (visible(el)) out.push({ el: idOf(el), box: boxOf(el), css: pick(el) });
        for (const ch of el.children) walk(ch, depth + 1);
      };
      walk(root, 0);
      return { ok: true, count: out.length, items: out };
    }
    const els = [...document.querySelectorAll(p.sel || 'body')];
    const items = els.slice(0, 30).map(el => ({ el: idOf(el), box: boxOf(el), css: pick(el) }));
    return { ok: true, count: els.length, items };
  },
  // assets: danh mục "nguyên liệu hình" của trang — ảnh, icon svg inline,
  // font đang nạp, stylesheet link, background-image. Clone giống hệt cần
  // biết trang mẫu dùng font/icon/ảnh gì.
  assets: () => {
    const imgs = [...document.images].slice(0, 80).map(i => ({
      src: i.currentSrc || i.src, alt: (i.alt || '').slice(0, 80),
      w: i.naturalWidth, h: i.naturalHeight }));
    const svgs = [...document.querySelectorAll('svg')].slice(0, 60)
      .map(s => { const c = s.cloneNode(true);
        c.querySelectorAll('script').forEach(n => n.remove());
        return c.outerHTML.slice(0, 4000); });
    const cssLinks = [...document.querySelectorAll('link[rel="stylesheet"],link[rel="preload"]')]
      .map(l => l.href).slice(0, 60);
    const fonts = new Set();
    try { document.fonts.forEach(f => fonts.add(`${f.family} ${f.weight}`)); } catch (e) {}
    const bgs = new Set();
    const addBg = b => { if (b && b !== 'none')
      for (const m of b.matchAll(/url\(["']?([^"')]+)/g)) bgs.add(m[1]); };
    // cap scan nền — getComputedStyle mỗi node là một layout read.
    // 1) inline style: không reflow → quét rẻ hết body.
    for (const el of [...document.querySelectorAll('body *')].slice(0, 5000)) {
      if (bgs.size >= 40) break;
      addBg(el.style && el.style.backgroundImage);
    }
    // 2) stylesheet bg: chỉ đo computed ở node "đáng ngờ" (class/id/style
    // hint) trước; vẫn thiếu mới quét rộng với cap nhỏ hơn (1500 vs 5000).
    for (const el of [...document.querySelectorAll(
        'body [class*="bg"],body [class*="hero"],body [class*="banner"],' +
        'body [class*="cover"],body [class*="masthead"],body [id*="hero"],' +
        'body [id*="banner"],body [style]')].slice(0, 400)) {
      if (bgs.size >= 40) break;
      addBg(getComputedStyle(el).backgroundImage);
    }
    if (bgs.size < 40) {
      for (const el of [...document.querySelectorAll('body *')].slice(0, 1500)) {
        if (bgs.size >= 40) break;
        addBg(getComputedStyle(el).backgroundImage);
      }
    }
    return { ok: true, title: document.title, images: imgs, svgs,
             cssLinks, fonts: [...fonts].slice(0, 30), bgImages: [...bgs] };
  },
  // css: nội dung các stylesheet trang đang dùng (CSSOM — đọc được cả rule
  // do JS bơm). Sheet chặn CORS thì chỉ trả href để gọi fetch lấy nội dung.
  css: p => {
    const out = [];
    for (const ss of document.styleSheets) {
      try {
        const rules = [...ss.cssRules].map(r => r.cssText).join('\n');
        out.push({ href: ss.href || null, css: rules.slice(0, 200000),
                   truncated: rules.length > 200000 });
      } catch (e) {
        out.push({ href: ss.href || null, err: 'blocked' });
      }
      if (out.length >= 40) break;
    }
    return { ok: true, sheets: out };
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
