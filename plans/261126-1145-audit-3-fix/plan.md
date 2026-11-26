---
title: "Vá findings audit chat-bridge đợt 3 — consent downgrade qua nút Không, TOCTOU symlink grant folder, tách path policy dùng chung"
description: "Audit đợt 3 chấm phòng thủ cao (deny-list hai chiều, consent one-shot atomic, native dialog proof-of-human, wipe-on-url-change, probe validate hai đầu) nhưng tìm 2 HIGH: (1) bấm Không/Esc trên dialog native hạ card xuống đường Origin-forgeable → agent tự duyệt ngay sau khi học viên từ chối; (2) grant folder qua /api/permissions chỉ validate lúc request → đổi folder thành symlink trước spawn là gen-sandbox emit quyền cho ĐÍCH symlink (LaunchAgents → persistence ngoài Seatbelt). Kèm medium: dialog flood khi evict không kill proc, interpreter có hậu tố version lọt BRAIN_CMD_DENY, bot create không preview instructions, auto-approve ưu tiên allow_always. Plan vá theo thứ tự: tách path_guard.py dùng chung cho chat-bridge + gen-sandbox → vá 2 HIGH → medium → tests/docs; refactor route table do_POST là phase cuối tuỳ chọn, commit riêng."
status: done (phase 01–05 đã implement + test xanh; phase 06 route-table refactor để sau — commit riêng theo đúng plan)
priority: P0
effort: L
branch: main
tags: [security, sandbox, consent, symlink, refactor]
created: 2026-11-26
depends-on: 261120-2254-audit-2-fix (đã xong — plan này là đợt audit tiếp theo)
---

# Vá findings audit chat-bridge đợt 3

## Bối cảnh

Audit mới nhất (`chat-bridge.py` 2193 dòng + `gen-sandbox.py`,
`content_guard.py`, `serve.py`, `web/`) xác nhận nền phòng thủ tốt, nhưng
phát hiện **2 lỗ HIGH cùng một mô-típ**: điểm validate và điểm enforce
nằm ở hai nơi khác nhau, và phía enforce tin mù dữ liệu đã validate ở
thời điểm khác.

- **CAO-1 (consent downgrade):** `_native_confirm` khai `cancel button
  "Không"` → bấm Không/Esc sinh osascript error -128, stdout rỗng →
  `gui_failed=True` → `_native_fallback` phát lại card KHÔNG cờ native →
  agent `POST /api/respond` (token + Origin tự set được) tự duyệt —
  **ngay sau khi học viên đã bấm từ chối**. `_perm_native_confirm` bên
  cạnh đã vá đúng mô-típ này (không khai cancel button + check
  `declined`) — chỉ cần port pattern sang.
- **CAO-2 (TOCTOU symlink):** `/api/permissions` validate `isdir` +
  `path_sensitive` + `rw_grant_ok` một lần lúc request; `_apply` ghi raw
  path không re-check; `gen-sandbox._emit_paths` resolve realpath **mỗi
  lần build profile** (mỗi spawn não). Agent grant `my-course/x` (hợp lệ,
  trong write-allowlist) → sau đó `ln -s ~/Library/LaunchAgents x` →
  profile emit `file-read* file-write*` trên đích symlink → LaunchAgent
  = code chạy NGOÀI Seatbelt lúc login. Cửa sổ tấn công = từ lúc approve
  tới mọi spawn tương lai (không chỉ lúc chờ bấm).

## Bản đồ finding → phase

| # | Finding (mức) | Phase |
|---|---|---|
| CAO-1 | `cancel button` trong `_native_confirm` → từ chối = downgrade card | 02 |
| CAO-2 | Grant folder → symlink swap → sandbox cấp quyền đích symlink (kể cả đích NON-sensitive — escalation qua path card không hiện) | 01 (policy chung) + 03 (re-validate apply + emit + divergence rule) |
| M1 | Native/auto-approve chọn `allow*` đầu tiên → `allow_always` được pick thay `allow_once` | 04 |
| M2 | `/api/bot action=create` không gate + card activate chỉ hiện tên, instructions độc không preview | 04 |
| M3 | `BRAIN_CMD_DENY` lọt interpreter hậu tố version (`python3.12`, `perl5.40`…) + thiếu `brew`, `gh`, `java`, `dotnet`, `lua`, `Rscript`… | 04 |
| M4 | Eviction `local_pending`/`perm_pending` không `proc.terminate()` → spam gated endpoint = dialog flood native | 02 (cùng vùng code) |
| M5 | `/api/brain` preset đổi thẳng không gate — agent tự kill session, spawn churn, ghi brain.json qua cửa vòng | 04 |
| L1 | Probe `type:path` = oracle tồn-tại-file ngoài vùng đọc sandbox | 05 (ghi nhận trong SECURITY.md, không vá — probe upsert không gate là chủ đích) |
| L2 | `_SENSITIVE_DIRS` mac-centric: thiếu `~/.docker`, `~/.mozilla`, `~/.azure`, `~/.config/gcloud`, `~/.password-store`, 1Password, Windows browser paths | 01 (mở rộng list khi tách) |
| L3 | `/api/emit-event` + `/api/connections` upsert spoof `perm:auto`/`env_scrub` → dashboard sai | 05 (ghi nhận) |
| L4 | urllib forward `X-Bridge-Token` theo 3xx redirect cross-host — invariant mong manh (hiện không endpoint nào 3xx) | 05 (ghi nhận + hardening nhỏ nếu rẻ) |
| L5 | `/api/save-page` + CSP `allow-top-navigation` → trang clone trồng top-navigate ra site lừa đảo | 05 (đổi `allow-top-navigation-by-user-activation` nếu Chrome còn hỗ trợ, verify trước) |
| L6 | `tool`/`tool_call_update` title không kẹp độ dài | 04 (kẹp 200 y perm title) |
| L7 | `/api/prompt` không rate-limit → billing DoS | 05 (ghi nhận — prompt_lock serialize sẵn, throttle để sau) |
| L8 | `perm_pending.clear()` trên ready/done/err → card ACP mồ côi, native dialog treo tới TTL | 02 (kill proc khi clear) |

