# Plan — Nâng cấp `/phong-van` cho kiến trúc "bộ công cụ"

Ngày: 2026-11-27. Nguồn: rà soát `/phong-van` + `/tao-cong-cu` sau rework
(commit `4e2fa5a`, `ff3aa14`), đối chiếu repo `mattpocock/skills` và
report e2e persona Lan run 4 (`plans/261126-1707-e2e-personal/report.md`).

Mục tiêu: buổi phỏng vấn kết thúc bằng **bộ công cụ đã chạy thật ít nhất
một lần** — không phải danh sách hứa hẹn — và trợ lý **nhớ học viên**
qua các phiên.

## Bối cảnh mô hình mới (để đọc plan không cần tua lại)

- Phỏng vấn → bộ CÔNG CỤ. Mỗi mục = công cụ (skill mới / skill có sẵn /
  nhờ tự do — do `/tao-cong-cu` chọn) + `walkthrough.json` (SẢN PHẨM
  CHÍNH — modal tương tác trong portal) + `guide.md` (bản đọc).
- `walkthrough.json` là **runner**, không chỉ hướng dẫn: có `auto`
  (trợ lý tự làm), `check` (verify + thoát về chat), `cond` (skip step
  khi đã connect), `pick-file`, `choice`, `then_probe`, `copy`.
- E2E run 4 PASS toàn tuyến: pain "lọc khách theo tỉnh" → chọn đúng
  `/loc-khach` có sẵn; sinh guide ~1-2 phút; agent TỰ đọc CSV thật và
  phát hiện 4 khách thiếu tỉnh.

## Findings đã kiểm chứng

