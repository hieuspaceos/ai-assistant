// Trợ Lý AI — service worker.
// Giữ một kết nối WebSocket về ext-bridge trên máy (localhost:7684),
// nhận lệnh từ trợ lý, thực hiện trong browser thật của học viên,
// rồi trả kết quả về. Không gửi gì ra internet — chỉ nói với localhost.

const WS_URL = 'ws://127.0.0.1:7684/ext';
let ws = null;
let reconnectTimer = null;

function setBadge(on) {
  // Chữ nhỏ trên icon: ON = đang kết nối với trợ lý
  chrome.action.setBadgeText({ text: on ? 'ON' : '' });
  chrome.action.setBadgeBackgroundColor({ color: '#147a4f' });
}

function connect() {
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return;
  ws = new WebSocket(WS_URL);
  ws.onopen = () => setBadge(true);
  ws.onclose = ws.onerror = () => {
    setBadge(false);
    ws = null;
    if (!reconnectTimer) {
      reconnectTimer = setTimeout(() => { reconnectTimer = null; connect(); }, 3000);
    }
  };
  ws.onmessage = async (ev) => {
    let m;
    try { m = JSON.parse(ev.data); } catch { return; }
    if (!m.action) return;  // ping giữ kết nối
    const res = await handle(m.action, m.params || {});
    res.id = m.id;
    try { ws.send(JSON.stringify(res)); } catch {}
  };
}

// Service worker hay ngủ — alarm giữ nó thức và kết nối lại
chrome.alarms.create('keepalive', { periodInMinutes: 0.5 });
chrome.alarms.onAlarm.addListener(() => { if (!ws) connect(); });
chrome.runtime.onStartup.addListener(connect);
chrome.runtime.onInstalled.addListener(connect);
connect();

async function activeTabId() {
  const [t] = await chrome.tabs.query({ active: true, currentWindow: true });
  return t && t.id;
}

function sendToTab(tabId, msg) {
  return chrome.tabs.sendMessage(tabId, msg);
}

async function ensureContent(tabId) {
  // Content script có thể chưa chạy (trang mở trước khi cài extension)
  try {
    await chrome.scripting.executeScript({ target: { tabId }, files: ['content.js'] });
  } catch (e) {
    // trang chrome:// hoặc Web Store không cho chạy script
    throw new Error('trang này không cho extension chạy (trang hệ thống?)');
  }
}

const freshTabs = new Set();

// ── Sự kiện THẬT qua chrome.debugger (CDP Input domain) ─────────────
// Một số app (Zalo, Google Sheets grid, FB) check event.isTrusted —
// sự kiện synthetic từ content script bị bỏ qua. Input.* của CDP thì
// như chuột/bàn phím thật. Khi attach, Chrome hiện banner "đang gỡ lỗi" —
// hết việc nên detach.

function dbgCmd(tabId, method, params) {
  return chrome.debugger.sendCommand({ tabId }, method, params || {});
}

async function dbgEnsure(tabId) {
  try {
    await chrome.debugger.attach({ tabId }, '1.3');
  } catch (e) {
    if (!/already attached/i.test(String(e && e.message || e))) throw e;
  }
}

async function realClick(tabId, x, y, button) {
  await dbgEnsure(tabId);
  for (const type of ['mousePressed', 'mouseReleased']) {
    await dbgCmd(tabId, 'Input.dispatchMouseEvent',
      { type, x, y, button: button || 'left', clickCount: 1 });
  }
}

async function realMove(tabId, x, y) {
  await dbgEnsure(tabId);
  await dbgCmd(tabId, 'Input.dispatchMouseEvent', { type: 'mouseMoved', x, y });
}

