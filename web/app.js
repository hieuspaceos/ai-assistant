/* Portal "Trợ lý AI" — đọc my-course/manifest.json, hiển thị bài học.
   Serve từ root ai-assistant/ nên tài nguyên đều ở /my-course/... và /intro/... */

const TTYD_URL = 'http://localhost:7681';
const BRIDGE_URL = 'http://localhost:7682';
let manifest = null;
let currentLesson = null;
let chatChecked = false;
let chatMode = 'chat';

const $ = (sel) => document.querySelector(sel);

/* Hộp thoại nhỏ thay confirm()/alert() — đồng bộ style portal.
   uiConfirm(title, msg, okText) → Promise<boolean>
   uiAlert(title, msg)           → Promise<void> */
function uiDlg({title, msg, okText = 'Đồng ý', danger = false, canCancel = true}) {
  return new Promise(resolve => {
    const ov = $('#dlg-overlay');
    $('#dlg-title').textContent = title;
    $('#dlg-msg').textContent = msg;
    const okBtn = $('#dlg-ok'), cancelBtn = $('#dlg-cancel');
    okBtn.textContent = okText;
    okBtn.classList.toggle('danger', danger);
    cancelBtn.hidden = !canCancel;
    const done = (val) => {
      ov.hidden = true;
      document.removeEventListener('keydown', onKey);
      resolve(val);
    };
    const onKey = (e) => { if (e.key === 'Escape') done(false); };
    okBtn.onclick = () => done(true);
    cancelBtn.onclick = () => done(false);
    ov.onclick = (e) => { if (e.target === ov) done(false); };
    document.addEventListener('keydown', onKey);
    ov.hidden = false;
    okBtn.focus();
  });
}
const uiConfirm = (title, msg, okText) => uiDlg({title, msg, okText, danger: true});
const uiAlert = (title, msg) => uiDlg({title, msg, okText: 'Đã hiểu', canCancel: false});

async function loadManifest() {
  try {
    const res = await fetch('/my-course/manifest.json?_=' + Date.now());
    if (!res.ok) throw new Error('no manifest');
    manifest = await res.json();
  } catch {
    manifest = { learner_name: '', intro: '', lessons: [] };
  }
  renderLessonList();
  renderWelcome();
}

/* Welcome thay đổi theo trạng thái thật: chưa cài đặt → dẫn sang onboarding;
   chưa có bài → gợi ý /phong-van; đã có bài → nhắc chọn bài hoặc hỏi trợ lý. */
async function renderWelcome() {
  const hint = $('#welcome-hint'), title = $('#welcome-title');
  if (manifest.learner_name) title.textContent = 'Chào ' + manifest.learner_name + '!';

  let cfg = null;
  try {
    const r = await fetch(BRIDGE_URL + '/api/config', { signal: cfgSig() });
    cfg = await r.json();
  } catch { /* bridge chết */ }

  if (!cfg || !cfg.language) {
    hint.innerHTML = 'Trợ lý chưa sẵn sàng — mở lại file <code>start</code> rồi tải lại trang này. Nếu mới dùng lần đầu, bấm <a href="onboarding.html"><b>vào đây để cài đặt</b></a>.';
  } else if (!manifest.lessons.length) {
    hint.innerHTML = 'Chưa có bài nào? Bấm <b>Hỏi trợ lý</b> và gõ <code>/phong-van</code>, nó sẽ hỏi vài câu rồi thiết kế khoá học riêng cho bạn.';
  } else {
    hint.innerHTML = 'Chọn một bài bên trái để học — hoặc bấm <b>Hỏi trợ lý</b> để nhờ bất cứ việc gì, không cần mở bài học.';
  }
}
function cfgSig() { return (window.AbortSignal && AbortSignal.timeout) ? AbortSignal.timeout(2500) : undefined; }

