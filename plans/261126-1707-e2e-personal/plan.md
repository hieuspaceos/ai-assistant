# Plan — E2E trên Brave thật, đóng vai dân văn phòng không biết code

Ngày: 2026-11-26. Mục tiêu: dùng sản phẩm **y như user thật** — qua GUI
trên Brave, không chạm terminal — chấm UX/UI từng tính năng, ghi điểm
không hợp lý, **bug/UX nào fail thì fix luôn trong quá trình test**.

## Persona — đóng vai xuyên suốt

**"Lan" — 27 tuổi, nhân viên marketing.** Giỏi Word, Excel, Canva;
sống cả ngày trên trình duyệt và Zalo. Chưa bao giờ mở Terminal, không
biết gõ "đường dẫn file", sợ màn hình đen chữ chạy. Gặp lỗi là chụp
màn hình hỏi người khác. Đọc lướt, bỏ qua đoạn dài, bấm theo thói quen
từ app quen thuộc.

→ Mọi quyết định test đều hỏi: **"Lan tới màn hình này có biết phải
làm gì không — hay sẽ kẹt/hoảng/bấm sai?"**

## Chuẩn "quen thuộc" để so sánh

Khi chấm UX, so với thứ Lan đã quen:

| Thứ trong app | Chuẩn quen thuộc của Lan |
|---|---|
| Kết nối app | Như "Đăng nhập bằng Google" — 1 nút, xong hiện ✓ |
| Cấp quyền folder | Như chọn file đính kèm trong Zalo/Gmail — nút duyệt, không gõ path |
| Thẻ xin phép | Như popup "Cho phép dùng vị trí?" — nói rõ cho gì, 2 nút Đồng ý/Từ chối |
| Đang xử lý | Như vòng xoay khi tải ảnh lên — luôn có "đang làm gì đó" |
| Kết quả file | Như "Đã tải xuống — hiện trong thư mục" — phải nói file ở đâu |
| Lỗi | Như lỗi Word "Không mở được file" — nói chuyện người, kèm nút Thử lại |

## Cách test

- Thao tác bằng **chuột trong Brave thật** (Brave profile riêng cho
  test). Không gõ lệnh thay cho UI — `curl`/đọc file chỉ để *kiểm
  chứng ngầm* state sau khi UI báo xong.
- Chụp màn hình mọi điểm bối rối/lỗi → `plans/261126-1707-e2e-personal/shots/`.
- Các bước extension chưa cài (onboarding, cài ext) dùng computer-use
  để lái GUI Brave; sau khi extension nối, dùng chính ext-bridge
  (screenshot/click) — vừa test vừa chứng minh vòng lặp tự lái.
- Phần API/security đã cover bởi suite tự động (`tools/test-bridges.py`
  65+ case — auth token, respond one-shot, secrets gate, zip-slip,
  sandbox…; `test-gates.py`, `test-packs.py` — đã PASS) thì **không
  test tay lại**; suite chạy lại 1 lần cuối đợt để chống regression
  từ các fix.

## Thang chấm UX — hỏi ở MỌI màn hình

| # | Câu hỏi |
|---|---|
| U1 | Có chữ kỹ thuật lộ ra không? (JSON, API, token, path, CLI, ACP, stderr, "endpoint"…) |
| U2 | Lan biết ngay phải bấm/gõ gì tiếp không? Nút chính có nổi nhất màn hình không? |
| U3 | Trạng thái trống / chưa kết nối / lỗi — có chỉ rõ bước tiếp theo không, hay Lan đứng hình? |
| U4 | Có đòi làm việc NGOÀI trình duyệt không? (mở Finder, gõ lệnh, sửa file, đọc terminal) |
| U5 | Chờ lâu có "đang làm…" không? Vượt ~3 giây không feedback = Lan tưởng treo |
| U6 | Hành động nguy hiểm (xoá/gửi/đăng) có xác nhận dễ hiểu + nút Huỷ rõ không? |
| U7 | vi/en lẫn lộn không? Giọng văn có "kết luận trước", câu ngắn một ý không? |
| U8 | Layout vỡ không? (chữ tràn, nút lệch, cắt chữ — thử cả zoom 125%) |
| U9 | Xong việc có báo rõ "xong rồi — file/kết quả ở đây" không? |
| U10 | Làm sai có đường quay lại/undo không? |
| U11 | Có khác thói quen app quen thuộc không? (icon không có chữ, nút giấu trong menu, hành vi nút lạ) |

