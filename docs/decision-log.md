# ai-assistant — Decision Log

Các quyết định kiến trúc và **tại sao** — để sau này không gỡ ngược lại
vì quên lý do. Mới nhất lên đầu.

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
