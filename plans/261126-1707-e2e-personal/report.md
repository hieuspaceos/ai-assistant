# Report — E2E persona "Lan" (chạy tới Phase C)

Ngày: 2026-11-26 · Tester: Devin đóng vai Lan (dân văn phòng, không biết code)
Môi trường + bảng findings đầy đủ: `findings.md`

## Tóm tắt điều hành

Sản phẩm **đạt ở tầng hội thoại** — giọng agent, cách báo cáo, quy trình xin
phép đều đúng với người không biết code. Nút nghẽn lớn nhất nằm ở **lớp quyền
và môi trường máy thật**: duyệt mù theo từng lệnh, thiếu deps Python, binary
chưa ký, và một số chỗ "chết lặng" không báo gì.

**Đã fix trong session**: F-004 (P0 — onboarding không bao giờ hiện, đã retest
pass end-to-end), F-003 (P0 — portal im lặng khi token sai, banner 401 đã code),
F-013 (**P0 — extension không load được trên mọi trình duyệt** do match pattern
có port; đã fix + retest auto-pair `connected:true`), F-014 (P1 — `localhost:8080`
không redirect → trang mất CSS; đã fix 301).

**P0/P1 còn mở** (chi tiết trong findings.md):

- **F-008 P1 — duyệt mù theo từng lệnh**: việc "tóm tắt file Excel" 1 câu → 6+
  dialog "Trợ lý muốn làm một việc" không ghi việc gì, kéo dài 7+ phút.
  → Dialog phải nói việc cụ thể + đọc trong folder đã cấp không hỏi lại.
- **F-012 P1 — run fail thì im lặng**: tool cuối fail (hết hạn duyệt) → agent
  không gửi câu kết; Lan chờ trong vô vọng.
- **F-009/F-001 P1 — thiếu deps**: openpyxl không có trên máy mới → agent săn
  python mất phút, `pip3` fail PEP-668. → Ship venv deps trong bundle.
- **F-002 P1 — binary chưa ký Apple**: Gatekeeper chặn file tải về; owner đã có
  tài khoản Apple Developer → codesign + notarize trong pipeline.
- **F-003 P0 — banner 401**: đã code, cần retest trên Brave.

## Điểm sáng — giữ nguyên

- Agent nói chuyện đúng chuẩn AGENTS.md: kết luận trước, gom nhóm thay vì liệt
  kê, chỉ kể bất thường cần quyết định, đúng 1 câu hỏi cuối kèm đề xuất.
- Vòng file-ra-file hoàn chỉnh (CSV): tự tìm file trong folder con, tóm tắt
  phát hiện dữ liệu lộn xộn, dọn về 1 kiểu ghi, xuất file mới có BOM UTF-8
  (Excel mở đúng dấu), file gốc giữ nguyên, nói rõ file nằm đâu.
- Onboarding sau fix: 7 bước trôi chảy, quyền folder dạng checkbox, không đòi
  gõ path cho các ngăn quen thuộc.
- i18n vi/en parity gần tuyệt đối; 4 trang chính không lộ jargon.
- Test suite: test-packs ✅ test-gates ✅ test-content-guard (tĩnh) ✅.

## Coverage

| Phase | Trạng thái | Ghi chú |
|---|---|---|
| A — cài đặt & mở đầu | ✅ | Gatekeeper reject (F-002); launcher/install OK |
| B — onboarding | ✅ | F-004 fixed & retest; F-005/006/007 mở |
| C — portal & chat | 🟡 | C2/C3/C7 xong (F-008→012); C8–C11 mép chưa test |
| D — kết nối apps | 🟡 | F-013 fixed → ext load + auto-pair OK, probe "đang hoạt động"; còn chờ login E1–E5 cho app thật |
| E — 20 skills | 🟡 | tom-tat-file qua lời thường PASS end-to-end; cánh tay trình duyệt đã sống (F-013) |
| F — bài học | ⏸ | Manifest/slides có sẵn, chưa click qua UI |
| G — workflows | ⏸ | 4 workflow seed sẵn, chưa chạy qua UI |
| H — bots | ⏸ | Hằng active đúng; menu bot chưa rà |
| I — đời thường xấu | 🟡 | I8 máy-ngủ xảy ra thật → F-011/F-012 |
| W — rà chữ | 🟡 | Code-audit xong (parity, jargon); chưa rà trực quan |
| J — chốt | 🟡 | 3/4 suite PASS; content-guard live fail do cổng bị chiếm |

## Việc còn lại (theo thứ tự)

1. Owner mở khoá máy khi test chạy (dialog xin phép nằm sau màn khoá).
2. Owner cung cấp E1–E5: login Zalo/Google/Outlook/Canva trong profile test,
   WP test + app password, OA token → mở khoá Phase D và nửa Phase E.
3. Cài openpyxl vào môi trường test (hoặc ship venv) → retest case Excel.
4. Fix F-008 + F-012 (hai P1 ảnh hưởng mọi luồng chat) → retest C7.
5. Codesign + notarize `dist/troly` bằng tài khoản Apple Developer → F-002.
6. Retest banner 401 (F-003) trên Brave thật.
7. Chạy nốt C8–C11, F, G, H, I còn lại, W trực quan.
