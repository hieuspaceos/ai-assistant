---
title: "Ship bản đầu cho học viên thật (đợt ship)"
description: "Gỡ 4 vật cản giữa sản phẩm và học viên thật đầu tiên: chưa có bản Windows (nền tảng chính), extension phải load unpacked, não mặc định trả phí, thông điệp 'cỗ máy sinh khoá học' làm mờ giá trị trợ lý làm việc. Xong đợt này = một học viên Windows không biết code cài được, dùng được, không tốn tiền não."
status: pending
priority: P1
effort: L
branch: main
tags: [packaging, ci, distribution, onboarding, positioning, critical]
created: 2026-11-20
depends-on: 261120-1635-fix-audit (đợt vá audit)
---

# Ship bản đầu cho học viên thật

## Bối cảnh — tại sao làm

Đánh giá tổng thể 2026-11-20: kiến trúc và thiết kế đã đúng, nhưng sản
phẩm **chưa tới tay được đúng đối tượng** vì 4 vật cản:

| # | Vật cản | Hệ quả |
|---|---------|--------|
| A | Windows là nền tảng chính (`start.bat` + `.ps1`) nhưng chưa có `troly.exe` — chỉ có bản macOS | Học viên Windows phải đi đường cài tay nhiều bước trong SETUP.md |
| B | Extension phải "Load unpacked" (bật Developer mode, chọn folder) | Bước kỹ thuật duy nhất còn lại không thể che giấu khỏi người không biết code |
| C | Não mặc định Devin = subscription trả phí; học viên không có sẵn | Rào cản kinh tế lớn nhất — lý do từ chối #1 của khách tiềm năng |
| D | Thông điệp lead bằng "cỗ máy sinh khoá học" | Giá trị bền (trợ lý làm việc thật) bị che; người nghe tưởng đây là LMS |

Cả 4 đều là việc "đóng hàng", không phải thiết kế lại.

## Thiết kế tổng thể

1. **CI build Windows** — GitHub Actions matrix (macos + windows) chạy
   `tools/build.sh` (đã sẵn, PyInstaller không cross-compile nên bắt
   buộc build trên OS đích — runner Windows của GHA giải quyết việc
   "không có máy Windows"). Chạy 3 smoke test trước khi build, attach
   artifact lên GitHub Release khi tag `v*`.
2. **Extension lên Web Store** — hồ sơ đã soạn ở
   `docs/extension-store-listing.md`; còn thiếu privacy policy (thêm
   `site/privacy.html` — landing đã deploy troly.hieuspace.com) và
   screenshot. Sau duyệt: onboarding chuyển sang link store, giữ
   load-unpacked cho dev.
3. **Não miễn phí trong onboarding** — thêm trường `cost` vào
   `BRAIN_PRESETS`, preset Gemini CLI (free tier tài khoản Google cá
   nhân) hiện badge "miễn phí" và xếp lên đầu khi không có não nào
   cài sẵn. Không đổi default `brain.json` — chỉ đổi *gợi ý*.
4. **Định vị lại: assistant-first** — README/site/SETUP lead bằng
   "trợ lý làm việc thật tự thiết kế khoá học dạy bạn", khoá học thành
   differentiator chứ không phải headline.
5. **Đóng băng `.ps1`** — khi `troly.exe` có mặt, đường `.ps1`+`.bat`
   thành dev-only: đánh dấu frozen, `test-parity.py` hạ xuống
   warn-only, docs chỉ còn đường `troly`.

## Trade-off đã quyết

1. **Gemini free tier thay vì não local** — Ollama/local model chạy
   được nhưng chất lượng thấp cho agent + nặng máy học viên. Gemini
   free tier (xác minh quota hiện hành khi implement) là điểm cân tốt
   nhất "không tốn tiền mà vẫn làm được việc".
2. **SmartScreen/Gatekeeper cảnh báo** — file exe mới không ký sẽ bị
   chặn. Chấp nhận trong pilot (đã ghi từ plan bridge-auth); ký code
   tính khi có >vài chục user.
3. **`.ps1` đóng băng chứ không xoá** — vẫn là đường dev/debug trên
   Windows khi chưa có binary; chỉ ngừng yêu cầu parity tuyệt đối.

## Phases

| # | Phase | Nội dung | Link |
|---|-------|----------|------|
| 1 | CI build Windows | `.github/workflows/build.yml` matrix + tests + release attach | [phase-01](./phase-01-ci-windows.md) |
| 2 | Web Store | zip + privacy page + submit listing + sau-duyệt đổi onboarding | [phase-02](./phase-02-web-store.md) |
| 3 | Não miễn phí | `cost` trong presets, onboarding ưu tiên Gemini, copy minh bạch giá | [phase-03](./phase-03-free-brain.md) |
| 4 | Reposition | README + `site/` + SETUP + PDR lead bằng assistant-first | [phase-04](./phase-04-reposition.md) |
| 5 | Freeze `.ps1` | đánh dấu dev-only, `test-parity.py` warn-only, docs một đường | [phase-05](./phase-05-freeze-ps1.md) |

## Rủi ro chính

- **R1**: `build.sh` chưa chạy trên Windows bao giờ — SEP detection
  `MINGW64_NT` đúng cho git-bash GHA nhưng hidden-imports có thể thiếu
  module Windows-only (`winreg` nằm trong `import` lồng hàm — PyInstaller
  vẫn tìm thấy, verify khi build). Phase 1 có checklist debug.
- **R2**: review Web Store từ chối quyền `debugger` — đường dự phòng đã
  có sẵn trong listing doc (bản lite bỏ `t*`, hoặc enterprise
  ExtensionInstallForcelist).
- **R3**: Gemini free tier đổi quota/chính sách — copy trong onboarding
  phải nói "miễn phí theo chính sách hiện tại của Google", không hứa
  vĩnh viễn. Verify quota thật lúc implement.
- **R4**: freeze `.ps1` sớm quá khi `troly.exe` chưa được kiểm chứng
  trên Windows thật — phase 5 CHỈ chạy sau khi có ít nhất 1 máy Windows
  cài bản CI chạy OK (checklist trong phase 1).

## Out of scope

- Relay/mobile — plan `261120-1500-relay-mobile` riêng, chạy sau đợt này.
- Ký code / notarization.
- Auto-update online (update = exe mới đè code — đã có).
- Installer wizard (`.msi`/`.pkg`) — file đơn đủ cho giai đoạn này.

## Thứ tự thực thi

Phase 1 → 3 → 4 → 5 làm được trên macOS + CI. Phase 2 phần submit là
việc NGƯỜI DÙNG (tài khoản dev $5, nút bấm trên console) — agent chuẩn
bị sẵn mọi thứ, người dùng chỉ upload. Phase 5 sau khi phase 1 kiểm
chứng được trên Windows thật.
