/* Portal "Trợ lý AI" — đọc my-course/manifest.json, hiển thị bài học.
   Serve từ root ai-assistant/ nên tài nguyên đều ở /my-course/... và /intro/... */

const TTYD_URL = 'http://localhost:7681';
const BRIDGE_URL = 'http://localhost:7682';
let manifest = null;
let currentLesson = null;
let chatChecked = false;
let chatMode = 'chat';
let LANG = 'vi';

/* Chuỗi UI theo ngôn ngữ trong my-course/config.json (onboarding chọn vi/en).
   Phần tử tĩnh trong index.html gắn data-i18n / data-i18n-ph /
   data-i18n-title / data-i18n-html; chuỗi động trong file này dùng t(). */
const I18N = {
  vi: {
    loading: 'Đang tải…',
    lessons: 'Bài học',
    recipesTitle: 'Công thức nhanh',
    recipeHint: 'Gõ các lệnh này trong tab “Hỏi trợ lý”',
    introLesson: 'Làm quen & cài đặt',
    emptyLessons: 'Chưa có bài nào. Mở tab "Hỏi trợ lý" và gõ /phong-van nhé.',
    emptyApps: 'Chưa có app nào — trợ lý tự thêm khi bạn cần.',
    tabSlide: 'Slide', tabGuide: 'Hướng dẫn', tabExercise: 'Bài tập', tabAsk: 'Hỏi trợ lý',
    welcomeTitle: 'Chào bạn!',
    welcomeSub: 'Trợ lý AI làm việc thật trên máy bạn — và nó tự dạy bạn dùng nó qua một khoá học riêng.',
    chatFrameTitle: 'Chat với trợ lý (kiểu tin nhắn)',
    how1: '<b>Nhờ trợ lý</b> bất cứ việc gì — bấm nút <b>Hỏi trợ lý</b> phía trên.',
    how2: '<b>Chọn một bài</b> bên trái để xem slide và hướng dẫn.',
    how3: '<b>Kẹt cứ hỏi</b>: không có câu hỏi nào là “ngốc” cả.',
    extTitle: 'Trạng thái cánh tay trình duyệt (extension Trợ Lý AI)',
    extOn: 'Đã nối trình duyệt', extOff: 'Chưa nối trình duyệt',
    extStale: 'Extension bản cũ', updateNew: 'Có bản mới {v} — bấm để tải',
    extUpdateHint: 'Extension đang là bản {cur}, bản mới nhất là {exp} — tải file troly mới rồi gỡ extension cũ và Load unpacked lại trong brave://extensions.',
    settings: 'Cài đặt', closeTitle: 'Đóng',
    brainTitle: 'Bộ não của trợ lý',
    brainHint: 'Trợ lý nghĩ và làm việc bằng chương trình AI này — chỉ đổi khi máy bạn có sẵn chương trình khác (đổi xong trợ lý khởi động lại trong vài giây).',
    brainCurrent: 'đang dùng', brainSwitching: 'Đang đổi…',
    brainDone: 'Đã đổi xong', brainFail: 'Chưa đổi được',
    brainCostFree: 'miễn phí', brainCostByok: 'app miễn phí', brainCostPaid: 'trả phí',
    connCodeTitle: 'Mã kết nối',
    connCodeHint: 'Khi extension Trợ Lý AI hỏi mã, dán mã này vào — giống đưa chìa khoá nhà cho nó, chỉ cần một lần.',
    connCopy: 'Sao chép', connCopied: 'Đã sao chép ✓',
    appsTitle: 'Kết nối ứng dụng',
    appsHint: 'Chấm xanh = trợ lý dùng được ngay · Chấm xám = cần thêm một bước nhỏ — cứ hỏi trợ lý trong chat, nó dẫn từng bước.',
    foldersTitle: 'Folder trợ lý được đọc',
    foldersHint: 'Trợ lý chỉ được mở các ngăn trong danh sách này (giống cho phép người giúp việc mở ngăn tủ nào). Thêm folder ở đây, hoặc đồng ý khi trợ lý xin trong chat.',
    folderPh: 'dán đường dẫn folder…',
    readOnly: 'chỉ đọc', readWrite: 'đọc + sửa',
    addBtn: 'Thêm', addFolderBtn: '+ thêm folder',
    delPermTitle: 'Gỡ quyền', recheckTitle: 'Kiểm tra lại',
    btnOpen: 'Mở trang', btnSetup: 'Cài',
    openTitle: 'Mở trang này trên trình duyệt', setupTitle: 'Điền thông tin kết nối',
    saveCheck: 'Lưu & kiểm tra',
    setupLocal: 'Chỉ lưu trên máy bạn, vào file ẩn — không gửi đi đâu.',
    dlgCancel: 'Huỷ', dlgOk: 'Đồng ý', dlgOkShort: 'Đã hiểu',
    delLessonTitle: 'Xoá bài này (giữ lại công thức)',
    helloPrefix: 'Chào ',
    creating: 'File đang được tạo — quay lại sau nhé.',
    slideCreating: 'Slide đang được tạo — quay lại sau vài phút nhé.',
    noExercise: 'Bài này không có bài tập — chỉ cần mở được trợ lý là đạt.',
    delConfirmTitle: 'Xoá bài "{t}"?',
    delConfirmMsg: 'Slide, video, hướng dẫn của bài này sẽ mất hết. Công thức nhanh (như /anh-web) vẫn được giữ lại vì bạn đã học xong.',
    delOk: 'Xoá bài',
    delFailTitle: 'Chưa xoá được',
    delFailMsg: 'Kiểm tra lại xem chat-bridge có đang chạy không nhé — thử chạy lại file start.',
    gateTitle: 'Cần bạn xác nhận',
    gateMsg: 'Đã gửi thẻ xác nhận vào tab "Hỏi trợ lý" — bấm "Đồng ý" bên đó để hoàn tất.',
    warnChat: '<b>Chế độ Chat chưa mở:</b> chạy lại <code>start.bat</code>, hoặc bấm sang tab <b>Terminal</b> bên cạnh để dùng tạm.',
    warnCli: '<b>Terminal chưa mở:</b> chạy lại <code>start.bat</code>, hoặc mở PowerShell gõ <code>devin</code> để học bình thường.',
    hintNotReady: 'Trợ lý chưa sẵn sàng — mở lại file <code>start</code> rồi tải lại trang này. Nếu mới dùng lần đầu, bấm <a href="onboarding.html"><b>vào đây để cài đặt</b></a>.',
    hintNoLessons: 'Chưa có bài nào? Bấm <b>Hỏi trợ lý</b> và gõ <code>/phong-van</code>, nó sẽ hỏi vài câu rồi thiết kế khoá học riêng cho bạn.',
    hintReady: 'Chọn một bài bên trái để học — hoặc bấm <b>Hỏi trợ lý</b> để nhờ bất cứ việc gì, không cần mở bài học.',
    botChipTitle: 'Đổi trợ lý',
    botGeneral: 'Trợ lý chung',
    botNew: 'Tạo trợ lý mới',
    botNewTitle: 'Tạo trợ lý mới',
    botNamePh: 'Tên trợ lý…',
    botCreateBtn: 'Tạo',
    botNeeds: 'Cần nối:',
    botConnOk: 'đã nối', botConnWarn: 'chưa nối — nối sau cũng được',
    botErr: 'Chưa đổi được trợ lý — thử lại nhé',
    botCreating: 'Đang tạo…',
    botImport: 'Nhập trợ lý từ file',
    botImportTitle: 'Nhập trợ lý',
    botImportWarn: 'Đọc kỹ lời dặn dưới đây — nếu thấy chỗ bảo gửi tin, xoá gì đó, hay làm việc lạ thì đừng nhập.',
    botImportSkills: 'Công thức đi kèm:',
    botImportNeeds: 'Cần nối:',
    botImportBtn: 'Nhập trợ lý này',
    botImporting: 'Đang nhập…',
    botImportDone: 'Đã nhập — trợ lý nằm trong menu, bạn tự chọn khi sẵn sàng.',
  },
  en: {
    loading: 'Loading…',
    lessons: 'Lessons',
    recipesTitle: 'Quick recipes',
    recipeHint: 'Type these in the "Ask the assistant" tab',
    introLesson: 'Getting started & setup',
    emptyLessons: 'No lessons yet. Open "Ask the assistant" and type /interview.',
    emptyApps: 'No apps yet — the assistant adds them as needed.',
    tabSlide: 'Slide', tabGuide: 'Guide', tabExercise: 'Exercise', tabAsk: 'Ask the assistant',
    welcomeTitle: 'Hello!',
    welcomeSub: 'Your AI assistant does real work on this machine — and it teaches you to use it through a course built just for you.',
    chatFrameTitle: 'Chat with the assistant',
    how1: '<b>Ask the assistant</b> for anything — click <b>Ask the assistant</b> above.',
    how2: '<b>Pick a lesson</b> on the left to see slides and the guide.',
    how3: '<b>Stuck? Just ask</b> — no question is a silly one.',
    extTitle: 'Browser arm status (Trợ Lý AI extension)',
    extOn: 'Browser connected', extOff: 'Browser not connected',
    extStale: 'Extension outdated', updateNew: 'New version {v} — click to download',
    extUpdateHint: 'Extension is v{cur}, latest is v{exp} — download the new troly file, then remove and re-load the extension at brave://extensions.',
    settings: 'Settings', closeTitle: 'Close',
    brainTitle: 'Assistant brain',
    brainHint: 'The assistant thinks and works through this AI program — only change it if another one is already installed (it restarts in a few seconds).',
    brainCurrent: 'in use', brainSwitching: 'Switching…',
    brainDone: 'Switched', brainFail: 'Couldn\'t switch',
    brainCostFree: 'free', brainCostByok: 'free app', brainCostPaid: 'paid',
    connCodeTitle: 'Connection code',
    connCodeHint: 'If the Trợ Lý AI extension asks for a code, paste this in — like handing it the house key, once is enough.',
    connCopy: 'Copy', connCopied: 'Copied ✓',
    appsTitle: 'App connections',
    appsHint: 'Green dot = ready to use · Gray dot = needs one small step — just ask the assistant in chat, it will walk you through.',
    foldersTitle: 'Folders the assistant may read',
    foldersHint: 'The assistant can only open drawers on this list (like telling a helper which cabinets they may open). Add folders here, or approve when the assistant asks in chat.',
    folderPh: 'paste a folder path…',
    readOnly: 'read-only', readWrite: 'read + write',
    addBtn: 'Add', addFolderBtn: '+ add folder',
    delPermTitle: 'Remove access', recheckTitle: 'Check again',
    btnOpen: 'Open', btnSetup: 'Set up',
    openTitle: 'Open this page in your browser', setupTitle: 'Enter connection details',
    saveCheck: 'Save & check',
    setupLocal: 'Saved only on this machine, in a hidden file — never sent anywhere.',
    dlgCancel: 'Cancel', dlgOk: 'OK', dlgOkShort: 'Got it',
    delLessonTitle: 'Delete this lesson (keeps the recipes)',
    helloPrefix: 'Hi ',
    creating: 'This file is being created — check back soon.',
    slideCreating: 'Slides are being created — check back in a few minutes.',
    noExercise: 'This lesson has no exercise — opening the assistant is enough.',
    delConfirmTitle: 'Delete lesson "{t}"?',
    delConfirmMsg: 'Its slides, video and guide will be gone for good. Quick recipes (like /web-images) stay because you already learned them.',
    delOk: 'Delete',
    delFailTitle: 'Couldn\'t delete',
    delFailMsg: 'Check whether the chat bridge is running — try running the start file again.',
    gateTitle: 'Needs your confirmation',
    gateMsg: 'A confirmation card was sent to the "Ask the assistant" tab — tap "Đồng ý" (agree) there to finish.',
    warnChat: '<b>Chat mode isn\'t up:</b> run the <code>start</code> file again, or switch to the <b>Terminal</b> tab meanwhile.',
    warnCli: '<b>Terminal isn\'t up:</b> run the <code>start</code> file again, or open a shell and type <code>devin</code>.',
    hintNotReady: 'The assistant isn\'t ready — run the <code>start</code> file again and reload. First time here? <a href="onboarding.html"><b>Click to set up</b></a>.',
    hintNoLessons: 'No lessons yet? Click <b>Ask the assistant</b> and type <code>/interview</code> — it will ask a few questions then design a course just for you.',
    hintReady: 'Pick a lesson on the left — or click <b>Ask the assistant</b> for anything, no lesson needed.',
    botChipTitle: 'Switch assistant',
    botGeneral: 'General assistant',
    botNew: 'Create an assistant',
    botNewTitle: 'Create an assistant',
    botNamePh: 'Assistant name…',
    botCreateBtn: 'Create',
    botNeeds: 'Needs:',
    botConnOk: 'connected', botConnWarn: 'not connected — you can connect later',
    botErr: 'Couldn\'t switch assistants — try again',
    botCreating: 'Creating…',
    botImport: 'Import assistant from file',
    botImportTitle: 'Import assistant',
    botImportWarn: 'Read the instructions below carefully — if anything says to send messages, delete things, or do odd actions, do not import.',
    botImportSkills: 'Bundled recipes:',
    botImportNeeds: 'Needs:',
    botImportBtn: 'Import this assistant',
    botImporting: 'Importing…',
    botImportDone: 'Imported — it\'s in the menu, switch to it when ready.',
  },
};
function t(k) { return (I18N[LANG] && I18N[LANG][k]) || I18N.vi[k] || k; }
function applyI18n() {
  document.querySelectorAll('[data-i18n]').forEach(el => { el.textContent = t(el.dataset.i18n); });
  document.querySelectorAll('[data-i18n-html]').forEach(el => { el.innerHTML = t(el.dataset.i18nHtml); });
  document.querySelectorAll('[data-i18n-ph]').forEach(el => { el.placeholder = t(el.dataset.i18nPh); });
  document.querySelectorAll('[data-i18n-title]').forEach(el => { el.title = t(el.dataset.i18nTitle); });
}
async function initI18n() {
  try {
    const r = await bfetch(BRIDGE_URL + '/api/config', { signal: cfgSig() });
    const c = await r.json();
    if (c && c.language) LANG = c.language;
  } catch { /* bridge chưa chạy → giữ mặc định vi */ }
  applyI18n();
}

