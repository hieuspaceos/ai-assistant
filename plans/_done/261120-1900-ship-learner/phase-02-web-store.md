# Phase 2 — Extension lên Chrome Web Store

> **Status: phần chuẩn bị xong** — privacy.html, zip, screenshot,
> justification đủ 7 mục đều sẵn. Còn lại là việc NGƯỜI DÙNG: tài khoản
> dev $5 + upload/điền form + (khuyến nghị) 1 ảnh icon trên toolbar chụp
> tay. Sau duyệt mới làm mục 2c.

## Mục tiêu

Học viên cài extension bằng MỘT link store thay vì quy trình
Developer-mode + Load unpacked. Phần submit là việc người dùng; phase
này chuẩn bị mọi thứ để họ chỉ cần upload + bấm.

## File động

| File | Action | Việc |
|---|---|---|
| `site/privacy.html` | create | privacy policy tiếng Việt + English — bắt buộc có URL public khi submit extension xin quyền nhạy cảm |
| `docs/extension-store-listing.md` | modify | bổ sung checklist cuối: privacy URL, versioning của bản store |
| `extension/manifest.json` | modify | bump `version` theo semver trước mỗi lần submit (store yêu cầu version tăng) |
| `web/onboarding.html` | modify | sau duyệt: bước cài extension → link store; giữ đường unpacked cho dev |
| `web/app.js` | modify | sau duyệt: pill "bản cũ" dẫn link store thay vì hướng dẫn Load unpacked |
| `SETUP.md` | modify | sau duyệt: Bước 5 → "bấm link → Add to Chrome", phần unpacked chuyển xuống mục dev |

## Chi tiết

### 2a. Trước submit (agent làm được hết)

1. `site/privacy.html` — trang tĩnh cùng theme landing, nội dung đã có
   sẵn trong listing doc ("không gửi gì ra internet, mọi dữ liệu ở lại
   máy, mã kết nối một lần"). Deploy cùng troly.hieuspace.com → có URL
   public `https://troly.hieuspace.com/privacy.html`.
2. `cd extension && zip -r ../troly-ext.zip .` (zip từ TRONG folder).
3. Chụp 2-3 screenshot 1280×800: icon trên toolbar với badge ON, portal
   đang chạy, Zalo Web được trợ lý đọc (che tin nhắn thật).
4. Đối chiếu lại form quyền: `tabs`, `scripting`, `activeTab`,
   `alarms`, `debugger`, `storage`, `<all_urls>` — mỗi quyền cần 1-2
   câu justification (debugger đã có sẵn trong listing doc; viết nốt
   cho `<all_urls>` + `storage`).

### 2b. Submit (NGƯỜI DÙNG làm — agent hướng dẫn)

- Tạo tài khoản dev $5 tại Chrome Web Store Developer Console.
- Upload zip + điền listing vi/en đã soạn + privacy URL + screenshots.
- Câu hỏi "single purpose": extension là companion của trợ lý local —
  mô tả đã viết sẵn đáp ứng được.

### 2c. Sau duyệt

1. Verify extension ID store = ID unpacked (`key` cố định trong
   manifest đảm bảo trùng — kiểm `EXT_ID` trong `web/app.js` và
   `web/onboarding.html`, sửa nếu Google cấp ID khác).
2. Onboarding bước extension: nút "Cài từ Chrome Web Store" mở link
   store; khối hướng dẫn unpacked thu nhỏ thành details "cho dev".
3. Pill trạng thái extension: khi chưa cài, click → mở link store.
4. SETUP Bước 5 viết lại 3 dòng: mở link → Add to Chrome → ghim icon.
5. Extension auto-update từ store → mục "outdated pill" trong SECURITY/
   runbook cập nhật: bản store tự cập nhật, chỉ bản unpacked mới cần
   Load lại tay.

## Acceptance

- Extension có trang store public, cài bằng link một bước
- Onboarding trên máy sạch: cài xong extension có badge ON không cần
  dán mã (auto-pair vẫn chạy vì `externally_connectable` + cùng ID)
- SETUP.md không còn yêu cầu Developer mode với learner

## Rủi ro

- **Review từ chối `debugger`**: fallback đã thiết kế sẵn — bản "lite"
  bỏ nhóm `t*` (feature-detect `chrome.debugger` trước khi attach; mất
  nhập liệu thật trên Zalo/Sheets nhưng đọc vẫn được), hoặc phát hành
  unlisted cho nhóm pilot. Quyết định khi có kết quả review thật.
- **Version handshake**: store update chậm lan hơn app update → pill
  "bản cũ" có thể báo sai ngắn hạn sau mỗi release — chấp nhận (đã có
  cơ chế expected-version trong ext-bridge).
- **`key` không đảm bảo ID store**: CWS có thể gán ID khác ID hiện tại
  dù manifest có `key` → `EXT_ID` hardcode trong `app.js` +
  `onboarding.html` (`mdalidmkajiinlpdefjchbgcejjjmpeh`) trỏ sai →
  auto-pair chết. Vá = sửa EXT_ID + release `troly` mới — nên cân
  nhắc làm `EXT_ID` list `[id_store, id_unpacked]` thử lần lượt để
  không phải hotfix khi Google gán ID khác.