function renderLessonList() {
  const box = $('#lessons');
  box.innerHTML = '';

  const intro = document.createElement('button');
  intro.className = 'lesson';
  intro.innerHTML = `<span class="num">0</span><span class="t">Làm quen &amp; cài đặt</span>`;
  intro.onclick = () => selectLesson(null, intro);
  box.appendChild(intro);

  if (!manifest.lessons.length) {
    const p = document.createElement('p');
    p.className = 'empty';
    p.textContent = 'Chưa có bài nào. Mở tab "Hỏi trợ lý" và gõ /phong-van nhé.';
    box.appendChild(p);
    return;
  }

  manifest.lessons.forEach((b, i) => {
    const btn = document.createElement('button');
    btn.className = 'lesson';
    btn.innerHTML = `<span class="num">${i + 1}</span><span class="t">${escapeHtml(b.title)}</span>` +
      `<span class="del" role="button" title="Xoá bài này (giữ lại công thức)">×</span>`;
    btn.onclick = () => selectLesson(b, btn);
    btn.querySelector('.del').onclick = (ev) => { ev.stopPropagation(); deleteLesson(b); };
    box.appendChild(btn);
  });

  if (manifest.learner_name) $('#learner-name').textContent = '👋 ' + manifest.learner_name;

  if (manifest.recipes && manifest.recipes.length) {
    $('#recipes').hidden = false;
    $('#recipe-list').innerHTML = manifest.recipes.map(c =>
      `<div class="recipe" title="${escapeHtml(c.meaning)}"><code>${escapeHtml(c.command)}</code><span>${escapeHtml(c.meaning)}</span></div>`
    ).join('');
  }
}

async function deleteLesson(b) {
  const ok = await uiConfirm(
    `Xoá bài "${b.title}"?`,
    'Slide, video, hướng dẫn của bài này sẽ mất hết. Công thức nhanh (như /anh-web) vẫn được giữ lại vì bạn đã học xong.',
    'Xoá bài');
  if (!ok) return;
  try {
    const res = await fetch(BRIDGE_URL + '/api/delete-lesson', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({folder: b.folder})});
    const data = await res.json();
    if (!res.ok) throw new Error(data.err || 'lỗi');
  } catch (e) {
    await uiAlert('Chưa xoá được', 'Kiểm tra lại xem chat-bridge có đang chạy không nhé — thử chạy lại file start.');
    return;
  }
  if (currentLesson === b) {
    currentLesson = null;
    document.querySelectorAll('.lesson-tab').forEach(t => t.hidden = true);
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    $('#content').hidden = true;
    $('#welcome').hidden = false;
  }
  await loadManifest();
}

function selectLesson(lesson, btn) {
  document.querySelectorAll('.lesson').forEach(el => el.classList.remove('active'));
  btn.classList.add('active');
  currentLesson = lesson;
  $('#welcome').hidden = true;
  document.querySelectorAll('.lesson-tab').forEach(t => t.hidden = false);
  $('#content').hidden = false;
  if (lesson === null) loadIntro();
  else loadLesson(lesson);
  switchTab('slide');
}

function baseUrl(lesson) { return '/my-course/' + lesson.folder + '/'; }

function loadIntro() {
  setPaneHtml('slide', iframe('/intro/slides.html'));
  loadMdInto('guide', '/SETUP.md');
  $('#guide-video').hidden = true;
  setPaneHtml('exercise', emptyMsg('Bài này không có bài tập — chỉ cần mở được trợ lý là đạt.'));
}

function loadLesson(lesson) {
  const base = baseUrl(lesson);
  setPaneHtml('slide', lesson.has_slides !== false
    ? iframe(base + 'slides.html')
    : emptyMsg('Slide đang được tạo — quay lại sau vài phút nhé.'));
  loadMdInto('guide', base + 'guide.md');
  loadMdInto('exercise', base + 'exercise.md');

  const gv = $('#guide-video');
  if (lesson.has_video) {
    gv.innerHTML = `<video controls src="${base}video.mp4"></video>`;
    gv.hidden = false;
  } else {
    gv.innerHTML = '';
    gv.hidden = true;
  }
}