## Nguyên tắc vá

1. **Fix trước, tách sau — commit riêng.** Security diff phải review
   được trên cấu trúc hiện tại; refactor route table (phase-06) là
   commit riêng không đổi hành vi.
2. **Enforce ở đúng điểm enforce.** Vá ở request-time chỉ là lớp ngoài;
   gen-sandbox (nơi phát quyền thật) phải tự kiểm lại — đúng pattern
   `run_probe` re-validate đã có sẵn.
3. **Tách tối thiểu, có động cơ bảo mật.** `path_guard.py` sinh ra vì
   CAO-2 cần share policy — không chia nhỏ file vì "dài quá". File gạch
   ngang (`gen-sandbox.py`) không `import` được → module mới đặt tên
   underscore theo convention `content_guard`.
4. **Packaging zero-change — nhưng import phải tự bootstrap.** `tools/`
   đã nằm trong `CODE_DIRS` (launcher), `datas` (troly.spec),
   `ALLOW_DIRS` (update.py) → file mới tự đi theo cả 3 đường phân phối.
   ⚠ `runpy.run_path` KHÔNG add script-dir vào `sys.path` (đã test —
   `troly gen-sandbox` frozen sẽ `ModuleNotFoundError`): mọi file .py
   mới import sibling PHẢI tự `sys.path.insert(0,
   os.path.dirname(os.path.abspath(__file__)))` theo convention
   `chat-bridge.py:30`. Bỏ sót dòng này = supervisor/gen_sandbox_profile
   nuốt exception → **spawn não KHÔNG Seatbelt (fail-open âm thầm)**.
5. **`.ps1` đã đóng băng** — endpoint mới/logic mới chỉ vào `.py`
   (PY_ONLY_OK). Riêng CAO-1 phải grep `chat-bridge.ps1` xem có bug
   downgrade tương đương không → quyết định vá tối thiểu hay ghi nhận.
6. **Không phá UX học viên.** Card/dial* vẫn là luồng duyệt quen thuộc;
   thắt chặt không được kẹt onboarding hay portal.

## Phases

1. **phase-01-path-guard** — Tách `tools/path_guard.py`: move
   `_SENSITIVE_DIRS`/`_SENSITIVE_ROOTS`/`path_sensitive`/`rw_grant_ok`
   khỏi chat-bridge, mở rộng list (L2), chat-bridge + gen-sandbox cùng
   import. Move thuần + mở rộng list, chưa đổi hành vi.
2. **phase-02-native-consent** — CAO-1: bỏ `cancel button`, thêm
   `declined` check y `_perm_native_confirm`; M4+L8: `proc.terminate()`
   khi evict/clear + cap số dialog native đồng thời.
3. **phase-03-symlink-toctou** — CAO-2: `_apply` re-validate trên
   realpath; `build_profile` bỏ grant có realpath đụng sensitive/vi phạm
   `rw_grant_ok`.
4. **phase-04-medium-hardening** — M1 (pick `allow_once` trước), M3
   (deny regex + bổ sung binary), M2 (preview instructions trong card
   activate), M5 (gate preset `/api/brain`), L6 (kẹp title).
5. **phase-05-tests-docs** — test mới (path_guard, declined-flow phần
   test được), cập nhật test-gates khai báo `/api/brain`, SECURITY.md
   ghi nhận L1/L3/L7, grep ps1 cho bug tương đương.
6. **phase-06-route-table** (tuỳ chọn, commit riêng) — `do_POST` elif
   chain 660 dòng → `POST_ROUTES` dict; test-gates enumerate dict key
   thay regex-parse source.

## Acceptance

- Bấm Không/Esc trên dialog native → card chết hẳn, `POST /api/respond
  {id, optionId:"ok"}` với Origin+token đúng vẫn 404/invalid — không có
  đường nào apply sau khi user từ chối.
- `ln -s ~/Library/LaunchAgents my-course/x` sau khi grant → spawn não kế
  KHÔNG có `LaunchAgents` trong profile (kiểm: `sandbox-exec -f` rồi
  `touch ~/Library/LaunchAgents/t.plist` bị deny); tương tự symlink `~/.ssh`
  không đọc được trong sandbox; `ln -s ~/Documents x` (đích KHÔNG nhạy
  cảm) cũng bị divergence rule chặn — sandbox chỉ nhận đúng vùng card
  đã hiện.
- `POST /api/permissions` grant hợp lệ → swap symlink → bấm Đồng ý →
  `_apply` từ chối path đã đổi (broadcast err, không ghi grant độc).
- `{"cmd":"python3.12"}`, `{"cmd":"brew"}`, `{"cmd":"gh"}` ở `/api/brain`
  → reject như `python3` hiện nay; `/api/brain {"id":"gemini"}` → 202
  card chứ không đổi thẳng.
- Spam 50 request gated → tối đa N dialog native mở, evict kill proc —
  `ps` không thấy osascript mồ côi.
- `python3 tools/test-gates.py`, `test-parity.py`, `test-bridges.py` PASS.
