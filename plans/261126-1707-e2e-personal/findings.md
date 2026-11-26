# Findings — E2E persona "Lan" (Brave thật)

Ngày chạy: 2026-11-26. Tester: Devin (đóng vai Lan — dân văn phòng, không biết code).

## Môi trường test

- Install test: `~/TroLyAI-e2e` (bootstrap từ repo source qua `tools/launcher.py`, VERSION 1.0.3)
- Binary thật `dist/troly` (v1.0.0, adhoc-signed arm64) — test riêng phần Gatekeeper/double-click
- Brave test: instance riêng `--user-data-dir=~/lan-test-brave` (không đụng profile chính)
- Dev stack repo (serve:8080, chat:7682, ext:7684) — dừng trước khi test install
- Fixture: `~/Downloads/lan-test/`
- Não: `devin` CLI 3000.15.14 có sẵn; `gemini` không có

## Điều kiện owner bị thiếu (test nhánh "chưa kết nối")

- **E1**: Brave profile chưa login Zalo/Google/Outlook/Canva → test nhánh chưa-kết-nối + hint
- **E2**: Không có WordPress test site → test nhánh chưa kết nối + lỗi sai thông tin
- **E3**: Không có Zalo OA token → test hint dẫn lấy token
- **E5**: Trang mẫu clone — tự chọn trang public đơn giản

## Bảng findings

