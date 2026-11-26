/* Portal "Trợ lý AI" — đọc workspace/manifest.json, hiển thị bài học.
   Serve từ root ai-assistant/ nên tài nguyên đều ở /workspace/... và /intro/... */

const TTYD_URL = 'http://localhost:7681';
const BRIDGE_URL = 'http://localhost:7682';
let manifest = null;
let currentLesson = null;
let chatChecked = false;
let chatMode = 'chat';
let LANG = 'vi';

/* Chuỗi UI theo ngôn ngữ trong workspace/config.json (onboarding chọn vi/en).
   Phần tử tĩnh trong index.html gắn data-i18n / data-i18n-ph /
   data-i18n-title / data-i18n-html; chuỗi động trong file này dùng t(). */
const I18N = {
  vi: {
    loading: 'Đang tải…',
    lessons: 'Công cụ',
    recipesTitle: 'Công thức nhanh',
    recipeHint: 'Gõ các lệnh này trong tab “Hỏi trợ lý”',
    introLesson: 'Làm quen & cài đặt',
    emptyLessons: 'Chưa có công cụ nào. Mở tab "Hỏi trợ lý" và gõ /phong-van nhé.',
    emptyApps: 'Chưa có app nào — trợ lý tự thêm khi bạn cần.',
    tabSlide: 'Slide', tabGuide: 'Hướng dẫn', tabExercise: 'Bài tập', tabAsk: 'Hỏi trợ lý',
    welcomeTitle: 'Chào bạn!',
    welcomeSub: 'Trợ lý AI làm việc thật trên máy bạn — và nó tự làm ra những công cụ riêng cho bạn, kèm hướng dẫn từng-bước dùng ngay.',
    chatFrameTitle: 'Chat với trợ lý (kiểu tin nhắn)',
    how1: '<b>Nhờ trợ lý</b> bất cứ việc gì — bấm nút <b>Hỏi trợ lý</b> phía trên.',
    how2: '<b>Chọn một công cụ</b> bên trái để xem hướng dẫn — hoặc bấm <b>▶ Dùng ngay</b>.',
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
    brainPending: 'Đã gửi thẻ xác nhận — vào tab Hỏi trợ lý bấm Đồng ý',
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
    adminLink: 'Dành cho quản trị viên (IT) →',
    delPermTitle: 'Gỡ quyền', recheckTitle: 'Kiểm tra lại',
    btnOpen: 'Mở trang', btnSetup: 'Cài',
    openTitle: 'Mở trang này trên trình duyệt', setupTitle: 'Điền thông tin kết nối',
    saveCheck: 'Lưu & kiểm tra',
    setupLocal: 'Chỉ lưu trên máy bạn, vào file ẩn — không gửi đi đâu.',
    dlgCancel: 'Huỷ', dlgOk: 'Đồng ý', dlgOkShort: 'Đã hiểu',
    delLessonTitle: 'Xoá hướng dẫn này (giữ lại lệnh /…)',
    helloPrefix: 'Chào ',
    creating: 'File đang được tạo — quay lại sau nhé.',
    slideCreating: 'Slide đang được tạo — quay lại sau vài phút nhé.',
    noExercise: 'Mục này không có phần thêm — mở hướng dẫn là đủ.',
    wzStep: 'Bước', wzBack: 'Quay lại', wzNext: 'Tiếp', wzDone: 'Xong — xem toàn bộ',
    wzAll: 'Xem hết', wzSteps: 'Xem từng bước', wzIntro: 'Giới thiệu',
    wtLaunch: '▶ Dùng ngay', wtClose: 'Đóng hướng dẫn',
    wtSkip: 'Bỏ qua', wtSend: 'Gửi', wtPick: 'Chọn file/folder',
    wtOpenUrl: 'Mở trang', wtDidIt: 'Mình đã làm xong', wtWaiting: 'Trợ lý đang làm — đợi xíu…',
    wtAuto: 'Để trợ lý lo luôn', wtReveal: 'Mở trong Finder',
    wtDownload: 'Tải file', wtOk: 'Đúng rồi', wtNotYet: 'Chưa thấy — nhờ trợ lý',
    wtCopy: 'Copy', wtCopied: 'Đã copy ✓', wtDone: 'Xong', wtAsked: 'Đã nhờ trợ lý ✓',
    delConfirmTitle: 'Xoá mục "{t}"?',
    delConfirmMsg: 'Toàn bộ nội dung của mục này (hướng dẫn và file kèm theo) sẽ mất hết. Lệnh /… vẫn được giữ lại vì nó nằm trong bộ công thức của bạn.',
    delOk: 'Xoá',
    delFailTitle: 'Chưa xoá được',
    delFailMsg: 'Kiểm tra lại xem chat-bridge có đang chạy không nhé — thử chạy lại file start.',
    gateTitle: 'Cần bạn xác nhận',
    gateMsg: 'Đã gửi thẻ xác nhận vào tab "Hỏi trợ lý" — bấm "Đồng ý" bên đó để hoàn tất.',
    warnChat: '<b>Chế độ Chat chưa mở:</b> chạy lại <code>start.bat</code>, hoặc bấm sang tab <b>Terminal</b> bên cạnh để dùng tạm.',
    warnCli: '<b>Terminal chưa mở:</b> chạy lại <code>start.bat</code>, hoặc mở PowerShell gõ <code>devin</code> để học bình thường.',
    hintNotReady: 'Trợ lý chưa sẵn sàng — mở lại file <code>start</code> rồi tải lại trang này. Nếu mới dùng lần đầu, bấm <a href="onboarding.html"><b>vào đây để cài đặt</b></a>.',
    hintNoLessons: 'Chưa có công cụ nào? Bấm <b>Hỏi trợ lý</b> và gõ <code>/phong-van</code>, nó sẽ hỏi vài câu rồi làm bộ công cụ riêng cho bạn.',
    hintReady: 'Chọn một công cụ bên trái để dùng — hoặc bấm <b>Hỏi trợ lý</b> để nhờ bất cứ việc gì, không cần mở hướng dẫn.',
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
    wfTitle: 'Quy trình',
    wfRun: 'Chạy',
    wfRunning: 'Đang chạy…',
    wfCheckTitle: 'kiểm kết quả',
    wfAllOk: 'Tất cả đúng ✓',
    wfHasIssue: 'Có vấn đề',
    wfVerifyOk: 'Máy tự kiểm: đủ ✓',
    wfVerifyFail: 'Máy tự kiểm: chưa thấy kết quả',
    wfNeedConn: 'Cần mở trước: {apps} — chạy xong trợ lý sẽ dẫn bạn nối.',
    wfNeedPerm: 'Trợ lý chưa được phép đọc: {paths} — nó sẽ xin quyền khi chạy, bạn đồng ý là được.',
    wfBusy: 'Trợ lý đang làm việc khác — đợi xong rồi chạy lại nhé.',
    wfSentErr: 'Không gửi được cho trợ lý — thử chạy lại file start.',
    wfIssueFix: 'Quy trình "{title}" vừa chạy có vấn đề ở các mục: {issues} — kiểm tra lại và sửa cho đúng.',
    wfIssueFixAll: 'Quy trình "{title}" vừa chạy xong nhưng kết quả chưa đúng — kiểm tra lại và sửa.',
    wfVerifyFailMsg: 'kiểm tra tự động không thấy file kết quả',
  },
  en: {
    loading: 'Loading…',
    lessons: 'Tools',
    recipesTitle: 'Quick recipes',
    recipeHint: 'Type these in the "Ask the assistant" tab',
    introLesson: 'Getting started & setup',
    emptyLessons: 'No tools yet. Open "Ask the assistant" and type /interview.',
    emptyApps: 'No apps yet — the assistant adds them as needed.',
    tabSlide: 'Slide', tabGuide: 'Guide', tabExercise: 'Exercise', tabAsk: 'Ask the assistant',
    welcomeTitle: 'Hello!',
    welcomeSub: 'Your AI assistant does real work on this machine — and it builds tools just for you, each with a step-by-step walkthrough.',
    chatFrameTitle: 'Chat with the assistant',
    how1: '<b>Ask the assistant</b> for anything — click <b>Ask the assistant</b> above.',
    how2: '<b>Pick a tool</b> on the left to see the guide — or hit <b>▶ Use it now</b>.',
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
    brainPending: 'Approval card sent — press Đồng ý in the chat tab',
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
    adminLink: 'For IT administrators →',
    delPermTitle: 'Remove access', recheckTitle: 'Check again',
    btnOpen: 'Open', btnSetup: 'Set up',
    openTitle: 'Open this page in your browser', setupTitle: 'Enter connection details',
    saveCheck: 'Save & check',
    setupLocal: 'Saved only on this machine, in a hidden file — never sent anywhere.',
    dlgCancel: 'Cancel', dlgOk: 'OK', dlgOkShort: 'Got it',
    delLessonTitle: 'Remove this guide (keeps the /command)',
    helloPrefix: 'Hi ',
    creating: 'This file is being created — check back soon.',
    slideCreating: 'Slides are being created — check back in a few minutes.',
    noExercise: 'This entry has no extra section — the guide is enough.',
    wzStep: 'Step', wzBack: 'Back', wzNext: 'Next', wzDone: 'Done — view all',
    wzAll: 'View all', wzSteps: 'Step by step', wzIntro: 'Overview',
    wtLaunch: '▶ Use it now', wtClose: 'Close walkthrough',
    wtSkip: 'Skip', wtSend: 'Send', wtPick: 'Pick file/folder',
    wtOpenUrl: 'Open page', wtDidIt: 'I did it', wtWaiting: 'Assistant is working — hold on…',
    wtAuto: 'Let the assistant do it', wtReveal: 'Open in Finder',
    wtDownload: 'Download', wtOk: 'Looks right', wtNotYet: 'Not there — ask the assistant',
    wtCopy: 'Copy', wtCopied: 'Copied ✓', wtDone: 'Done', wtAsked: 'Assistant asked ✓',
    delConfirmTitle: 'Remove "{t}"?',
    delConfirmMsg: 'All of this entry\u2019s content (guide and bundled files) will be gone for good. The /command stays — it lives with your other quick recipes.',
    delOk: 'Delete',
    delFailTitle: 'Couldn\'t delete',
    delFailMsg: 'Check whether the chat bridge is running — try running the start file again.',
    gateTitle: 'Needs your confirmation',
    gateMsg: 'A confirmation card was sent to the "Ask the assistant" tab — tap "Đồng ý" (agree) there to finish.',
    warnChat: '<b>Chat mode isn\'t up:</b> run the <code>start</code> file again, or switch to the <b>Terminal</b> tab meanwhile.',
    warnCli: '<b>Terminal isn\'t up:</b> run the <code>start</code> file again, or open a shell and type <code>devin</code>.',
    hintNotReady: 'The assistant isn\'t ready — run the <code>start</code> file again and reload. First time here? <a href="onboarding.html"><b>Click to set up</b></a>.',
    hintNoLessons: 'No tools yet? Click <b>Ask the assistant</b> and type <code>/interview</code> — it will ask a few questions then build tools just for you.',
    hintReady: 'Pick a tool on the left — or click <b>Ask the assistant</b> for anything, no guide needed.',
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
    wfTitle: 'Workflows',
    wfRun: 'Run',
    wfRunning: 'Running…',
    wfCheckTitle: 'check the result',
    wfAllOk: 'All correct ✓',
    wfHasIssue: 'There\'s a problem',
    wfVerifyOk: 'Auto-check: OK ✓',
    wfVerifyFail: 'Auto-check: result not found',
    wfNeedConn: 'Open first: {apps} — the assistant will guide you after it runs.',
    wfNeedPerm: 'The assistant can\'t read: {paths} — it will ask when it runs, just approve.',
    wfBusy: 'The assistant is busy — wait for it to finish, then run again.',
    wfSentErr: 'Couldn\'t reach the assistant — try running the start file again.',
    wfIssueFix: 'The workflow "{title}" just ran with problems in: {issues} — please check and fix.',
    wfIssueFixAll: 'The workflow "{title}" just finished but the result is wrong — please check and fix.',
    wfVerifyFailMsg: 'auto-check could not find the output files',
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
    const res = await bfetch('/workspace/manifest.json?_=' + Date.now());
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
    document.querySelectorAll('.tool-tab').forEach(t => t.hidden = true);
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
  $('#content').hidden = false;
  // Tab hiện theo file bài thật sự có: bài cũ (thiếu flag) giữ nguyên
  // cả 3 tab; bài mới chỉ có guide → giấu hẳn Slide/Bài tập thay vì
  // hiện màn "đang tạo". Intro có slide + guide, không có bài tập.
  const isIntro = lesson === null;
  const tabs = {
    slide:    isIntro || lesson.has_slides !== false,
    guide:    true,
    exercise: !isIntro && lesson.has_exercise !== false,
  };
  document.querySelectorAll('.tool-tab').forEach(t => { t.hidden = !tabs[t.dataset.tab]; });
  if (isIntro) loadIntro();
  else loadLesson(lesson);
  switchTab(tabs.slide ? 'slide' : 'guide');
}

function baseUrl(lesson) { return '/workspace/' + lesson.folder + '/'; }

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
  if (lesson.has_exercise !== false) loadMdInto('exercise', base + 'exercise.md');
  loadWalkthrough(base);

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
    const render = txt => (window.marked && window.DOMPurify)
      ? DOMPurify.sanitize(marked.parse(txt))
      : escapeHtml(txt).replace(/\n/g, '<br>');   // thiếu thư viện → chữ thường
    // guide có các "### Bước/Step" → render thành wizard từng-bước
    if (pane === 'guide' && /^###\s+/m.test(md)) { buildGuideWizard(md, render); return; }
    setPaneHtml(pane, `<div class="md">${render(md)}</div>`);
    if (pane === 'guide') watchGuideScroll($('#guide-md .md'));
  } catch {
    setPaneHtml(pane, emptyMsg(fallbackTitle || t('creating')));
  }
}

