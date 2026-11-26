# ai-assistant — Decision Log

Các quyết định kiến trúc và **tại sao** — để sau này không gỡ ngược lại
vì quên lý do. Mới nhất lên đầu.

## 2026 — Audit đợt 5: parity worker↔collector, marker Cf, consent mid-dialog

**Worker port nguyên repair flow của collector (`pending_key`).** Vì:
worker trả `machine_key` cho bất kỳ ai biết `beacon_secret` — bí mật
shared toàn org — nên một nhân viên lấy được key của mọi máy trong org.
Port nguyên semantics audit-4: re-pair máy approved chỉ `repair=1` +
`pending`, admin duyệt → `pending_key`, máy nhận qua pair kế.
`schema.sql` thêm 2 cột; DB cũ được `ensureV2` ALTER lazy một lần/
isolate (không có migrations dir — schema.sql vẫn là nguồn chân thật,
lệnh ALTER tay ghi chú cuối file).

**`_fold` strip toàn bộ category Cf (ZWSP/ZWNJ/ZWJ/BOM/WJ/soft
hyphen).** Vì: `\s*` trong `_MARKER_RE` không khớp ký tự format →
`<<<​EXTERNAL_UNTRUSTED_END​>>>` chèn ZWSP sống sót qua sanitize,
não nhìn thấy marker END giả y hệt thật = wrapper escape. Chi phí đã
cân: emoji chuỗi ZWJ rớt joiner — chấp nhận được.

**`exec_allowed` check DENY trên raw trước normalize; DENY thêm `&`,
`\n`, `\r`, `${`, `(`.** Vì: `\n` bị `split()` nuốt thành space trước
khi check, `&` đơn (background) chưa nằm trong DENY → pattern
`sleep *` từng auto-duyệt cả `sleep 1 & whoami` lẫn
`sleep 1\nrm -rf x`. Lệnh phức hợp phải rơi về card xác nhận, không
được auto-duyệt.

**CSP sandbox phủ mọi document-type scriptable, không chỉ `.html`.**
Vì: `.svg` (image/svg+xml có `<script>`), `.xml` (XSLT), `.xhtml`…
dưới `/my-course/` mở trực tiếp chạy script trong origin :8080 → đọc
`localStorage.bridge_token` → gọi mọi API bridge. `CSP_SUFFIXES`
liệt kê hết loại render-thành-document; media thuần không áp (ảnh
trong `<img>` vốn không chạy script, áp sandbox chỉ làm Chrome ép
download thay vì hiển thị).

**Consent: dialog chết giữa chừng = deny, không fallback Origin.** Vì:
`gui_failed` (spawn được rồi chết: returncode≠0, stdout rỗng) trước đây
hạ card về đường Origin — não tự forge duyệt được. Giờ chỉ `Popen`
fail (headless thật, `p is None`) mới fallback; chết giữa chừng xử như
từ chối (`-32800` cho card ACP / đóng card cho card local). Lưu ý:
`(allow process*)` của Seatbelt KHÔNG cho phép `signal` — não trong
sandbox không kill được `osascript` (kiểm chứng trên Darwin 27); vector
còn lại chỉ là resource-exhaustion làm `Popen` fail, nên phân biệt hai
đường này là chặn hợp lý chứ không phải chặn khẩn cấp.

**Bỏ `SSH_AUTH_SOCK`/`DBUS_*`/`DISPLAY`/`XAUTHORITY`/`WAYLAND_DISPLAY`
khỏi env não — cả Terminal mode.** Vì: brain CLI headless không cần
session/desktop bus; `SSH_AUTH_SOCK` cho đọc-ký SSH key, DBus nói
chuyện keyring, X11 điều khiển input + đọc màn hình. `term-gate` (cả
`.sh` lẫn `.ps1`) trước exec não thừa hưởng toàn bộ env launcher —
giờ unset phần ngoài allowlist y `scrub_env` (+ extras của
`.devin/env-allowlist.json`, parity `load_env_extra`).

**`update.py`: `_man_ok` lọc manifest theo format TRƯỚC khi fetch zip;
`fetch` có `cap`.** Vì: collector hostile ép máy tải zip rác (DoS
disk/RAM — `r.read()` không đáy). Manifest sai format bỏ nguồn ngay;
`fetch` đọc `cap+1` để phát hiện vượt trần (server nói dối
Content-Length cũng không lọt — phần thừa nằm trong socket bị bỏ khi
đóng).

**`serve.py` blocklist `collector.json` + `*.local.json` theo
basename.** Vì: `collector.json` ở ROOT máy vendor chứa org secrets —
không nằm trong dot-folder nên lọt qua chặn dotfile; `*.local.json`
(`secrets.local.json`, `mcp_config.local.json`) cũng là secret.

**`/api/setup` gate khi có `fleet.json`.** Vì: máy cty provision sẵn
có `.devin/fleet.json` — skill/config do pack quản; agent gọi setup
đè onboarding trước đây chạy không card nếu `config.json` chưa có
`language`.

**Ghi nhận có chủ đích (không sửa): `devin_files` cho phép pack ghi
`mcp_config.local.json`.** Pack CỐ Ý không ký (đợt 3) → org admin có
thể khai MCP server mà brain CLI tự spawn ở lượt kế = kênh exec của
admin trên máy học viên. Chấp nhận vì org admin vốn đã có quyền đẩy
pack + license; trên macOS MCP process nằm trong Seatbelt profile của
não (mitigate), trên máy chưa sandbox là đặc quyền đã-biết của pack —
ghi ở đây để ai review pack sau này biết `devin_files` là rào duy nhất.

