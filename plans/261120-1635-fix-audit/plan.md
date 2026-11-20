---
title: "Vá các lỗi audit 2026-11-20 — parity ps1/py + skill pack + smoke test"
description: "Audit toàn cục phát hiện: chat-bridge.ps1 thiếu /api/save-page (clone-view không lưu được trên Windows — nền tảng chính), clone-trang/trang-moi nằm ngoài skill-packs nên bản đóng gói mất tính năng headline, en pack thiếu bản clone, không có test nào cho ~2000 dòng code nhạy cảm bảo mật, secrets.local.json không chmod 600, doc lệch port"
status: in-progress (phase 1-4 xong; phase 5 chờ máy Windows)
priority: P1
effort: M
branch: main
tags: [bugfix, parity, packaging, tests, docs]
created: 2026-11-20
depends-on: 261120-1420-bridge-auth (đợt 1+2, đã merge)
---

# Vá các lỗi audit 2026-11-20

## Bối cảnh — audit tìm được gì

Review tổng thể repo (chấm ~8/10) phát hiện các lỗi thật, xếp theo mức độ:

| # | Lỗi | Hệ quả |
|---|---|---|
| A | `chat-bridge.ps1` thiếu `POST /api/save-page` (chỉ có trong `.py`) | Trên Windows — nền tảng CHÍNH — nút "Lưu lại trang" trong `web/clone-view.html` gọi `:7682/api/save-page` → 404. Tính năng sửa trang clone chết |
| B | `clone-trang` + `trang-moi` chỉ có trong `.devin/skills/` (active), KHÔNG có trong `.devin/skill-packs/vi/` | `build.sh`/`launcher.py` chỉ bundle skill-packs → học viên cài bản `troly` không có skill clone dù README quảng cáo đây là tính năng đầu bảng + `manifest.json` recipes đã list `/clone-trang` |
| C | `skill-packs/en/` thiếu bản clone | Học viên chọn English mất luôn tính năng |
| D | Không có test nào | ~2000 dòng bridge (token auth, path traversal guard, WS handshake viết tay) không có gì kiểm chứng — drift như lỗi A sẽ tái diễn |
| E | `secrets.local.json` ghi qua `save_json` không `chmod 600` | Token được bảo vệ thì secret cũng phải được — file credential của học viên |
| F | Doc lệch: `PLAN.md` ghi ext-bridge `:7683` (thực tế `:7684`); `skills-system.md` ghi en pack "17 skill" (thực tế 18); `start.bat` comment "mo 2 thu" (mở 4) | Người đọc sau hiểu sai hệ thống |
| G | 8 file đang sửa dở chưa commit (tính năng `extVersion`) | Work-in-progress treo trong working tree |
| H | `my-course/manifest.json` seed có `recipes` hardcode tiếng Việt (`/clone-trang`, `/nen-anh`…) | Học viên English thấy lệnh vi trong sidebar tới khi `/interview` sinh lại manifest |

Nguyên nhân gốc của A+B: **3 con đường chạy** (`.py` cho macOS, `.ps1` cho
Windows, binary đóng gói) trôi khỏi nhau vì không có test parity và không
có quy trình "thêm endpoint/skill → phải chạm cả 3 chỗ".

## Thiết kế tổng thể

Sửa triệt để theo 2 hướng:

1. **Vá lỗi** — port thiếu, đưa skill về đúng pack, chmod secret, sửa doc.
2. **Chặn tái phát** — smoke test tối thiểu chạy được bằng stdlib trên cả
   macOS lẫn Windows (`pwsh` có sẵn PowerShell 5.1+, không cần cài):
   - `tools/test-bridges.py`: test endpoint-level của chat-bridge.py +
     ext-bridge.py (auth, save-page sandbox, brain cmd whitelist).
   - `tools/test-parity.py`: đọc TỈNH cả `chat-bridge.py` lẫn `chat-bridge.ps1`,
     diff tập endpoint — test này FAIL NGAY hôm nay vì save-page, và sẽ bắt
     được mọi drift sau này. Đây là phòng thủ chính chống lỗi A tái diễn.
   - `tools/test-packs.py`: diff `.devin/skills/` vs `skill-packs/<lang>/` —
     mọi skill có recipe trong manifest hoặc được nhắc trong README phải
     thuộc ít nhất một pack.

Test là script stdlib chạy tay (`python3 tools/test-bridges.py`), KHÔNG dựng
framework — đúng triết lý "không dependency" của project.

## Phases

| # | Phase | Nội dung | Link |
|---|-------|----------|------|
| 1 | ps1 parity | port `/api/save-page` + `extVersion` health vào `chat-bridge.ps1`; diff toàn bộ endpoint tìm drift còn sót | [phase-01](./phase-01-ps1-parity.md) |
| 2 | Skill pack parity | `clone-trang`+`trang-moi` vào `skill-packs/vi/`; viết bản `en` (`clone-page`/`new-page`); sửa doc liên quan | [phase-02](./phase-02-skill-pack-parity.md) |
| 3 | Smoke tests | `test-bridges.py` + `test-parity.py` + `test-packs.py` — stdlib, chạy trên máy dev | [phase-03](./phase-03-bridge-tests.md) |
| 4 | Hardening + docs + commit | `chmod 600` secrets ở `.py` (ghi chú ACL Windows ở `.ps1`); sửa `PLAN.md` :7683; commit work `extVersion` đang dở | [phase-04](./phase-04-hardening-docs.md) |
| 5 | Kiểm chứng Windows | checklist tay trên máy Windows thật — mở khoá "chờ test Windows" trong PLAN.md | [phase-05](./phase-05-windows-verify.md) |

## Rủi ro chính

- **R1**: `chat-bridge.ps1` là file **UTF-8 có BOM — bắt buộc giữ**:
  PowerShell 5.1 dùng BOM để nhận encoding; mất BOM → toàn bộ chuỗi tiếng
  Việt trong file (thông báo lỗi, mô tả não) vỡ font trên máy học viên.
  Mọi edit `.ps1` phải ghi lại kèm BOM. Và file HTML do save-page ghi ra
  thì phải **no BOM** — `[IO.File]::WriteAllText` UTF8Encoding($false),
  vì viewer đọc file trực tiếp.
- **R2**: en clone skills dịch sai tên marker `data-cs-*` — marker là
  contract của pipeline, giữ nguyên tiếng Anh trong bản en, chỉ dịch lời dẫn.
- **R3**: parity test quá giòn (mỗi refactor nhỏ cũng fail) → test chỉ diff
  tập endpoint public `/api/*`, không diff implementation.
- **R4**: phase 5 cần máy Windows thật — nếu chưa có, để pending và ghi
  checklist sẵn; không block 4 phase đầu.

## Out of scope (ghi rõ để không scope-creep)

- Gộp `.ps1` vào `.py` hay ngược lại (single-binary ở plan `bridge-auth`
  phase 8 đã hướng tới bỏ hẳn `.ps1` — plan này chỉ vá parity, không
  refactor kiến trúc)
- Relay/mobile (`261120-1500-relay-mobile` đã cover)
- CI/CD pipeline chạy test tự động — test script chạy tay trước khi
  release; CI gắn sau nếu repo có GitHub Actions
- Test cho extension (`background.js`/`content.js`) — cần harness khác,
  để đợt sau
- Khoá GET `my-course/` trên :8080 (trade-off đã quyết, chờ relay)

## Thứ tự thực thi

Phase 1→2→3→4 làm tuần tự trên macOS, commit gọn từng phase. Phase 5 là
việc tay trên máy Windows — checklist để sẵn, chạy khi có máy.
