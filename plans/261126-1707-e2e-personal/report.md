# Report — E2E persona "Lan" (run 2, sau full reset)

Ngày: 2026-11-26 (đợt 2). Environment reset sạch: `~/TroLyAI-e2e` + `~/lan-test-brave` xoá dựng lại, fixture `~/Downloads/lan-test/` giữ.

## Kết quả theo phase

| Phase | Trạng thái | Ghi chú |
|---|---|---|
| A cài đặt | ✅ | Fresh install chạy đúng, portal/onboarding redirect đúng (F-004 fixed). F-002 binary chưa ký Apple vẫn open — chờ cert owner |
| B onboarding | ✅ PASS | 7 bước chạy trọn vẹn. **F-005 native folder picker hoạt động** (nút "Chọn bằng cách duyệt…" mở hộp macOS, path `~/...` dedupe preset). **F-007 rerun guard PASS** (mở lại onboarding → "Bạn đã cài xong rồi!") |
| C chat | ✅ | C2 reply đúng vai + 1 câu hỏi. C7 Excel tóm tắt đầy đủ nhờ **F-009 venv auto-provision** (ensure-deps chạy lúc boot → `.venv` có openpyxl/docx). F-012 warn-on-silent-fail đã ship |
| D apps | 🟡 partial | Extension auto-pair OK ("Đã nối trình duyệt", F-013 fixed). Màn Cài đặt: chấm xanh/xám + hint từng app, token + giải thích "chìa khoá nhà". App thật (Zalo/Google/Outlook) cần owner login — E1–E5 blocked |
| E skills | ✅ core | Excel summary + gom-file end-to-end: 15 file → da-gom/3 nhóm, gốc giữ nguyên. Skill `gom-file` tự invoke |
| F bài học | ✅ sau fix | **F-017**: `intro/` thiếu trong CODE_DIRS → bài 0 lỗi 404 thô — đã fix, slide đẹp |
| G workflows | ✅ | "Dọn folder Downloads" chạy được — đối chiếu checklist tự báo cáo số file, có đường undo |
| H bots | ✅ | Bot Hằng (marketing) activate, selector đổi bot OK |
| I đời thường | 🟡 partial | F-011 countdown hint ship. **F-015 mới**: quyền cấp giữa chừng không ăn vào phiên đang chạy — đã fix bằng perm_dirty respawn |
| W rà chữ | ✅ headless | i18n vi/en parity tốt; jargon chỉ trong comment code; 1 chỗ "chat-bridge" còn trong câu lỗi |
| J suite | ✅ | test-packs PASS, test-gates PASS (18 endpoint), test-content-guard static PASS (live fail do cổng chiếm — môi trường), test-distribution PASS |

## Findings đợt 2 (thêm F-015 → F-018)

- **F-015 P1 (fixed)**: quyền folder cấp giữa phiên không vào sandbox não đang chạy → ghi bị chặn, agent bảo Lan restart app. Fix: `perm_dirty` → prompt kế respawn não. Retest pass.
- **F-016 P2 (noted)**: a11y index đổi theo DOM — thuộc test harness.
- **F-017 P1 (fixed)**: `intro/` thiếu trong launcher CODE_DIRS → bài 0 "Làm quen" 404. Đã fix + retest.
- **F-018 P2 (open)**: run_id reset sau bridge restart → history.jsonl trộn phiên (dashboard đếm sai).

## Fix chưa commit (đợt 2)

- `tools/chat-bridge.py` — perm_dirty respawn (F-015), pick-folder endpoint (F-005), _perm_title/_tool_title (F-008/F-010), _native_dialog_lock (F-006), F-012 warn
- `tools/launcher.py` — intro/ vào CODE_DIRS (F-017), ensure-deps hook (F-009)
- `tools/ensure-deps.py` — mới, venv auto-provision
- `web/onboarding.html` — pick-folder button, F-007 guard
- `web/chat.html` — F-011 countdown hint, F-010 label
- `tools/test-gates.py` — khai /api/pick-folder OPEN_OK
- `tools/content_guard.py`, `tools/gen-sandbox.py` — allowlist + deny-write (F-008)
- `findings.md`, `report.md`

## Còn lại (blocker owner)

- F-002: binary cần Apple Developer cert ký (owner đã có tài khoản)
- D real apps: Zalo/Google/Outlook/Canva login trên Brave test (E1–E5)
- Phase W trực quan: rà chữ trên screenshots từng màn (một phần đã qua headless)
