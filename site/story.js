// story engine — spec: sketches/storyboard.md, plan: plans/261126-1236-story-anim
// one renderer, five role configs; scenes advance on a beat timer, play once.
// pains are mini app windows ({ui}) — the interface itself is the pain.

const STORY = {
  marketing: {
    who: "Minh · marketing",
    cal: ["Thứ 2", "Thứ 3", "Thứ 4"],
    pains: [
      { ui: "zalo", n: "9" },
      { ui: "messenger", n: "3" },
      { ui: "sheet", n: "!" },
    ],
    stake: "khách A chờ báo giá từ 8h",
    cap1: "Sáng nào cũng thế này.",
    tasks: [
      ["đọc hộ tin Zalo", "zalo", "6 hội thoại · 3 người đang chờ bạn"],
      ["cập nhật sheet theo file này", "sheet", "báo giá đã đối chiếu xong"],
      ["nén mấy ảnh kia", "img", "300 ảnh · gốc nguyên"],
    ],
    teachWord: "việc sáng",
    memoryLine: "Mình cập nhật theo mẫu báo giá của công ty bạn như lần trước nhé.",
    recipe: "/viec-sang",
    ready: [["zalo", "Zalo đã tóm tắt"], ["sheet", "Báo giá cập nhật"], ["img", "Ảnh đã nén, gốc nguyên"]],
    payoff: "Không cần nhờ — nó tự chạy, mỗi sáng.",
    saved: "~45 phút",
    savedCap: "mỗi sáng",
  },
  sales: {
    who: "Lan · sales",
    cal: ["Tuần 44", "Tuần 45", "Tuần 46"],
    pains: [
      { ui: "excel", n: "3000" },
      { ui: "whatsapp", n: "3" },
      { ui: "doc", n: "1" },
    ],
    stake: "3 khách chờ báo giá từ sáng",
    cap1: "Thứ hai nào cũng thế này.",
    tasks: [
      ["tách theo tỉnh, mỗi tỉnh một file", "excel", "47 file · gốc nguyên"],
      ["soạn báo giá cho khách A theo mẫu", "doc", "nháp báo giá sẵn duyệt"],
      ["lọc ai chưa follow trong sheet này", "excel", "list khách cần gọi lại"],
    ],
    teachWord: "list tuần",
    memoryLine: "Mình chia theo tỉnh, báo giá theo mẫu công ty bạn như mọi tuần.",
    recipe: "/list-tuan",
    ready: [["excel", "47 file theo tỉnh"], ["doc", "Báo giá nháp sẵn"], ["files", "List follow-up chờ"]],
    payoff: "Thứ hai không còn là cơn ác mộng.",
    saved: "~3 giờ",
    savedCap: "mỗi tuần",
  },
  office: {
    who: "Hoa · văn phòng",
    cal: ["Thứ 2", "Thứ 3", "Thứ 4"],
    pains: [
      { ui: "gmail", n: "14" },
      { ui: "doc", n: "1" },
      { ui: "zoho", n: "6" },
    ],
    stake: "sếp cần báo cáo trước 5h",
    cap1: "Chiều nào cũng thế này.",
    tasks: [
      ["điền file Excel này vào mẫu báo cáo", "doc", "bảng Word đã đầy"],
      ["gom hoá đơn theo tháng", "files", "Tháng-10, Tháng-11 xếp hàng"],
      ["tóm tắt mail chưa đọc", "gmail", "14 mail · 3 cần trả lời hôm nay"],
    ],
    teachWord: "việc chiều",
    memoryLine: "Mình điền đúng mẫu của công ty bạn như mọi tuần nhé.",
    recipe: "/viec-chieu",
    ready: [["doc", "Báo cáo đã điền"], ["files", "Hoá đơn theo tháng"], ["gmail", "Mail đã tóm tắt"]],
    payoff: "Bạn chỉ còn một việc: duyệt.",
    saved: "~1.5 giờ",
    savedCap: "mỗi chiều",
  },
  content: {
    who: "Trang · content",
    cal: ["Bài 12", "Bài 13", "Bài 14"],
    pains: [
      { ui: "wp", n: "5" },
      { ui: "img", n: "20" },
      { ui: "web", n: "!" },
    ],
    stake: "bài hôm qua vẫn thiếu meta",
    cap1: "Bài nào cũng thế này.",
    tasks: [
      ["đăng 5 bài này, nhớ điền meta", "wp", "nháp lên · meta đầy · chờ duyệt"],
      ["sửa alt cho cả loạt ảnh cũ", "img", "mỗi ảnh đã có mô tả"],
      ["kiểm lại meta mấy bài cũ", "web", "list lỗi trượt ra"],
    ],
    teachWord: "bài mới",
    memoryLine: "Mình điền meta theo cách site bạn vẫn làm nhé.",
    recipe: "/bai-moi",
    ready: [["wp", "5 nháp đã đăng"], ["img", "Alt ảnh đầy đủ"], ["web", "Meta cũ đã soi"]],
    payoff: "Meta + alt tự xong — bạn chỉ viết bài.",
    saved: "~30 phút/bài",
    savedCap: "mỗi bài mới",
  },
  design: {
    who: "Tuấn · design",
    cal: ["Thứ 2", "Thứ 3", "Thứ 4"],
    pains: [
      { ui: "img", n: "500" },
      { ui: "web", n: "!" },
      { ui: "outlook", n: "4" },
    ],
    stake: "sếp hỏi ảnh lúc 3h",
    cap1: "Cuối ngày nào cũng thế này.",
    tasks: [
      ["nén và đổi tên theo tour", "img", "folder sạch, tên thành hàng"],
      ["ảnh nào còn quá lớn cho web", "web", "list đỏ · đã nén nốt"],
      ["gom hết vào folder theo ngày", "files", "Downloads sạch"],
    ],
    teachWord: "ảnh mới",
    memoryLine: "Mình nén webp 80%, tên theo tour, gốc không đụng như mọi lần.",
    recipe: "/anh-moi",
    ready: [["img", "Ảnh nén + đúng tên"], ["web", "Quá lớn đã xử"], ["files", "Folder theo ngày"]],
    payoff: "Mỗi chiều.",
    saved: "~35 phút",
    savedCap: "mỗi chiều",
  },
};