| # | Finding | Mức | Bằng chứng |
|---|---|---|---|
| P-01 | Context học viên bốc hơi sau buổi phỏng vấn — manifest chỉ là list tool, không nhớ vai trò/nỗi đau/tần suất/trạng thái | cao | `workspace/manifest.json` schema chỉ có `lessons[]`; không file profile nào |
| P-02 | Không hỏi tần suất/thời gian — trong khi `tao-cong-cu` có luật "không tạo skill cho việc chỉ làm 1 lần" → freq là **input bắt buộc của routing** mà không ai thu | cao | `tao-cong-cu/SKILL.md` mục "Không làm"; `phong-van` không câu nào hỏi freq |
| P-03 | `workspace/workflows/` không được đọc — pain trùng workflow card có sẵn sẽ bị sinh tool mới thừa | trung | `phong-van`/`tao-cong-cu` không nhắc workflows; dir có 3 card |
| P-04 | Taxonomy lệch: phong-van Nhánh A nói 2 dạng ("Bài học / Công cụ riêng"), tao-cong-cu chọn 3 hình thức — form "nhờ tự do" vô hình với người phỏng vấn | trung | `phong-van` L74-78 vs `tao-cong-cu` bước 1 |
| P-05 | Spec intake nông — tool encode giả định cứng (prefill, var, path); giả định sai = tool chết lần chạy đầu. `tao-cong-cu` chỉ "hỏi TỐI ĐA 2 câu" | cao | `tao-cong-cu` mục "Đầu vào"; e2e run 4 agent tự peek CSV mới phát hiện edge case |
| P-06 | Không có done-criteria "tool đã chạy" — buổi kết thúc khi files ghi xong, chưa chắc tool hoạt động | cao | `phong-van` Giai đoạn 5 chỉ ghi manifest + chào |
| P-07 | tool-00 "Kết nối" thừa cho connector login-only — `cond:{conn:'x'}` trong walkthrough tự skip bước nếu đã nối; tool-00 chỉ cần cho connector credentials (WP App Password, Sheets MCP) | trung | `templates/walkthrough.json` `_flow.cond`; `phong-van` L131-141 |
| P-08 | Không có nhánh xử lý nỗi đau nhạy cảm (gửi tin hàng loạt, auto-reply khách, cào data) — chỉ đánh giá khả thi, không đánh giá chính sách | trung | Nhánh A chỉ có "Khả thi không?" |
| P-09 | Chọn bot role bằng suy đoán skills thay vì hỏi nghề; e2e tìm thấy bug thật: click gallery trật → bot đặt tên theo TÊN HỌC VIÊN ("Lan — văn phòng") | trung | `phong-van` Giai đoạn 6; report.md finding cuối run 4 |
| P-10 | `ask_user_question` bị skip không có hướng xử lý | thấp | — |
| P-11 | Vocabulary sót: "Bài học/giáo trình/khoá học" lẫn trong thân skill dù header nói "không phải bài giảng" — e2e pass nên là debt, không phải bug hành vi | thấp | `phong-van` L74-78, 112, 114, 162, 187, 201, 217 |
| P-12 | Stage 1.5 đứng trước Stage 2 nhưng phụ thuộc output của nó — agent đọc tuần tự dễ chạy sai | thấp | `phong-van` L39-55 |
| P-13 | Dữ liệu test cũ sót: `tool-01/02` còn slides.html/video.mp4/sample-files/exercise.md (~1.8-1.9MB mỗi folder), manifest `has_slides:true` — nhiễu e2e và ship theo nếu repo là template | thấp | `ls workspace/tool-01-*` |
| P-14 | Nhịp buổi phỏng vấn: "gom hết → build cuối" tạo cú chờ 5-10 phút và trì hoãn win đầu tiên | trung | `phong-van` Giai đoạn 3→4 tuần tự |
| P-15 | Naming drift thật đã xảy ra: e2e run 4 (sau commit rename) vẫn ghi agent sinh folder `lesson-03-tach-khach-theo-tinh` — bằng chứng nhẹ rằng vocab sót CÓ THỂ ảnh hưởng output, không chỉ cosmetic | thấp | `report.md` run 4 |
| P-16 | `learner_name` đang trùng 2 nơi (`config.json` + `manifest.json`) — thêm `learner.json` sẽ là nguồn thứ 3 nếu không quy ước | thấp | `web/app.js` L284/332 đọc `manifest.learner_name` |
| P-17 | `templates/lesson.md` mới sửa nửa vời: đã nói "tutorial dùng công cụ" nhưng còn "# {{lesson_name_outcome}}", "Bài này dạy bạn dùng công cụ"; `docs/skills-system.md` ghi "20 skill" (thực tế 21/pack) | thấp | `templates/lesson.md` L27-29; `skills-system.md` L10-11 |

## Quyết định thiết kế đề xuất (cần owner duyệt)

- **D1 — Phân vai sạch**: phỏng vấn thu `nỗi đau + freq + per_time +
  connector + file/app ví dụ`, bàn giao spec; `tao-cong-cu` đảm nhiệm
  spec-grade intake (file thật, output mong muốn, edge case, người nhận
  kết quả) cho TỪNG tool — hưởng lợi cả đường ad-hoc "biến việc vừa
  làm thành công cụ".
- **D2 — Nhịp xen kẽ** (đề xuất): xác nhận 1 nỗi đau → tao-cong-cu
  build → chạy walkthrough luôn → nỗi đau tiếp. Win sớm thay vì chờ
  cuối buổi. Phương án còn lại: giữ gom→build hàng loạt, chỉ thêm
  "chạy tool đầu" ở cuối.
- **D3 — Done-criteria**: buổi phỏng vấn "xong" khi ≥1 tool đã chạy
  trọn với học viên nhìn thấy (dùng `auto`/`check`/`cond`).
- **D4 — `workspace/learner.json`** ghi tăng dần trong suốt buổi:

