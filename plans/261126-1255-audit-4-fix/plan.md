---
title: "Vá findings audit collector.py + extension — porg path traversal, vendor key god-mode, ref data-tlai do trang kiểm soát, snapshot/dom lộ secrets"
description: "Audit collector.py (845 dòng) + extension (content.js/background.js/manifest.json) có 2 PoC chạy thật: (1) porg không sanitize → vendor key ghi JSON ra ngoài DATA/ qua '../../x'; (2) _body() trả non-dict → handler crash, connection rớt. Ngoài ra vendor key = super-admin trên mọi collector (key nằm plaintext trong collector.json của khách), re-pair trả machine_key chỉ bằng shared beacon_secret, và trang web kiểm soát được mục tiêu click qua attr data-tlai trong DOM. Plan chia 2 nhóm: phase 01–03 vá ngay không phụ thuộc quyết định (~15 dòng collector + 3 file extension); phase 04–06 là 3 quyết định design (vendor key scope, re-pair repair flow, releases scope) — mỗi phase ghi sẵn option + khuyến nghị, chờ chọn rồi mới code. Phase 07 tests/docs cuối."
status: done (phase 01–07 ✅ — 04/05/06 chọn Option A: vendor_read_key + "*" rollup-only, repair flow + migration v2, release_key riêng; test-fleet + test-distribution xanh; worker/index.js chưa port repair — ghi nhận SECURITY.md)
priority: P0
effort: M
branch: main
tags: [security, collector, extension, fleet]
created: 2026-11-26
depends-on: 261126-1145-audit-3-fix (xong — audit này chấm file khác)
---

# Vá findings audit collector + extension (đợt 4)

## Bối cảnh

Audit `tools/collector.py` (fleet collector single-file, stdlib-only —
3 tier: LAN self-host / customer VPS / vendor-hosted) và `extension/`
(content.js + background.js + manifest.json — cánh tay trình duyệt của
trợ lý). Verify lại hôm nay: **toàn bộ finding còn nguyên** — file
collector y nguyên 845 dòng khớp số dòng audit trích; extension chỉ có
một hardening quanh vấn đề (`actQuery` whitelist attr ở
`content.js:186-195`, scroll re-resolve ref `sN` ở :219) nhưng không vá
finding nào.

Hai PoC đã chạy thật lúc audit:

- `POST /api/packs {"org":"../../esc2",...}` + vendor key → ghi
  `/tmp/esc2/9.json` thoát khỏi `DATA/` (`collector.py:655-676`)
- `POST` với body `[1,2,3]` → `b.get` AttributeError → traceback,
  connection rớt không response (`collector.py:249-262`)

Quyết định đã chốt từ discuss: **KHÔNG tách collector.py** — single-file
stdlib-only là deployment contract (máy IT không-biết-code copy một file
là chạy), 845 dòng chưa tới ngưỡng đau, phần lớn là một class Handler.

## Bản đồ finding → phase

| # | Finding (mức) | Phase |
|---|---|---|
| 1.1 | `porg` traversal → arbitrary JSON write ngoài DATA/ + crash `latest-{porg}.json` (CAO, PoC) | 01 |
| 1.4 | `_body` non-dict → crash mọi POST (CAO, PoC); **+ nested non-dict trong `_beacon`** (`{"snapshot":[1],"counts":[1]}` cũng crash — phát hiện khi audit lại plan) | 01 |
| 1.5a | Upload `latest.json` đè manifest → fleet update hỏng (DoS nhẹ) + ghi không atomic | 01 |
| 1.8 | Lost-update race merge `counts` (hai `_db_lock` riêng) | 01 |
| 1.7 | Rate limit per-IP sụp sau reverse proxy | 01 |
| S1 | `license_status` tin `lic["org"]` từ máy → license org B "ok" trên máy org A | 01 |
| S2 | `org_pings` không trần → bảng phình | 01 |
| 2.1 | Ref `data-tlai` trong DOM → trang gắn ref giả chọn mục tiêu click; attr cũ sót giữa snapshot (CAO) | 02 |
| 2.2 | `labelOf` đọc `el.value` (trừ password) → form data lọt vào snapshot | 02 |
| 2.3 | `dom` action lộ `input[type=hidden]` value + `meta csrf-token` | 02 |
| 2.6 | `r \|\| {ok:true}` nuốt sự cố content script + `ACTIONS[__proto__]` | 03 |
| 2.7 | `{action, ...params}` — params đè `action` (latent allowlist bypass) | 03 |
| 2.4 | Debugger attach không tự detach → banner "gỡ lỗi" treo | 03 |
| 2.5 | Không URL assertion — action chạy trên tab đã navigate sang trang khác | 03 |
| S3 | `externally_connectable` mọi port localhost | 03 |
| S4 | Token sai → vòng reconnect 3s vô hạn (RAM extToken bị đè) | 03 |
| 1.2 | Vendor key = super-admin mọi collector; cùng key dùng outbound telemetry (CAO) | 04 ⏸ |
| 1.5b | `REL_DIR` global multi-org — admin org A đẩy release ảnh hưởng máy org B | 06 ⏸ |
| 1.3 | Re-pair trả `machine_key` bằng shared `beacon_secret` | 05 ⏸ |
| 1.6 | Boot message khuyên `?key=` trong URL | 07 |
| S5 | Doc drift `vendor-infra.md:97` flag `--org` không tồn tại; `:18` khuyên `?key=` | 07 |

