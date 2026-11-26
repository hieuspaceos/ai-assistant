# Plan — 1-click cài & B2B sẵn sàng bán

Ngày: 2026-11-26. Nguồn: audit trải nghiệm cài đặt + quản trị fleet.

Mục tiêu: (a) người mới **tải 1 file → bấm 1 nút → xài được** mà không
chạm terminal; (b) công ty triển khai N máy **không ngồi từng máy**,
quản trị đúng như troly.hieuspace.com quảng cáo.

## Rào cản hiện tại (kết quả audit)

| # | Rào cản | Ai gặp |
|---|---|---|
| 1 | Extension chưa lên Web Store → user phải Dev-mode Load unpacked | cá nhân + fleet |
| 2 | Não AI không đi kèm → user tự cài CLI (`winget`/`npm`/login) | cá nhân + fleet |
| 3 | Binary chưa ký → Gatekeeper/SmartScreen chặn, EDR cty flag | cá nhân + fleet |
| 4 | `install.ps1`/`install.sh` interactive (`Read-Host`) → không chạy được qua GPO/Intune/MDM | fleet |
| 5 | Không có cơ chế cấp não tập trung → IT cài + login tay từng máy | fleet |
| 6 | Dashboard chưa gán tên NV vào máy, chưa export seat report | fleet |

## Việc CHỈ owner làm được (không giao cho code được)

- [ ] **E1.** Submit extension lên Chrome Web Store (unlisted): zip
      `troly-ext.zip` đã có, listing + screenshot đã soạn trong
      `docs/extension-store-listing.md`. Lưu ý: `debugger` +
      `<all_urls>` host permission → form **Justifications** bắt buộc
      giải thích từng permission (viết sẵn trước khi submit, review có
      thể kéo vài tuần).
- [ ] **E2.** Xác minh ID thật Google cấp sau submit — nếu khác `key`
      trong manifest hiện tại → báo để cập nhật `EXT_ID` trong
      `web/app.js` + `web/onboarding.html` + `deploy/force-install.md`.
- [ ] **E3.** macOS: lấy App Store Connect API key (hoặc Apple ID +
      app-specific password) + cert "Developer ID Application" (.p12
      export từ Keychain) → đưa vào GitHub Secrets cho CI ký.
- [ ] **E4.** Windows: chọn + mua signing — Azure Trusted Signing
      (~$10/tháng, CI-friendly) hoặc SSL.com eSigner (OV). Cần xác minh
      danh tính/org của bạn với provider.
- [ ] **E5.** Quyết định hướng "não của công ty" (xem Phase 05 — đây là
      quyết định sản phẩm, không phải code).

## Tasks

### Phase 01 — Extension lên Store + dọn chỗ nhận update

Phụ thuộc: E1, E2. Việc trong repo:

- [ ] Verify `troly-ext.zip` build từ `extension/` mới nhất (manifest
      hiện v0.2 — quyết định bump version trước submit không).
- [ ] Sau khi store duyệt: cập nhật `SETUP.md` Bước 5 → "cài từ Chrome
      Web Store 1 click" (giữ Load unpacked làm đường dev); cập nhật
      README mục update extension ("bấm Update" thay "xoá + Load
      unpacked"); landing page nếu có nhắc extension.
- [ ] `deploy/force-install.md` từ "giấy" thành "dùng được" — đổi giới
      thiệu đầu file, thêm mục kiểm chứng sau khi store ID thật.
- [ ] Onboarding/Settings: phần kết nối extension nhận biết bản store
      (ID từ `key` manifest = ID force-install dùng — giữ `key` thì ID
      store đúng luôn, verify lại `EXT_ID` hardcode trong web/).

### Phase 02 — Ký số + notarize releases (CI)

Phụ thuộc: E3 (mac), E4 (win). File: `.github/workflows/build.yml`,
`tools/build.sh`.

- [ ] macOS job: import `.p12` vào keychain tạm → `codesign --sign
      "Developer ID Application: …" --options runtime --timestamp` lên
      `dist/troly` → zip → `xcrun notarytool submit --wait` → release
      asset đã notarize. Secrets: `MACOS_P12`, `MACOS_P12_PASSWORD`,
      `NOTARY_KEY`/`NOTARY_ISSUER`/`NOTARY_KEY_ID` (hoặc apple-id trio).
- [ ] Windows job: sau PyInstaller → ký `TroLyAI.exe`:
      Azure Trusted Signing → `azure/trusted-signing-action`; hoặc
      eSigner → `signtool` + CKA plugin. Secrets theo provider E4 chọn.
- [x] Không đợi E4: chỉnh nút tải trên `site/index.html` + đầu
      `SETUP.md` ghi rõ "SmartScreen: More info → Run anyway" /
      "macOS: chuột phải → Open" — interim cho tới khi ký xong.
- [ ] `docs/troubleshooting-runbook.md` mục SmartScreen cập nhật lại
      sau khi exe đã ký.

### Phase 03 — Onboarding tự cài não (đóng lỗ hổng "1 click" lớn nhất)

Độc lập, làm song song được. File: `tools/install-brain.py` (+ `.ps1`),
`tools/chat-bridge.*` (endpoint), `web/onboarding.html` (progress UI).

- [x] `tools/install-brain` — script cài não, allowlist cứng preset
      (không nhận lệnh tuỳ ý):
  - Gemini (đường free, mặc định gợi ý): Windows `winget install
    OpenJS.NodeJS` → `npm i -g @google/gemini-cli`; macOS `brew
    install node` (có brew) hoặc tải Node.pkg (cần admin — hướng dẫn
    lúc đó). Kiểm `shutil.which("gemini")` sau cài.
  - Devin: `irm https://cli.devin.ai/install.ps1 | iex` (win) /
    `curl … | sh` (mac).
  - In progress ra stdout dạng JSON-line để bridge đọc.
- [x] Endpoint `POST /api/install-brain {id}` trên chat-bridge: chỉ
      nhận id trong `BRAIN_PRESETS`, spawn script, `GET
      /api/install-brain/status` trả progress cho onboarding poll.
      Giữ threat model: endpoint chỉ chạy script nội bộ, không exec
      lệnh tự do; rate-limit như các POST khác.
- [x] Onboarding UI: nút "Cài não này" → trạng thái "đang cài… (vài
      phút)" → "đã cài" tự chọn não. Thất bại → giữ đường fallback cũ
      (mở link vendor + hướng dẫn tay).