**Worker housekeeping: `loadOrgs` cache 30s/isolate + bust khi write;
`/api/fleet` gom usage một query; `pruneDaily` ở cron.** Vì: SELECT
orgs mỗi request và N+1 usage là hai hot-path vô ích; bảng
audit/usage/sessions/org_pings/pending-spam phình vô hạn nếu không
prune. Cache bust ở org-create/rotate-secret nên secret mới có hiệu
lực ngay, không chờ TTL. **Nhưng bust chỉ dọn isolate hiện tại** —
rotate xong, secret cũ vẫn sống ≤30s trên isolate khác → mọi đường SO
SECRET (`/api/pair` suy org từ `beacon_secret`, `authAdmin` nhánh
`X-Admin-Key`) gọi `loadOrgs(env, fresh=true)` đọc thẳng D1: secret
đã rotate chết ngay, secret mới dùng được ngay. Cache chỉ còn phục vụ
consumer không-nhạy (`licenseStatus`, list org dashboard). `ensureV2`
cũng phải kiểm TỪNG cột một — gate chung `repair` mà ALTER
`pending_key` lỗi/migrate tay thiếu thì cột thiếu không bao giờ được
thêm.

**Consent warn dùng type event `"warn"` riêng, không phải `"err"`.**
Vì: `broadcast()` coi `ready|done|err` là tín hiệu kết-lượt → kill
toàn bộ `perm_pending` + nhả `prompt_lock`; dialog chết giữa lượt mà
phát `err` sẽ đồng thời giết card khác đang chờ và nhả lock cho
prompt kế chen giữa. `warn` render như lỗi trong chat nhưng giữ
`setBusy` — và chỉ phát khi card CÒN pending (cancel/evict từ chat
cũng `terminate()` proc → `gui_failed` giả nếu không check).

## 2026 — Audit đợt 4: tách 3 tầng key, repair flow, `*` rollup-only

**`telemetry.key` là outbound-only, không phải key admin.** Vì: nó nằm
trong `collector.json` mọi khách — giả định "sẽ lộ" thay vì "giữ kín".
Trước đây cùng key đó mở `_admin_org` = `"*"` (god-mode xuyên org) —
kẻ đọc config khách chiếm luôn dashboard vendor. Giờ inbound chỉ
`POST /api/org-ping` (ghi rollup — worst case là spam dòng ping, đã
prune 90 ngày). Key đọc vendor tách thành `vendor_read_key` — chỉ đặt
trên collector của vendor, KHÔNG ship trong config khách.

**`"*"` = rollup-only, KHÔNG machine-level.** Vì: `/api/fleet`,
`/api/pending`, `/api/fleet/<mid>` trả hostname/learner/snapshot —
PII cấp máy, khác hẳn "org-level" mà docstring vendor key từng hứa.
Whitelist exact-match (`/api/org-pings`, `/api/license`, `/api/packs`)
thay vì để `org == "*"` rơi qua mọi branch — các nhánh `org == "*"`
trong query fleet/pending giờ là dead code cố ý (giữ cho chặt: thêm
endpoint mới mà quên gate thì mặc định 403, không fail-open).

**Mọi approve ghi `pending_key`; `machine_key` chỉ set lúc pair phát.**
Vì: bản vá đầu ghi `machine_key` trực tiếp cho máy mới, chỉ repair mới
dùng `pending_key` — hệ quả là máy approved pair lần kế rơi nhánh
"re-pair" và không bao giờ nhận được key đầu tiên (phải duyệt 2 lần).
Một đường duy nhất — `pending_key` là "key đang chờ phát" — xoá luôn
sự phân biệt cấp-mới/cấp-lại: hai flow một code path, rotate key tự có
(key cũ chết đúng lúc key mới được nhận — không downtime). Đổi lại:
trong khoảng chờ máy pair, key cũ vẫn sống — revoke ngay nếu nghi
bị lộ, đừng chờ repair.

**`release_key` riêng khỏi admin_key org.** Vì: release là artifact
vendor đã ký — admin org A không có lý do đẩy release xuống máy org B
(mà cũng không nên đẩy xuống org A — nội dung phải đi qua ký của
vendor trước). Không set `release_key` = upload tắt hẳn, release chỉ
lên qua `mirror_loop` hoặc copy tay — đúng cho collector khách, vốn
không bao giờ tự phát release.

**Bài học lặp lại từ audit-3 + audit-4: vá đường tấn công rất dễ phá
happy path.** Cả hai đợt audit-lại đều bắt regression do chính vá gây
ra (first-approve chết; revoke kẹt cờ; `SELECT org` thiếu cột;
`onerror`+`onclose` cùng handler đếm x2; regex `[A-Za-z0-9._-]+` vô
tình xoá check `.`/`..` gốc). Quy ước: test phải đi qua ĐÚNG vòng đời
(pair → approve → pair → key → beacon), không được encode hành vi
vá vào expected mà không đọc lại luồng người dùng.

## 2026 — Audit đợt 3: path_guard dùng chung, 2 vòng audit-lại tự bắt regression

**Policy đường dẫn sống trong `tools/path_guard.py`, không nhân bản.**
Vì: cả hai lỗ HIGH của audit-3 cùng một mô-típ — điểm validate
(chat-bridge, request/apply-time) và điểm enforce (gen-sandbox, mỗi
spawn) nằm ở hai file khác nhau và phía enforce tin mù. Nhân bản
`_SENSITIVE_DIRS`/`rw_grant_ok` = chắc chắn drift, mà drift ở đây là
sandbox escape. Tên underscore bắt buộc vì `gen-sandbox.py` gạch ngang
không import được. Bẫy đã học: `runpy.run_path` KHÔNG add script-dir
vào `sys.path` → mọi script frozen import sibling PHẢI tự
`sys.path.insert(dirname(__file__))` — thiếu thì exception bị
supervisor nuốt = spawn não KHÔNG Seatbelt (fail-open âm thầm).

