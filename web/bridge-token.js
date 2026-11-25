/* "Chìa khoá nhà" cho mọi API bridge (:7682, :7684).
   File start mở portal kèm ?t=<mã> → lưu vào localStorage để mọi trang
   cùng origin (kể cả iframe chat/clone-view) dùng chung, rồi xoá mã khỏi
   thanh địa chỉ cho gọn.
   bfetch() = fetch + tự gắn X-Bridge-Token — CHỈ với 2 port bridge thật.
   Trước gắn cho MỌI URL loopback → request nạp nội dung /my-course/ trên
   :8080 cũng đèo token: một service worker scope /my-course/ (não ghi .js
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
  window.bfetch = function (url, o) {
    o = o || {};
    try {
      const u = new URL(url, location.href);
      if ((u.hostname === 'localhost' || u.hostname === '127.0.0.1' ||
           u.hostname === '[::1]' || u.hostname === '::1') &&
          BRIDGE_PORTS[u.port]) {
        o.headers = Object.assign(
          { 'X-Bridge-Token': window.BRIDGE_TOKEN }, o.headers || {});
      }
    } catch (e) { /* URL lạ → để fetch tự xử */ }
    return fetch(url, o);
  };
})();