async function realKey(tabId, key, modifiers) {
  const K = {
    Enter:     { code: 'Enter',     key: 'Enter',     vk: 13, text: '\r' },
    Tab:       { code: 'Tab',       key: 'Tab',       vk: 9 },
    Escape:    { code: 'Escape',    key: 'Escape',    vk: 27 },
    Backspace: { code: 'Backspace', key: 'Backspace', vk: 8 },
    Delete:    { code: 'Delete',    key: 'Delete',    vk: 46 },
    ArrowUp:   { code: 'ArrowUp',   key: 'ArrowUp',   vk: 38 },
    ArrowDown: { code: 'ArrowDown', key: 'ArrowDown', vk: 40 },
    ArrowLeft: { code: 'ArrowLeft', key: 'ArrowLeft', vk: 37 },
    ArrowRight:{ code: 'ArrowRight',key: 'ArrowRight',vk: 39 },
  }[key || 'Enter'] || { code: 'Key' + String(key).toUpperCase(), key, vk: String(key).toUpperCase().charCodeAt(0) };
  await dbgEnsure(tabId);
  const params = { code: K.code, key: K.key,
    windowsVirtualKeyCode: K.vk, nativeVirtualKeyCode: K.vk };
  if (K.text) { params.text = K.text; params.unmodifiedText = K.text; }
  if (modifiers) params.modifiers = modifiers; // bitmask: 1=Alt 2=Ctrl 4=Meta 8=Shift
  await dbgCmd(tabId, 'Input.dispatchKeyEvent', { type: 'keyDown', ...params });
  await dbgCmd(tabId, 'Input.dispatchKeyEvent', { type: 'keyUp', ...params });
}


async function inTab(tabId, action, params) {
  const id = tabId || await activeTabId();
  if (!id) return { ok: false, err: 'không tìm thấy tab' };
  try {
    // Content script cũ (trước khi extension cập nhật) vẫn trả lời action
    // quen thuộc → kiểm tra 'ping' một lần/tab: script cũ không hiểu nó
    // → nạp lại content.js mới. Sau extension reload, listener cũ chết →
    // sendToTab throw → cũng nạp lại.
    if (!freshTabs.has(id)) {
      const pong = await sendToTab(id, { action: 'ping' });
      if (!pong || !pong.ok) throw new Error('content script cũ');
      freshTabs.add(id);
    }
    const r = await sendToTab(id, { action, ...params });
    return r || { ok: true };
  } catch (e) {
    // thử nạp content script rồi gọi lại
    await ensureContent(id);
    freshTabs.add(id);
    const r = await sendToTab(id, { action, ...params });
    return r || { ok: true };
  }
}