const ROLE_LABELS = {
  marketing: "Marketing", sales: "Sales", office: "Văn phòng",
  content: "Content/SEO", design: "Design",
};

const APP_NAME = {
  zalo: "Zalo", messenger: "Messenger", whatsapp: "WhatsApp",
  sheet: "Sheet", excel: "Excel", doc: "Word", wp: "WordPress",
  gmail: "Gmail", zoho: "Zoho Mail", outlook: "Outlook",
  img: "Canva", files: "Files", web: "Web",
};

// beat budget per scene — total ~24s
const HOLD = { pile: 5000, tasks: 7800, memory: 5600, auto: 5600 };

const esc = s => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/"/g, "&quot;");

// mini app windows — recognizable interfaces, not text labels
const MZ = `<div class="mz"><i><b></b><span><s></s><s></s></span><u>9</u></i><i><b></b><span><s></s><s></s></span><u>3</u></i><i><b></b><span><s></s><s></s></span><u>1</u></i></div>`;
const MS = `<div class="ms">${"<i></i>".repeat(12)}</div>`;
const MM = `<div class="mm"><i><b></b><span><s></s><s></s></span></i><i><b></b><span><s></s><s></s></span></i><i><b></b><span><s></s><s></s></span></i></div>`;

const MINI_BODY = {
  zalo: MZ, messenger: MZ, whatsapp: MZ,
  sheet: MS, excel: MS,
  gmail: MM, zoho: MM, outlook: MM,
  doc: `<div class="md"><i style="width:72%"></i><i style="width:92%"></i><i style="width:58%"></i><em></em><i style="width:80%"></i><i style="width:64%"></i></div>`,
  wp: `<div class="mw"><b></b><div class="mwl"><i><u></u></i><i><u></u></i><i><u></u></i></div></div>`,
  mail: `<div class="mm"><i><b></b><span><s></s><s></s></span></i><i><b></b><span><s></s><s></s></span></i><i><b></b><span><s></s><s></s></span></i></div>`,
  img: `<div class="mi">${"<i></i>".repeat(6)}</div>`,
  files: `<div class="mf"><i><b></b><s></s></i><i><b></b><s></s></i><i><b></b><s></s></i></div>`,
  web: `<div class="mx"><b></b><em>200KB<wbr>max</em></div>`,
};