// phần tử cuộn thật là .md / .wz-body (nó mới có overflow:auto), không phải
// #guide-md — gắn lại sau mỗi lần render vì DOM bị thay
function watchGuideScroll(el) {
  if (el) el.addEventListener('scroll', () => {
    $('#guide-video').classList.toggle('mini', el.scrollTop > 80);
  });
}

/* Guide kiểu tutorial từng-bước → wizard giống onboarding: mỗi "### Bước N"
   một màn, nút Quay lại / Tiếp, "Xem hết" mở lại trang đầy đủ. Các section
   "## " sau bước cuối (bảng nhớ) thành step phụ lục riêng. */
function buildGuideWizard(md, render) {
  const box = $('#guide-md');
  const steps = [];
  const chunks = md.split(/^###\s+/m);
  const intro = chunks.shift().trim();
  if (intro) steps.push({ title: t('wzIntro'), body: intro });
  chunks.forEach(c => {
    const nl = c.indexOf('\n');
    const title = (nl < 0 ? c : c.slice(0, nl)).trim();
    const rest = nl < 0 ? '' : c.slice(nl + 1);
    const sub = rest.split(/^##\s+/m);
    steps.push({ title, body: sub[0].trim() });
    sub.slice(1).forEach(s => {
      const nl2 = s.indexOf('\n');
      steps.push({ title: (nl2 < 0 ? s : s.slice(0, nl2)).trim(), body: (nl2 < 0 ? '' : s.slice(nl2 + 1)).trim() });
    });
  });
  let cur = 0;
  function draw() {
    const last = cur === steps.length - 1;
    box.innerHTML = `
      <div class="wz">
        <div class="wz-top">
          <span class="wz-prog">${escapeHtml(t('wzStep'))} ${cur + 1}/${steps.length}</span>
          <button type="button" class="wz-link" data-act="all">${escapeHtml(t('wzAll'))}</button>
        </div>
        <div class="wz-body">
          ${steps[cur].title ? `<h3 class="wz-title">${escapeHtml(steps[cur].title)}</h3>` : ''}
          <div class="md">${render(steps[cur].body)}</div>
        </div>
        <div class="wz-nav">
          <button type="button" class="wz-btn" data-act="prev" ${cur === 0 ? 'disabled' : ''}>← ${escapeHtml(t('wzBack'))}</button>
          <button type="button" class="wz-btn wz-primary" data-act="next">${last ? escapeHtml(t('wzDone')) : escapeHtml(t('wzNext')) + ' →'}</button>
        </div>
      </div>`;
    box.querySelector('[data-act=prev]').onclick = () => { cur--; draw(); };
    box.querySelector('[data-act=next]').onclick = () => { if (last) showDoc(); else { cur++; draw(); } };
    box.querySelector('[data-act=all]').onclick = showDoc;
    watchGuideScroll(box.querySelector('.wz-body'));
  }
  function showDoc() {
    box.innerHTML = `
      <div class="wz">
        <div class="wz-top">
          <span class="wz-prog"></span>
          <button type="button" class="wz-link" data-act="steps">${escapeHtml(t('wzSteps'))}</button>
        </div>
        <div class="wz-body"><div class="md">${render(md)}</div></div>
      </div>`;
    box.querySelector('[data-act=steps]').onclick = draw;
    watchGuideScroll(box.querySelector('.wz-body'));
  }
  draw();
}

function setPaneHtml(pane, html) {
  $(pane === 'guide' ? '#guide-md' : '#pane-' + pane).innerHTML = html;
}

/* ============ WALKTHROUGH — hướng dẫn tương tác từng-bước ============
   walkthrough.json trong folder bài → nút "▶ Dùng ngay" trong pane guide.
   Runner là renderer câm: mỗi step.kind một widget, vars nối data giữa
   các bước, cond/optional/then_probe điều khiển flow. */

let currentWT = null;   // {data, base} của bài đang mở
let wt = null;          // trạng thái runner đang chạy

async function loadWalkthrough(base) {
  currentWT = null;
  try {
    const r = await bfetch(base + 'walkthrough.json?_=' + Date.now());
    if (r.ok) currentWT = { data: await r.json(), base };
  } catch { /* không có file → không nút */ }
  const btn = $('#wt-launch');
  if (btn) { btn.hidden = !currentWT; btn.textContent = t('wtLaunch'); btn.onclick = () => wtStart(); }
}

function wtStart() {
  if (!currentWT || wt) return;
  const saved = JSON.parse(localStorage.getItem(wtSaveKey()) || '0');
  wt = { data: currentWT.data, base: currentWT.base, vars: {},
         i: saved || 0, timer: null, onDocClick: null };
  const ov = document.createElement('div');
  ov.id = 'wt-overlay';
  ov.innerHTML = '<div class="wt-dim"></div><div class="wt-spot" hidden></div>' +
                 '<div class="wt-card"></div>';
  document.body.appendChild(ov);
  wtDraw();
}

function wtSaveKey() { return 'wt_progress_' + (currentLesson ? currentLesson.folder : 'x'); }

function wtStop() {
  if (!wt) return;
  if (wt.timer) clearInterval(wt.timer);
  if (wt.onDocClick) document.removeEventListener('click', wt.onDocClick, true);
  const ov = $('#wt-overlay');
  if (ov) ov.remove();
  localStorage.removeItem(wtSaveKey());
  wt = null;
}

function wtSubst(s) {
  return String(s == null ? '' : s).replace(/\{\{(\w+)\}\}/g,
    (m, k) => wt.vars[k] != null ? wt.vars[k] : m);
}

/* cond: {conn:'zalo'} | {var:'x',equals:'v'} | {path:'~/...'} → true = hiện */
async function wtCondOk(s) {
  const c = s.cond;
  if (!c) return true;
  try {
    if (c.conn) {
      const r = await (await bfetch(BRIDGE_URL + '/api/check-connection', {
        method: 'POST', body: JSON.stringify({ id: c.conn })
      })).json();
      return !!r.ok;
    }
    if (c.var) return String(wt.vars[c.var]) === String(c.equals);
    if (c.path) {
      const r = await (await bfetch(BRIDGE_URL + '/api/check-path', {
        method: 'POST', body: JSON.stringify({ path: wtSubst(c.path) })
      })).json();
      return !!r.ok;
    }
  } catch { /* probe lỗi → cứ hiện bước */ }
  return true;
}

/* tìm step hiện kế tiếp (bỏ qua step có cond sai), hướng +1/-1 */
async function wtNextIdx(from, dir) {
  let i = from;
  while (i >= 0 && i < wt.data.steps.length) {
    if (await wtCondOk(wt.data.steps[i])) return i;
    i += dir;
  }
  return i < 0 ? 0 : wt.data.steps.length - 1;
}

async function wtGo(delta) {
  localStorage.setItem(wtSaveKey(), String(wt.i));
  wt.i = await wtNextIdx(wt.i + delta, delta >= 0 ? 1 : -1);
  wtDraw();
}

function wtPoll(until) {   // until: 'event' | 'done' | {conn:id}
  if (wt.timer) clearInterval(wt.timer);
  let after = null, tries = 0;
  wt.timer = setInterval(async () => {
    if (!wt) return;
    try {
      if (until.conn) {
        const r = await (await bfetch(BRIDGE_URL + '/api/check-connection', {
          method: 'POST', body: JSON.stringify({ id: until.conn })
        })).json();
        if (r.ok) { clearInterval(wt.timer); wt.timer = null; wtGo(1); }
      } else {
        if (after == null) {
          const d0 = await (await bfetch(BRIDGE_URL + '/api/poll?since=0')).json();
          after = d0.next || 0;
          return;
        }
        const d = await (await bfetch(BRIDGE_URL + '/api/poll?since=' + after)).json();
        after = (d.next != null) ? d.next : after;
        const hit = (d.events || []).some(ev =>
          until === 'done' ? (ev.t === 'done' || ev.t === 'err')
                           : (ev.t !== 'perm'));
        if (hit) { clearInterval(wt.timer); wt.timer = null; wtGo(1); }
      }
      if (++tries > 300) { clearInterval(wt.timer); wt.timer = null; }
    } catch { /* vòng sau thử tiếp */ }
  }, 2000);
}

function wtSpot(target) {
  const spot = $('#wt-overlay .wt-spot');
  const el = target && document.querySelector(target);
  if (!el) { spot.hidden = true; return; }
  const r = el.getBoundingClientRect();
  spot.hidden = false;
  spot.style.cssText = `left:${r.left - 6}px;top:${r.top - 6}px;` +
    `width:${r.width + 12}px;height:${r.height + 12}px;`;
}

async function wtPostPrompt(text) {
  await bfetch(BRIDGE_URL + '/api/prompt', {
    method: 'POST', body: JSON.stringify({ text }) });
}

async function wtDraw() {
  if (!wt) return;
  if (wt.timer) { clearInterval(wt.timer); wt.timer = null; }
  if (wt.onDocClick) { document.removeEventListener('click', wt.onDocClick, true); wt.onDocClick = null; }

  const steps = wt.data.steps;
  const s = steps[wt.i];
  const card = $('#wt-overlay .wt-card');
  const N = steps.length;
  const sub = x => wtSubst(x);
  const md = x => (window.marked && window.DOMPurify)
    ? DOMPurify.sanitize(marked.parse(sub(x))) : escapeHtml(sub(x)).replace(/\n/g, '<br>');

  /* spotlight (hoặc dim thường) */
  if (s.kind === 'spotlight' && s.target) wtSpot(s.target);
  else wtSpot(null);

  /* media kèm step */
  let media = '';
  const m = s.media;
  if (m && m.src) {
    const src = wt.base + m.src;
    if (m.type === 'video') media = `<video controls class="wt-media" src="${escapeHtml(src)}"></video>`;
    else if (m.type === 'file') media = `<a class="wt-chip" href="${escapeHtml(src)}" target="_blank" download>📎 ${escapeHtml(m.src)}</a>`;
    else media = `<img class="wt-media" src="${escapeHtml(src)}" alt="">`;
  }

  /* widget theo kind */
  let w = '', nav = '';
  const next = `<button class="wt-btn wt-primary" data-a="next">${escapeHtml(t('wzNext'))} →</button>`;
  const back = wt.i > 0 ? `<button class="wt-btn" data-a="back">← ${escapeHtml(t('wzBack'))}</button>` : '<span></span>';
  const skip = s.optional ? `<button class="wt-link" data-a="next">${escapeHtml(t('wtSkip'))}</button>` : '';

  switch (s.kind) {
    case 'prompt':
      w = `<input class="wt-input" id="wt-in" value="${escapeHtml(sub(s.prefill))}"` +
          ` placeholder="${escapeHtml(sub(s.placeholder))}">` +
          `<button class="wt-btn wt-primary" data-a="send">${escapeHtml(t('wtSend'))} →</button>`;
      nav = back + '<span class="wt-nav-r">' + skip + '</span>'; break;
    case 'input': case 'pick-file':
      w = `<input class="wt-input" id="wt-in" placeholder="${escapeHtml(sub(s.placeholder))}">` +
          (s.kind === 'pick-file' ? `<button class="wt-btn" data-a="pick">${escapeHtml(t('wtPick'))}…</button>` : '') +
          `<button class="wt-btn wt-primary" data-a="save">${escapeHtml(t('wzNext'))} →</button>`;
      nav = back + '<span class="wt-nav-r">' + skip + '</span>'; break;
    case 'choice':
      w = (s.options || []).map(o =>
        `<button class="wt-btn wt-opt" data-a="choice" data-v="${escapeHtml(o)}">${escapeHtml(o)}</button>`).join('');
      nav = back + '<span class="wt-nav-r">' + skip + '</span>'; break;
    case 'open-url':
      w = `<button class="wt-btn wt-primary" data-a="openurl">${escapeHtml(t('wtOpenUrl'))} ↗</button>`;
      nav = back + `<span class="wt-nav-r">${skip}<button class="wt-btn wt-primary" data-a="next">${s.then_probe ? escapeHtml(t('wtDidIt')) : escapeHtml(t('wzNext'))} →</button></span>`; break;
    case 'wait-perm': case 'wait-run':
      w = `<div class="wt-waiting">⏳ ${escapeHtml(t('wtWaiting'))}</div>`;
      nav = back + '<span class="wt-nav-r"><button class="wt-link" data-a="next">' + escapeHtml(t('wzNext')) + ' →</button></span>'; break;
    case 'auto':
      w = `<button class="wt-btn wt-primary" data-a="auto">${escapeHtml(t('wtAuto'))} →</button>`;
      nav = back + '<span></span>'; break;
    case 'open':
      w = `<code class="wt-chip">${escapeHtml(sub(s.path))}</code>` +
          `<button class="wt-btn" data-a="reveal">${escapeHtml(t('wtReveal'))}</button>`;
      nav = back + `<span class="wt-nav-r">${skip}${next}</span>`; break;
    case 'watch': case 'download':
      if (s.kind === 'download' && m && m.src)
        w = `<a class="wt-btn wt-primary" href="${escapeHtml(wt.base + m.src)}" download>${escapeHtml(t('wtDownload'))} 📎</a>`;
      nav = back + `<span class="wt-nav-r">${skip}${next}</span>`; break;
    case 'check':
      w = (s.expect ? `<div class="wt-expect">✅ ${escapeHtml(sub(s.expect))}</div>` : '') +
          `<button class="wt-btn wt-primary" data-a="next">${escapeHtml(t('wtOk'))} →</button>` +
          `<button class="wt-btn" data-a="help">${escapeHtml(t('wtNotYet'))}</button>`;
      nav = back + '<span></span>'; break;
    case 'copy':
      w = `<code class="wt-chip">${escapeHtml(sub(s.text))}</code>` +
          `<button class="wt-btn" data-a="copy">${escapeHtml(t('wtCopy'))}</button>`;
      nav = back + `<span class="wt-nav-r">${skip}${next}</span>`; break;
    case 'done':
      nav = `<span></span><button class="wt-btn wt-primary" data-a="close">${escapeHtml(t('wtDone'))} ✓</button>`; break;
    default: /* say */
      nav = back + `<span class="wt-nav-r">${skip}${next}</span>`;
  }

  card.innerHTML =
    `<div class="wt-head"><span class="wt-prog">${escapeHtml(t('wzStep'))} ${wt.i + 1}/${N}</span>` +
    `<button class="wt-x" data-a="close" title="${escapeHtml(t('wtClose'))}">✕</button></div>` +
    `<h3 class="wt-title">${escapeHtml(sub(s.title))}</h3>` +
    `<div class="wt-body md">${md(s.body)}${media}</div>` +
    (w ? `<div class="wt-widget">${w}</div>` : '') +
    `<div class="wt-nav">${nav}</div>`;

  /* hành vi nút */
  card.querySelectorAll('[data-a]').forEach(b => b.onclick = async () => {
    const a = b.dataset.a;
    if (a === 'close') return wtStop();
    if (a === 'back') return wtGo(-1);
    if (a === 'next') return wtGo(1);
    if (a === 'send') {
      const v = ($('#wt-in') || {}).value; if (!v || !v.trim()) return;
      b.disabled = true; await wtPostPrompt(v.trim()).catch(() => {});
      return wtGo(1);
    }
    if (a === 'save') {
      const v = ($('#wt-in') || {}).value || '';
      if (s.var) wt.vars[s.var] = v.trim();
      return wtGo(1);
    }
    if (a === 'pick') {
      const r = await (await bfetch(BRIDGE_URL + '/api/pick-folder',
        { method: 'POST', body: '{}' })).json().catch(() => ({}));
      if (r.path) { $('#wt-in').value = r.path; if (s.var) wt.vars[s.var] = r.path; }
      return;
    }
    if (a === 'choice') { if (s.var) wt.vars[s.var] = b.dataset.v; return wtGo(1); }
    if (a === 'openurl') { window.open(sub(s.url), '_blank'); if (s.then_probe && s.then_probe.app) wtPoll({ conn: s.then_probe.app }); return; }
    if (a === 'auto') {
      b.disabled = true; b.textContent = '⏳ ' + t('wtWaiting');
      await wtPostPrompt(sub(s.send)).catch(() => {});
      wtPoll('done'); return;
    }
    if (a === 'reveal') {
      await bfetch(BRIDGE_URL + '/api/reveal', {
        method: 'POST', body: JSON.stringify({ path: sub(s.path) }) }).catch(() => {});
      return;
    }
    if (a === 'copy') {
      try { await navigator.clipboard.writeText(sub(s.text)); b.textContent = t('wtCopied'); } catch {}
      return;
    }
    if (a === 'help') {
      await wtPostPrompt('mình đang làm theo hướng dẫn từng bước nhưng kẹt ở bước "' + sub(s.title) + '" — ' + sub(s.expect || s.body)).catch(() => {});
      b.textContent = t('wtAsked'); return;
    }
  });

  /* wait kinds tự qua */
  if (s.kind === 'wait-run') wtPoll('done');
  if (s.kind === 'wait-perm') wtPoll('event');
  if (s.kind === 'open-url' && s.then_probe && s.then_probe.app) wtPoll({ conn: s.then_probe.app });

  /* spotlight click_target: bấm thật vào chỗ sáng là qua bước */
  if (s.kind === 'spotlight' && s.target && s.click_target) {
    wt.onDocClick = e => {
      const el = e.target.closest(s.target);
      if (el) { e.preventDefault(); e.stopPropagation(); el.click(); wtGo(1); }
    };
    document.addEventListener('click', wt.onDocClick, true);
  }
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
        if (r.pending) {
          // mọi đổi não giờ qua thẻ xác nhận (202) — não chưa đổi, báo
          // đúng nghĩa chờ duyệt rồi re-sync select về não đang dùng
          msg.textContent = r.msg || t('brainPending');
          setTimeout(renderBrain, 2000);
        } else {
          msg.textContent = r.ok ? t('brainDone') : (r.err || t('brainFail'));
          if (r.ok && r.brain && r.brain.terminal) brainTerminal = r.brain.terminal;
        }
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
        const r = await bfetch(BRIDGE_URL + '/api/bot', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action: 'activate', id: it.dataset.id || null })
        });
        const d = await r.json().catch(() => ({}));
        // đổi trợ lý qua consent gate — xác nhận xong trong chat mới đổi
        if (d.pending) await uiAlert(t('gateTitle'), d.msg || t('gateMsg'));
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
    const ra = await bfetch(BRIDGE_URL + '/api/bot', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'activate', id: d.bot.id })
    });
    const da = await ra.json().catch(() => ({}));
    if (da.pending) await uiAlert(t('gateTitle'), da.msg || t('gateMsg'));
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
      if (d2.pending) {
        // cài bot qua consent gate — xác nhận trong chat mới cài thật
        $('#bot-overlay').hidden = true;
        await uiAlert(t('gateTitle'), d2.msg || t('gateMsg'));
      } else if (!r.ok) { uiAlert(t('botImportTitle'), d2.err || t('botErr')); }
      else {
        $('#bot-overlay').hidden = true;
        uiAlert(t('botImportTitle'), t('botImportDone'));
        await loadBots();
      }
    } catch { uiAlert(t('botErr'), ''); }
    btn.disabled = false; btn.textContent = t('botImportBtn');
  };
};