- [x] Bước đăng nhập sau cài: Gemini/`devin` login đều mở trình
      duyệt OAuth — onboarding hướng dẫn "bấm nút → trình duyệt mở
      trang đăng nhập, đăng nhập xong quay lại đây" + poll `/api/health`
      brain cho tới khi sống.
- [x] Test: `tools/test-bridges.py` thêm case endpoint chỉ nhận preset
      id + reject lệnh lạ. Parity .py/.ps1 như mọi endpoint khác.

### Phase 04 — Silent install cho IT (fleet deploy không ngồi máy)

File: `deploy/install.ps1`, `deploy/install.sh`, `deploy/DEPLOY.md`.

- [x] `install.ps1 -Quiet [-NoSandbox]` — bỏ `Read-Host`; `-NoSandbox`
      bỏ tạo `troly-agent` (ghi warn). Không flag thì giữ interactive
      như cũ. `-ForUser` đã có.
- [x] `install.sh` tương đương (`--quiet`, `--no-sandbox`).
- [x] `deploy/DEPLOY.md` thêm mục "cài không ngồi máy": GPO startup
      script / Intune win32 app (`install.ps1 -Quiet` trong
      `installcommand`), lưu ý admin + reboot.
- [x] Extension trong silent path: nhắc rõ force-install policy phải
      áp TRƯỚC hoặc ngay sau cài (phụ thuộc Phase 01).

### Phase 05 — Não cho cả org (quyết định sản phẩm → rồi mới code)

E5 — chọn MỘT hướng:

- [x] **A. Tối thiểu (khuyến nghị làm trước):** `deploy/install-brain.ps1`
      IT chạy cùng `install.ps1` (winget cài CLI) + pack field `brain`
      → `apply-pack.py` ghi `brain.json` cho **máy chưa onboard** (cùng
      rule `permissions_template`: không đè máy đang chạy). Login vẫn
      per-user lần đầu — doc DEPLOY.md dặn "NV đăng nhập não ngày đầu".
- [ ] **B. Creds qua pack:** pack mang API key/service account của org
      vào máy. Cần thiết kế riêng: pack hiện nằm cleartext tại collector
      (admin đọc được) → secret trong pack phải mã hoá theo máy hoặc
      chấp nhận "org-admin đọc được key org". Bàn riêng trước khi làm.
- [ ] **C. Não relay của vendor:** không cần CLI/đăng nhập nào trên máy
      — máy nói chuyện não qua endpoint vendor. Ưu: đúng nghĩa "cài và
      xài", gộp cả bài toán cá nhân. Nhược: infra mới, chi phí không
      biết trước của vendor, privacy story đổi (prompt rời máy qua
      vendor relay), cần billing/seat gắn license. Chỉ làm khi A+B
      không đủ với thực địa.

### Phase 06 — Dashboard vận hành (fleet tiện hơn)

File: `collector-web/`, `tools/collector.py`, `worker/src/index.js`
(giữ parity hai bản — `test-fleet.py` khoá endpoint set).

- [x] Gán nhãn máy→nhân viên: `POST /api/machine/<id>/label`
      (admin_key scope org) + ô edit trên dashboard; label hiển thị
      cạnh hostname.
- [x] `GET /api/seats/export` CSV (org, machines, active30, seats,
      exceeded) — chủ cty in báo cáo gia hạn.
- [x] `deploy/DEPLOY.md` mục "nhân viên nghỉ": revoke máy → gỡ folder
      + extension policy → thu hồi seat (liên kết checklist sẵn có).

## Thứ tự gợi ý

1. **E1** submit extension ngay (review Google chờ vài tuần — bắt đầu
   sớm nhất). Song song làm Phase 03 (auto-install não) — việc giá trị
   nhất cho mục tiêu "1 click".
2. Phase 02 phần interim (dòng hướng dẫn SmartScreen trên site/SETUP)
   — 30 phút, làm luôn; ký số làm khi E3/E4 xong.
3. Phase 01 + Phase 04 khi store duyệt xong.
4. Phase 05-A sau khi 03–04 ổn; B/C là quyết định riêng.
5. Phase 06 cuối — tiện chứ không chặn.

## Xong khi nào

- Cá nhân: tải file → (win: Run anyway / mac: right-click Open — hoặc
  không còn warning nếu đã ký) → portal mở → onboarding cài não bằng 1
  nút → đăng nhập Google → chat được. Extension 1 click từ Store.
- Fleet: IT chạy `install.ps1 -Quiet` qua GPO/Intune (hoặc tay ~2
  phút/máy) + force-install extension + pack đẩy brain.json → máy hiện
  pending → duyệt → xong. NV chỉ đăng nhập não lần đầu.