const $ = (sel) => document.querySelector(sel);

/* Hộp thoại nhỏ thay confirm()/alert() — đồng bộ style portal.
   uiConfirm(title, msg, okText) → Promise<boolean>
   uiAlert(title, msg)           → Promise<void> */
function uiDlg({title, msg, okText = t('dlgOk'), danger = false, canCancel = true}) {
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
const uiAlert = (title, msg) => uiDlg({title, msg, okText: t('dlgOkShort'), canCancel: false});

async function loadManifest() {
  try {
    const res = await bfetch('/my-course/manifest.json?_=' + Date.now());
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
  title.textContent = manifest.learner_name
    ? t('helloPrefix') + manifest.learner_name + '!'
    : t('welcomeTitle');

  let cfg = null;
  try {
    const r = await bfetch(BRIDGE_URL + '/api/config', { signal: cfgSig() });
    cfg = await r.json();
  } catch { /* bridge chết */ }

  if (!cfg || !cfg.language) {
    hint.innerHTML = t('hintNotReady');
  } else if (!manifest.lessons.length) {
    hint.innerHTML = t('hintNoLessons');
  } else {
    hint.innerHTML = t('hintReady');
  }
}
function cfgSig() { return (window.AbortSignal && AbortSignal.timeout) ? AbortSignal.timeout(2500) : undefined; }

function renderLessonList() {
  const box = $('#lessons');
  box.innerHTML = '';

  const intro = document.createElement('button');
  intro.className = 'lesson';
  intro.innerHTML = `<span class="num">0</span><span class="t">${escapeHtml(t('introLesson'))}</span>`;
  intro.onclick = () => selectLesson(null, intro);
  box.appendChild(intro);

  if (!manifest.lessons.length) {
    const p = document.createElement('p');
    p.className = 'empty';
    p.textContent = t('emptyLessons');
    box.appendChild(p);
    return;
  }

  manifest.lessons.forEach((b, i) => {
    const btn = document.createElement('button');
    btn.className = 'lesson';
    btn.innerHTML = `<span class="num">${i + 1}</span><span class="t">${escapeHtml(b.title)}</span>` +
      `<span class="del" role="button" title="${escapeHtml(t('delLessonTitle'))}">×</span>`;
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
  // xác nhận nằm ở thẻ trong chat (consent gate) — không hỏi lại ở đây
  try {
    const res = await bfetch(BRIDGE_URL + '/api/delete-lesson', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({folder: b.folder})});
    const data = await res.json();
    if (!res.ok) throw new Error(data.err || 'lỗi');
    if (data.pending) {
      await uiAlert(t('gateTitle'), data.msg || t('gateMsg'));
      return;               // bài chỉ mất sau khi bấm Đồng ý trong chat
    }
  } catch (e) {
    await uiAlert(t('delFailTitle'), t('delFailMsg'));
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
  setPaneHtml('exercise', emptyMsg(t('noExercise')));
}

function loadLesson(lesson) {
  const base = baseUrl(lesson);
  setPaneHtml('slide', lesson.has_slides !== false
    ? iframe(base + 'slides.html')
    : emptyMsg(t('slideCreating')));
  loadMdInto('guide', base + 'guide.md');
  loadMdInto('exercise', base + 'exercise.md');

  const gv = $('#guide-video');
  if (lesson.has_video) {
    gv.innerHTML = `<video controls src="${escapeHtml(base)}video.mp4"></video>`;
    gv.hidden = false;
  } else {
    gv.innerHTML = '';
    gv.hidden = true;
  }
}

async function loadMdInto(pane, url, fallbackTitle) {
  try {
    const res = await bfetch(url + '?_=' + Date.now());
    if (!res.ok) throw 0;
    const md = await res.text();
    const html = (window.marked && window.DOMPurify)
      ? DOMPurify.sanitize(marked.parse(md))
      : escapeHtml(md).replace(/\n/g, '<br>');   // thiếu thư viện → chữ thường
    setPaneHtml(pane, `<div class="md">${html}</div>`);
    // phần tử cuộn thật là .md (nó mới có overflow:auto), không phải #guide-md —
    // gắn sau mỗi lần render vì DOM bị thay
    if (pane === 'guide') {
      const md = document.querySelector('#guide-md .md');
      if (md) md.addEventListener('scroll', () => {
        $('#guide-video').classList.toggle('mini', md.scrollTop > 80);
      });
    }
  } catch {
    setPaneHtml(pane, emptyMsg(fallbackTitle || t('creating')));
  }
}

function setPaneHtml(pane, html) {
  $(pane === 'guide' ? '#guide-md' : '#pane-' + pane).innerHTML = html;
}
// sandbox="allow-scripts" (KHÔNG allow-same-origin): slide thành opaque
// origin — script chạy nhưng tự nó cũng không đọc được localStorage/token
// của portal kể cả nếu CSP sót. Đã kiểm: slide không dùng localStorage/
// fetch/parent. Clone-view KHÔNG qua hàm này (edit cần same-origin).
function iframe(src) { return `<iframe class="deck" sandbox="allow-scripts" src="${escapeHtml(src)}"></iframe>`; }
function emptyMsg(txt) { return `<div class="empty-msg">${txt}</div>`; }
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
    const r = await bfetch(url + (path || ''), { signal: ctrl.signal, ...(cors ? {} : { mode: 'no-cors' }) });
    return cors ? r.ok : true;
  } catch { return false; }
}

let brainTerminal = 'devin';   // lệnh mở CLI của não — đọc từ /api/brain
async function initChat() {
  chatChecked = true;
  $('#mode-chat').onclick = () => setChatMode('chat');
  $('#mode-cli').onclick = () => setChatMode('cli');
  bfetch(BRIDGE_URL + '/api/brain').then(r => r.json())
    .then(d => { brainTerminal = (d.current && d.current.terminal) || 'devin'; })
    .catch(() => {});
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
      status.innerHTML = `<span class="warn">${t('warnChat')}</span>`;
    }
  } else {
    if (await ping(TTYD_URL)) {
      // ttyd -a append ?arg= vào cuối lệnh → term-gate tự nhận mã kết nối,
      // học viên khỏi gõ tay. Không arg → gate hỏi mã (fallback an toàn).
      if (!termFrame.src) termFrame.src = TTYD_URL + '/?arg=' + encodeURIComponent(window.BRIDGE_TOKEN || '');
      status.innerHTML = '';
    } else {
      status.innerHTML = `<span class="warn">${t('warnCli').replace('devin', brainTerminal)}</span>`;
    }
  }
}