/* ---- workflows: quy trình "bấm là chạy" ----
   File tĩnh workspace/workflows/*.json — card → panel inputs+preflight
   → POST /api/prompt (kênh gõ tay y hệt) → poll đợi done → checklist
   người tick + verify tự động (count-glob). Không endpoint mới phía
   write — gate y nguyên. */

let workflows = [];
const loc = (o) => (o && (o[LANG] || o.vi)) || '';
const subst = (s, ins) => String(s || '').replace(/\{\{(\w+)\}\}/g,
  (m, k) => (ins[k] != null && ins[k] !== '') ? ins[k] : m);

async function loadWorkflows() {
  try {
    // :8080 file tĩnh — fetch trần, không gắn token (bridge-token.js)
    const r = await fetch('/workspace/workflows/index.json?_=' + Date.now());
    if (!r.ok) return;
    const idx = await r.json();
    const wfs = (await Promise.all((idx.workflows || []).map(async (id) => {
      try {
        const rr = await fetch('/workspace/workflows/' +
          encodeURIComponent(id) + '.json?_=' + Date.now());
        if (!rr.ok) return null;
        const w = await rr.json();
        return (w && w.id && w.prompt) ? w : null;
      } catch { return null; }
    }))).filter(Boolean);
    workflows = wfs;
    renderWorkflows();
  } catch { /* không có workflows/ → section ẩn, máy cá nhân không nhiễu */ }
}