```json
{
  "learner_name": "", "role": "", "tools_used": [],
  "goal": "<câu trả lời: muốn khỏi phải làm việc gì>",
  "pains": [
    {"desc": "...", "freq": "1 lần/tuần", "per_time": "~30 phút",
     "connector": "zalo", "file_example": "~/Downloads/...",
     "spec": "đầu ra mong muốn bằng lời học viên",
     "status": "heard|approved|built|ran|skipped",
     "tool": "tool-03"}
  ]
}
```

  `status` tiến dần = resume tự nhiên + `/hoc-bai` personal hoá + sau
  này báo được "tiết kiệm ~X giờ/tuần". Re-entry đọc file này thay vì
  chỉ nhìn manifest. Quy ước chống trùng (P-16): `learner.json` là
  nguồn sự thật cho profile; `manifest.learner_name` chỉ là bản copy
  để portal hiển thị (portal đọc manifest), `config.json.learner_name`
  giữ nguyên cho onboarding — khi sửa tên ở đâu thì đồng bộ 3 chỗ.
- **D5 — tool-00 thu nhỏ**: chỉ sinh cho connector cần credentials;
  connector login-only xử lý inline bằng `cond` + `open-url` trong
  walkthrough của tool đầu tiên dùng nó.
- **D6 — Nhánh nhạy cảm**: Nhánh A thêm đánh giá chính sách — gửi tin
  hàng loạt/auto-reply/thanh toán/cào data → đặt ranh giới bằng lời
  tử tế, đề xuất biến thể an toàn (soạn sẵn để duyệt tay), không nhận
  làm tool tự-động-hoàn-toàn.
- **D7 — Câu hỏi thêm** (mỗi câu một mục đích): nghề/chức danh (chọn
  bot role đúng, tránh bug "Lan — văn phòng"); freq + per_time (routing
  skill-vs-guide + ROI); "file này từ đâu tới, xong gửi ai" (upstream/
  downstream → spec output); "đã thử AI nào chưa, sao bỏ" (kỳ vọng cũ);
  câu chốt goal ("khỏi phải làm gì thì mừng").
- **D8 — Không làm** (ghi rõ để khỏi tranh luận lại): frontier/design
  -tree của `grilling`; learning-records/retrieval/spacing của `teach`;
  SINH workflow card mới (walkthrough đã chiếm vai trò — chỉ ĐỌC
  workflows); engineering skills của mattpocock cho học viên; đa học
  viên một máy (đã là câu hỏi mở trong roadmap).

## Tasks

**Quy tắc sửa skill (đã verify):** `.devin/skills/` và `.devin/skill-packs/vi/`
hiện giống hệt nhau từng byte (`diff -q` sạch). Mọi sửa đổi skill → sửa ở
`.devin/skills/` rồi copy nguyên file sang `skill-packs/vi/` + viết bản en
tương đương trong `skill-packs/en/` (bản en là dịch, không cần giống chữ)
+ chạy `tools/test-packs.py`. Quên đồng bộ = bản đóng gói `troly` thiếu
skill — đã từng mất `/clone-trang` vì lỗi này.

### Phase 1 — Sửa `/phong-van` (doc, không đụng runtime)

Lưu ý phụ thuộc: nếu owner duyệt **D2 (nhịp xen kẽ)** thì viết luồng
Giai đoạn 3-4 theo dạng xen kẽ ngay trong phase này, tránh viết lại 2 lần.
Task "re-entry đọc learner.json" nằm ở Phase 3 vì cần file tồn tại trước.

- [ ] Đồng bộ taxonomy: Nhánh A trỏ thẳng sang 3 hình thức của
      `tao-cong-cu` (skill mới / có sẵn / nhờ tự do), bỏ khái niệm
      "Bài học".
- [ ] Gập Giai đoạn 1.5 vào cuối Giai đoạn 2 (map connector theo từng
      nỗi đau ngay khi xác nhận).
- [ ] Thêm câu hỏi theo D7 vào đúng nhịp hiện có (không phá giọng
      ELI10, mỗi lượt một câu).
- [ ] Thêm nhánh nhạy cảm (D6) trong Nhánh A.
- [ ] Thêm routing check: đọc `workspace/workflows/index.json` +
      `.devin/skills/` trước khi chốt danh sách — pain khớp workflow/
      skill có sẵn thì nói ngay "nhà bạn có sẵn rồi".
