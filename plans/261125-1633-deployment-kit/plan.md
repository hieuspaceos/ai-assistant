# Plan 4/5 — Deployment kit: extension Web Store + install + DEPLOY.md

Ngày: 2026-11-25. Mục tiêu: gói để **đội triển khai (hoặc IT khách) cài
N máy theo một checklist**, không cần người viết code đứng cạnh. Gồm
hai nửa: (a) tháo gỡ điểm yếu vận hành lớn nhất — extension load
unpacked từng máy; (b) bộ hồ sơ cài đặt cho IT.

## Phần A — Extension lên Chrome Web Store (unlisted) + force-install

Load unpacked hiện tại: bật Developer mode (đáng sợ cho IT), update
tay từng máy, Chrome có thể khoá unpacked bất cứ lúc nào. Doanh nghiệp
có đường chuẩn: **publish unlisted + ExtensionInstallForcelist** — IT
đẩy policy xuống máy, extension tự cài + tự update, nhân viên không
bấm gì.

### Tasks

- [x] `tools/build-ext.sh` / `.ps1` — zip `extension/` thành bản release
      (đọc version từ manifest.json, đặt tên `troly-ext-<ver>.zip`).
      **GIỮ trường `key` trong manifest** — EXT_ID
      (`mdalidmkajiinlpdefjchbgcejjjmpeh`, hardcode `web/app.js`) được
      derive từ key này; store derive ID từ `key` khi upload lần đầu
      nên giữ key = giữ ID = flow `set-token` portal→ext khỏi sửa.
      Nếu vì lý do nào ID đổi → phải sửa EXT_ID trong app.js + đẩy
      release mới (audit round 5).
- [x] Audit trước publish (checklist, không code):
      - `manifest.json`: version bump, `externally_connectable` giữ
        localhost-only, icon đủ size (128 cho store), description
        vi+en rõ ràng.
      - Store listing cần: icon 128, 1-2 screenshot, mô tả, **privacy
        policy URL** (bắt buộc cho extension có host quyền rộng) —
        ĐÃ CÓ: `site/privacy.html` (song ngữ, nội dung đúng: chỉ gửi
        về 127.0.0.1) → deploy lên
        `https://troly.hieuspace.com/privacy` rồi điền URL đó vào
        listing. Task còn lại: deploy site + kiểm nội dung khớp
        extension thật.
      - Justify permissions khi submit — theo manifest THẬT:
        `debugger` (đọc/điều khiển trang), `scripting` + `activeTab`
        + `<all_urls>` (thao tác trang user đang login), `tabs`
        (quản tab), `alarms` (keepalive service worker), `storage`.
        Không có nativeMessaging — đừng khai. Viết sẵn đoạn giải
        thích + screen recording (review kỹ với quyền rộng này).
      - Chọn **unlisted** — người ngoài store không tìm thấy, chỉ ai có
        link cài được; đủ cho force-install.
- [x] `deploy/force-install.md` — hướng dẫn IT:
      - Windows: GPO/Registry
        `HKLM\Software\Policies\Google\Chrome\ExtensionInstallForcelist`
        = `<ext-id>;https://clients2.google.com/service/update2/crx`
      - macOS: plist `com.google.Chrome` cùng key (qua MDM hoặc tay).
      - Edge: tương đương (`ExtensionInstallForcelist` Edge key).
      - Kiểm chứng: `chrome://policy` thấy policy + extension tự hiện.
      - Lưu ý token: extension cần mã kết nối máy — portal tự đẩy qua
        `externally_connectable` `{t:'set-token'}` khi nhân viên mở
        portal lần đầu (đã có flow này).

## Phần B — Bộ cài + DEPLOY.md cho IT

### Tasks

