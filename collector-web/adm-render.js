/* adm-render.js — phần render dùng chung giữa hai màn hình quản trị:
     web/admin.html        → trạng thái MỘT máy (đọc thẳng từ bridge :7682)
     collector-web/        → chi tiết một máy trên dashboard fleet (đọc
                             snapshot mà beacon đã gửi lên collector)
   Hai server khác nhau phục vụ file này: portal :8080 đọc từ web/,
   collector :8790 đọc bản copy trong collector-web/ (hoặc fallback web/
   khi chạy từ repo — xem find_static trong tools/collector.py). Nếu sửa
   file này nhớ đồng bộ collector-web/adm-render.js — test-fleet.py kiểm.
   Snapshot từ beacon có thể thiếu poll.events (chỉ có counts) — render
   phải xuống cấp êm, không vỡ. */
window.AdmRender = (function () {
  const I18N = {
    vi: {
      sys: 'Hệ thống', bot: 'Trợ lý', perm: 'Folder được phép',
      conn: 'Kết nối ứng dụng', ev: 'Hoạt động gần đây',
      brain: 'Bộ não', brainCmd: 'Lệnh chạy', version: 'Phiên bản',
      extVer: 'Extension yêu cầu', lang: 'Ngôn ngữ', learner: 'Học viên',
      active: 'đang dùng', none: '—', empty: 'Chưa có',
      evTypes: { ready: 'sẵn sàng', text: 'nói', tool: 'công cụ',
                 perm: 'xin phép', perm_done: 'đã trả lời thẻ',
                 'perm:auto': 'tự duyệt (allowlist)', done: 'xong lượt',
                 err: 'lỗi', warn: 'cảnh báo',
                 inj_suspect: 'nghi nội dung độc' },
      accRead: 'chỉ đọc', accRW: 'đọc + sửa',
      countsSince: 'lượt kể từ lần báo trước',
      toolFail: '⚠ không tự cập nhật được',
    },
    en: {
      sys: 'System', bot: 'Assistant', perm: 'Allowed folders',
      conn: 'App connections', ev: 'Recent activity',
      brain: 'Brain', brainCmd: 'Command', version: 'Version',
      extVer: 'Extension required', lang: 'Language', learner: 'Learner',
      active: 'active', none: '—', empty: 'None yet',
      evTypes: { ready: 'ready', text: 'text', tool: 'tool',
                 perm: 'permission', perm_done: 'card answered',
                 'perm:auto': 'auto-approved', done: 'turn done',
                 err: 'error', warn: 'warning',
                 inj_suspect: 'suspect content' },
      accRead: 'read', accRW: 'read-write',
      countsSince: 'events since last report',
      toolFail: '⚠ cannot self-update',
    },
  };

  const esc = s => String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
  const row = (k, v) =>
    `<div class="adm-row"><span class="k">${esc(k)}</span><span class="v">${esc(v)}</span></div>`;
  const t = (S, k) => S[k] || I18N.vi[k] || k;

  /* els = {sys, bots, perms, conns, evs} — element đích của 5 card.
     d = {health, brain, config, bots, perms, conns, poll|counts}.
     Beacon gửi snapshot.counters thay vì event stream → nhánh counts. */
  function renderInto(els, d, S) {
    const b = (d.brain && d.brain.current) || {};
    const cfg = d.config || {};
    els.sys.innerHTML =
      row(t(S, 'version'), (d.health || {}).version || t(S, 'none')) +
      row(t(S, 'extVer'), (d.health || {}).extVersion || t(S, 'none')) +
      row(t(S, 'brain'), (b.label || b.id || t(S, 'none'))) +
      row(t(S, 'brainCmd'), b.cmd ? [b.cmd].concat(b.args || []).join(' ') : t(S, 'none')) +
      row(t(S, 'lang'), cfg.language || t(S, 'none')) +
      row(t(S, 'learner'), cfg.learner_name || t(S, 'none')) +
      // audit-6 F11: beacon báo máy không chạy được update/pack
      // (thiếu python trên Windows source-mode) — badge cảnh báo
      (d.tool_fail ? row(t(S, 'toolFail'), d.tool_fail) : '');

    const bots = (d.bots && d.bots.bots) || [];
    els.bots.innerHTML = bots.length
      ? '<ul class="adm-list">' + bots.map(x =>
          `<li><span class="mono">${esc(x.name || x.id)}</span>` +
          (x.id === (d.bots || {}).active
            ? `<span class="adm-tag">${esc(t(S, 'active'))}</span>` : '') +
          `</li>`).join('') + '</ul>'
      : `<p class="adm-empty">${esc(t(S, 'empty'))}</p>`;

    const folders = (d.perms && d.perms.folders) || [];
    els.perms.innerHTML = folders.length
      ? '<ul class="adm-list">' + folders.map(f =>
          `<li><span class="mono">${esc(f.path)}</span>` +
          `<span class="adm-tag">${esc(f.access === 'read-write' ? t(S, 'accRW') : t(S, 'accRead'))}</span></li>`
        ).join('') + '</ul>'
      : `<p class="adm-empty">${esc(t(S, 'empty'))}</p>`;

    const apps = (d.conns && d.conns.apps) || [];
    els.conns.innerHTML = apps.length
      ? '<ul class="adm-list">' + apps.map(a =>
          `<li><span class="mono">${esc(a.name || a.id)}</span>` +
          `<span class="adm-tag ${a.status === 'connected' ? '' : 'gray'}">${esc(a.status || '?')}</span>` +
          (a.check_message ? `<span class="adm-ev">${esc(a.check_message)}</span>` : '') +
          `</li>`).join('') + '</ul>'
      : `<p class="adm-empty">${esc(t(S, 'empty'))}</p>`;

    // Snapshot fleet chỉ có đếm, không có event text (privacy) — hai nhánh
    const evs = (d.poll && d.poll.events) || null;
    if (evs) {
      els.evs.innerHTML = evs.length
        ? evs.slice(-15).reverse().map(e => {
            const lbl = (t(S, 'evTypes') || {})[e.t] || e.t;
            const det = e.title || e.msg || '';
            return `<div class="adm-ev"><b>${esc(lbl)}</b>` +
                   (det ? ` — ${esc(String(det).slice(0, 90))}` : '') + `</div>`;
          }).join('')
        : `<p class="adm-empty">${esc(t(S, 'empty'))}</p>`;
    } else {
      const counts = d.counts || {};
      const ks = Object.keys(counts);
      els.evs.innerHTML = ks.length
        ? `<div class="adm-ev">${esc(t(S, 'countsSince'))}:</div>` +
          ks.sort().map(k =>
            `<div class="adm-ev"><b>${esc((t(S, 'evTypes') || {})[k] || k)}</b>` +
            ` — ${esc(counts[k])}</div>`).join('')
        : `<p class="adm-empty">${esc(t(S, 'empty'))}</p>`;
    }
  }

  return { I18N, esc, row, t, renderInto };
})();