initI18n().finally(loadManifest);

/* ---- trạng thái extension Trợ Lý AI (cánh tay trình duyệt) ---- */
const EXT_BRIDGE = 'http://localhost:7684';
// ID cố định nhờ "key" trong manifest — gửi mã kết nối cho extension
// mỗi lần portal mở (idempotent); trang options có ô dán dự phòng.
const EXT_ID = 'mdalidmkajiinlpdefjchbgcejjjmpeh';
function tryPairExt() {
  try {
    if (!window.chrome || !chrome.runtime || !chrome.runtime.sendMessage) return;
    chrome.runtime.sendMessage(EXT_ID,
      { t: 'set-token', token: window.BRIDGE_TOKEN }, () => void chrome.runtime.lastError);
  } catch (e) { /* chưa cài extension */ }
}
tryPairExt();
let expectedExtV = null;   // version extension đúng = version trong payload đang chạy
async function pollExtStatus() {
  const el = $('#ext-status'), txt = $('#ext-status-text');
  try {
    const sig = (window.AbortSignal && AbortSignal.timeout) ? AbortSignal.timeout(3000) : undefined;
    const r = await bfetch(EXT_BRIDGE + '/api/browser/status', { signal: sig });
    const d = await r.json();
    const stale = d.connected && expectedExtV && d.extVersion && d.extVersion !== expectedExtV;
    el.classList.toggle('on', !!d.connected);
    el.classList.toggle('stale', !!stale);
    txt.textContent = stale ? t('extStale') : (d.connected ? t('extOn') : t('extOff'));
    const note = $('#ext-update-note');
    if (note) {
      note.hidden = !stale;
      if (stale) note.textContent = t('extUpdateHint')
        .replace('{cur}', 'v' + d.extVersion).replace('{exp}', 'v' + expectedExtV);
    }
  } catch {
    el.classList.remove('on');
    el.classList.remove('stale');
    txt.textContent = t('extOff');
  }
}
pollExtStatus();
setInterval(pollExtStatus, 10000);
// Extension đã nối nhưng bản cũ → bấm pill mở Cài đặt để xem cách cập nhật
$('#ext-status').onclick = () => {
  if ($('#ext-status').classList.contains('stale')) settingsOverlay.hidden = false;
};