**Hai vòng audit-lại sau khi vá, tự bắt 3 regression — đáng ghi vì
cả ba đều là kiểu lỗi "trông vô hại":**
- `getattr(self, ROUTES.get(path), None)`: `.get()` trả `None` mà
  getattr yêu cầu name là string → TypeError giết handler thread thay
  vì 404. Default của getattr không cứu được name=None — phải check
  trước VÀ vẫn giữ default (route trỏ method hỏng → 404 không crash).
- `_SENSITIVE_DIRS` entry Windows `~\AppData\…`: trên POSIX expanduser
  trả literal tương đối → realpath resolve dưới cwd lúc import →
  two-way check biến ancestor của cwd thành sensitive → grant
  `~/Desktop` bị từ chối oan. Lý luận "literal không match gì nên vô
  hại" SAI vì realpath làm nó tuyệt đối. Fix: lọc `isabs` sau
  expanduser — mỗi nền chỉ giữ entry resolve được.
- Cap `recipes` đoán field `label` trong khi schema thật là
  `{command, meaning}` → mất dữ liệu lặng lẽ. Bài học: hàm
  chuẩn-hoá/whitelist phải đối chiếu schema của consumer (đây là
  `skill-packs/recipes/*.json` + `app.js` render), không đoán.

**`NATIVE_MAX` reject chứ không queue/downgrade.** Vì: mọi đường
xuống card không-native đều là Origin-forgeable — "chờ một lát" nghe
hiền nhưng tạo kênh attack mới đúng lúc hệ thống đang bị spam. Reject
409 / JSON-RPC error cho cả hai phía (portal + não ACP) và đếm qua CẢ
`local_pending` lẫn `perm_pending` — đếm một bên thì flood được bằng
bên kia.

**Preset `/api/brain` cũng qua card.** Vì: agent cầm `BRIDGE_TOKEN`
(env) gọi được endpoint — preset đổi thẳng = kill session, spawn
churn, ghi `brain.json` (file mà sandbox deny-write) qua cửa vòng.
Denylist `BRAIN_CMD_DENY` không bao giờ đầy đủ nên card custom phải
nói thẳng "chạy lệnh tuỳ ý" — nếu card trông như "đã lọc" thì học
viên duyệt với kỳ vọng sai.

## 2026 — Admin 2 tầng: pack CỐ Ý không ký, rotate-secret, bridge.token rotate

**Pack KHÔNG ký ed25519 như release — trust bất đối xứng là chủ đích.**
Vì: hai artifact phục vụ hai vai trò khác nhau. Release do VENDOR phát
cho mọi org → ký bằng key offline, collector bị chiếm cũng không phát
được release giả. Pack do CTY-ADMIN phát cho org mình — họ vốn không
được cầm vendor key, nên ký vendor cho pack là không thể (trừ khi
master ký hộ từng pack = nghẽn vận hành). Blast radius khi collector
bị chiếm bị khoanh theo org: `packs/latest-<org>.json` chỉ máy org đó
kéo về (`packHint` lấy org từ row đã xác thực bằng machine_key, không
tin body tự khai), và máy con áp `exec-allowlist` của pack nên payload
độc vẫn bị siết hành vi. Giảm thiểu thật sự nằm ở `rotate-secret` —
khi nghi secret/collector lộ thì master xoay khoá org (kể cả đá toàn
bộ máy về pending buộc re-pair). Nếu sau này cần chặt hơn: cấp cho
mỗi org một signing key riêng (org-admin giữ) thay vì dùng chung
vendor key — KHÔNG dùng vendor key cho pack.

**`rotate-secret` chỉ đụng khoá org, KHÔNG đụng session tài khoản.**
Vì: hai hệ thống credential độc lập — `admin_key`/`beacon_secret` là
khoá ORG (kênh cũ + máy con pair), còn session gắn với tài khoản người
(bảng `admins`). Secret lộ → rotate chặt kênh bị lộ; tài khoản lộ →
đổi pass/khoá account (đã xoá session ở `/api/password` + admin-update).
Gộp hai hành động sẽ làm rotate định kỳ (hygiene) vô tình đá admin
đang làm việc. `kill_machines` là opt-in riêng vì đó là hành động phá
vận hành — máy phải có fleet.json mới + được duyệt lại.

**`bridge.token` rotate mỗi lần start thay vì persist mãi.** Vì: token
là gốc tin cậy duy nhất mặt phẳng local (mọi bridge xác thực bằng nó);
file 0600 nhưng same-user process vẫn đọc được — persist mãi nghĩa là
một lần lộ = lộ vĩnh viễn. Rotate gần-miễn-phí vì mọi consumer đọc
file lúc boot (chat/ext-bridge) hoặc lazy mỗi cycle (beacon); thứ duy
nhất gãy là session extension đang sống — vốn đã reset cùng restart.
Ranh giới same-user vẫn chấp nhận (giống Chrome DevTools port) —
rotate chỉ rút ngắn cửa sổ tấn công, không dời ranh giới.

## 2026 — Audit v9: vá audit — clone-view XSS, term-gate.cmd RCE, card ACP tự duyệt