function renderWorkflows() {
  const sec = $('#workflows'), box = $('#workflow-list');
  if (!workflows.length) { sec.hidden = true; return; }
  sec.hidden = false;
  box.innerHTML = '';
  const depts = {};
  workflows.forEach(w => { (depts[w.dept || ''] ||= []).push(w); });
  const multi = Object.keys(depts).length > 1;
  Object.keys(depts).sort().forEach(dep => {
    if (multi && dep) {
      const h = document.createElement('div');
      h.className = 'wf-dept';
      h.textContent = dep;
      box.appendChild(h);
    }
    depts[dep].forEach(w => {
      const card = document.createElement('button');
      card.className = 'wf-card';
      card.innerHTML =
        `<span class="wf-icon">${escapeHtml(w.icon || '⚙️')}</span>` +
        `<span class="wf-body"><b>${escapeHtml(loc(w.title) || w.id)}</b>` +
        `<small>${escapeHtml(loc(w.desc))}</small></span>` +
        `<span class="wf-go">${escapeHtml(t('wfRun'))}</span>`;
      card.onclick = () => openWorkflow(w);
      box.appendChild(card);
    });
  });
}

let wfCurrent = null;

function openWorkflow(wf) {
  wfCurrent = wf;
  $('#wf-title').textContent = loc(wf.title) || wf.id;
  $('#wf-desc').textContent = loc(wf.desc);
  const ib = $('#wf-inputs');
  ib.innerHTML = '';
  (wf.inputs || []).forEach(inp => {
    const row = document.createElement('div');
    row.className = 'wf-input-row';
    row.innerHTML =
      `<label>${escapeHtml(loc(inp.label) || inp.key)}</label>` +
      `<input data-k="${escapeHtml(inp.key)}" ` +
      `placeholder="${escapeHtml(inp.placeholder || '')}">`;
    ib.appendChild(row);
  });
  $('#wf-preflight').innerHTML = '';
  $('#wf-overlay').hidden = false;
  const first = ib.querySelector('input');
  if (first) first.focus();
  runWfPreflight(wf);
}

