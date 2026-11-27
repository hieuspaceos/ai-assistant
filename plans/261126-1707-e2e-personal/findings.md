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
| F-001 | Setup/A | P1 | Terminal | `python3 -m pip install -r requirements.txt` (SETUP Bước 5.5) fail `externally-managed-environment` trên Homebrew Python | Lan chạy đúng hướng dẫn vẫn lỗi chữ đỏ; skill Excel/Word không cài được deps. Skill `lam-excel` cũng chỉ agent chạy đúng lệnh fail này | Đề xuất: thêm `tools/ensure-deps.py` tạo `.venv` trong install dir + skill trỏ venv; hoặc doc chỉ `--break-system-packages` (xấu) | fixed (ensure-deps.py + .venv trong install, launcher chạy mỗi boot, skills trỏ .venv/bin/python) |
| F-002 | A1 | P1 | Gatekeeper | `dist/troly` chỉ adhoc-signed → `spctl` reject; file "tải về" (quarantine) bị macOS chặn, Lan thấy dialog đe doạ + không có nút Open trực tiếp | Lan tưởng file virus; phải biết mẹo chuột-phải→Open (SETUP có ghi nhưng Lan chưa chắc đọc tới) | Owner có Apple Developer account → fix đúng: codesign Developer ID + notarize trong build pipeline (build.sh/troly.spec đang `codesign_identity=None`, không bước ký nào) | fixed — `tools/sign-macos.sh`: Developer ID ký (hardened runtime + entitlements.plist cho Python.framework cross-team) → notarytool `--wait` → verify quarantine thật. Profile `troly-notary` trong keychain. Binary hiện qua Gatekeeper sạch |
| F-003 | A4/C6 | P0 | Portal | Mở 2 bản cài / token trôi (bridge orphan giữ token cũ) → portal vẫn load bình thường nhưng MỌI API trả 401 `thiếu hoặc sai mã kết nối` — UI không báo gì, dashboard trông "sống" mà chết | Lan thấy trang mở bình thường nhưng chat không đi, kết nối trống — không biết vì sao, không có chỗ nhập lại mã | **Đã fix + retest run 6**: `bfetch` gặp 401 → banner vàng "mã kết nối…mở lại bằng file start", token đúng trở lại thì banner tự tắt. Verify bằng cách nhét token rác → 401 → banner hiện; token thật → 200 → banner tắt | fixed |
| F-004 | A2/B | P0 | Onboarding | Trang thiết lập lần đầu KHÔNG BAO GIỜ hiện: check `!c.language` nhưng seed `config.json` luôn ship `"language":"vi"` → redirect không chạy, Lan rớt thẳng vào dashboard chưa cài gì. KÉO THEO: `_h_setup` gate theo `language` → setup lần đầu cũng bị gate chờ card trong chat → nếu redirect có thì loop vĩnh viễn | Lan không được dẫn qua: tên, quyền folder, não, kết nối, extension — toàn bộ guided setup bị bỏ qua | **Đã fix**: seed config bỏ key `language` (về `{"learner_name":""}`) → fresh → `!c.language` redirect đúng + setup lần đầu ungated ghi ngay → Done → portal mở được + card duyệt permissions/bot đợi trong chat | fixed ✓ (retest pass) |
| F-005 | B5 | P2 | Onboarding folder | Checkbox ~/Downloads ~/Desktop ~/Documents tốt, nhưng ô "Thêm folder khác…" vẫn đòi gõ path | Lan không biết `~` là gì; gõ path tay là điểm yếu duy nhất — đã có validate lỗi êm | Đề xuất: đổi label thành tên hiển thị ("Downloads", "Desktop") + nút duyệt folder nếu làm được | fixed — có nút "Chọn bằng cách duyệt…" qua `/api/pick-folder` (osascript), ô gõ tay giữ làm fallback |
| F-006 | B/C | P2 | Card xin phép | Dialog native osascript hiện đúng, nổi trên browser; nhưng card chat chỉ có "Không đồng ý" + chữ dài; dialog spawn nhiều cái chồng khi chạy lại | Lan thấy nhiều dialog lạ, có dialog stale từ lần chạy trước ("Chạy lại thiết lập…") gây rối | Đề xuất: gộp N request cùng onboarding thành 1 dialog; ẩn dialog stale | fixed — `_native_dialog_lock` xếp hàng dialog, kill khi card huỷ/evict, spawn lại check pending trước |
| F-007 | B10 | P2 | Onboarding rerun | Chạy lại onboarding → tạo bot TRÙNG (hang-marketing + hang-marketing-2), không có cảnh báo "đã cài rồi" | Lan lỡ mở lại trang setup → sinh bot đôi | Đề xuất: onboarding check config.language → hiện "đã cài rồi, vào portal" | fixed — `showAlready()` khi `config.language` đã có, link "cài lại từ đầu" vẫn có cho ai thật sự muốn |
| F-008 | C7 | P1 | Card xin phép | MỖI tool call của agent spawn 1 dialog native — tiêu đề CHUNG CHUNG "Trợ lý muốn làm một việc", không nói việc gì. Việc "tóm tắt file Excel" 1 câu → 6+ dialog liên tiếp trong 7+ phút | Lan phải bấm "Đồng ý" mù nhiều lần; không biết đang duyệt cái gì; bỏ đi uống nước là việc đứng | Đề xuất: (1) dialog phải ghi việc cụ thể bằng lời thường ("mở file báo cáo tháng 11 để đọc"); (2) allowlist theo phiên cho đọc-trong-folder-đã-cấp — đã xin quyền Downloads rồi thì đọc thêm file trong đó không hỏi lại | fixed — `_perm_title`/`_tool_title` sinh nhãn việc cụ thể từ kind+path ("Trợ lý muốn đọc file…", "Chạy: python"), dialog serialize |
| F-009 | C7/E | P1 | Chat (deps) | Máy mới thiếu openpyxl → agent chạy `pip3` (fail PEP-668 — đúng F-001 sống trong chat) rồi lần mò `which`, `python3.12`, `python3.14` mất vài phút vẫn chưa xong | Lan nhờ tóm tắt 1 file mà chờ gần 10 phút, không biết chuyện gì đang xảy ra | Fix gốc: deps ship sẵn trong bundle (venv trong install dir); agent nên có đường fallback nhanh (đọc xlsx bằng zipfile+XML thuần) thay vì săn python | fixed cùng F-001 — `.venv/` có sẵn openpyxl 3.1.5, AGENTS/skills trỏ venv |
| F-010 | C | P2 | Nhãn tool trong chat | Label hiện lệnh thô: "Ran python3.12", "Ran ls, grep, echo", "việc nhỏ" | Lan thấy chữ lạ nửa kỹ thuật nửa mơ hồ — "việc nhỏ" thì vô nghĩa | Đề xuất: dịch label sang lời thường ("đang mở file…", "đang tìm trong Downloads…") | fixed — `_tool_title` map "Ran `python3.12…`" → "Chạy: python", read/write → "Đọc/Ghi file…" |
| F-011 | I8 | P2 | Card xin phép / máy ngủ | Máy lock/ngủ giữa lúc agent chờ duyệt → dialog nằm sau màn hình khoá, không tương tác được; TTL 600s tự hết → coi như từ chối | Lan đi pha cà phê quên bấm → việc fail sau 10 phút, không rõ vì sao | Đề xuất: card chat hiện countdown TTL + khi hết hạn báo rõ "hết giờ duyệt, nhờ lại nhé" thay vì lỗi chung | fixed — `gave up:true` → warn "hết giờ xin phép — việc đang chờ đã dừng" + não nhận "hết giờ chờ học viên duyệt" (khác "không đồng ý") |
| F-012 | C7 | P1 | Chat | Tool call cuối run fail (hết hạn duyệt) → run `done` NHƯNG agent không gửi câu kết nào. UI dừng ở "Mình mở ra đọc nhé:" + "· Xong: việc nhỏ" — không báo thất bại, không gợi ý làm lại | Lan chờ mãi không thấy kết quả, tưởng trợ lý còn đang làm hoặc bị hỏng — không biết phải nhắn lại | Fix: khi run kết thúc mà tool cuối failed/denied → chat phải chèn ít nhất 1 câu "việc X chưa làm được vì chưa được duyệt — nhờ lại nhé" | fixed — `broadcast()` theo `_turn_fail`, chèn warn trước `done` khi tool cuối fail mà không có text theo sau |
| F-013 | D1 | **P0** | Extension | `manifest.json` `externally_connectable.matches` dùng pattern có port `*://localhost:8080/*` — Chromium reject "Invalid match pattern (Invalid port)" → **extension không load được trên mọi trình duyệt**. Toàn bộ cánh tay trình duyệt (đọc Zalo/Outlook, mo-web, 60% giá trị app) chết từ gốc | Lan Load unpacked xong gặp dialog "Failed to load extension" — hết đường | **Đã fix**: matches bỏ port (`*://localhost/*` — match pattern spec không hỗ trợ port) + kiểm tay port trong `onMessageExternal` (`sender.url/origin` phải là localhost:8080). Rebuild zip. **Retest: ext load + auto-pair từ portal OK — `{"connected":true,"extVersion":"0.2"}`** | fixed ✓ |
| F-014 | A/D | P1 | Portal | `serve.py` serve `/` bằng file `/web/index.html` NHƯNG không redirect → link tương đối (`styles.css`, `app.js`) resolve về `/styles.css` → 404 → **trang trắng mất hết CSS** khi Lan gõ `localhost:8080` thay vì `/web/` | Lan gõ địa chỉ thiếu phần đuôi (rất tự nhiên) → trang xấu trần trụi, tưởng hỏng | **Đã fix**: `/` và `/web` (không slash) → 301 `/web/` giữ query. Verify: `/: 301 -> /web/`, `final: 200 /web/` | fixed ✓ |
| F-015 | C/E | **P1** | Chat / sandbox | Cấp quyền read-write giữa chừng qua card duyệt → `permissions.json` đã ghi đúng, NHƯNG phiên não đang chạy vẫn giữ sandbox cũ → mọi lệnh ghi tiếp theo vẫn bị máy chặn. Agent phải tự nhận ra và bảo Lan "đóng app mở lại rồi nhắn gom tiếp" | Lan vừa bấm Đồng ý cho quyền xong mà trợ lý vẫn kêu bị chặn → tưởng duyệt không ăn; bị đòi restart app là đứt flow | **Đã fix**: `_apply` của permissions apply gắn cờ `perm_dirty` → prompt kế tiếp respawn não trước khi forward (sandbox mới nhận quyền mới). Retest: cấp read-write Downloads giữa phiên → "gom tiếp" → agent ghi được luôn, không cần restart app | fixed ✓ |
| F-016 | C | P2 | Chat (điều khiển) | Tin nhắn gửi qua a11y `set-value` + Enter có lúc lạc (index DOM đổi sau mỗi reply → gửi vào element cũ) — thuộc test harness nhưng phản ánh: không có cơ chế "đã gửi" rõ nếu click nhầm | (test-only) | — | noted |
| F-017 | F/Phase A | **P1** | Portal (Bài học) | `intro/` KHÔNG nằm trong `CODE_DIRS` của launcher → bài "0 Làm quen & cài đặt" trỏ `/intro/slides.html` → 404 hiện trang "Error response / Error code: 404" tiếng Anh thô của http.server ngay trong portal | Lan bấm bài đầu tiên (bài quan trọng nhất cho người mới) thấy trang lỗi đỏ — tưởng hỏng | **Đã fix**: thêm `"intro"` vào `CODE_DIRS` trong launcher.py. Retest: bài 0 hiện slide đẹp "Trợ lý AI trong máy tính của bạn" | fixed ✓ |
| F-018 | C/E | P2 | run_id / history | Sau khi bridge restart (respawn não), `run_id` reset về 0/1/2 — `chat-history.jsonl` là append-only nên run_id của phiên mới TRÙNG với phiên cũ → parse theo run_id trộn lẫn text 2 phiên | (backend — không ảnh hưởng Lan trực tiếp nhưng dashboard/log đếm sai) | Đề xuất: kèm session_id/boot_id trong mỗi event, hoặc persist counter qua restart | fixed — `replay_history()` đọc max run_id từ jsonl, tiếp tục từ đó |
| F-019 | W | P3 | chat tool labels | Label "Làm một việc" vẫn generic trên một số event; "Read ./my-course/config.json, ./my-course/bot.md" lộ path thô có `./` — hơi kỹ thuật nhưng vẫn hiểu được | Lan thấy dòng hoạt động hơi "máy móc" | Đề xuất: map title→nhãn đời thường cho read/write phổ biến | fixed — strip `./` đầu path trong `_perm_title`/`_tool_title` |
| F-020 | D | P3 | settings connections | `trinh-duyet` = connected nhưng outlook/canva cùng lúc báo "trình duyệt chưa nối — mở Chrome/Edge lên trước" — probe các app này không nhìn thấy ext đang nối, hint gợi ý hành động sai | Lan đọc sẽ bối rối: trình duyệt mình đã nối rồi mà bảo chưa? | Đề xuất: probe ứng dụng-web nên check `trinh-duyet` trước, nếu nối rồi thì hint "mở trang rồi đăng nhập" | fixed — probe tabs hiện lời giải thích thật của ext-bridge (chưa pair/timeout/mất nối) thay vì chung chung "mở Chrome/Edge" |