- [x] `deploy/install.ps1` (Windows, chạy PowerShell admin):
      1. Copy folder ai-assistant → `C:\TroLyAI\` (hoặc `%LOCALAPPDATA%`).
      2. `winget install tsl0922.ttyd` nếu thiếu.
      3. Tuỳ chọn `tools\setup-agent-user.ps1` (sandbox user) — hỏi Y/N,
         giải thích vì sao nên.
      4. Ghi `.devin\license.json` (copy từ thư mục bộ cài cty),
         `.devin\fleet.json` (collector URL cty) nếu có sẵn.
      5. Tạo shortcut Desktop `TroLyAI.bat` → `start.bat`.
      6. Mở portal lần đầu `start.bat` để sinh token + onboarding.
- [x] `deploy/install.sh` (macOS) — tương đương: copy → `~/TroLyAI`,
      brew install ttyd (hoặc cảnh báo), license/fleet copy, LaunchAgent
      tuỳ chọn, open start.sh.
- [x] `deploy/DEPLOY.md` — hướng dẫn đội triển khai/IT, mục lục:
      - Kiến trúc một máy (4 process + extension) — 1 hình.
      - Yêu cầu máy: Windows 10+/macOS, Chrome/Edge/Brave, quyền admin
        lúc cài (không cần lúc chạy).
      - Trước khi đi: gói bộ cài (folder zip + license.json +
        fleet.json + workflow pack cty nếu có).
      - Từng máy: install.ps1 → mở portal → onboarding cơ bản
        (chọn não, mã kết nối extension — hoặc force-install đã lo).
      - Cài collector (plan 1) — chọn theo tier:
        a) **Customer-hosted** (khuyến nghị nếu khách có domain):
           collector trên VPS/domain của họ (`fleet.<domain-cty>`),
           cert thật qua nginx/CapRover của khách — nhân viên remote
           beacon được, data ở lại hạ tầng khách.
        b) **LAN self-hosted**: một máy IT chạy `collector.py`,
           firewall mở 8790 inbound LAN — chỉ máy trong văn phòng.
        c) **Vendor-hosted**: `troly.hieuspace.com/fleet/` — khách
           không có gì; `fleet.json` trỏ URL đó, kèm điều khoản DPA.
      - Extension: hai đường — force-install (khuyến nghị fleet) hoặc
        unpacked tay (máy lẻ).
      - Checklist nghiệm thu mỗi máy: portal mở được, chat trả lời,
        extension dot xanh, `/api/health` version đúng, beacon thấy
        trên dashboard sau 15'.
      - Vận hành: update tự về qua release; pack mới qua collector;
        sự cố → xem admin.html tại máy.
      - Rollback: gỡ shortcut + folder; dữ liệu nhân viên nằm trong
        `my-course/` — backup trước khi gỡ.
- [x] `deploy/CHECKLIST.md` — bản in 1 trang cho người đi cài: tick
      từng mục per máy, cột "máy/người dùng/kết quả/ghi chú".
- [x] `deploy/vendor-infra.md` — hạ tầng phía vendor trên
      `troly.hieuspace.com` (audit round 7):
      - `site/` → static hosting (landing + `/privacy`).
      - `/releases/` → thư mục tĩnh chứa `latest.json` + zips —
        build-release ký xong rsync/upload lên đây.
      - `troly.hieuspace.com/fleet/` → hosted collector (plan 1):
        path-based qua nginx, per-org SQLite, meta-telemetry
        endpoint `/fleet/api/org-ping`.
      - VPS tối thiểu $5-10/tháng; static có thể tách sang GitHub
        Pages/Netlify nếu muốn VPS chỉ chạy collector.

### Phase liên quan

- [x] `docs/codebase-summary.md`: mục `deploy/` mới.
- [x] `docs/troubleshooting-runbook.md`: bổ sung "triển khai cty" —
      lỗi thường gặp khi cài hàng loạt (policy chặn, proxy, winget thiếu,
      execution policy).

## GATE

- `build-ext.sh` chạy ra zip hợp lệ (`chrome --pack-extension` hoặc
  load unpacked test được).
- `install.ps1` trên máy Windows sạch → portal chạy, token sinh,
  license/fleet đúng chỗ.
- DEPLOY.md đưa cho người không biết repo — cài được không cần hỏi
  lại (self-test: đọc doc giả vờ là IT, theo đúng từng bước).

## Rủi ro / mở

- Web Store review: extension với `debugger` + `all_urls` thường bị
  review kỹ — chuẩn bị screen recording demo + justification kỹ. Nếu
  bị reject → fallback: self-hosted CRX + policy `update_url` (Chrome
  Windows chỉ cho force-install từ store — Edge cũng vậy; self-host
  chỉ cứu được Linux → bắt buộc phải qua store được).
- Unlisted vẫn public nếu ai có link — chấp nhận (extension vô dụng
  không có bridge/token máy đó).
- Install script chạy admin → script phải review kỹ (không download
  thực thi từ ngoài, chỉ winget/store chính thức).

## Kết quả (implement xong 2026-11-25)

- `tools/build-ext.sh`: zip đúng shape (manifest ở root, giữ `key` →
  EXT_ID ổn định), lint manifest (key + connectable localhost + icon)
  trước gói; loại .DS_Store/*.pem/*.crx. Chạy ra dist/troly-ext-0.2.zip.
- `deploy/`: DEPLOY.md (kiến trúc + 3 tier + nghiệm thu + vận hành),
  install.ps1 (robocopy loại state, winget ttyd, hỏi sandbox user,
  license/fleet từ company/, shortcut), install.sh (tar exclude,
  brew ttyd, LaunchAgent opt-in), force-install.md (Registry/GPO/
  plist/Edge + kiểm chứng chrome://policy), CHECKLIST.md in 1 trang,
  vendor-infra.md (sơ đồ /releases/ + /fleet/ + org-ping + nguyên tắc).
- docs/codebase-summary.md: bảng tools mới + mục deploy/.
- docs/troubleshooting-runbook.md: mục 9 "Triển khai cty" 11 lỗi hay gặp.
- PHẦN CÒN LẠI NGOÀI REPO (ops, không code được): upload zip lên
  Chrome Web Store (tài khoản dev $5, chọn unlisted, điền privacy URL
  sau khi deploy site/privacy.html lên troly.hieuspace.com/privacy);
  chạy install.ps1 trên máy Windows sạch; dẫn DEPLOY.md cho người khác
  đọc self-test. Audit-publish checklist giữ trong plan này.