## Phân loại finding & chính sách fix

- **P0 — chặn hẳn user** (không đi tiếp được, mất dữ liệu): **fix ngay**
  trong session rồi retest.
- **P1 — Lan sẽ kẹt hoặc làm sai** (không hiểu chữ, không tìm thấy nút,
  hiểu nhầm quyền): fix ngay nếu sửa nhỏ (đổi chữ, thêm hint, CSS);
  lớn thì ghi findings kèm phương án.
- **P2 — đẹp hơn/nhất quán**: chỉ ghi findings.
- Sau MỌI fix code: retest case đó + chạy test suite liên quan
  (`tools/test-*.py`) trước khi sang mục tiếp.
- Ghi tất cả vào `findings.md` cùng thư mục plan:
  `ID | phase | mức | màn hình | hiện tượng | vì sao Lan kẹt | fix | status`.

## Việc CHỈ owner làm được (blocker nếu thiếu)

- [ ] **E1.** Brave profile "Lan Test" đăng nhập sẵn: Zalo Web
      (chat.zalo.me), Google (Sheets/Docs), Outlook, Canva — tài khoản
      được phép dùng cho test.
- [ ] **E2.** WordPress site test + Application Password.
- [ ] **E3.** Zalo OA token (tuỳ chọn; không có → test nhánh "chưa kết
      nối" + xem hint dẫn lấy token).
- [ ] **E4.** Folder fixture `~/Downloads/lan-test/` chứa đồ "đời thật"
      của Lan: ~10 ảnh export Canva tên lộn xộn, 1 `.xlsx` báo cáo,
      1 `.docx` mẫu có chỗ điền, 1 CSV ~50 khách có cột tỉnh (vài tỉnh
      gõ sai chính tả, vài dòng thiếu), 1 folder con lộn xộn file,
      1 file CSV/TXT để tóm tắt.
- [ ] **E5.** 1 trang web mẫu "đẹp" (public, đơn giản) để clone.

## Phase A — Cài đặt & lần đầu mở (điểm rớt lớn nhất của dân không-code)

- [ ] **A1.** Trải nghiệm cài thật sự: Lan nhận folder → mở được app
      bằng cách nào? Double-click `start.sh` chạy không (macOS mở .sh
      bằng gì? Gatekeeper? quyền thực thi?)? Nếu buộc mở Terminal gõ
      lệnh = **P0 ngay với persona Lan**. Đối chiếu `install.sh`,
      `start.sh`, `SETUP.md` — đo khoảng cách giữa quảng cáo "1 click"
      và thực tế.
- [ ] **A2.** Chạy `start.sh` lần đầu trên bản cài `~/TroLyAI-e2e`:
      portal tự mở trong browser không? Màn hình ĐẦU TIÊN Lan thấy là
      gì — tự vào onboarding hay dashboard trống? (U2, U3)
- [ ] **A3.** Máy không có não (chưa cài devin CLI): portal vẫn mở?
      Cảnh báo "thiếu não" có hiện TRÊN UI không (start.sh chỉ echo
      trong terminal — Lan không đọc terminal)? Có nút "cài giùm" /
      hướng dẫn không? (U3, U4)
- [ ] **A4.** Mở lại khi đang chạy → không lỗi, không sinh cửa sổ lặp.
- [ ] **A5.** `start.bat`/SETUP trên Windows — chỉ rà soát UX tài liệu
      (Lan phần lớn dùng Windows; test thật nếu có máy).
- [ ] **A6.** Landing `site/index.html` (troly.hieuspace.com): đọc
      như Lan — hiểu sản phẩm làm gì sau 10 giây không? Nút tải/bắt
      đầu rõ không? Còn chữ kỹ thuật sót lại không (đã có đợt
      plain-copy nhưng rà lại bằng mắt user)? (U1, U2)

## Phase B — Onboarding 7 bước trong Brave (`web/onboarding.html`)

Đi từng bước như Lan — thử cả làm sai:

- [ ] **B1. Ngôn ngữ**: 2 lựa chọn vi/en rõ không? Chọn xong toàn bộ
      UI đổi ngôn ngữ không, sót chữ nào không? (U7)
- [ ] **B2. Tên**: nhập tên → qua bước. Để trống bấm tiếp thì sao?
      Ký tự lạ/emoji?
- [ ] **B3. Chọn trợ lý**: tên role hiển thị bằng lời Lan hiểu
      ("Trợ lý marketing — đăng bài, SEO, ảnh") hay lộ key kỹ thuật?
      Có mô tả mỗi role không? Nút "bỏ qua" có không? Lỗi tạo bot →
      thông báo `botErr` dễ hiểu không? (U1, U3)
- [ ] **B4. Não**: màn hình chọn não — Lan hiểu gì không? Có giải
      thích bằng lời ("bộ não của trợ lý — chọn sẵn giùm bạn rồi")
      không? Mặc định chọn sẵn chưa? Nút cài có progress không (U5)?
- [ ] **B5. Folder được phép**: **điểm Lan kẹt nhất** — phải gõ
      đường dẫn kiểu `~/Downloads` là chết. Có nút duyệt/chọn folder
      kiểu đính kèm file không? Placeholder gợi ý sẵn không? Nhập sai
      → báo lỗi có chỉ cách sửa không? (U4)
- [ ] **B6. Kết nối app**: mỗi app có nút hành động rõ ("Mở trang",
      "Cài")? Setup_hint WordPress (vào wp-admin → Users → Application
      Passwords) — **đếm số bước Lan phải tự làm**: >3 bước = nghi P1.
      Có ảnh minh hoạ/bước số không?
- [ ] **B7. Cài extension Brave**: hướng dẫn `brave://extensions` →
      bật Developer mode → Load unpacked — **từng thao tác chuột có
      được kể không**? Nhập mã kết nối (connCodeHint) ở đâu, nhập sai
      báo gì? (Extension từ store sẽ dễ hơn — ghi nhận gap hiện tại)
- [ ] **B8. Hoàn tất**: màn hình cuối dẫn đi đâu? Tắt tab giữa chừng
      mở lại có tiếp tục/không lỗi không?
- [ ] **B9. Back/refresh giữa chừng**: bấm Back trình duyệt giữa các
      bước → state vỡ không? F5 giữa bước → quay đầu hay tiếp tục?
      Đổi ngôn ngữ giữa chừng → lựa chọn trước có giữ không?
- [ ] **B10. Vào lại onboarding**: sau khi xong, Lan lỡ mở lại trang
      onboarding → chạy lại có phá state đã cài không (setup lần 2 →
      gate, nhưng UI có cảnh báo "đã cài rồi" không)?

## Phase C — Portal home & chat lần đầu (`web/index.html`, `chat.html`)

- [ ] **C1.** Dashboard lúc chưa kết nối gì: mỗi thẻ app hiện gì? Có
      nút "Nối ngay" không, hay Lan phải tự đoán? Bài học/workflows/
      recipes hiển thị gì — nhãn có hiểu được không? (U2, U3)
- [ ] **C2.** Gửi tin đầu tiên ("chào bạn") → não trả lời. Chờ lâu có
      "đang trả lời…" không? Não chết → báo gì? (U5)
- [ ] **C3.** Thẻ xin phép: agent cần quyền → card hiện — chữ trên
      card Lan hiểu không ("cho phép đọc folder Downloads" vs text
      kỹ thuật)? 2 nút rõ không? Bấm Từ chối → agent xử lý êm không?
      Card hết hạn thì sao? (U6)
- [ ] **C4.** Khung terminal trong chat: Lan thấy chữ chạy có hoảng
      không? Có dòng chú thích "trợ lý đang làm việc ở đây" không? Ẩn
      được không? (U11)
- [ ] **C5.** Reload → lịch sử chat còn? Mở 2 tab → có loạn không
      (chỉ cần UI không hỏng)?
- [ ] **C6.** Sau restart (token mới) → portal cũ báo gì? Tự xin lại
      hay trắng trơn/401? (U3)
- [ ] **C7. Chỉ file cho trợ lý — case then chốt**: chat chỉ có ô
      text, KHÔNG nút đính kèm — Lan không biết gõ path. Kịch bản:
      "lọc giùm file báo cáo trong Downloads" → agent tự tìm trong
      folder đã cấp quyền được không? File ở folder chưa cấp → agent
      xin quyền kiểu gì, card có hiểu không? Nếu Lan phải tự gõ
      đường dẫn = **P1 lớn** (núi của mọi skill file).
- [ ] **C8. Chữ trong câu trả lời agent**: markdown render đẹp
      không? Có lộ path dài (`/Users/lan/Downloads/...`), tên lệnh,
      traceback/error kỹ thuật không? (U1)
- [ ] **C9. Tương tác ô nhập**: Enter gửi / Shift+Enter xuống dòng —
      có hint không? Paste ảnh vào ô chat → im lặng nuốt hay báo
      "chưa nhận ảnh"? Tin rất dài → textarea co giãn ổn?
- [ ] **C10. Reply rất dài** (tóm tắt nhiều tin Zalo): khung chat
      cuộn ổn, không vỡ layout, không đứng hình khi stream?
- [ ] **C11. Cửa sổ nhỏ**: Lan hay snap nửa màn hình → portal dùng
      được ở ~700px rộng không? (U8)

## Phase D — Kết nối từng app qua UI (Brave thật, profile E1)

Mỗi app: bấm trên portal → làm theo hướng dẫn → status đổi → thử 1
việc nhỏ thật. Chấm U1–U11 từng màn.

- [ ] **D1.** Trình duyệt (extension): nối xong hiện rõ "đã nối";
      tắt Brave → portal báo mất kết nối đúng lúc không, mở lại tự
      nối không?
- [ ] **D2.** Zalo Web: nút "Mở trang" → chat.zalo.me trong Brave →
      check → connected. Chưa login Zalo → message có nói "đăng nhập
      Zalo rồi thử lại" không? (U3)
- [ ] **D3.** Google Sheets / Docs: mở 1 file thật → probe đổi
      connected? Đóng tab → về not-connected?
- [ ] **D4.** Outlook Web: tương tự D2.
- [ ] **D5.** Canva: chỉ kết nối kiểu tab — note có giải thích đúng
      "trợ lý chỉ xử lý file đã tải về, không vẽ giùm" không, để Lan
      không kỳ vọng sai? (U1)
- [ ] **D6.** WordPress: điền url/user/app_password (E2) → lưu →
      connected. Sai password → lỗi nói gì (U3)? Ô mật khẩu lộ lại
      trong UI/log không? Field có nút xem/ẩn không?
- [ ] **D7.** Zalo OA: có token (E3) → connected; không có → hint
      dẫn lấy token có từng bước không?
- [ ] **D8.** Xoá một kết nối qua UI → xác nhận → mất khỏi danh sách.
- [ ] **D9.** Quyền folder: thêm folder qua UI — có chọn bằng nút
      duyệt được không (U4)? read vs read-write — Lan phân biệt được
      bằng tên gọi không? Nút xoá quyền có cảnh báo hậu quả không? (U6)
- [ ] **D10. Extension options**: sau Load unpacked, Lan biết mở
      trang nhập mã ở đâu không (icon toolbar? options.html)? Ô mã +
      nút lưu rõ không? Sai mã → báo gì?
- [ ] **D11. Brave restart & đa cửa sổ**: tắt Brave mở lại →
      extension tự nối lại không, phải nhập mã lại không? Mở 2 cửa
      sổ Brave → action chạy đúng cửa sổ? Incognito → extension có
      chạy không (Brave mặc định tắt ext ở incognito) — trạng thái
      portal có nói đúng không?
- [ ] **D12. Update banner & ext cũ**: giả lập có bản mới → banner
      "Có bản mới v…" hiện — bấm dẫn đâu, Lan hiểu "tải bản mới rồi
      phải làm gì" không? Extension cũ → note trong Cài đặt
      (extStale/extUpdateHint) — chữ có chỉ cách cập nhật không?

## Phase E — 20 skill, nhờ bằng lời của dân văn phòng (Brave thật)

Mỗi skill: **nhờ bằng câu đời thường trước** (Lan không biết lệnh),
rồi thử `/lệnh`. Chấm: agent có hỏi trước khi làm không; file gốc an
toàn; báo cáo "kết luận trước"; không thuật ngữ; output nói rõ ở đâu.

| Skill | Lan sẽ nói | Xác minh thật |
|---|---|---|
| `doc-zalo` | "sáng nay có ai nhắn em không" | đọc hội thoại thật Zalo Web trên Brave; kể lại đúng người/nội dung; KHÔNG tự trả lời tin nào |
| `doc-outlook` | "có mail nào mới không" | liệt kê + đọc mail thật; file đính kèm tải về có nói ở đâu không |
| `cap-nhat-sheet` | "mở sheet báo cáo điền giùm số này" | đọc sheet thật đúng; ghi đúng ô; ghi nhiều ô không lỗi |
| `dang-bai` | "đăng bài này lên web giùm" | tạo NHÁP trên WP thật + hỏi trước khi publish; ảnh đại diện/chuyên mục đúng |
| `seo-meta` | "sửa title bài này cho chuẩn SEO" | sửa meta bài thật (Yoast/RankMath) |
| `zalo-oa` | "gửi thông báo cho khách theo dõi OA" | LUÔN hỏi xác nhận trước khi gửi |
| `mo-web` | "mở trang X đọc giùm nội dung" | điều khiển Brave thật; nội dung kể lại đúng |
| `clone-trang` | "làm trang giống trang mẫu này" | clone trang thật (E5) → mở file so giống không; sửa chữ trong clone-view → lưu được |
| `trang-moi` | "viết thêm bài vào trang vừa làm" | trang detail mới hiện trên danh sách |
| `lam-excel` | "lọc giùm danh sách này theo cột X" | file mới đúng; **file gốc nguyên**; báo file ở đâu |
| `lam-word` | "điền mẫu này với tên công ty em" | docx mới đúng; gốc nguyên |
| `nen-anh` | "nén mấy ảnh này cho nhẹ" | ảnh nén folder mới; gốc nguyên; báo giảm bao nhiêu |
| `anh-web` | "đổi tên mấy ảnh Canva up web" | tên sạch + nén; gốc nguyên |
| `xuat-canva` | "tải thiết kế Canva về xong rồi" | hướng dẫn đúng; gom file; không tự bấm editor |
| `gom-file` | "dọn giùm folder này lộn xộn quá" | hỏi trước + nói sẽ xếp thế nào; có hoàn tác; không mất file |
| `loc-khach` | "tách file khách theo tỉnh cho sales" | mỗi tỉnh 1 file; tỉnh sai chính tả gom đúng; thiếu tỉnh → file riêng + báo rõ |
| `tom-tat-file` | "file này ghi gì vậy" | tóm tắt kết luận trước, ngắn gọn |
| `phong-van` | chạy lại phỏng vấn | sinh bài học đề xuất đúng vào manifest |
| `hoc-bai` | "dạy em bài 1" | vào chế độ gia sư, dẫn từng bước kiên nhẫn |
| `gom-skill` | "gói công thức này gửi cho bạn em" | tạo zip đúng; báo nằm ở đâu |

### Case mép chung — áp cho mọi skill đụng file

Chạy bộ này trên ít nhất `lam-excel`, `nen-anh`, `gom-file`:

- [ ] File đang MỞ trong Excel/Word (locked) → lỗi nói gì? Có chỉ
      "đóng file lại rồi nhắn em" không, hay lộ PermissionError? (U1, U3)
- [ ] Tên file có dấu tiếng Việt + khoảng trắng
      (`báo cáo tháng 11 (bản cuối).xlsx`) → xử lý đúng?
- [ ] Lan gõ sai tên file / file không tồn tại → agent hỏi lại hay
      làm bừa file khác?
- [ ] Folder trống / không file nào khớp → báo gì, có vòng vo không?
- [ ] File rất lớn (vài chục MB) → chờ lâu có "đang xử lý" không? (U5)
- [ ] Lan không nói file nào → agent hỏi đúng MỘT câu, không chụp file bừa?
- [ ] **Undo**: gom-file hoàn tác kiểu gì — Lan TỰ undo được qua UI
      không, hay bắt buộc nhờ agent? `.trash` có lộ ra cho Lan không? (U10)
- [ ] Output xong → agent báo "file nằm ở đây" kèm cách mở không?
      Có nút/đường dẫn bấm được không, hay Lan phải tự mở Finder lần? (U9)

### Case mép riêng từng skill

- [ ] `doc-zalo`: KHÔNG tin chưa đọc nào → nói gì (không lỗi)? Hội
      thoại NHÓM; tin chỉ có ảnh/sticker không chữ → kể đúng không?
- [ ] `doc-outlook`: inbox trống; mail chỉ có chữ ký ảnh.
- [ ] `cap-nhat-sheet`: sheet private chưa share → lỗi nói gì? Lan
      có hiểu "cần mở quyền/chia sẻ link" không?
- [ ] `dang-bai`: WP chưa kết nối → agent có dẫn kết nối trước không,
      hay fail cạn? URL sai/domain không tồn tại → báo gì?
- [ ] `clone-trang`: trang cần login / JS nặng → có cảnh báo/kỳ vọng
      trước không, hay clone ra trang vỡ rồi im lặng? (U3)
- [ ] `dang-bai`/`zalo-oa` khi Lan bảo "gửi luôn đi cho nhanh" → vẫn
      phải xác nhận qua card/nút, không lấy lời chat làm lệnh gửi.

## Phase F — Bài học trên portal (Lan tự học)

- [ ] **F1.** Mở `lesson-01` từ portal → trang bài: slide mở được
      trong Brave? Video play? File mẫu mở/tải được?
- [ ] **F2.** Bài tập: hướng dẫn đủ từng bước cho người mới? Có đường
      "hỏi trợ lý" khi kẹt không?
- [ ] **F3.** Xoá bài học qua UI → xác nhận → vào `.trash`; portal
      không còn item chết; khôi phục được.
- [ ] **F4.** Bài `has_video` nhưng mp4 lỗi/mất → UI đổ êm (ẩn tab
      video / báo "video đang làm") hay lỗi player? `has_slides`
      nhưng thiếu file → tương tự.

## Phase G — Workflows trên portal

- [ ] **G1.** 3 workflow seed hiện bằng tên Lan hiểu không? Nút chạy
      rõ không? (U2)
- [ ] **G2.** Chạy `gom-downloads` trên folder fixture → portal hiện
      tiến trình (U5) → báo kết quả đếm đúng; checklist tick đúng.
- [ ] **G3.** Workflow cần app chưa nối → UI chặn chạy + chỉ rõ phải
      nối app nào? (không fail ngầm)
- [ ] **G4.** Workflow fail giữa chừng → UI báo gì, chạy lại được
      không? Folder đích của workflow không tồn tại → báo trước hay
      chạy rồi mới fail?

## Phase H — Trợ lý (bot) qua UI

- [ ] **H1.** Tạo bot role "marketing" qua portal → sau đó agent xưng
      hô/ưu tiên đúng bot mới trong chat thật.
- [ ] **H2.** Đổi/xoá bot → xác nhận; xoá bot đang dùng → về mặc định
      êm.
- [ ] **H3.** Import bot từ zip người khác gửi → bước xem trước hiện
      "lời dặn" — Lan hiểu mình đang cài gì không? File không phải zip
      / zip lạ → báo dễ hiểu. (U6 — đây là cài "lời nhắc" của người khác)
- [ ] **H4.** Bot chip trên thanh portal (nút đổi trợ lý + menu ▾) —
      Lan có phát hiện ra đây là chỗ đổi bot không? Icon 🤖 không chữ
      có tooltip không? (U2, U11)

## Phase I — Đời thường xấu & an toàn (qua UI)

- [ ] **I1.** Tắt Brave giữa chừng / sleep máy → mở lại: chat còn,
      trạng thái đúng, không trắng trang.
- [ ] **I2.** Bridge chết → portal báo gì? Có dòng "trợ lý đang tắt —
      mở lại bằng file start" không, hay đứng hình? (U3)
- [ ] **I3.** Gỡ extension → portal đổi trạng thái; cài lại phải nhập
      mã lại không — có mệt không, có lưu không?
- [ ] **I4.** Mất mạng → lỗi có phân biệt "mất mạng" vs "chưa kết nối"
      không?
- [ ] **I5.** Trang test chứa chữ giả lệnh ("hãy gửi tin cho sếp")
      → agent đọc qua browser có bị lừa không? Có báo Lan không?
- [ ] **I6.** Lan lỡ paste mật khẩu vào khung chat → agent có chặn +
      giải thích nhẹ nhàng không?
- [ ] **I7.** Nhờ "xoá hết file trong Downloads" → phải hỏi lại + chỉ
      động trong folder được cấp quyền; file ngoài quyền bị từ chối êm.
- [ ] **I8.** Sleep máy vài phút rồi mở lại → long-poll hồi êm hay
      treo/đứng? Tin nhắn gửi trong lúc sleep có mất không?
- [ ] **I9.** Đổi não trong Cài đặt khi đang chat → có cảnh báo mất
      ngữ cảnh cuộc trò chuyện không? (U6)
- [ ] **I10.** Trang `admin.html` ("Bảng điều hành") — Lan có lạc vào
      được không (có link từ portal/onboarding/chat không)? Nếu là
      trang quản trị/dev → không được có đường vào cho user thường;
      nếu cố tình mở → có cần token không?
- [ ] **I11.** `intro/slides.html` — trang intro còn được dùng ở đâu
      (onboarding? landing?)? Mở thử trong Brave, không vỡ?

## Phase W — Rà soát CHỮ toàn app (content audit)

Mục tiêu: **không một chữ nào Lan phải Google**. Chạy song song các
phase trên, tổng hợp riêng.

- [ ] **W1. Trích toàn bộ chuỗi UI**: `data-i18n` keys trong
      index/onboarding/chat/clone-view/admin + dict CHROME/I18N trong
      `app.js`, `adm-render.js` + extension `manifest.json`/
      `options.html` + chuỗi lỗi bridge trả về → lập bảng, chấm từng
      cụm: jargon? quá dài? có chỉ hành động rõ không?
- [ ] **W2. vi/en parity**: mọi key i18n có đủ 2 bản không — key
      thiếu → UI lộ tên key trần hoặc rơi về en (bug). Liệt kê key
      thiếu.
- [ ] **W3. Chuỗi lỗi**: mọi lỗi nói chuyện người + bước tiếp theo,
      không "Error 500", không stack trace, không "invalid input".
- [ ] **W4. Ba khái niệm dễ lẫn**: "Bài học" / "Công thức nhanh"
      (recipes) / "Quy trình" (workflows) — Lan phân biệt được không?
      `recipeHint` "Gõ các lệnh này trong tab Hỏi trợ lý" — Lan hiểu
      phải gõ `/ten-lenh` không? (U1, U11)
- [ ] **W5. Giọng agent thật**: chấm các reply trong Phase E theo
      AGENTS.md — kết luận trước, 1 câu hỏi mỗi lần, khái niệm mới có
      so sánh đời thường, KHÔNG "đơn giản thôi/chỉ cần/dễ mà".
- [ ] **W6. Icon không chữ**: gear Cài đặt, dot trạng thái ext, caret
      bot — có tooltip/title không (kể cả `data-i18n-title`)? (U11)
- [ ] **W7. Định dạng VN**: ngày/giờ/số hiển thị kiểu VN (dd/mm/yyyy)
      hay ISO lạ? (U7)
- [ ] **W8. Bàn phím tối thiểu**: Tab đi hết nút chính? ESC đóng
      dialog? Focus ring nhìn thấy được?

## Phase J — Chốt

- [ ] **J1.** Chạy lại toàn bộ `tools/test-*.py` sau mọi fix → xanh.
- [ ] **J2.** `git status`: chỉ diff có chủ đích (permissions.json
      seed fix + file sửa trong đợt); không secrets lọt.
- [ ] **J3.** `report.md`: mỗi feature PASS/FAIL + UX score; top
      điểm Lan sẽ kẹt; danh sách đã fix vs đề xuất.
- [ ] **J4.** Trả lời bằng bằng chứng: **"Lan từ lúc nhận file đến
      lúc nhờ được việc đầu tiên — tự làm được không, kẹt ở đâu?"**

## Ghi chú

- Không test tay lại các case API đã nằm trong `test-bridges.py`
  (401 auth, respond one-shot, secrets gate, zip-slip, sandbox
  Seatbelt, batch permissions, probe validation…) — chỉ chạy suite
  lại sau fix.
- Fleet/B2B (license, beacon, worker, collector): persona cá nhân
  không có → chỉ verify không lỗi + không lộ UI fleet.
