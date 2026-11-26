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


---

# Run 3 — full reset lần 2 (2026-11-26 tối)

Reset sạch `~/TroLyAI-e2e` + `~/lan-test-brave`, fixture lan-test về nguyên trạng. Install mới bằng `TROLY_DATA=~/TroLyAI-e2e launcher.py run` (supervisor foreground).

## Kết quả

| Phase | Run 3 |
|---|---|
| A cài đặt | ✅ Fresh install lên đủ 4 port, `/`→301→200, ensure-deps dựng venv ngay |
| B onboarding | ✅ 7 bước trơn tru: tên "Lan" hiện ở portal ("Chào Lan!"), 2 thẻ duyệt qua dialog native, Hằng active, KHÔNG trùng bot (B10 của run 1 không tái hiện) |
| C chat | ✅ C2 "Chào Lan, mình là Hằng — trợ lý marketing của bạn" đúng vai; warn "vừa nạp lại quyền mới" (F-015) hiện đúng sau khi cấp quyền |
| D apps | ✅ partial+: Settings modal đủ, "Mở trang" Zalo mở được tab chat.zalo.me qua extension, probe tự cập nhật "đang mở sẵn — nhờ được ngay". **F-020 P3**: outlook/canva báo "trình duyệt chưa nối" trong khi ext đã nối |
| E / phỏng vấn | ✅ **Flagship**: `/phong-van` nhận ra đã có khoá học → hỏi bài mới → Lan kêu "nén ảnh" → sinh trọn lesson-03: guide+exercise+13 slide+video.mp4 ~2 phút kèm .vtt+sample-files (6 ảnh ~47MB), manifest tự cập nhật, portal hiện sau reload. Agent còn tự quét "đơn giản/chỉ cần/dễ" để tuân AGENTS.md |
| F bài học | ✅ Slide deck bài 3 render đẹp (dark theme, 1/13, nav ‹ ›) |
| I đời thường | ✅ Kill chat-bridge → watchdog tự respawn (~3s), não sống, prompt sau chạy bình thường ("Pong! Mình vẫn đây") |
| W | ✅ Settings modal + slide bài 3: sạch jargon, giải thích "chìa khoá nhà", chấm xanh/xám |
| J suite | ✅ test-packs / test-gates / test-distribution đều PASS |

## Findings mới run 3
- F-020 (P3): hint "trình duyệt chưa nối" mâu thuẫn khi ext đã nối.

## Ghi chú vận hành
- Lần chạy `launcher.py run` đầu in "đang chạy sẵn" rồi thoát vì phát hiện orphans từ run trước → phải kill orphans + chạy lại. Nhỏ nhưng là trap khi reset thủ công.

## Run 4 — retest /phong-van sau rework (công cụ + guide, bỏ slide/video)

Reset toàn bộ (xoá install + Brave profile + fixture artifacts), fresh
install, onboarding qua CDP thay orca. Kết quả **PASS toàn tuyến**:

- `/phong-van` nhận ra khoá học có sẵn → chỉ hỏi thêm việc mới, không
  phỏng vấn lại.
- Với pain "lọc khách theo tỉnh" agent chọn đúng dạng **skill có sẵn**
  (`/loc-khach`) — không tạo skill trùng.
- Sinh `lesson-03-tach-khach-theo-tinh/` **chỉ chứa guide.md** — không
  slides.html, exercise.md, video-script.md, sample-files.
- Guide 6 bước dùng đúng "từ vựng bước" (Gõ lệnh / Chỉ file / Duyệt
  quyền / Mở kết quả), agent đọc CSV thật và phát hiện 4 khách thiếu
  tỉnh → ghi vào lời chốt.
- Manifest: `has_slides:false, has_video:false, has_exercise:false` →
  portal chỉ hiện tab **Hướng dẫn**, guide render thành **wizard
  Bước 1/9** (intro + 6 bước + 2 bảng phụ lục), nav Tiếp/Quay lại/Xem
  hết hoạt động. Shot: `shots/wizard-new-lesson.png`.
- Thời gian sinh bài: ~1-2 phút (trước ~15 phút do render video).

Finding mới (nhỏ): khi click gallery không trúng card, onboarding tạo
bot theo tên học viên + role office mặc định ("Lan — văn phòng") — hơi
lẫn giữa tên người và tên bot.

## Run 5 — walkthrough end-to-end trên công cụ thật (kiến trúc mới)

Full reset (install + Brave profile), binary `dist/troly` rebuild sau
rename `my-course`→`workspace`. Đây là run đầu test **kiến trúc bộ công
cụ + walkthrough tương tác** — thay hoàn toàn slide/video/bài tập.

### Flagship — Phase F

`/phong-van` → Lan kể pain "cộng điểm KPI xếp hạng team mỗi tháng" →
agent đọc file Excel mẫu thật (phát hiện file gửi sai loại, xin file
đúng) → sinh `tool-03-xep-hang-kpi` gồm skill + `guide.md` +
`walkthrough.json` 9 bước.

Walkthrough chạy **đủ 9/9 bước trên công cụ thật**:

- `prompt` gửi thẳng `/xep-hang-kpi <path>` vào chat thật — `{{file}}`
  từ `pick-file` chèn đúng
- `wait-perm`/`wait-run` tự qua bước khi duyệt/xong (đã fix cursor poll
  hứng event đến sớm — F-022)
- `open` bấm "Mở trong Finder" reveal thật folder kết quả
- `check` 2 nút Đúng/Chưa thấy, `done` chốt "lần sau gõ /xep-hang-kpi"
- Agent xử lý thật song song: ra `workspace/ket-qua/kpi-xep-hang-thang-10.xlsx`
- Resume qua localStorage, chạy lại về đầu, xoá công cụ → `.trash`,
  manifest lệch/JSON hỏng → nút ẩn êm

### Fix phát sinh trong run (đã commit)

- **F-025/F-026 (P0)**: chat-bridge không lên được khi não fail —
  call_sync chờ hết 30s (waiter không được wake khi não chết) + check
  `result:{}` falsy bỏ session/new. Cả hai làm mọi prompt "chưa có
  session" trên máy não lỗi → fix xong, suite xanh.
- **F-021**: wizard guide chồng walkthrough → guide có walkthrough giờ
  là tài liệu tra cứu, wizard chỉ cho bài cũ.
- **F-023**: bot-chip đè tabs.
- Terminal tắt mặc định (config.terminal + POST /api/config) — nhẹ RAM,
  bật lại trong Cài đặt. Bỏ header learner-name (trùng lời chào) + bỏ
  dòng tool-status trong chat.
- `/hoc-bai`→`/huong-dan` (en `/tutor`→`/guide`) đồng bộ tên tab.

### Suite cuối run — tất cả PASS

test-bridges **151/0**, gates 20 endpoint, packs 21/21/21, parity,
walkthrough, content-guard, distribution, fleet, worker.

### Nhận xét chung

Kiến trúc "bộ công cụ + walkthrough" hoạt động đúng thiết kế: công cụ
sinh ra dùng được ngay qua walkthrough tương tác, không cần đọc guide
trước. Ba điểm giá trị nhất: (1) prompt bước gửi thẳng vào chat —
walkthrough "làm thật" chứ không chỉ xem; (2) wait-* tự qua bước nhờ
event stream; (3) file kết quả ra thật, Finder mở được ngay.