// requires.connections → chấm trạng thái app; requires.permissions →
// folder cần có trong permissions.json. Cảnh báo, KHÔNG chặn cứng —
// não vẫn xin quyền/dẫn nối khi chạy.
async function runWfPreflight(wf) {
  const pf = $('#wf-preflight');
  const req = wf.requires || {};
  const warns = [];
  if ((req.connections || []).length) {
    try {
      const c = await (await bfetch(BRIDGE_URL + '/api/connections')).json();
      const apps = c.apps || [];
      const missing = req.connections.filter(id => {
        const a = apps.find(x => x.id === id);
        return !a || a.status !== 'connected';
      });
      if (missing.length) {
        const names = missing.map(id => {
          const a = apps.find(x => x.id === id);
          return (a && (loc(a.name) || a.name)) || id;
        });
        warns.push(t('wfNeedConn').replace('{apps}', names.join(', ')));
      }
    } catch { /* bridge chết → bỏ preflight, prompt vẫn gửi được */ }
  }
  if ((req.permissions || []).length) {
    try {
      const p = await (await bfetch(BRIDGE_URL + '/api/permissions')).json();
      // so theo đuôi path: workflow khai "~/Downloads", permissions
      // lưu tuyệt đối "/Users/x/Downloads" → đuôi khớp là đủ
      const granted = (p.folders || []).map(f =>
        String(f.path || f).replace(/\\/g, '/').toLowerCase());
      const missing = req.permissions.filter(path => {
        const rel = String(path).replace(/\\/g, '/')
          .replace(/^~?\/?/, '').toLowerCase().replace(/\/$/, '');
        return !granted.some(g =>
          g.replace(/\/$/, '').endsWith('/' + rel) ||
          g.replace(/\/$/, '') === rel);
      });
      if (missing.length) {
        warns.push(t('wfNeedPerm').replace('{paths}', missing.join(', ')));
      }
    } catch {}
  }
  if (warns.length) {
    pf.innerHTML = warns.map(w =>
      `<div class="wf-warn">${escapeHtml(w)}</div>`).join('');
  }
}