**`.cmd` KHÔNG BAO GIỜ được đọc argv/input không tin cậy — dùng `.ps1`.**
Vì: expansion `%1`/`%t%` trong batch được re-parse — payload `?arg=`
chứa `"` phá quote của `if "%t%"==...` → `& <lệnh>` chạy trực tiếp =
RCE **không cần mã kết nối** (trang web ngoài nhúng link
`localhost:7681/?arg=%22%26<cmd>` — ttyd `-O` chỉ kiểm Origin của WS
handshake, không chặn GET trang). Không tồn tại cách expansion
attacker-data an toàn trong cmd nên `term-gate.cmd` bị thay bằng
`term-gate.ps1` (PowerShell nhận argv không re-lex; token compare
`String.Equals` ordinal; `BRAIN_TERM` validate charset+deny y
`term-gate.sh`); `chat-terminal.ps1` + `launcher.py` trỏ sang `.ps1`,
file `.cmd` chỉ còn là forwarder không-kèm-arg (luôn hỏi tay). Bash
không bị class này — gán `$1` vào biến không re-lex.

**Card ACP (`perm_pending`) đi qua đầy đủ consent-gate model.** Vì:
`id` của `session/request_permission` do CHÍNH não tự khai + não có
sẵn `BRIDGE_TOKEN` → respond không check Origin = não tự duyệt mọi
tool call đắt (exec, ghi file) — lớp "người duyệt" chỉ là nghi thức.
Giờ: card ACP cũng đòi Origin loopback; macOS siết hơn — option duyệt
chỉ qua `_perm_native_confirm` (osascript dialog → chọn option
`allow_*` đầu; "Không"/hết hạn → báo `-32800` cho não ngay), chat chỉ
còn nút "Không". **id trùng card đang mở bị từ chối ngay lúc đăng ký**
— não đọc được id card `local-*` qua `/api/poll`, trùng id thì card
ACP che card consent (click "Đồng ý" cho grant-folder resolve thành
approval cho tool call của não). `.ps1` parity: `badId` check +
`LocalPending` ưu tiên trước + `perm_done` broadcast. Residual
Windows: không có native dialog → não forge Origin vẫn tự duyệt được —
muốn chặt hẳn cần kênh out-of-band proof-of-human (ghi SECURITY.md).

**Dữ liệu trang clone nhúng vào UI editor phải escape + marker phải do
editor tự tạo.** Vì: `clone-view.html` interpolate `src`/`href`/
`innerText` thẳng vào popover `innerHTML` — attribute chứa `"` phá tag
→ XSS trong origin portal (đọc `localStorage.bridge_token`, tự duyệt
card, lái extension — `/web/` không CSP); và `serialize()` "khôi phục"
mọi `data-cs-sv-*` thành attribute thật → trang nguồn tự khai
`data-cs-sv-onclick` = cấy script vào file đã lưu. Giờ: `esc()` mọi
giá trị, `prepareEditable` strip `data-cs-sv-*`/`data-cs-added-*` có
sẵn trong nguồn trước khi xử lý.

Kèm đợt này: `_SENSITIVE_DIRS`/`Test-SensitivePath` + Brave/Arc/
Vivaldi/Opera (đúng trình duyệt docs hướng dẫn); Host check loopback
cho `:7682`/`:7684` (DNS rebinding — `.ps1` đã có sẵn nhờ http.sys
prefix); `X-Frame-Options: SAMEORIGIN` (serve.py + serve.ps1);
`turn_gen` race đóng trong `store_lock`; `spawn_brain` kill fallback;
`hist_write` lock; `.trash/` GC (giữ 20 mới nhất, >30 ngày xoá); bots
cap 50; `actQuery` whitelist attr (`value` chỉ cấm trên input
password/hidden — skill cap-nhat-sheet cần đọc `#t-name-box`);
`save_json` tmp duy nhất qua mkstemp; ACP `id` non-scalar → `-32602`;
`read-brain.ps1` validate `cmd`/`terminal` một chỗ cho `start.bat` +
`chat-terminal.ps1`; `check-path`/`probe path` qua `path_sensitive`
(hết oracle dò-tồn-tại-file `~/.ssh`); pong WS qua `ext_send_lock`;
`perm_done` tra card bằng dataset (id não tự khai chứa `"` phá
querySelector).

## 2026 — Audit v8 (S4): Windows sandbox = user hạn chế + CreateProcessWithLogonW

**Não Windows chạy dưới user `troly-agent` kém quyền, không phải
AppContainer và không phải "ACL cùng user".** Vì: Windows không có cơ
chế nào hạn chế filesystem của process *cùng* user (chmod ngược được),
nên chỉ cross-user hoặc AppContainer mới có nghĩa. AppContainer đúng
semantic Seatbelt hơn nhưng cần capability SID per-folder + P/Invoke
phức tạp và ma trận test rộng hơn nhiều. Cross-user spawn dùng
`CreateProcessWithLogonW` qua `TroLy.AgentSpawn` (C# Add-Type nhúng
trong `chat-bridge.ps1`): stdio ACP qua anonymous pipes (handle inherit
qua spawn được — khác `runas`/`Start-Process -Credential` không redirect
stdio), Job Object `KILL_ON_JOB_CLOSE` để kill cả cây (non-admin không
`TerminateProcess` được process user khác — handle Job của chính bridge
mới là đường đi, và handle đóng hết thì kernel tự giết con mồ côi).
Credential `troly-agent` ngẫu nhiên, giữ DPAPI trong
`.devin/agent-user.cred` — chỉ Windows user chủ giải mã, agent đọc file
cũng vô dụng.

**ACL mirror Seatbelt, không phải "cấp full project".** RX toàn cây +
ghi chỉ `my-course/`, `.devin/skills/`, `.logs/` + deny-write tường minh
`tools/`, `web/`, `extension/`, `.git/`, `brain.json`, JSON điều khiển,
`bot.md` — agent ghi được mã nguồn bridge là code chạy quyền chủ.
Secrets deny-F. `bridge.token` deny-W (vẫn đọc được để gọi bridge).
Brain CLI cần binary dir + config dir của chủ (`~/.config/devin`,
`~/.claude`…) — grant RX đúng não đang chọn, y hệt macOS nơi agent cùng
user nên đọc sẵn. KHÔNG grant `~/.npm`: cache chủ mà agent ghi được =
đặt package độc cho chủ `npx` chạy = thoát sandbox — con dùng
`NPM_CONFIG_CACHE` riêng trong profile `troly-agent`.

