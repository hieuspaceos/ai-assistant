# ai-assistant — Decision Log

Các quyết định kiến trúc và **tại sao** — để sau này không gỡ ngược lại
vì quên lý do. Mới nhất lên đầu.

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