async function loadMdInto(pane, url, fallbackTitle) {
  try {
    const res = await fetch(url + '?_=' + Date.now());
    if (!res.ok) throw 0;
    const md = await res.text();
    const html = (window.marked && window.DOMPurify)
      ? DOMPurify.sanitize(marked.parse(md))
      : escapeHtml(md).replace(/\n/g, '<br>');   // thiếu thư viện → chữ thường
    setPaneHtml(pane, `<div class="md">${html}</div>`);
  } catch {
    setPaneHtml(pane, emptyMsg(fallbackTitle || 'File đang được tạo — quay lại sau nhé.'));
  }
}

function setPaneHtml(pane, html) {
  $(pane === 'guide' ? '#guide-md' : '#pane-' + pane).innerHTML = html;
}
function iframe(src) { return `<iframe class="deck" src="${escapeHtml(src)}"></iframe>`; }
function emptyMsg(t) { return `<div class="empty-msg">${t}</div>`; }
function escapeHtml(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }

/* ---- tabs ---- */
document.querySelectorAll('.tab').forEach(btn => {
  btn.onclick = () => switchTab(btn.dataset.tab);
});

function switchTab(name) {
  // Hỏi trợ lý dùng được kể cả khi chưa chọn bài — ẩn welcome, mở content
  $('#welcome').hidden = true;
  $('#content').hidden = false;
  document.querySelectorAll('.tab').forEach(b => b.classList.toggle('active', b.dataset.tab === name));
  document.querySelectorAll('.pane').forEach(p => p.hidden = true);
  const pane = $('#pane-' + name);
  if (pane) pane.hidden = false;
  if (name === 'chat' && !chatChecked) initChat();
}

/* ---- chat / terminal ---- */
async function ping(url, path, cors) {
  const ctrl = new AbortController();
  setTimeout(() => ctrl.abort(), 2500);
  try {
    // cors=true: server phải trả ACAO đúng origin portal — dịch vụ lạ chiếm
    // port sẽ bị coi là "chết" thay vì false-positive như no-cors
    const r = await fetch(url + (path || ''), { signal: ctrl.signal, ...(cors ? {} : { mode: 'no-cors' }) });
    return cors ? r.ok : true;
  } catch { return false; }
}

async function initChat() {
  chatChecked = true;
  $('#mode-chat').onclick = () => setChatMode('chat');
  $('#mode-cli').onclick = () => setChatMode('cli');
  setChatMode('chat');
}

async function setChatMode(mode) {
  chatMode = mode;
  $('#mode-chat').classList.toggle('active', mode === 'chat');
  $('#mode-cli').classList.toggle('active', mode === 'cli');
  const status = $('#terminal-status');
  const chatFrame = $('#chat-frame');
  const termFrame = $('#terminal-frame');
  chatFrame.hidden = mode !== 'chat';
  termFrame.hidden = mode !== 'cli';

  if (mode === 'chat') {
    if (await ping(BRIDGE_URL, '/api/health', true)) {
      if (!chatFrame.src) chatFrame.src = '/web/chat.html?bridge=' + encodeURIComponent(BRIDGE_URL);
      status.innerHTML = '';
    } else {
      status.innerHTML = `<span class="warn"><b>Chế độ Chat chưa mở:</b> chạy lại <code>start.bat</code>,
        hoặc bấm sang tab <b>Terminal</b> bên cạnh để dùng tạm.</span>`;
    }
  } else {
    if (await ping(TTYD_URL)) {
      if (!termFrame.src) termFrame.src = TTYD_URL;
      status.innerHTML = '';
    } else {
      status.innerHTML = `<span class="warn"><b>Terminal chưa mở:</b> chạy lại <code>start.bat</code>,
        hoặc mở PowerShell gõ <code>devin</code> để học bình thường.</span>`;
    }
  }
}

loadManifest();

/* ---- video mini-player: cuộn hướng dẫn xuống thì video thu nhỏ nổi góc ---- */
$('#guide-md').addEventListener('scroll', () => {
  $('#guide-video').classList.toggle('mini', $('#guide-md').scrollTop > 80);
});

