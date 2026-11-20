/* "Chìa khoá nhà" cho mọi API bridge (:7682, :7684).
   File start mở portal kèm ?t=<mã> → lưu vào localStorage để mọi trang
   cùng origin (kể cả iframe chat/clone-view) dùng chung, rồi xoá mã khỏi
   thanh địa chỉ cho gọn.
   bfetch() = fetch + tự gắn X-Bridge-Token — NHƯNG chỉ với URL loopback:
   mã là "chìa khoá nhà mình", không bao giờ gửi ra internet. */
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
  window.bfetch = function (url, o) {
    o = o || {};
    try {
      const u = new URL(url, location.href);
      if (u.hostname === 'localhost' || u.hostname === '127.0.0.1' ||
          u.hostname === '[::1]' || u.hostname === '::1') {
        o.headers = Object.assign(
          { 'X-Bridge-Token': window.BRIDGE_TOKEN }, o.headers || {});
      }
    } catch (e) { /* URL lạ → để fetch tự xử */ }
    return fetch(url, o);
  };
})();