/* ---- Cập nhật: banner khi GitHub Release có bản mới hơn VERSION đang chạy ---- */
function semverGt(a, b) {
  const pa = String(a).replace(/^v/, '').split('.').map(Number);
  const pb = String(b).replace(/^v/, '').split('.').map(Number);
  for (let i = 0; i < Math.max(pa.length, pb.length); i++) {
    const x = pa[i] || 0, y = pb[i] || 0;
    if (x !== y) return x > y;
  }
  return false;
}
async function checkForUpdate() {
  try {
    const [gh, health] = await Promise.all([
      fetch('https://api.github.com/repos/hieuspaceos/ai-assistant/releases/latest',
            { signal: AbortSignal.timeout(5000) }),
      bfetch(BRIDGE_URL + '/api/health').then(r => r.json()).catch(() => null)
    ]);
    if (health && health.extVersion) expectedExtV = health.extVersion;
    if (!gh.ok || !health) return;
    const rel = await gh.json();
    const latest = (rel.tag_name || '').replace(/^v/, '');
    if (latest && semverGt(latest, health.version || '0')) {
      const b = $('#update-banner');
      b.textContent = t('updateNew').replace('{v}', 'v' + latest);
      b.href = rel.html_url;
      b.hidden = false;
    }
  } catch { /* mất mạng thì thôi — portal local vẫn dùng bình thường */ }
}
checkForUpdate();