- [ ] Giai đoạn 6: hỏi nghề tường minh + nếu bot đã tồn tại thì không
      tạo thêm (bug P-09).
- [ ] Quy tắc skip `ask_user_question`: skip = dùng phán đoán tốt nhất
      + ghi vào learner.json, không hỏi lặp.
- [ ] Dọn vocabulary (P-11, P-12, P-15): "giáo trình/khoá học/bài" →
      "bộ công cụ/công cụ/mục" cho nhất quán với header — e2e run 4 đã
      thấy folder `lesson-03` lọt qua sau rename.

### Phase 2 — Nâng `tao-cong-cu` phần Đầu vào

- [ ] Nâng "hỏi TỐI ĐA 2 câu" thành spec intake đủ để build: file/app
      nguồn (xin peek 1 file thật qua folder đã cấp quyền — e2e đã cho
      thấy agent làm được), output mong muốn, 1-2 edge case ("thiếu dữ
      liệu thì sao"), người nhận kết quả.
- [ ] Skill sinh ra phải có bước tự-kiểm: đọc file/app trước, xác nhận
      cấu trúc với học viên, hỏi nếu lệch giả định — đẩy độ bền vào
      tool thay vì dồn hết vào buổi phỏng vấn.
- [ ] Routing input chính thức: `freq` (từ learner.json/học viên) quyết
      skill-vs-guide theo luật "không skill cho việc 1 lần" đã có.

### Phase 3 — `learner.json` + ghi tăng dần

- [ ] Schema theo D4 + quy ước dedup `learner_name` (P-16); ghi sau mỗi
      nỗi đau xác nhận (không đợi cuối buổi).
- [ ] `tao-cong-cu` cập nhật `status` + `tool` khi build/ran xong.
- [ ] Re-entry `/phong-van`: đọc status → đề xuất tiếp việc dở (thay
      cho rule "đừng phỏng vấn lại" hiện tại).
- [ ] `/hoc-bai` đọc learner.json để gọi đúng tên/nỗi đau của họ.

### Phase 4 — Done-criteria + tool-00 thu nhỏ

- [ ] Phỏng vấn kết thúc bằng chạy thật tool đầu (walkthrough `auto` +
      `check`) — sửa Giai đoạn 5 thành "mời bấm ▶ chạy cùng mình".
- [ ] Quy tắc tool-00 mới (D5): chỉ cho connector credentials; login
      -only → `cond`+`open-url` inline.
- [ ] Nếu duyệt D2 xen kẽ: viết lại nhịp Giai đoạn 3-4 thành vòng
      "xác nhận → build → chạy → tiếp".

### Phase 5 — Đồng bộ + dọn dẹp

- [ ] Đồng bộ bản en: `skill-packs/en/interview` + `skill-packs/en/
      make-tool` theo thay đổi vi; chạy `tools/test-packs.py`. (Hiện
      packs đang sạch — vi 21 ↔ en 21, active == pack vi.)
- [ ] Chạy `tools/test-walkthrough.py` cho mọi walkthrough sinh ra.
- [ ] Dọn `workspace/tool-01,02` artifact cũ + sửa manifest flags
      (P-13) hoặc ghi rõ là fixture test.
- [ ] Sửa `templates/lesson.md` phần vocab còn sót + `skills-system.md`
      "20 skill" → 21 (P-17); rà `AGENTS.md` chỗ "dẫn một bài".
- [ ] Retest e2e persona (ít nhất đường pain file-based có pick-file +
      chạy tool đầu trong buổi).

## Backlog (không làm trong plan này)

- Questionnaire cho sếp/team lead (mượn `to-questionnaire`) → điền vào
  `rules.local.md` — chờ khi có pilot B2B thật.
- Pain log ẩn danh ra `.logs/` để nhìn nỗi đau lặp → quyết pack mới.
- Báo "tiết kiệm X giờ/tuần" từ freq×per_time trong learner.json.
- Workflow ↔ tool unification (hai hệ thống card đang overlap khái
  niệm) — cần quyết định sản phẩm riêng.