async function runWorkflow() {
  const wf = wfCurrent;
  if (!wf) return;
  const inputs = {};
  document.querySelectorAll('#wf-inputs input')
    .forEach(i => { inputs[i.dataset.k] = i.value.trim(); });
  const text = subst(wf.prompt, inputs);
  if (!text.trim()) return;
  $('#wf-run').disabled = true;
  try {
    const r = await bfetch(BRIDGE_URL + '/api/prompt', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({text})});
    if (!r.ok) {
      const d = await r.json().catch(() => ({}));
      $('#wf-overlay').hidden = true;
      await uiAlert(t('wfTitle'), d.err || t('wfBusy'));
      return;
    }
  } catch {
    $('#wf-overlay').hidden = true;
    await uiAlert(t('wfTitle'), t('wfSentErr'));
    return;
  } finally {
    $('#wf-run').disabled = false;
  }
  $('#wf-overlay').hidden = true;
  $('#wf-checklist').hidden = true;
  switchTab('chat');
  startWfWatch(wf, inputs);
}

// theo dõi lượt chạy: mốc poll hiện tại → đợi event 'done'/'err'
let wfWatch = null;
async function startWfWatch(wf, inputs) {
  stopWfWatch();
  try {
    const d = await (await bfetch(BRIDGE_URL + '/api/poll?since=0')).json();
    wfWatch = { wf, inputs, after: d.next || 0, tries: 0,
                timer: setInterval(pollWf, 2000) };
  } catch { /* bridge mất — không có checklist nhưng prompt đã đi */ }
}
function stopWfWatch() {
  if (wfWatch && wfWatch.timer) clearInterval(wfWatch.timer);
  wfWatch = null;
}
async function pollWf() {
  if (!wfWatch) return;
  try {
    const d = await (await bfetch(
      BRIDGE_URL + '/api/poll?since=' + wfWatch.after)).json();
    wfWatch.after = (d.next != null) ? d.next : wfWatch.after;
    let done = false;
    for (const ev of (d.events || [])) {
      if (ev.t === 'done') { done = true; break; }
      if (ev.t === 'err') { stopWfWatch(); return; }
    }
    if (done) { finishWf(); return; }
    if (++wfWatch.tries > 300) stopWfWatch();   // ~10 phút → ngừng đợi
  } catch { /* poll lỗi → vòng sau thử tiếp */ }
}