/* ---- trạng thái extension Trợ Lý AI (cánh tay trình duyệt) ---- */
const EXT_BRIDGE = 'http://localhost:7683';
async function pollExtStatus() {
  const el = $('#ext-status'), txt = $('#ext-status-text');
  try {
    const sig = (window.AbortSignal && AbortSignal.timeout) ? AbortSignal.timeout(3000) : undefined;
    const r = await fetch(EXT_BRIDGE + '/api/browser/status', { signal: sig });
    const d = await r.json();
    el.classList.toggle('on', !!d.connected);
    txt.textContent = d.connected ? 'Đã nối trình duyệt' : 'Chưa nối trình duyệt';
  } catch {
    el.classList.remove('on');
    txt.textContent = 'Chưa nối trình duyệt';
  }
}
pollExtStatus();
setInterval(pollExtStatus, 10000);

/* ---- Cài đặt: kết nối app + folder được phép — gom vào nút ⚙ cuối sidebar ---- */
const settingsOverlay = $('#settings-overlay');

$('#settings-btn').onclick = async () => {
  settingsOverlay.hidden = false;
  renderFolders();
  const apps = await renderApps();
  // kiểm tra lại trạng thái THẬT của từng app ngầm — panel cập nhật dần,
  // không hiện số liệu cũ đã lưu từ lần trước
  if (apps && apps.length) {
    apps.forEach(a => {
      fetch(BRIDGE_URL + '/api/check-connection', {
        method: 'POST', body: JSON.stringify({ id: a.id })
      }).then(() => renderApps()).catch(() => {});
    });
  }
};
$('#settings-close').onclick = () => { settingsOverlay.hidden = true; };
settingsOverlay.onclick = (e) => { if (e.target === settingsOverlay) settingsOverlay.hidden = true; };
document.addEventListener('keydown', e => {
  if (e.key === 'Escape' && !settingsOverlay.hidden) settingsOverlay.hidden = true;
});

async function renderApps() {
  let apps = [];
  try {
    const d = await (await fetch(BRIDGE_URL + '/api/connections')).json();
    apps = d.apps || [];
    const list = $('#app-list');
    list.innerHTML = '';
    if (!apps.length) {
      const p = document.createElement('p');
      p.className = 'empty';
      p.textContent = 'Chưa có app nào — trợ lý tự thêm khi bạn cần.';
      list.appendChild(p);
      return apps;
    }
    for (const a of apps) {
      const wrap = document.createElement('div');
      wrap.className = 'app-wrap';
      const row = document.createElement('div');
      row.className = 'app-row';
      const on = a.status === 'connected';
      // dòng phụ giải thích chấm xanh/xám nghĩa là gì — tránh hiểu nhầm
      // "đang mở trong trình duyệt" thành "đã đăng nhập app"
      const sub = a.check_message || a.note || '';
      row.innerHTML =
        `<span class="app-dot ${on ? 'on' : ''}"></span>` +
        `<span class="app-name" title="${escapeHtml(a.note)}">` +
          `<span class="app-name-t">${escapeHtml(a.name)}</span>` +
          `<span class="app-sub">${escapeHtml(sub)}</span>` +
        `</span>` +
        (a.open_url
          ? `<button class="app-open" title="Mở trang này trên trình duyệt">Mở trang</button>`
          : '') +
        `<button class="app-check" title="Kiểm tra lại">↻</button>`;
      const openBtn = row.querySelector('.app-open');
      if (openBtn) openBtn.onclick = () => { window.open(a.open_url, '_blank'); };
      row.querySelector('.app-check').onclick = async () => {
        row.querySelector('.app-check').textContent = '…';
        const r = await (await fetch(BRIDGE_URL + '/api/check-connection', {
          method: 'POST', body: JSON.stringify({ id: a.id })
        })).json();
        renderApps();
        if (!r.ok && r.msg) row.title = r.msg;
      };
      wrap.appendChild(row);

      // app cần mã kết nối (WP, Zalo OA…) → nút "Cài" mở form dán thông tin,
      // không bắt học viên tự sửa file JSON
      if (a.setup_fields && a.setup_fields.length) {
        const setupBtn = document.createElement('button');
        setupBtn.className = 'app-open';
        setupBtn.textContent = 'Cài';
        setupBtn.title = 'Điền thông tin kết nối';
        const form = document.createElement('div');
        form.className = 'app-setup';
        form.hidden = true;
        form.innerHTML =
          (a.setup_hint ? `<p class="app-setup-hint">${escapeHtml(a.setup_hint)}</p>` : '') +
          a.setup_fields.map(f =>
            `<label>${escapeHtml(f.label)}` +
            `<input data-k="${escapeHtml(f.key)}" type="${f.secret ? 'password' : 'text'}"` +
            ` placeholder="${escapeHtml(f.ph || '')}"></label>`
          ).join('') +
          `<div class="app-setup-foot">` +
            `<button class="app-save">Lưu & kiểm tra</button>` +
            `<span class="app-setup-hint">Chỉ lưu trên máy bạn, vào file ẩn — không gửi đi đâu.</span>` +
          `</div>`;
        setupBtn.onclick = () => { form.hidden = !form.hidden; };
        row.insertBefore(setupBtn, row.querySelector('.app-check'));
        form.querySelector('.app-save').onclick = async () => {
          const fields = {};
          form.querySelectorAll('input').forEach(i => {
            if (i.value.trim()) fields[i.dataset.k] = i.value.trim();
          });
          if (!Object.keys(fields).length) return;
          const btn = form.querySelector('.app-save');
          btn.textContent = 'đang lưu…';
          const res = await (await fetch(BRIDGE_URL + '/api/secrets', {
            method: 'POST', body: JSON.stringify({ app: a.id, fields })
          })).json();
          if (res.err) { btn.textContent = res.err; return; }
          await fetch(BRIDGE_URL + '/api/check-connection', {
            method: 'POST', body: JSON.stringify({ id: a.id })
          });
          renderApps();
        };
        wrap.appendChild(form);
      }
      list.appendChild(wrap);
    }
  } catch { /* bridge chưa chạy — giấu mục này */ }
  return apps;
}