| ID | Phase | Mức | Màn hình | Hiện tượng | Vì sao Lan kẹt | Fix | Status |
|----|-------|-----|----------|-----------|----------------|-----|--------|
| F-001 | Setup/A | P1 | Terminal | `python3 -m pip install -r requirements.txt` (SETUP Bước 5.5) fail `externally-managed-environment` trên Homebrew Python | Lan chạy đúng hướng dẫn vẫn lỗi chữ đỏ; skill Excel/Word không cài được deps. Skill `lam-excel` cũng chỉ agent chạy đúng lệnh fail này | Đề xuất: thêm `tools/ensure-deps.py` tạo `.venv` trong install dir + skill trỏ venv; hoặc doc chỉ `--break-system-packages` (xấu) | open |
| F-002 | A1 | P1 | Gatekeeper | `dist/troly` chỉ adhoc-signed → `spctl` reject; file "tải về" (quarantine) bị macOS chặn, Lan thấy dialog đe doạ + không có nút Open trực tiếp | Lan tưởng file virus; phải biết mẹo chuột-phải→Open (SETUP có ghi nhưng Lan chưa chắc đọc tới) | Owner có Apple Developer account → fix đúng: codesign Developer ID + notarize trong build pipeline (build.sh/troly.spec đang `codesign_identity=None`, không bước ký nào) | open — cần cert của owner |
| F-003 | A4/C6 | P0 | Portal | Mở 2 bản cài / token trôi (bridge orphan giữ token cũ) → portal vẫn load bình thường nhưng MỌI API trả 401 `thiếu hoặc sai mã kết nối` — UI không báo gì, dashboard trông "sống" mà chết | Lan thấy trang mở bình thường nhưng chat không đi, kết nối trống — không biết vì sao, không có chỗ nhập lại mã | **Đã fix**: thêm check token — khi `bfetch` gặp 401 liên tiếp → banner "mã kết nối không còn đúng — mở lại bằng file start/troly" + nút nhập mã tay | in-progress |
| F-004 | A2/B | P0 | Onboarding | Trang thiết lập lần đầu KHÔNG BAO GIỜ hiện: check `!c.language` nhưng seed `config.json` luôn ship `"language":"vi"` → redirect không chạy, Lan rớt thẳng vào dashboard chưa cài gì. KÉO THEO: `_h_setup` gate theo `language` → setup lần đầu cũng bị gate chờ card trong chat → nếu redirect có thì loop vĩnh viễn | Lan không được dẫn qua: tên, quyền folder, não, kết nối, extension — toàn bộ guided setup bị bỏ qua | **Đã fix**: seed config bỏ key `language` (về `{"learner_name":""}`) → fresh → `!c.language` redirect đúng + setup lần đầu ungated ghi ngay → Done → portal mở được + card duyệt permissions/bot đợi trong chat | fixed ✓ (retest pass) |
| F-005 | B5 | P2 | Onboarding folder | Checkbox ~/Downloads ~/Desktop ~/Documents tốt, nhưng ô "Thêm folder khác…" vẫn đòi gõ path | Lan không biết `~` là gì; gõ path tay là điểm yếu duy nhất — đã có validate lỗi êm | Đề xuất: đổi label thành tên hiển thị ("Downloads", "Desktop") + nút duyệt folder nếu làm được | open |
| F-006 | B/C | P2 | Card xin phép | Dialog native osascript hiện đúng, nổi trên browser; nhưng card chat chỉ có "Không đồng ý" + chữ dài; dialog spawn nhiều cái chồng khi chạy lại | Lan thấy nhiều dialog lạ, có dialog stale từ lần chạy trước ("Chạy lại thiết lập…") gây rối | Đề xuất: gộp N request cùng onboarding thành 1 dialog; ẩn dialog stale | open |
| F-007 | B10 | P2 | Onboarding rerun | Chạy lại onboarding → tạo bot TRÙNG (hang-marketing + hang-marketing-2), không có cảnh báo "đã cài rồi" | Lan lỡ mở lại trang setup → sinh bot đôi | Đề xuất: onboarding check config.language → hiện "đã cài rồi, vào portal" | open |
| F-008 | C7 | P1 | Card xin phép | MỖI tool call của agent spawn 1 dialog native — tiêu đề CHUNG CHUNG "Trợ lý muốn làm một việc", không nói việc gì. Việc "tóm tắt file Excel" 1 câu → 6+ dialog liên tiếp trong 7+ phút | Lan phải bấm "Đồng ý" mù nhiều lần; không biết đang duyệt cái gì; bỏ đi uống nước là việc đứng | Đề xuất: (1) dialog phải ghi việc cụ thể bằng lời thường ("mở file báo cáo tháng 11 để đọc"); (2) allowlist theo phiên cho đọc-trong-folder-đã-cấp — đã xin quyền Downloads rồi thì đọc thêm file trong đó không hỏi lại | open |
| F-009 | C7/E | P1 | Chat (deps) | Máy mới thiếu openpyxl → agent chạy `pip3` (fail PEP-668 — đúng F-001 sống trong chat) rồi lần mò `which`, `python3.12`, `python3.14` mất vài phút vẫn chưa xong | Lan nhờ tóm tắt 1 file mà chờ gần 10 phút, không biết chuyện gì đang xảy ra | Fix gốc: deps ship sẵn trong bundle (venv trong install dir); agent nên có đường fallback nhanh (đọc xlsx bằng zipfile+XML thuần) thay vì săn python | open |
| F-010 | C | P2 | Nhãn tool trong chat | Label hiện lệnh thô: "Ran python3.12", "Ran ls, grep, echo", "việc nhỏ" | Lan thấy chữ lạ nửa kỹ thuật nửa mơ hồ — "việc nhỏ" thì vô nghĩa | Đề xuất: dịch label sang lời thường ("đang mở file…", "đang tìm trong Downloads…") | open |
| F-011 | I8 | P2 | Card xin phép / máy ngủ | Máy lock/ngủ giữa lúc agent chờ duyệt → dialog nằm sau màn hình khoá, không tương tác được; TTL 600s tự hết → coi như từ chối | Lan đi pha cà phê quên bấm → việc fail sau 10 phút, không rõ vì sao | Đề xuất: card chat hiện countdown TTL + khi hết hạn báo rõ "hết giờ duyệt, nhờ lại nhé" thay vì lỗi chung | open |
| F-012 | C7 | P1 | Chat | Tool call cuối run fail (hết hạn duyệt) → run `done` NHƯNG agent không gửi câu kết nào. UI dừng ở "Mình mở ra đọc nhé:" + "· Xong: việc nhỏ" — không báo thất bại, không gợi ý làm lại | Lan chờ mãi không thấy kết quả, tưởng trợ lý còn đang làm hoặc bị hỏng — không biết phải nhắn lại | Fix: khi run kết thúc mà tool cuối failed/denied → chat phải chèn ít nhất 1 câu "việc X chưa làm được vì chưa được duyệt — nhờ lại nhé" | open |
| F-013 | D1 | **P0** | Extension | `manifest.json` `externally_connectable.matches` dùng pattern có port `*://localhost:8080/*` — Chromium reject "Invalid match pattern (Invalid port)" → **extension không load được trên mọi trình duyệt**. Toàn bộ cánh tay trình duyệt (đọc Zalo/Outlook, mo-web, 60% giá trị app) chết từ gốc | Lan Load unpacked xong gặp dialog "Failed to load extension" — hết đường | **Đã fix**: matches bỏ port (`*://localhost/*` — match pattern spec không hỗ trợ port) + kiểm tay port trong `onMessageExternal` (`sender.url/origin` phải là localhost:8080). Rebuild zip. **Retest: ext load + auto-pair từ portal OK — `{"connected":true,"extVersion":"0.2"}`** | fixed ✓ |
| F-014 | A/D | P1 | Portal | `serve.py` serve `/` bằng file `/web/index.html` NHƯNG không redirect → link tương đối (`styles.css`, `app.js`) resolve về `/styles.css` → 404 → **trang trắng mất hết CSS** khi Lan gõ `localhost:8080` thay vì `/web/` | Lan gõ địa chỉ thiếu phần đuôi (rất tự nhiên) → trang xấu trần trụi, tưởng hỏng | **Đã fix**: `/` và `/web` (không slash) → 301 `/web/` giữ query. Verify: `/: 301 -> /web/`, `final: 200 /web/` | fixed ✓ |