async function handle(action, p) {
  try {
    switch (action) {
      case 'tabs': {
        const tabs = await chrome.tabs.query({});
        return { ok: true, tabs: tabs.map(t => ({ id: t.id, title: t.title, url: t.url, active: t.active })) };
      }
      case 'open': {
        const t = await chrome.tabs.create({ url: p.url || 'about:blank', active: true });
        return { ok: true, tabId: t.id };
      }
      case 'activate': {
        if (p.tabId) await chrome.tabs.update(p.tabId, { active: true });
        return { ok: true };
      }
      case 'close': {
        if (p.tabId) await chrome.tabs.remove(p.tabId);
        return { ok: true };
      }
      case 'screenshot': {
        // captureVisibleTab chỉ chụp tab ĐANG ACTIVE của một window —
        // nếu chỉ định tabId thì activate nó trước rồi chụp đúng window của nó
        let windowId = null;
        if (p.tabId) {
          const t = await chrome.tabs.get(p.tabId);
          await chrome.tabs.update(p.tabId, { active: true });
          windowId = t.windowId;
        }
        const dataUrl = await chrome.tabs.captureVisibleTab(windowId, { format: 'png' });
        return { ok: true, png_b64: dataUrl.split(',')[1] };
      }
      case 'reload':
        chrome.runtime.reload();
        return { ok: true };
      // Sự kiện THẬT (trusted) — dùng khi app bỏ qua sự kiện synthetic.
      // tclick: click chuột thật vào tâm phần tử (sel/ref → toạ độ, hoặc x,y).
      // ttype : click thật vào ô rồi gõ text thật (Input.insertText) —
      //         đường duy nhất gõ được vào editor Zalo/grid Sheets.
      // tkey  : nhấn phím thật (Enter, Tab, mũi tên...) sau click thật.
      case 'tclick': {
        const id = p.tabId || await activeTabId();
        await chrome.tabs.update(id, { active: true }); // toạ độ theo viewport
        let { x, y } = p;
        if (x == null || y == null) {
          const r = await inTab(id, 'rect', { sel: p.sel, ref: p.ref });
          if (!r.ok) return r;
          x = r.x; y = r.y;
        }
        await realClick(id, x, y, p.button);
        return { ok: true };
      }
      // tright: chuột phải (context menu). tmove: hover để lộ nút ẩn.
      case 'tright': {
        const id = p.tabId || await activeTabId();
        await chrome.tabs.update(id, { active: true });
        let { x, y } = p;
        if (x == null || y == null) {
          const r = await inTab(id, 'rect', { sel: p.sel, ref: p.ref });
          if (!r.ok) return r;
          x = r.x; y = r.y;
        }
        await realClick(id, x, y, 'right');
        return { ok: true };
      }
      case 'tmove': {
        const id = p.tabId || await activeTabId();
        await chrome.tabs.update(id, { active: true });
        let { x, y } = p;
        if (x == null || y == null) {
          const r = await inTab(id, 'rect', { sel: p.sel, ref: p.ref });
          if (!r.ok) return r;
          x = r.x; y = r.y;
        }
        await realMove(id, x, y);
        return { ok: true };
      }
      case 'ttype': {
        const id = p.tabId || await activeTabId();
        await chrome.tabs.update(id, { active: true });
        const r = await inTab(id, 'rect', { sel: p.sel, ref: p.ref });
        if (!r.ok) return r;
        await realClick(id, r.x, r.y);
        await new Promise(res => setTimeout(res, 400));
        if (p.text) {
          await dbgCmd(id, 'Input.insertText', { text: p.text });
        }
        return { ok: true };
      }
      // Chèn text THẬT tại con trỏ đang đứng — không click (dùng sau
      // khi đã chọn đúng ô/vị trí, vd grid Sheets).
      // mode mặc định 'ime' (Input.insertText — cho ô editable thường);
      // mode 'char' bắn keyDown/keyUp từng ký tự — cần cho canvas grid
      // như Google Sheets (nó bắt đầu edit ô trên keyDown thật).
      case 'tinsert': {
        const id = p.tabId || await activeTabId();
        await dbgEnsure(id);
        if (p.text && p.mode === 'char') {
          for (const ch of String(p.text)) {
            const up = ch.toUpperCase();
            const vk = /[A-Z0-9]/.test(up) ? up.charCodeAt(0)
                     : ch === ' ' ? 32 : 0;
            const kp = { code: /[A-Z]/.test(up) ? 'Key' + up
                       : /[0-9]/.test(up) ? 'Digit' + up : up,
                       key: ch, text: ch, unmodifiedText: ch,
                       windowsVirtualKeyCode: vk, nativeVirtualKeyCode: vk };
            await dbgCmd(id, 'Input.dispatchKeyEvent', { type: 'keyDown', ...kp });
            await dbgCmd(id, 'Input.dispatchKeyEvent', { type: 'keyUp', ...kp });
            await new Promise(r => setTimeout(r, 35));
          }
        } else if (p.text) {
          await dbgCmd(id, 'Input.insertText', { text: p.text });
        }
        return { ok: true };
      }
      case 'tkey': {
        const id = p.tabId || await activeTabId();
        await chrome.tabs.update(id, { active: true });
        if (p.sel || p.ref) {
          const r = await inTab(id, 'rect', { sel: p.sel, ref: p.ref });
          if (r.ok) {
            await realClick(id, r.x, r.y);
            await new Promise(res => setTimeout(res, 300));
          }
        }
        await realKey(id, p.key, p.modifiers);
        return { ok: true };
      }
      case 'tdetach': {
        const id = p.tabId || await activeTabId();
        try { await chrome.debugger.detach({ tabId: id }); } catch (e) {}
        return { ok: true };
      }
      case 'snapshot': case 'click': case 'type': case 'query':
      case 'scroll': case 'scrollables': case 'read': case 'wait':
      case 'fetch': case 'key': case 'paste': case 'rect':
      case 'dom': case 'styles': case 'assets': case 'css':
        return await inTab(p.tabId, action, p);
      default:
        return { ok: false, err: 'action lạ: ' + action };
    }
  } catch (e) {
    return { ok: false, err: String(e && e.message || e) };
  }
}