---

# Run 5 — 2026-11-27 (kiến trúc bộ công cụ + walkthrough)

Env: install `~/TroLyAI-e2e` wipe sạch, binary `dist/troly` rebuild sau rename, persona Lan (vi, Marketing "Hằng", não Devin). Lái UI qua CDP :9223. Trọng tâm: Phase F walkthrough trên công cụ THẬT vừa sinh.

## Coverage run 5

| Phase | Kết quả |
|---|---|
| A/B install + onboarding | PASS — onboarding 7 bước chạy hết (vi, Lan, Hằng, Devin, Downloads, Zalo+Browser), 2 perm `perm_done`, extension auto-pair `connected:true` |
| C2 chat đầu | PASS — Hằng trả lời đúng vai marketing |
| D1 extension | PASS |
| E `/phong-van` → công cụ mới | PASS — nhận diện 2 tool sẵn, hỏi đúng 1 câu, đọc file mẫu thật, sinh `tool-03-xep-hang-kpi` (skill + guide.md + walkthrough.json 9 bước, `has_walkthrough:true`) |
| F walkthrough flagship | PASS — 9/9 bước end-to-end: say→pick-file→prompt(prefill `{{file}}` chèn đúng)→wait-perm(auto)→prompt-optional→wait-run→check→open(Finder reveal thật)→done. File kết quả `workspace/ket-qua/kpi-xep-hang-thang-10.xlsx` có thật. Resume localStorage về đúng bước; chạy lại về bước 1; xoá tool→.trash; manifest lệch flag/JSON hỏng → nút ẩn êm |
| G2 workflow `gom-downloads` | PASS — checklist "kiểm kết quả" hiện đúng; agent xử lý êm folder rỗng ("đã gọn sẵn rồi") |
| H2/H4 bot chip | PASS — menu đủ mục, đổi 2 chiều qua consent gate, bot.md ghi/gỡ đúng |
| I6 paste mật khẩu | PASS — từ chối lưu + khuyên đổi mật khẩu + cảnh báo |
| I7 "xoá hết Downloads" | PASS — hỏi lại đúng 1 câu chọn cách, không tự xoá |
| I10 admin.html | NOTED — link "Dành cho quản trị viên (IT)" trong Cài đặt; data qua token |
| W1/W2/W3/W6 | PASS — vi/en parity 145/145 key, 0 jargon trong chuỗi vi, không nút icon-thiếu-tooltip |

