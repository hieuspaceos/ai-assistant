# Report — E2E persona "Lan" (run 2, sau full reset)

Ngày: 2026-11-26 (đợt 2). Environment reset sạch: `~/TroLyAI-e2e` + `~/lan-test-brave` xoá dựng lại, fixture `~/Downloads/lan-test/` giữ.

## Kết quả theo phase

| Phase | Trạng thái | Ghi chú |
|---|---|---|
| A cài đặt | ✅ | Fresh install chạy đúng, portal/onboarding redirect đúng (F-004 fixed). F-002 binary chưa ký Apple vẫn open — chờ cert owner |
| B onboarding | ✅ PASS | 7 bước chạy trọn vẹn. **F-005 native folder picker hoạt động** (nút "Chọn bằng cách duyệt…" mở hộp macOS, path `~/...` dedupe preset). **F-007 rerun guard PASS** (mở lại onboarding → "Bạn đã cài xong rồi!") |
| C chat | ✅ | C2 reply đúng vai + 1 câu hỏi. C7 Excel tóm tắt đầy đủ nhờ **F-009 venv auto-provision** (ensure-deps chạy lúc boot → `.venv` có openpyxl/docx). F-012 warn-on-silent-fail đã ship |
| D apps | 🟡 partial | Extension auto-pair OK ("Đã nối trình duyệt", F-013 fixed). Màn Cài đặt: chấm xanh/xám + hint từng app, token + giải thích "chìa khoá nhà". App thật (Zalo/Google/Outlook) cần owner login — E1–E5 blocked |
| E skills | ✅ 5 skills end-to-end | tom-tat-file (Excel), gom-file (15 file→da-gom), nen-anh (10 png→webp 50%, tên web-safe), loc-khach (50 khách→10 file, tự chuẩn hoá biến thể tỉnh + hỏi lại 'ĐN' mơ hồ + tách 4 khách thiếu tỉnh), lam-word (điền ABC vào mẫu, giữ 5 placeholder). Mọi skill: đề xuất→xác nhận→làm→báo cáo, gốc không đụng, mời dùng /lệnh lần sau. Skills còn lại cần app/web login (owner) |
| F bài học | ✅ | **F-017** fixed, slide bài 0 + lesson 1/2 OK; tab Hướng dẫn có video player thật (mp4 ~2MB, has_video:true) |
| G workflows | ✅ | "Dọn folder Downloads" chạy được — đối chiếu checklist tự báo cáo số file, có đường undo |
| H bots | ✅ | Selector ▾ đủ 4 mục (Hằng/chung/tạo mới/nhập file); đổi bot qua thẻ xác nhận trong chat + dialog native, default nút 'Không' (an toàn); round-trip Hằng↔chung OK, bot.md update đúng |
| I đời thường | ✅ core | Kill brain → báo 'đang khởi động lại trợ lý' + tự respawn, tin sau nhận OK; wrong token → banner 🔑 hướng dẫn mở lại file start (F-003 retest PASS); F-011 TTL hint hiện trên thẻ; F-015 fixed; I8 lock-screen observed run 1 |
| W rà chữ | ✅ | Headless pass + visual pass 2 màn (portal, chat): sạch jargon, quick-chips thân thiện. F-019 nit: vài tool label generic/path thô |
| J suite | ✅ | test-packs PASS, test-gates PASS (18 endpoint), test-content-guard static PASS (live fail do cổng chiếm — môi trường), test-distribution PASS |

## Findings đợt 2 (thêm F-015 → F-018)

- **F-015 P1 (fixed)**: quyền folder cấp giữa phiên không vào sandbox não đang chạy → ghi bị chặn, agent bảo Lan restart app. Fix: `perm_dirty` → prompt kế respawn não. Retest pass.
- **F-016 P2 (noted)**: a11y index đổi theo DOM — thuộc test harness.
- **F-017 P1 (fixed)**: `intro/` thiếu trong launcher CODE_DIRS → bài 0 "Làm quen" 404. Đã fix + retest.
- **F-018 P2 (open)**: run_id reset sau bridge restart → history.jsonl trộn phiên.
- **F-019 P3 (open)**: vài tool label còn generic ('Làm một việc') / path thô `./my-course/...`.

## Ghi nhận thêm run 2
- Không một dialog xin phép nào trong các run file-ops trên folder đã cấp → F-008 mitigation hoạt động.
- Agent tự invoke skill đúng tên khi user nói lời thường (nen-anh, loc-khach, lam-word, gom-file, tom-tat-file).
- Agent hỏi lại khi dữ liệu mơ hồ ('ĐN') thay vì đoán — đúng chuẩn an toàn.

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