async function finishWf() {
  const run = wfWatch;
  stopWfWatch();
  if (!run) return;
  const ver = await runWfVerify(run.wf, run.inputs).catch(() => null);
  showWfChecklist(run.wf, ver, run.inputs);
}

// verify tự động: {dir, glob, min_count} → GET /api/count-glob.
// dir có thể chứa {{input}}; nếu trỏ vào FILE thì lấy folder cha.
async function runWfVerify(wf, inputs) {
  const v = wf.verify;
  if (!v || !v.dir) return null;
  let dir = subst(v.dir, inputs);
  if (/\.[A-Za-z0-9]{1,8}$/.test(dir)) dir = dir.replace(/\/[^/]*$/, '');
  const u = BRIDGE_URL + '/api/count-glob?path=' + encodeURIComponent(dir) +
    '&pattern=' + encodeURIComponent(v.glob || '*');
  const d = await (await bfetch(u)).json();
  const need = v.min_count || 1;
  return { ok: d.ok && (d.count || 0) >= need, count: d.count || 0, need };
}

let wfCheckWf = null, wfCheckInputs = {};

function showWfChecklist(wf, ver, inputs) {
  wfCheckWf = wf;
  wfCheckInputs = inputs || {};
  $('#wf-check-title').textContent =
    (loc(wf.title) || wf.id) + ' — ' + t('wfCheckTitle');
  const chip = $('#wf-verify-chip');
  if (ver) {
    chip.hidden = false;
    chip.className = ver.ok ? 'ok' : 'fail';
    chip.textContent = ver.ok ? t('wfVerifyOk') : t('wfVerifyFail');
  } else chip.hidden = true;
  $('#wf-check-items').innerHTML = (wf.checklist || []).map((c, i) =>
    `<label class="wf-check-item"><input type="checkbox" data-i="${i}">` +
    `<span>${escapeHtml(c)}</span></label>`).join('');
  $('#wf-checklist').hidden = false;
  // verify đỏ → tự nhờ não kiểm tra lại (vòng sửa) + theo dõi lượt mới
  if (ver && !ver.ok) {
    sendWfFix(wf, [t('wfVerifyFailMsg')], wfCheckInputs, true);
  }
}