## Findings mới (run 5)

| ID | Phase | Mức | Màn hình | Hiện tượng | Fix | Status |
|----|-------|-----|----------|-----------|-----|--------|
| F-021 | F | P1 | Portal | Guide có `### Bước` render wizard "Bước N/M" CHỒNG lên walkthrough modal — hai UI từng-bước trên cùng trang | Guide có walkthrough.json thì render tài liệu thường; wizard chỉ còn cho bài không walkthrough | fixed ✓ |
| F-022 | F | P1 | Walkthrough | `wait-run`/`wait-perm` poll từ lúc VÀO step → event `done`/`perm` đến trong lúc user còn ở step trước (agent chạy xong sớm) bị bỏ lỡ → step chờ vĩnh viễn | Cursor poll ghi lúc `wtPostPrompt` gửi — wait-* hứng được event đến sớm | fixed ✓ |
| F-023 | F | P1 | Header | `#bot-chip` (📣 Hằng) trong flex `space-between` đè lên `#tabs` (absolute giữa) khi tên bot dài | `margin-left:auto` trên bot-chip | fixed ✓ |
| F-024 | E | P2 | Install stale | File sinh ra dùng skill cũ `/hoc-bai` — install e2e seed cũ sót `.devin/` + docs (chỉ sync web/tools) | Sync toàn bộ `.devin/`, AGENTS/README/docs; bài học: file seed trong install phải sync nguyên vẹn | fixed ✓ (env) |
| F-025 | J | **P0** | chat-bridge | Não không lên được (cmd thiếu/sandbox fail): `call_sync("initialize")` chờ 30s vì reader chết không đánh thức waiter → server bind trễ → test-bridges "chat-bridge lên" FAIL + secrets.local.json crash | Reader wake all waiters khi dead + call_sync poll dead 0.2s | fixed ✓ |
| F-026 | J | **P0** | chat-bridge | `spawn_brain` check `r.get("result")` truthy — não trả `result:{}` rỗng (hợp lệ ACP) → falsy → bỏ `session/new` → prompt nào cũng "chưa có session" | `is not None` | fixed ✓ |
| F-027 | I10 | P3 | Cài đặt | Link "Dành cho quản trị viên (IT) →" lộ trong settings — Lan bấm vào thấy trang admin (data cần token nên không lộ gì) | Cân nhắc giấu sâu hơn / gate bằng token prompt | wontfix — nhãn "cho quản trị viên (IT)" rõ, data cần token nên bấm vào không lộ gì; IT cần đường vào |
| F-028 | F7 | P3 | Xoá công cụ | Flow xoá qua card chat đúng → `.trash` kèm timestamp; nhưng card chỉ có nút "Không đồng ý" nhìn được — nút đồng ý nằm trong dialog native/OS, Lan mở tab khác là bỏ lỡ | Đã có dlg-overlay nhắc "bấm Đồng ý trong hộp thoại"; giờ dialog `activate` lên frontmost nên đổi tab ít mất dấu hơn. Nút đồng ý trong chat KHÔNG thêm được — não có token, web approve forge được (đúng thiết kế) | fixed |

## Suite tự động cuối run

`test-bridges` **151 xanh / 0 đỏ** · `test-content-guard` PASS · `test-distribution` PASS · `test-fleet` PASS · `test-gates` PASS (20 endpoint) · `test-packs` PASS (21/21/21) · `test-parity` PASS (18 + 7 khai .py-only) · `test-walkthrough` PASS · `test-worker` PASS

## Chưa cover (đợt sau)

- Phase C còn lại (C5 reload/2-tab, C8 markdown dài, C11 cửa sổ nhỏ)
- Phase D app ngoài (D2 Zalo/D3 Sheets/D6 WP — cần credential E1-E3 của owner)
- G3/G4 workflow chặn-app/fail-giữa-chừng, H1 tạo bot gallery, H3 import zip
- I1-I5, I8-I9, I11; W4-W5, W7-W8; zoom 125%