/* ---- Cài đặt: kết nối app + folder được phép — gom vào nút ⚙ cuối sidebar ---- */
const settingsOverlay = $('#settings-overlay');

$('#settings-btn').onclick = async () => {
  settingsOverlay.hidden = false;
  renderBrain();
  renderConnCode();
  renderFolders();
  const apps = await renderApps();
  // kiểm tra lại trạng thái THẬT của từng app ngầm — panel cập nhật dần,
  // không hiện số liệu cũ đã lưu từ lần trước
  if (apps && apps.length) {
    apps.forEach(a => {
      bfetch(BRIDGE_URL + '/api/check-connection', {
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

// "Bộ não" — dropdown preset ĐÃ CÀI (não chưa cài không cho chọn từ đây;
// não lạ do nhập tay ở onboarding vẫn hiện dòng "đang dùng" để không mất chọn)
async function renderBrain() {
  try {
    const d = await (await bfetch(BRIDGE_URL + '/api/brain')).json();
    const row = $('#brain-row');
    const opts = (d.presets || []).filter(p => p.installed);
    const have = new Set(opts.map(o => o.id));
    row.innerHTML = '';
    const sel = document.createElement('select');
    sel.className = 'brain-sel';
    if (d.current && d.current.id && !have.has(d.current.id)) {
      const o = document.createElement('option');
      o.value = d.current.id;
      o.textContent = (d.current.label || d.current.id) + ' (' + t('brainCurrent') + ')';
      sel.appendChild(o);
    }
    opts.forEach(p => {
      const o = document.createElement('option');
      o.value = p.id;
      const cost = p.cost === 'free' ? t('brainCostFree')
        : p.cost === 'byok' ? t('brainCostByok') : t('brainCostPaid');
      o.textContent = p.label + ' · ' + cost;
      sel.appendChild(o);
    });
    sel.value = (d.current && d.current.id) || 'devin';
    const msg = document.createElement('span');
    msg.className = 'brain-msg';
    sel.onchange = async () => {
      sel.disabled = true; msg.textContent = t('brainSwitching');
      try {
        const r = await (await bfetch(BRIDGE_URL + '/api/brain', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ id: sel.value })
        })).json();
        msg.textContent = r.ok ? t('brainDone') : (r.err || t('brainFail'));
        if (r.ok && r.brain && r.brain.terminal) brainTerminal = r.brain.terminal;
      } catch { msg.textContent = t('brainFail'); }
      sel.disabled = false;
      setTimeout(() => { msg.textContent = ''; }, 5000);
    };
    row.appendChild(sel); row.appendChild(msg);
  } catch { /* bridge chưa chạy — giấu mục này */ }
}

// "Mã kết nối" — để học viên copy dán vào extension khi nó hỏi (đường dự
// phòng; đường chính là auto-pair từ onboarding)
function renderConnCode() {
  const row = $('#conn-row');
  row.innerHTML = '';
  const code = document.createElement('code');
  code.className = 'conn-code';
  code.textContent = window.BRIDGE_TOKEN || '—';
  const btn = document.createElement('button');
  btn.className = 'mini-btn';
  btn.textContent = t('connCopy');
  btn.onclick = async () => {
    try {
      await navigator.clipboard.writeText(window.BRIDGE_TOKEN || '');
      btn.textContent = t('connCopied');
    } catch { btn.textContent = t('connCodeTitle'); }
    setTimeout(() => { btn.textContent = t('connCopy'); }, 3000);
  };
  row.appendChild(code); row.appendChild(btn);
}

async function renderApps() {
  let apps = [];
  try {
    const list = $('#app-list');
    // một form "Cài" đang mở → không rebuild (rebuild = mất trắng chữ đang
    // gõ). auto-refresh 15s + mỗi check-connection đều gọi hàm này → phải bỏ qua.
    if (list.querySelector('.app-setup:not([hidden])')) return null;
    const d = await (await bfetch(BRIDGE_URL + '/api/connections')).json();
    apps = d.apps || [];
    list.innerHTML = '';
    if (!apps.length) {
      const p = document.createElement('p');
      p.className = 'empty';
      p.textContent = t('emptyApps');
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
          ? `<button class="app-open" title="${escapeHtml(t('openTitle'))}">${escapeHtml(t('btnOpen'))}</button>`
          : '') +
        `<button class="app-check" title="${escapeHtml(t('recheckTitle'))}">↻</button>`;
      const openBtn = row.querySelector('.app-open');
      if (openBtn) openBtn.onclick = () => { window.open(a.open_url, '_blank'); };
      row.querySelector('.app-check').onclick = async () => {
        row.querySelector('.app-check').textContent = '…';
        const r = await (await bfetch(BRIDGE_URL + '/api/check-connection', {
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
        setupBtn.textContent = t('btnSetup');
        setupBtn.title = t('setupTitle');
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
            `<button class="app-save">${escapeHtml(t('saveCheck'))}</button>` +
            `<span class="app-setup-hint">${escapeHtml(t('setupLocal'))}</span>` +
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
          btn.textContent = '…';
          const res = await (await bfetch(BRIDGE_URL + '/api/secrets', {
            method: 'POST', body: JSON.stringify({ app: a.id, fields })
          })).json();
          if (res.err) { btn.textContent = res.err; return; }
          // ghi credential qua consent gate — thông tin chỉ lưu sau khi
          // bấm Đồng ý trong chat; giữ form mở để họ thấy chưa xong
          if (res.pending) {
            btn.textContent = t('saveCheck');
            await uiAlert(t('gateTitle'), res.msg || t('gateMsg'));
            return;
          }
          await bfetch(BRIDGE_URL + '/api/check-connection', {
            method: 'POST', body: JSON.stringify({ id: a.id })
          });
          form.hidden = true;   // đóng form trước khi render — không bị skip
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
    const d = await (await bfetch(BRIDGE_URL + '/api/permissions')).json();
    const fs = d.folders || [];
    $('#folder-list').innerHTML = '';
    for (const f of fs) {
      const row = document.createElement('div');
      row.className = 'folder-row';
      row.innerHTML =
        `<span class="folder-path" title="${escapeHtml(f.note || f.path)}">${escapeHtml(f.path)}</span>` +
        `<span class="folder-lv">${f.access === 'read-write' ? t('readWrite') : t('readOnly')}</span>` +
        `<button class="folder-del" title="${escapeHtml(t('delPermTitle'))}">×</button>`;
      row.querySelector('.folder-del').onclick = async () => {
        const r = await (await bfetch(BRIDGE_URL + '/api/remove-permission', {
          method: 'POST', body: JSON.stringify({ path: f.path })
        })).json().catch(() => ({}));
        if (r.pending) await uiAlert(t('gateTitle'), r.msg || t('gateMsg'));
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
  const r = await (await bfetch(BRIDGE_URL + '/api/permissions', {
    method: 'POST',
    body: JSON.stringify({ path: p, access: $('#folder-access').value })
  })).json();
  if (r.err) { $('#folder-path').value = ''; $('#folder-path').placeholder = r.err; return; }
  $('#folder-path').value = '';
  $('#folder-add').hidden = true;
  $('#folder-add-btn').hidden = false;
  if (r.pending) await uiAlert(t('gateTitle'), r.msg || t('gateMsg'));
  renderFolders();
};

// chỉ làm mới khi panel cài đặt đang mở — sidebar không còn hiển thị 2 mục này
setInterval(() => {
  if (!settingsOverlay.hidden) { renderApps(); renderFolders(); }
}, 15000);

/* ---- Trợ lý theo nghề (bots) — chip trên header + gallery tạo mới ---- */
let botsState = { active: null, bots: [], templates: [] };
let connMap = {};

async function loadBots() {
  try {
    const [b, k] = await Promise.all([
      bfetch(BRIDGE_URL + '/api/bots').then(r => r.json()),
      bfetch(BRIDGE_URL + '/api/connections').then(r => r.json()).catch(() => ({ apps: [] }))
    ]);
    botsState = { active: b.active, bots: b.bots || [], templates: b.templates || [] };
    connMap = {}; (k.apps || []).forEach(a => connMap[a.id] = a);
  } catch { /* bridge chưa chạy — giữ state cũ */ }
  renderBotChip();
}

function renderBotChip() {
  const chip = $('#bot-chip');
  const active = botsState.bots.find(x => x.id === botsState.active);
  $('#bot-chip-ava').textContent = active ? (active.avatar || '🤖') : '🤖';
  $('#bot-chip-name').textContent = active ? active.name : t('botGeneral');
  chip.hidden = false;
}

function botNeedsHtml(needs) {
  return (needs || []).map(n => {
    const a = connMap[n];
    const ok = a && a.status === 'connected';
    const nm = (a && a.name) || n;
    return `<span class="need ${ok ? 'ok' : 'warn'}" title="${ok ? t('botConnOk') : t('botConnWarn')}">${escapeHtml(nm)} ${ok ? '✓' : '⚠'}</span>`;
  }).join(' ');
}

$('#bot-chip').onclick = (e) => {
  e.stopPropagation();
  const menu = $('#bot-menu');
  if (!menu.hidden) { menu.hidden = true; return; }
  const items = botsState.bots.map(x =>
    `<button class="bot-item${x.id === botsState.active ? ' on' : ''}" data-id="${escapeHtml(x.id)}">` +
    `<span>${escapeHtml(x.avatar || '🤖')}</span> ${escapeHtml(x.name)}` +
    (x.id === botsState.active ? ' <span class="need ok">✓</span>' : '') +
    `</button>`).join('');
  menu.innerHTML = items +
    `<button class="bot-item${!botsState.active ? ' on' : ''}" data-id=""><span>🤖</span> ${escapeHtml(t('botGeneral'))}${!botsState.active ? ' <span class="need ok">✓</span>' : ''}</button>` +
    `<div class="bot-sep"></div>` +
    `<button class="bot-item" data-new="1"><span>＋</span> ${escapeHtml(t('botNew'))}</button>` +
    `<button class="bot-item" data-imp="1"><span>📥</span> ${escapeHtml(t('botImport'))}</button>`;
  menu.hidden = false;
  menu.querySelectorAll('.bot-item').forEach(it => {
    it.onclick = async () => {
      menu.hidden = true;
      if (it.dataset.new) { openBotGallery(); return; }
      if (it.dataset.imp) { $('#bot-file').click(); return; }
      try {
        await bfetch(BRIDGE_URL + '/api/bot', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action: 'activate', id: it.dataset.id || null })
        });
        await loadBots();
        loadManifest();   // recipes đổi theo trợ lý
      } catch { uiAlert(t('botErr'), ''); }
    };
  });
};
document.addEventListener('click', () => { const m = $('#bot-menu'); if (m) m.hidden = true; });
$('#bot-menu').onclick = e => e.stopPropagation();

/* Gallery tạo trợ lý — tái dùng template của onboarding, render vào overlay */
let galleryTpl = null;
function openBotGallery() {
  galleryTpl = null;
  const g = $('#bot-gallery');
  g.innerHTML = '';
  $('#bot-import-view').hidden = true;
  const title = document.querySelector('#bot-panel .settings-head span');
  if (title) title.textContent = t('botNewTitle');   // reset sau import view
  botsState.templates.forEach(tp => {
    const nm = (tp.suggested_bot_name && (tp.suggested_bot_name[LANG] || tp.suggested_bot_name.vi)) || '';
    const card = document.createElement('div');
    card.className = 'bot-gcard';
    card.innerHTML =
      `<span class="bot-gava">${escapeHtml(tp.avatar || '🤖')}</span>` +
      `<div><b>${escapeHtml((tp.name && (tp.name[LANG] || tp.name.vi)) || tp.id)}</b>` +
      `<small>${escapeHtml((tp.desc && (tp.desc[LANG] || tp.desc.vi)) || '')}</small>` +
      `<div class="need-row">${botNeedsHtml(tp.needs)}</div></div>`;
    card.onclick = () => {
      galleryTpl = tp;
      g.querySelectorAll('.bot-gcard').forEach(c => c.classList.remove('sel'));
      card.classList.add('sel');
      $('#bot-create-row').hidden = false;
      const inp = $('#bot-create-name');
      inp.value = nm; inp.focus();
    };
    g.appendChild(card);
  });
  $('#bot-create-row').hidden = true;
  $('#bot-overlay').hidden = false;
}
$('#bot-close').onclick = () => { $('#bot-overlay').hidden = true; };
$('#bot-overlay').onclick = e => { if (e.target.id === 'bot-overlay') e.target.hidden = true; };
$('#bot-create-btn').onclick = async () => {
  if (!galleryTpl) return;
  const btn = $('#bot-create-btn');
  btn.disabled = true; btn.textContent = t('botCreating');
  try {
    const name = $('#bot-create-name').value.trim() || galleryTpl.id;
    const r = await bfetch(BRIDGE_URL + '/api/bot', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        action: 'create', name, role: galleryTpl.id, avatar: galleryTpl.avatar,
        skills: galleryTpl.skills, needs: galleryTpl.needs, recipes: galleryTpl.recipes,
        instructions: (galleryTpl.instructions && (galleryTpl.instructions[LANG] || galleryTpl.instructions.vi)) || ''
      })
    });
    const d = await r.json().catch(() => ({}));
    if (!r.ok || !d.bot) throw 0;
    await bfetch(BRIDGE_URL + '/api/bot', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'activate', id: d.bot.id })
    });
    $('#bot-overlay').hidden = true;
    await loadBots();
    loadManifest();
  } catch { uiAlert(t('botErr'), ''); }
  btn.disabled = false; btn.textContent = t('botCreateBtn');
};

/* Nhập trợ lý từ file .zip — preview instructions TRƯỚC khi ghi thật */
$('#bot-file').onchange = async (e) => {
  const f = e.target.files[0];
  e.target.value = '';
  if (!f) return;
  let b64;
  try {
    b64 = await new Promise((res, rej) => {
      const r = new FileReader();
      r.onload = () => res(String(r.result).split(',')[1] || '');
      r.onerror = rej;
      r.readAsDataURL(f);
    });
  } catch { uiAlert(t('botErr'), ''); return; }
  let d;
  try {
    const r = await bfetch(BRIDGE_URL + '/api/bot-import', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ file: b64 })
    });
    d = await r.json();
    if (!r.ok) { uiAlert(t('botImportTitle'), d.err || t('botErr')); return; }
  } catch { uiAlert(t('botErr'), ''); return; }
  const p = d.preview;
  const ins = typeof p.instructions === 'object'
    ? (p.instructions[LANG] || p.instructions.vi || '') : (p.instructions || '');
  $('#bot-gallery').innerHTML = '';
  $('#bot-create-row').hidden = true;
  const v = $('#bot-import-view');
  v.hidden = false;
  v.innerHTML =
    `<div class="bot-gcard"><span class="bot-gava">${escapeHtml(p.avatar || '🤖')}</span>` +
    `<div><b>${escapeHtml(p.name || '')}</b> <small>${escapeHtml(p.role || '')}</small>` +
    `<div class="need-row">${botNeedsHtml(p.needs)}</div></div></div>` +
    `<p class="bot-import-warn">${escapeHtml(t('botImportWarn'))}</p>` +
    `<div class="bot-import-ins">${escapeHtml(ins) || '<i>—</i>'}</div>` +
    `<p class="note">${escapeHtml(t('botImportSkills'))} <code>${(p.skills || []).map(escapeHtml).join('</code> <code>') || '—'}</code></p>` +
    `<div class="row" style="justify-content:flex-end"><button class="mini-btn" id="bot-imp-ok">${escapeHtml(t('botImportBtn'))}</button></div>`;
  const title = document.querySelector('#bot-panel .settings-head span');
  if (title) title.textContent = t('botImportTitle');
  $('#bot-overlay').hidden = false;
  $('#bot-imp-ok').onclick = async () => {
    const btn = $('#bot-imp-ok');
    btn.disabled = true; btn.textContent = t('botImporting');
    try {
      const r = await bfetch(BRIDGE_URL + '/api/bot-import-confirm', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ stage: p.stage })
      });
      const d2 = await r.json().catch(() => ({}));
      if (!r.ok) { uiAlert(t('botImportTitle'), d2.err || t('botErr')); }
      else {
        $('#bot-overlay').hidden = true;
        uiAlert(t('botImportTitle'), t('botImportDone'));
        await loadBots();
      }
    } catch { uiAlert(t('botErr'), ''); }
    btn.disabled = false; btn.textContent = t('botImportBtn');
  };
};

loadBots();