**Degrade mềm + test CI Windows thật.** Cred vắng hoặc spawn lỗi → về
đường spawn thường kèm event cảnh báo (policy-only như trước, không
kẹt UX). `TROLY_NO_SANDBOX=1` tắt hẳn. CI `test-windows` chạy
`setup-agent-user.ps1` thật + smoke test `AgentSpawn` (whoami,
deny-read/write, stdio 2 chiều, Job kill) + e2e `chat-bridge.ps1` với
`fakebrain.exe` trả `pong:troly-agent` — chứng minh não thật chạy dưới
user hạn chế chứ không phải fallback. Residual đã biết: grant folder
mới qua `/api/permissions` chỉ enforce sau khi chạy lại setup (ACL
không regen tự động như Seatbelt); consent gate Windows vẫn đường
Origin (dialog native ở đây sẽ là proof được — `troly-agent` không
điều khiển GUI session chủ — nhưng chưa implement).

## 2026 — Audit v7: consent gate macOS = proof-of-human, xoá bài vào thùng rác

**Card nội bộ (`local-*`) trên macOS duyệt qua hộp thoại native
`osascript`, không qua HTTP.** Vì: `/api/respond` đòi Origin loopback
nhưng Origin chỉ là header — agent giữ token thì giả được Origin và tự
duyệt card chính mình, nên gate chỉ là "nghi thức + hiển thị". Trên
macOS, `osascript` nằm trong deny-exec của Seatbelt và agent không
điều khiển GUI → dialog do BRIDGE spawn là bằng chứng người bấm thật.
`respond ok` qua HTTP giờ trả `403` (card không bị consume — chờ
dialog); `__cancel__` vẫn nhận qua HTTP để học viên từ chối từ chat và
giết luôn dialog đang mở. GUI không chạy được (headless/SSH/
`TROLY_NO_NATIVE_GATE=1`) → phát lại card không cờ native, về đường
Origin cũ — degrade về đúng mức an toàn trước đây chứ không kẹt UX.
Windows giữ đường Origin: agent full quyền inject được input nên dialog
native ở đó không phải proof — chờ sandbox Windows (S4).

**`/api/delete-lesson` move vào `my-course/.trash/` thay vì `rmtree`.**
Vì: đây là hành động phá duy nhất bấm nhầm "Đồng ý" là không cứu được
— học viên không-coder dễ bấm vội. Tên trong trash kèm
`timestamp-hex` tránh đụng khi xoá lại cùng tên; manifest vẫn gỡ entry
ngay. `.trash/` vào filter build (build.sh + troly.spec) — dữ liệu làm
việc, không seed. Khôi phục = move ngược + trả entry manifest.

**Watchdog lượt treo (`TROLY_TURN_TIMEOUT`, mặc định 1200s).** Vì:
não sống nhưng im với prompt → `prompt_lock`/`$PromptBusy` kẹt 409
vĩnh viễn, không đường thoát cho người không-coder. Timer
(`threading.Timer` + `turn_gen` chống giết nhầm lượt mới; ps1 check
theo request tick vì đơn luồng) → báo "kẹt" cho học viên + kill →
prompt sau self-heal qua `spawn_brain`. `expect_death` để kill chủ
động không bị báo trùng "dừng đột ngột" — đổi não cũng hết message giả.

## 2026 — Audit v6: ba lỗi sót sau 5 vòng lock-down

**`path_sensitive` so HAI chiều, không một.** Vì: deny-list folder nhạy
cảm chỉ chặn path nằm DƯỚI nó — grant `~/Library` (folder CHA) đọc được
hết Keychains/Cookies/profile trình duyệt, grant `~/.config` đọc hết
credential mọi CLI não. Thêm chiều "path chứa folder nhạy cảm" + đưa
`LaunchAgents`/`Startup`/`autostart` (persistence = code chạy ngoài
sandbox lúc login) vào list. Parity `Test-SensitivePath` trên ps1.

**`read-write` từ chối trên/trong vùng mã nguồn.** Vì: grant RW trên
`~/Desktop` hay `tools/` = ghi được `tools/*.py`, `brain.json`,
`.git/hooks` → spawn/exec kế chạy code NGOÀI Seatbelt — toàn bộ
write-allowlist vô nghĩa. `rw_grant_ok` chặn ở API; `gen-sandbox.py`
emit `deny file-write*` cho vùng code làm lớp thứ hai khi
permissions.json bị sửa tay. Đọc vẫn mở — não cần đọc `AGENTS.md`.

**`terminal` cũng qua BRAIN_CMD_DENY.** Vì: chỉ check `cmd` là sót nửa
cửa — `brain.json` với `terminal:"sh"` làm term-gate exec shell trần
trong ttyd cho ai có mã kết nối (start.sh đọc file thô, không qua
load_brain). Check ở cả `load_brain`/`Get-Brain` (file), `POST
/api/brain` (request), và lớp cuối trong `term-gate.sh` ngay trước
`exec`. Cùng đợt: deny-list thêm git/awk/tar/editor/pager/wrapper/
docker (exec qua args), wp probe ps1 bắt `https://` như bản py.

