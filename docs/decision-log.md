# ai-assistant — Decision Log

Các quyết định kiến trúc và **tại sao** — để sau này không gỡ ngược lại
vì quên lý do. Mới nhất lên đầu.

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