async function renderFolders() {
  try {
    const d = await (await fetch(BRIDGE_URL + '/api/permissions')).json();
    const fs = d.folders || [];
    $('#folder-list').innerHTML = '';
    for (const f of fs) {
      const row = document.createElement('div');
      row.className = 'folder-row';
      row.innerHTML =
        `<span class="folder-path" title="${escapeHtml(f.note || f.path)}">${escapeHtml(f.path)}</span>` +
        `<span class="folder-lv">${f.access === 'read-write' ? 'đọc+sửa' : 'chỉ đọc'}</span>` +
        `<button class="folder-del" title="Gỡ quyền">×</button>`;
      row.querySelector('.folder-del').onclick = async () => {
        await fetch(BRIDGE_URL + '/api/remove-permission', {
          method: 'POST', body: JSON.stringify({ path: f.path })
        });
        renderFolders();
      };
      $('#folder-list').appendChild(row);
    }
  } catch { /* bridge chưa chạy */ }
}

$('#folder-add-btn').onclick = () => {
  $('#folder-add').hidden = false;
  $('#folder-add-btn').hidden = true;
  $('#folder-path').focus();
};
$('#folder-save').onclick = async () => {
  const p = $('#folder-path').value.trim();
  if (!p) return;
  const r = await (await fetch(BRIDGE_URL + '/api/permissions', {
    method: 'POST',
    body: JSON.stringify({ path: p, access: $('#folder-access').value })
  })).json();
  if (r.err) { $('#folder-path').value = ''; $('#folder-path').placeholder = r.err; return; }
  $('#folder-path').value = '';
  $('#folder-add').hidden = true;
  $('#folder-add-btn').hidden = false;
  renderFolders();
};

// chỉ làm mới khi panel cài đặt đang mở — sidebar không còn hiển thị 2 mục này
setInterval(() => {
  if (!settingsOverlay.hidden) { renderApps(); renderFolders(); }
}, 15000);