**Mọi so-sánh deny phải `.lower()`/case-insensitive.** Vì: APFS/NTFS
không phân biệt hoa-thường — `which("Python3")` resolve ra python3 thật,
`exec "Python3"` chạy được, nhưng `"Python3" in deny` thì False. `POST
/api/brain` sót `.lower()` trên `cmd` từ trước (ps1 đã ToLower);
`term-gate.sh` `case` phân biệt hoa-thường → phải `tr` hạ chữ trước khi
match. Audit lại đợt vá phát hiện — đây là lý do phải so cùng dạng
canonical ở mọi điểm kiểm.

**Ghi credential + đổi link nút "Mở trang" qua consent gate.** Vì:
agent tự gọi `POST /api/secrets` với `url` mới = xoá sạch creds thật
(cơ chế wipe-khi-đổi-url vốn chống exfil lại thành vũ khí DoS), còn
url+pass tới host lạ = kênh exfil; `open_url` trong `/api/connections`
đổi link nút "Mở trang" quen-thuộc thành site phishing học viên sẽ
bấm tự nhiên. `/api/secrets` + `/api/remove-connection` gate toàn bộ;
`/api/connections` chỉ gate khi `open_url` MỚI hoặc KHÁC giá trị cũ —
upsert status/name của portal chạy thẳng, không thể card mỗi lần cập
nhật. Card `open_url` hiện đích link trong title. Parity cả .ps1.
Frontend form "Cài" hiện `pending` + giữ form mở. Không gate
`/api/bot*`: onboarding tạo+activate bot dây chuyền response→response,
gate vào là gãy flow — việc riêng.

## 2026 — Lock-down 6 phase (audit `plans/261120-1811-lock-down/`)

**Gate token trong shell thay vì flag ttyd.** Vì: test handshake thật
cho thấy `ttyd -O` chỉ so hostname bỏ qua port — `localhost:3000` vẫn
được 101. `term-gate.sh`/`.cmd` đòi `BRIDGE_TOKEN` ngay trong process
được spawn (autofill qua `ttyd -a` + `?arg=`, fallback prompt), áp cả
3 đường spawn: `start.sh`, `chat-terminal.ps1`, và `launcher.py`
(bản đóng gói — đường dễ sót nhất). Độc lập protocol ttyd, chặn cả
rebinding.

**CSP chỉ trên `/my-course/` + `/intro/`, không phải toàn server.** Vì:
portal `/web/` phải gọi bridge — cùng origin thì CSP chặt sẽ giết chat.
Nội dung agent/clone sinh ra mới là vùng không tin cậy; `connect-src
'none'` cắt mọi kênh về bridge còn `img-src` mở cho ảnh bài học.

**`/api/respond` validate pending thay vì tin client.** Vì: trước đây
nhận `id`/`optionId` tuỳ ý — ai có token tự duyệt được quyền của học
viên. Map `perm_pending` (TTL 600s, option theo đúng card đã phát)
được consume một lần; quan trọng: pop SAU khi validate option — pop
trước thì option rác cũng giết card (DoS nút bấm của học viên).

**Long-poll `/api/poll`, client tự tương thích.** Vì: poll 900ms sinh
~96 request/ phút cho event hiếm khi có. `wait=` tới 30s + `Condition`
đánh thức khi broadcast → độ trễ ~0 và ~97% ít request. `.ps1` không
implement `wait` — HttpListener đơn luồng giữ poll sẽ kẹt luôn
`/api/prompt`; client phát hiện server trả rỗng ngay thì tự nghỉ 900ms
như cũ — một giao thức, hai tốc độ, không phải hai phiên bản.

**Serialize `/api/prompt` bằng lock non-blocking, không queue.** Vì:
queue làm prompt thứ hai "thành công" rồi chạy khi học viên đã quên —
đúng thứ khiến agent làm việc không ai xin. 409 rõ ràng bắt client
đối mặt với "trợ lý đang bận" thay vì im lặng đan xen hai lượt.

**Seatbelt: whitelist-ghi + deny-enumeration cho đọc.** Vì: quirk thật
đã đo trên Darwin 27 — `(allow process*)` chỉ compile khi profile có
`file-read*` phủ tới `/`; whitelist-đọc thuần làm profile `Abort trap`
lúc load. Vậy `gen-sandbox.py` cho đọc `/` rồi duyệt cây deny mọi
sibling không nằm trên đường tới thư mục được phép (deny thắng allow —
đã verify: ~/.ssh, ~/Documents chặn, ~/Downloads có perm đọc được).
Ghi vẫn whitelist thuần. Residual: dir user tạo GIỮA hai lần regen đọc
được — chấp nhận vì regen mỗi spawn + mỗi đổi permissions. Windows giữ
policy-only cho tới khi spawn cross-user qua `troly-agent` verify được
(stdio pipe qua CreateProcessWithLogonW — chưa có máy test).

## 2026 — Cập nhật: release banner + version handshake

**Banner trong portal là "nút cập nhật" duy nhất.** Vì: học viên không
mở GitHub được — portal tự hỏi Releases API (public, không token),
so semver với `VERSION` đang chạy, chỉ hiện khi thật sự có bản mới.
Mất mạng thì im lặng — portal local không phụ thuộc internet.

**Extension báo `?v=` trong WS handshake, không phải endpoint.** Vì:
lúc nối là thời điểm duy nhất ext-bridge chắc chắn biết bản extension
thật — polling manifest phía portal chỉ thấy bản "kỳ vọng" trong
payload, không thấy bản đang chạy trong profile trình duyệt.
`?v=` đi kèm `?token=` nên không mở thêm cửa nào. Expected lấy từ
`extension/manifest.json` của payload qua `/api/health` — nguồn sự
thật duy nhất, không cần constant nhớ tay.

