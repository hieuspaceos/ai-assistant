/* "Chìa khoá nhà" cho mọi API bridge (:7682, :7684).
   File start mở portal kèm ?t=<mã> → lưu vào localStorage để mọi trang
   cùng origin (kể cả iframe chat/clone-view) dùng chung, rồi xoá mã khỏi
   thanh địa chỉ cho gọn.
   bfetch() = fetch + tự gắn X-Bridge-Token — CHỈ với 2 port bridge thật.
   Trước gắn cho MỌI URL loopback → request nạp nội dung /workspace/ trên
   :8080 cũng đèo token: một service worker scope /workspace/ (não ghi .js
   vào được vì đây là vùng write-allowlist) đọc trộm được header. :8080
   không cần token — request tới nó phải đi trần. */
(function () {
  const q = new URLSearchParams(location.search);
  const tok = q.get('t');
  if (tok) {
    localStorage.setItem('bridge_token', tok);
    q.delete('t');
    const rest = q.toString();
    history.replaceState(null, '',
      location.pathname + (rest ? '?' + rest : '') + location.hash);
  }
  window.BRIDGE_TOKEN = localStorage.getItem('bridge_token') || '';
  // Chỉ 2 port nói API bridge — :8080 (portal tĩnh) và :7681 (ttyd,
  // auth qua ?arg=) KHÔNG được đèo token theo header.
  const BRIDGE_PORTS = { '7682': 1, '7684': 1 };
  /* Mã kết nối trôi/lệch (mở 2 bản cài, bridge orphan giữ mã cũ): mọi API
     trả 401 nhưng portal trông vẫn "sống" → user tưởng hỏng không rõ vì sao.
     Bắt 401 đầu tiên trên port bridge → hiện banner chỉ đường sửa; bridge
     trả lời bình thường trở lại thì banner tự tắt. */
  let _warnEl = null;
  function _tokenWarn(show) {
    if (show) {
      if (_warnEl) return;
      _warnEl = document.createElement('div');
      _warnEl.style.cssText = 'position:fixed;top:0;left:0;right:0;' +
        'z-index:99999;background:#fff3cd;color:#5b4a00;padding:10px 16px;' +
        'font-size:14px;text-align:center;border-bottom:1px solid #e0c36a;' +
        'font-family:system-ui,sans-serif';
      _warnEl.innerHTML = '🔑 Trợ lý không nhận ra mã kết nối — ' +
        '<b>mở lại bằng file start</b> (hoặc biểu tượng Trợ Lý AI) rồi ' +
        'tải lại trang này.<br><span style="opacity:.75">The connection ' +
        'code is stale — reopen via the start file (or the Trợ Lý AI ' +
        'icon), then reload this page.</span>';
      const attach = () => document.body.appendChild(_warnEl);
      if (document.body) attach();
      else document.addEventListener('DOMContentLoaded', attach);
    } else if (_warnEl) {
      _warnEl.remove();
      _warnEl = null;
    }
  }
  window.bfetch = function (url, o) {
    o = o || {};
    let bridgeHit = false;
    try {
      const u = new URL(url, location.href);
      if ((u.hostname === 'localhost' || u.hostname === '127.0.0.1' ||
           u.hostname === '[::1]' || u.hostname === '::1') &&
          BRIDGE_PORTS[u.port]) {
        bridgeHit = true;
        o.headers = Object.assign(
          { 'X-Bridge-Token': window.BRIDGE_TOKEN }, o.headers || {});
      }
    } catch (e) { /* URL lạ → để fetch tự xử */ }
    const p = fetch(url, o);
    if (bridgeHit) p.then(r => _tokenWarn(r.status === 401), () => {});
    return p;
  };
})();