async function sendWfFix(wf, issues, inputs, rewatch) {
  const msg = issues.length
    ? t('wfIssueFix').replace('{title}', loc(wf.title) || wf.id)
        .replace('{issues}', issues.join('; '))
    : t('wfIssueFixAll').replace('{title}', loc(wf.title) || wf.id);
  try {
    const r = await bfetch(BRIDGE_URL + '/api/prompt', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({text: msg})});
    if (r.ok && rewatch) startWfWatch(wf, inputs || {});
  } catch { /* bridge mất */ }
}

$('#wf-run').onclick = runWorkflow;
$('#wf-close').onclick = () => { $('#wf-overlay').hidden = true; };
$('#wf-cancel').onclick = () => { $('#wf-overlay').hidden = true; };
$('#wf-overlay').onclick = (e) => {
  if (e.target === $('#wf-overlay')) $('#wf-overlay').hidden = true;
};
$('#wf-allok').onclick = () => { $('#wf-checklist').hidden = true; };
$('#wf-issue').onclick = async () => {
  const wf = wfCheckWf;
  if (!wf) { $('#wf-checklist').hidden = true; return; }
  const bad = [...document.querySelectorAll('#wf-check-items input')]
    .filter(c => !c.checked)
    .map(c => c.nextElementSibling.textContent);
  $('#wf-checklist').hidden = true;
  await sendWfFix(wf, bad, wfCheckInputs, true);
};

/* ---- /workflows ---- */

// thẻ consent gate chạy xong trong iframe chat (đổi trợ lý, xoá bài,
// sửa quyền…) → làm mới chip trợ lý + manifest cho khớp state trên đĩa
window.addEventListener('message', (e) => {
  if (e.origin === location.origin && e.data && e.data.t === 'gateDone') {
    loadBots();
    loadManifest();
  }
});

loadBots();
loadWorkflows();