**Stale pill chỉ cảnh báo, không tự update.** Vì: extension unpacked
không có cơ chế tự cập nhật — đường đúng là Web Store (auto-update
miễn phí); đến lúc đó pill vàng + hướng dẫn trong Cài đặt là đủ cho
người dùng thật.

## 2026 — `troly` single-binary + self-install

**Một binary nhiều vai qua argv, payload tự bung ra `~/TroLyAI`.** Vì:
PyInstaller không đóng được nhiều "chương trình" — một exe dispatch
`serve|chat-bridge|ext-bridge` cho ta supervisor + watchdog miễn phí.
User dir giữ đúng layout project nên không phải đổi một dòng code bridge
nào. Update = exe mới thấy VERSION khác → chỉ đè CODE_DIRS/CODE_FILES,
không đụng my-course/brain/secrets — "update = tải file mới mở lại".

**Child chạy qua `runpy` trong frozen exe + hidden-imports.** Vì: không
có Python trên máy học viên nên không spawn `python tools/x.py` được.
runpy cần module của tools nằm trong bundle — PyInstaller chỉ thấy
import tĩnh của launcher nên `http.server`… phải khai trong build.sh.

**Brain auto-install = nút mở trang hãng, không chạy lệnh hộ.** Vì: cài
CLI hãng thường cần quyền/UAC/đăng nhập — dẫn đúng trang an toàn hơn là
script cài hộ hỏng giữa chừng. "Kiểm tra lại" re-fetch `/api/brain`.

## 2026 — Bridge token + chống prompt injection (đợt siết bảo mật)

**Một `bridge.token` dùng chung cho mọi bridge, hai cách trình.** Vì:
mọi API từng mở toang trên loopback — process local vô danh lái được
extension (confused deputy), đọc `/api/secrets`, giả `/api/prompt`.
Một khoá duy nhất đủ: máy cá nhân một người dùng; multi-tenant mới cần
per-user. Header cho fetch/curl, `?token=` cho WS và lệnh một dòng;
cookie bị loại vì theo port (`:8080` không phủ `:7682`/`:7684`).

**`/api/health` + `OPTIONS` miễn token.** Vì: health chỉ trả
ok/brain/version cho watchdog; OPTIONS là preflight CORS — không thực
thi hành động, bắt token là portal chết hoàn toàn.

**GET `serve :8080` vẫn mở trên loopback.** Vì: `<img>` trong clone
không gắn được token, và process local đọc file trên disk được anyway —
khoá HTTP không thêm gì. Nhưng ghi cứng trong SECURITY: **khi có relay,
`/my-course/` phải qua token và `/.shots/` chặn** (screenshot tab có thể
chứa tin nhắn).

**Extension auto-pair qua `externally_connectable`, ô dán làm dự
phòng.** Vì: zero-paste cho người không biết kỹ thuật. `key` cố định
trong manifest → extension ID ổn định giữa mọi máy → portal biết ID để
`sendMessage`. Trang lạ không gọi được (matches giới hạn localhost);
kẻ lạ ghi đè token chỉ DoS reconnect, không đánh cắp gì.

**Chống prompt injection bằng luật trong AGENTS.md, không bằng code.**
Vì: filter nội dung độc là bài toán chưa giải được — lớp phòng thủ thực
tế là "nội dung ngoài = dữ liệu, hành động nguy hiểm luôn hỏi". Kèm
`CLAUDE.md` pointer vì não Claude đọc CLAUDE.md, không đọc AGENTS.md.

## 2026 — Clone pipeline

**Một file `.html` duy nhất cho site nhiều route, router băm tự viết.**
Vì: viewer sửa một file; tách file thì học viên phải sửa nhiều nơi và
quản lý đường dẫn — việc họ không làm được. Router băm `#/route` khớp
đúng cách site gốc hiển thị địa chỉ.

**`data-cs-*` markers thay vì parse DOM khi sửa.** Vì: viewer
(`clone-view.html`), `/trang-moi`, `clone-compare.py` cần một ngôn ngữ
chung. Marker là contract — ba consumer độc lập cùng hiểu một file.

**`data-cs-type`/`data-cs-template` là từ vựng mở.** Vì: danh sách đóng
nav/hero/blog… luôn sót loại lạ; `data-cs` đã chứa tên người-đọc nên
slug mới vẫn hiển thị đúng. Ép vào `misc` làm mất thông tin.

**Đo trên trình duyệt thật, không fetch HTML.** Vì: SPA render bằng JS
— fetch được vỏ rỗng; trình duyệt thật của học viên có sẵn phiên đăng
nhập và trang đã render xong. `webfetch`/Ctrl+S chỉ là fallback.

**`data-cs-ref` cho so tự động.** Vì: class clone cố tình chuẩn hoá
(`cs-wrap`) nên khớp theo tên selector cho ra nhiễu 100% — khớp theo
marker do mình ghi lúc dựng thì chính xác.

**`clone-compare.py` parse BMP tay, không Pillow.** Vì: máy học viên
không có pip; `sips` có sẵn trên macOS. Trade-off: `shot` chỉ chạy
macOS — chấp nhận vì styles-diff quan trọng hơn và chạy mọi nơi.

**`.bak` một bản trước khi ghi đè.** Vì: học viên sửa trong viewer rất
dễ phá file duy nhất. Stable `.bak` (không timestamp) — "undo một
bước", không phải backup; tránh rác file.

**Chữ nguồn được giữ tạm để đối chiếu, bắt buộc thay trước khi giao.**
Vì: so layout cần text có độ dài thật; nhưng giao phải là nội dung học
viên (bản quyền). Skill ghi rõ ngoại lệ này.

## 2026 — Siết bảo mật đợt 5 (audit chéo component)