const mini = t =>
  `<div class="mini mini--${t}"><div class="mini__bar">${APP_NAME[t]}</div><div class="mini__body">${MINI_BODY[t]}</div></div>`;

const tag = t => `<span class="tag tag--${t}">${APP_NAME[t]}</span>`;

function scenePile(c) {
  return `<div class="scene scene--pile" role="group" aria-label="Việc dồn, lặp mãi">
    <div class="cal beat" style="--i:0" aria-hidden="true">
      ${c.cal.map((d, i) => `<span class="cal__pg" style="--i:${i}">${esc(d)}</span>`).join("")}
    </div>
    <div class="pile">
      <div class="bell-slot" id="bell-slot" aria-hidden="true"></div>
      ${c.pains.map((p, i) => `<div class="pain beat" style="--i:${i + 1}">${mini(p.ui)}<span class="pain__n">${esc(p.n)}</span></div>`).join("")}
    </div>
    <div class="stake beat" style="--i:${c.pains.length + 1}">${esc(c.stake)}</div>
    <p class="scene__cap beat" style="--i:${c.pains.length + 2}">${esc(c.cap1)}</p>
  </div>`;
}

function sceneTasks(c) {
  return `<div class="scene scene--tasks" role="group" aria-label="Trợ lý làm hộ">
    <div class="tasks">
      <span class="bot" aria-hidden="true"></span>
      ${c.tasks.map(([ask, app, res], i) => `<div class="task beat" style="--i:${i}">
        <span class="task__ask">“${esc(ask)}”</span>
        <span class="task__res">${tag(app)}${esc(res)}</span>
      </div>`).join("")}
      <p class="teach beat" style="--i:${c.tasks.length}">lần sau bạn chỉ cần gõ <strong>“${esc(c.teachWord)}”</strong> là được</p>
    </div>
  </div>`;
}

function sceneMemory(c) {
  const w = Math.max(6, [...c.teachWord].length);
  return `<div class="scene scene--memory" role="group" aria-label="Nó nhớ việc của bạn">
    <div class="askline">
      <span class="askline__type" style="--typew:${w}ch">${esc(c.teachWord)}</span>
      <span class="askline__done" aria-hidden="true">✓ xong</span>
    </div>
    <p class="memory beat" style="--i:4">“${esc(c.memoryLine)}”</p>
    <div class="book beat" style="--i:6">
      <span class="book__label">sổ công thức của bạn</span>
      <code class="recipe">${esc(c.recipe)}</code>
    </div>
  </div>`;
}

function sceneAuto(c) {
  return `<div class="scene scene--auto" role="group" aria-label="Tự chạy mỗi ngày">
    <div class="cal beat" style="--i:0" aria-hidden="true">
      ${c.cal.map((d, i) => `<span class="cal__pg" style="--i:${i}">${esc(d)}</span>`).join("")}
    </div>
    <div class="morning">
      <svg class="person beat" style="--i:1" viewBox="0 0 88 80" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
        <circle cx="30" cy="22" r="10"/>
        <path d="M14 66c0-14 8-22 16-22s16 8 16 22"/>
        <path d="M6 66h76"/>
        <rect x="56" y="50" width="20" height="14" rx="3"/>
        <path d="M76 54h4a3 3 0 0 1 0 6h-4"/>
        <path d="M62 44c0-3 2-3 2-6M68 44c0-3 2-3 2-6" stroke-linecap="round"/>
      </svg>
      <div class="morning__list">
        ${c.ready.map(([app, r], i) => `<div class="ready beat" style="--i:${i + 2}">${tag(app)}${esc(r)}</div>`).join("")}
      </div>
    </div>
    <p class="saved beat" style="--i:${c.ready.length + 2}">Tiết kiệm <strong>${esc(c.saved)}</strong> ${esc(c.savedCap)}</p>
    <p class="scene__cap scene__cap--payoff beat" style="--i:${c.ready.length + 3}">${esc(c.payoff)}</p>
  </div>`;
}

