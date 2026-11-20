# Hồ sơ submit Chrome Web Store — extension "Trợ Lý AI"

Việc NGƯỜI DÙNG phải làm (agent không thay được): tạo tài khoản dev
Chrome Web Store ($5 một lần) tại https://chrome.google.com/webstore/devconsole,
upload `extension/` đã zip, điền listing dưới đây.

## Cần chuẩn bị trước khi submit

- [x] `cd extension && zip -r ../troly-ext.zip .` (zip từ TRONG folder — đã tạo, ~14K)
- [x] Screenshot 640×400: `docs/store-assets/portal-640x400.png` +
  `onboarding-640x400.png` (từ ảnh quay thật trong `site/assets/`).
  Nên chụp thêm 1 shot icon trên toolbar với badge ON — phần này phải
  chụp tay trên máy có extension cài sẵn.
- [x] Icon 128×128 (đã có `icons/` trong extension)
- [x] Privacy URL: `site/privacy.html` → sau deploy có
  `https://troly.hieuspace.com/privacy.html` (điền vào ô Privacy policy
  trong form submit)
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

## Justification cho từng quyền (điền trong form quyền khi submit)

**`debugger`**
> The extension drives Chrome DevTools Protocol ONLY on the tab the user
> is interacting with, to deliver real (trusted) input events — some web
> apps (Zalo Web, Google Sheets) ignore synthetic JS events. The debugger
> attaches per-action and detaches right after; the "debugging" banner
> appears visibly to the user. No network traffic is intercepted, no data
> leaves the machine.

**`tabs`**
> The extension needs to see which tab the user is viewing so the local
> assistant can act on the page the user actually has open — not a
> hidden or background tab. Tab URLs/titles never leave the machine.

**`scripting`**
> Used to run the assistant's small read/act scripts inside the page the
> user is looking at (read text, click a button, fill a field) — only
> after the user asks the assistant to do so. Scripts are fixed,
> shipped inside the extension, never fetched remotely.

**`activeTab`**
> Lets the extension act on the currently active tab only when the user
> invokes it — the standard least-privilege way to limit access to the
> page in front of the user.

**`alarms`**
> The MV3 service worker is suspended when idle; a short periodic alarm
> wakes it so the extension can keep/re-establish its local WebSocket
> connection to the user's own assistant on 127.0.0.1. No user data is
> involved.

**`storage`**
> Stores a single random "connection code" in `chrome.storage.local` so
> the extension can authenticate commands from the user's own local
> assistant. This is a few dozen bytes on-device; nothing is synced.

**Host access `<all_urls>`**
> The assistant's job is to read and act on whatever web app the user
> works in — Zalo Web, Outlook Web, WordPress admin, Google Sheets are
> all different domains the user chooses at runtime. Restricting to a
> fixed host list would break the core feature for any site we did not
> predict. All page access happens only on the user's open tab, only
> on the user's request, and no content leaves the machine.

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