**CSP `sandbox` cho `/my-course/` + `/intro/`, không `allow-same-origin`.**
Vì: trang clone nằm trong `my-course/` là nội dung bên thứ 3 (mục tiêu
prompt injection), mà lại chạy cùng origin portal — script trong đó đọc
được `localStorage.bridge_token` rồi iframe/`window.open` portal để
`fetch` bridge trong context không-CSP. `sandbox` đẩy trang sang opaque
origin: localStorage/iframe-DOM/service-worker đều chết mà script vẫn
chạy, link vẫn sống. `allow-same-origin` đặt vào là mất hết hiệu lực.

**`clone-view` edit qua `srcdoc` đã lọc `<script>`, view vẫn file thật.**
Vì: CSP sandbox làm iframe opaque → `contentDocument` cũ không đọc được
nữa. Edit nạp HTML qua `srcdoc` (chủ động chọn nên cùng origin được),
lọc script ra store riêng, khôi phục khi lưu — tính năng giữ nguyên mà
script của trang clone không bao giờ thực thi trong origin portal.

**`bfetch` chỉ gắn token cho port 7682/7684.** Vì: gắn cho mọi loopback
khiến request tới `/my-course/` trên `:8080` cũng kèm `X-Bridge-Token` —
một service worker đăng ký dưới scope `my-course/` đọc được header đó
rồi lái bridge trong context không chịu page-CSP.

**Consent gate cho `/api/setup` re-run, batch `paths` cho
`/api/permissions`, `GET /api/check-path`.** Vì: gate `/api/permissions`
(đợt trước) vô tình phá onboarding — request trả `202 pending` nhưng UI
coi như xong, folder "đã chọn" mà không hiệu lực. Setup re-run đè skill
pack nên phải qua card; first-run (config chưa có `language`) chạy luôn.
Batch = một card cho nhiều folder — mỗi card riêng thì không ai đọc.
`check-path` trả `isdir` không lộ metadata để onboarding kiểm folder
trước khi xin quyền.

**Deny-list path nhạy cảm + `open_url` chỉ http(s).** Vì: card xác nhận
không bảo vệ được người bấm đại — `~/.ssh`, keychain, profile trình
duyệt, home, root bị từ chối ngay cả khi request hợp lệ. `open_url`
`javascript:` chạy script trong origin portal → chỉ nhận `http(s)://`.

**Seatbelt: `process-exec` + `file-read*` cho binary thoát-sandbox.**
Vì: `open` spawn app ngoài sandbox qua launchd, `launchctl`/`crontab`
đăng ký job chạy ngoài sandbox, `security` đọc keychain, `pbpaste` đọc
clipboard, `screencapture` chụp màn — `file-read*` một mình chặn `cp`
nhưng không chặn exec (verify bằng `sandbox-exec` trên máy thật), phải
dùng cả hai literal. Chặn thêm mach-lookup `com.apple.pasteboard.1`
phòng đường FFI/ctypes.

**`BRAIN_CMD_DENY` dùng chung cho cả load và POST.** Vì: trước chỉ check
lúc `POST /api/brain` — `brain.json` sửa tay ghi `cmd:"powershell"` vẫn
spawn thẳng. List mở rộng thêm ssh/scp/rsync/tmux/lldb/swift/sudo/
sandbox-exec/sql-client (code-exec + exfil qua args).

**`troly.spec` tự lọc `my-course/`.** Vì: `build.sh` stage rồi xoá
`clone-work/` cẩn thận, nhưng ai build bằng spec thì bundle nguyên DOM
site thật của học viên (privacy + 4.4MB) vào binary phân phối — spec
phải lọc giống build.sh.

**Thread cap + socket timeout + unmask XOR theo khối.** Vì: thread-per-
connection không trần là DoS local rẻ nhất; socket không timeout để
client nhỏ giọt giữ thread vô hạn; unmask WS từng byte làm frame ảnh
chụp vài MB nghẹt vài giây.

## Trước đó — nền hệ thống

**`brain.json` tách não khỏi bridge; `/api/brain` đổi nóng.** Vì: bridge
đã nói ACP chuẩn — não thực chất chỉ là "process biết nói ACP qua
stdin/stdout". Devin biến mất hoặc học viên có sẵn CLI khác (Gemini,
Codex, Claude) thì hệ thống vẫn sống; onboarding có bước chọn não nên
không cần sửa file tay. `cmd` tự nhập bị giới hạn ở tên lệnh trần
(`[A-Za-z0-9_.-]+`, không path) — trang local bị nhiễm vẫn không spawn
được script lạ. Adapter não (codex-acp, claude-agent-acp) chạy qua npx
nhưng `requires` vẫn kiểm cả CLI gốc — thiếu `codex`/`claude` thì báo
"chưa cài" ngay tại onboarding.

**`devin acp` cho chế độ Chat, ttyd cho Terminal.** Vì: Chat cần render
markdown + tin nhắn kiểu app cho người không biết terminal; Terminal là
fallback khi học viên lớn hơn muốn CLI thật.

**Extension điều khiển trình duyệt thật thay vì headless.** Vì: giá trị
lớn nhất là đọc Zalo/Outlook/Sheets đang đăng nhập sẵn của học viên —
không cần lưu mật khẩu của họ ở đâu cả.

**Skill trong `.devin/skills/`, kho trong `skill-packs/<lang>/`.** Vì:
onboarding cài đúng ngôn ngữ một lần; sửa skill phải tác động ngay bản
active, kho chỉ để seed máy mới.

**Agent là lớp bảo vệ cuối, không phải UI.** Vì: học viên không đọc
được lệnh — nút approve kỹ thuật không bảo vệ được họ; quy tắc nói
trước khi đụng file nằm trong `AGENTS.md` áp cho mọi session.
