# Hồ sơ submit Chrome Web Store — extension "Trợ Lý AI"

Việc NGƯỜI DÙNG phải làm (agent không thay được): tạo tài khoản dev
Chrome Web Store ($5 một lần) tại https://chrome.google.com/webstore/devconsole,
upload `extension/` đã zip, điền listing dưới đây.

## Cần chuẩn bị trước khi submit

- [ ] `cd extension && zip -r ../troly-ext.zip .` (zip từ TRONG folder)
- [ ] 1–3 screenshot 1280×800: icon trên toolbar + portal đang lái browser
- [ ] Icon 128×128 (đã có `icons/` trong extension)
- [ ] Kiểm ID thật sau khi Google cấp → cập nhật `EXT_ID` trong
  `web/app.js` + `web/onboarding.html` nếu khác `key` hiện tại

## Listing — Tiếng Việt

**Tên:** Trợ Lý AI — cánh tay trình duyệt
**Mô tả ngắn:** Giúp trợ lý AI trên máy bạn đọc và thao tác trên trang web đang mở — chỉ khi bạn cho phép.
**Mô tả dài:**
Trợ Lý AI là extension đi kèm bộ trợ lý AI chạy trên chính máy của bạn
(không phải dịch vụ đám mây). Nó là "cánh tay" giúp trợ lý đọc nội dung
trang đang mở, bấm nút, gõ chữ — dùng phiên đăng nhập sẵn có của bạn,
KHÔNG thu thập hay gửi mật khẩu/dữ liệu đi đâu cả.

- Mọi lệnh đi qua "mã kết nối" một lần — phần mềm lạ trên máy không điều
  khiển được extension.
- Mọi dữ liệu ở lại trên máy bạn; extension không gửi gì ra internet.
- Bạn luôn thấy trợ lý đang làm gì trên màn hình.

## Listing — English

**Name:** Trợ Lý AI — browser arm
**Short desc:** Lets your local AI assistant read and act on the page you have open — only when you allow it.
**Full desc:**
Trợ Lý AI is the companion extension to a fully local AI assistant (not a
cloud service). It lets the assistant read the open page, click, and type
— using your existing signed-in sessions. It never collects or transmits
passwords or data.

- Every command requires a one-time connection code — rogue software on
  your machine cannot drive the extension.
- All data stays on your machine; nothing is sent to the internet.
- You always see what the assistant does on screen.

## Justification cho quyền `debugger` (bắt buộc ghi trong form quyền)

> The extension drives Chrome DevTools Protocol ONLY on the tab the user
> is interacting with, to deliver real (trusted) input events — some web
> apps (Zalo Web, Google Sheets) ignore synthetic JS events. The debugger
> attaches per-action and detaches right after; the "debugging" banner
> appears visibly to the user. No network traffic is intercepted, no data
> leaves the machine.

## Rủi ro & đường dự phòng

- Review có thể từ chối/trì hoãn vì quyền `debugger` — nếu bị từ chối:
  cân nhắc bản "lite" bỏ nhóm `t*` (mất nhập liệu thật trên Zalo/Sheets),
  hoặc đường B2B: Chrome enterprise policy `ExtensionInstallForcelist`
  cài sẵn cho fleet (vẫn cần host zip hoặc đăng unlisted).
- ID extension từ store do Google cấp từ `key` trong manifest — đã chốt
  `key` sẵn nên ID unpacked hiện tại và ID store GIỐNG nhau (verify lại
  sau submit; nếu khác thì sửa `EXT_ID` ở 2 file web).

## Sau khi được duyệt

1. Sửa `EXT_ID` trong `web/app.js` + `web/onboarding.html` nếu ID store
   khác ID hiện tại (`mdalidmkajiinlpdefjchbgcejjjmpeh`).
2. Bước extension trong onboarding/onboarding hint → đổi sang link store.
3. Bỏ hướng dẫn "Load unpacked" khỏi SETUP.md (giữ lại cho dev ở cuối).