function sceneEnd() {
  return `<div class="scene scene--end" role="group" aria-label="Kết">
    <div class="end">
      <p class="end__line">Càng dùng — càng của riêng bạn.</p>
      <p class="end__sub">Trợ lý AI trong máy bạn · tiếng Việt · làm việc thật</p>
      <div class="end__actions">
        <button type="button" class="replay" id="story-replay">Xem lại</button>
        <a class="btn btn--primary" href="#tai">Tải về</a>
      </div>
    </div>
  </div>`;
}

const storyEl = document.getElementById("story");
if (storyEl) {
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const stage = storyEl.querySelector(".story__stage");
  const rolesEl = storyEl.querySelector(".story__roles");
  const stepsEl = storyEl.querySelectorAll(".story__steps span");
  let timers = [], bellAnim = null, currentRole = "marketing", played = false;

  function renderRole(role) {
    const c = STORY[role];
    stage.innerHTML = scenePile(c) + sceneTasks(c) + sceneMemory(c) + sceneAuto(c) + sceneEnd();
    rolesEl.querySelectorAll(".story__role").forEach(b =>
      b.setAttribute("aria-selected", String(b.dataset.role === role)));
  }

  function stopTimers() { timers.forEach(clearTimeout); timers = []; }
  function stopBell() { bellAnim?.destroy(); bellAnim = null; }

  function setStep(idx) {
    stepsEl.forEach((s, i) => {
      s.classList.toggle("is-active", i === idx);
      s.classList.toggle("is-done", i < idx);
    });
  }

  const order = ["scene--pile", "scene--tasks", "scene--memory", "scene--auto", "scene--end"];

  function play() {
    stopTimers(); stopBell();
    played = true;
    const scenes = [...stage.querySelectorAll(".scene")];
    scenes.forEach(s => s.classList.remove("is-on"));
    let t = 400;
    order.forEach((cls, idx) => {
      timers.push(setTimeout(() => {
        scenes.forEach(s => s.classList.toggle("is-on", s.classList.contains(cls)));
        setStep(Math.min(idx, 3));
        if (cls === "scene--pile") startBell();
        else stopBell();
      }, t));
      t += HOLD[cls.replace("scene--", "")] || 2500;
    });
    const replay = stage.querySelector("#story-replay");
    if (replay) replay.addEventListener("click", play);
  }

  function startBell() {
    if (typeof lottie === "undefined" || bellAnim) return;
    const slot = stage.querySelector("#bell-slot");
    if (!slot) return;
    bellAnim = lottie.loadAnimation({
      container: slot, renderer: "svg", loop: true, autoplay: true,
      path: "assets/story/bell.json?v=2",
    });
  }

  rolesEl.innerHTML = `<span class="story__roles-label">Bạn làm nghề gì?</span>` +
    Object.keys(ROLE_LABELS).map(r =>
      `<button type="button" class="story__role" data-role="${r}" aria-selected="false">${ROLE_LABELS[r]}</button>`
    ).join("");
  rolesEl.addEventListener("click", e => {
    const b = e.target.closest(".story__role");
    if (!b || b.dataset.role === currentRole) return;
    currentRole = b.dataset.role;
    renderRole(currentRole);
    play();
  });

  renderRole(currentRole);

  if (reduced) {
    stage.querySelector(".scene--end").classList.add("is-on");
  } else {
    // play once when the stage scrolls into view
    const io = new IntersectionObserver((es, o) => es.forEach(e => {
      if (e.isIntersecting && !played) { play(); o.disconnect(); }
    }), { threshold: 0.35 });
    io.observe(stage);
  }
}