⏸ = phase có quyết định design chưa chốt — file phase ghi option +
khuyến nghị sẵn, chỉ code sau khi chọn.

## Nguyên tắc vá

1. **Không tách collector.py** — deployment contract. Gọn hơn được thì
   gọn, không tách file.
2. **Commit riêng mỗi phase** — diff security phải review độc lập;
   phase 04–06 có thể bỏ qua/thứ tự tuỳ quyết định.
3. **Không phá contract beacon ↔ collector** — `test-fleet.py` đã có
   integration test dựng collector thật; mọi vá auth/endpoint phải qua
   test này + thêm case mới.
4. **Extension vá xong nhớ repack** — `tools/build-ext.sh` nếu bản đóng
   gói đi kèm release; reload extension khi test tay.
5. **Verify bằng PoC lại** — hai PoC audit phải chạy lại sau phase-01
   (400 thay vì ghi file / crash).
6. **`.ps1` đóng băng** — beacon.ps1 không đụng; collector là file duy
   nhất bên server nên không vấn đề.

## Phases

1. **phase-01-collector-hard-fixes** — 1.1 + 1.4 + 1.5a + 1.8 + 1.7 +
   S1 + S2. ~30 dòng, không quyết định, PoC regression test luôn.
2. **phase-02-extension-content** — 2.1 (Map ref→el, isolated world),
   2.2 (bỏ `el.value` khỏi labelOf), 2.3 (strip input value + meta
   token trên clone `dom`).
3. **phase-03-extension-background** — 2.6 + 2.7 + 2.4 idle-detach +
   2.5 url/expectUrl + S3 siết port + S4 restore token sau N fail.
4. **phase-04-vendor-scope** ⏸ — 1.2: Option A tách `vendor_read_key`
   (khuyên) / Option B chỉ siết scope `"*"` read-rollup.
5. **phase-05-repair-flow** ⏸ — 1.3: Option A repair flow + migration
   v2 (khuyên cho vendor-hosted) / Option B ghi DEPLOY.md.
6. **phase-06-releases-scope** ⏸ — 1.5b: Option A `release_key` riêng
   (khuyên) / Option B per-org REL_DIR / Option C giữ global.
7. **phase-07-tests-docs** — 1.6 boot message, S5 doc drift, DEPLOY.md
   LAN-plaintext, SECURITY.md ghi nhận không vá (slow-loris slot, 200MB
   RAM, /api/license aggregate), chạy full test loop + re-PoC.

## Acceptance

- `POST /api/packs {"org":"../../x"}` (mọi loại key) → 400, không file
  nào tạo ngoài `DATA/`; `porg` hợp lệ vẫn ghi đúng `packs/<org>/<v>.json`.
- `POST` mọi endpoint với body `[1,2,3]` / `"str"` → 400 có response,
  connection không rớt; `{"snapshot":[1],"counts":[1]}` → không traceback.
- `POST /api/releases/latest.json` → 400; manifest ghi atomic (đọc giữa
  chừng không ra half-JSON).
- Trang tự gắn `data-tlai="e7"` lên nút mồi → `click e7` bấm đúng phần
  tử snapshot gán, không bấm mồi (refMap trong isolated world).
- Snapshot trên form có `input[type=text]` đang gõ + `input[type=hidden]`
  CSRF → tree không chứa giá trị; `dom` trả HTML không có `value=` của
  input và không có `content=` của `meta[name*=csrf]`.
- `msg.action="__proto__"` → `{ok:false}` thay vì `ok:true` nuốt lỗi.
- t* action xong ~2 phút idle → debugger detach, banner hết.
- Sau 3 lần WS 401 liên tiếp → extToken nạp lại từ storage thay vì
  hammer mãi.
- (Theo quyết định 04–06): vendor key chỉ đọc rollup / re-pair cần
  admin / release upload cần release_key.
- `python3 tools/test-fleet.py` PASS gồm cả case regression mới.
