---
title: "Vá toàn bộ findings audit 261120 — sandbox tự-thoát, confused deputy, Windows RNG, perf/scale"
description: "Audit sâu 3 mặt (bảo mật / hiệu năng / scale) phát hiện: agent sandboxed tự cấp quyền + ghi được code bridge (escape Seatbelt), bridge làm confused-deputy rò credentials (probe wp + file:// oracle), token Windows sinh bằng Get-Random non-CSPRNG, serve.ps1 serialize + đọc full file mỗi request, nợ parity ps1 tích luỹ"
status: draft
priority: P0
effort: L
branch: main
tags: [security, sandbox, windows, perf, audit-fix]
created: 2026-11-20
depends-on: 261120-1811-lock-down (đã xong — plan này là đợt lock-down tiếp theo)
---

# Vá toàn bộ findings audit 261120

## Bối cảnh

Audit mới nhất (báo cáo trong conversation) chấm nền bảo mật khá tốt nhưng
tìm ra **mâu thuẫn gốc**: thứ bị sandbox (agent) lại nắm chìa khoá của
chính cơ chế khoá nó — ghi được `permissions.json`, `brain.json`,
`tools/*.py`, và gọi được mọi API đặc quyền bằng `BRIDGE_TOKEN` trong env.

## Bản đồ finding → phase

| # | Finding (mức) | Phase |
|---|---|---|
| S1 | Agent tự cấp quyền → thoát Seatbelt (`permissions.json` writable + `/api/permissions` không gate + respawn regen profile) | 01 (chặn ghi file) + 03 (gate API) |
| S2 | `rw={cwd}` cho agent ghi `tools/*.py`, `brain.json`, `AGENTS.md`, `extension/`, `web/` → RCE ngoài sandbox sau restart | 01 |
| S3a | `/api/secrets` merge → đổi `wordpress.url` giữ creds → probe `wp` gửi `Authorization: Basic` tới host attacker | 02 |
| S3b | `/api/connections` nhận probe tuỳ ý → `urlopen(file://)` oracle đọc file ngoài sandbox; probe `path` oracle tồn tại | 02 |
| S4 | `bridge.token` Windows = `Get-Random` (System.Random, non-CSPRNG) ở `start.bat` + `chat-bridge.ps1` | 04 |
| S5 | Windows không enforcement → agent đọc `secrets.local.json` | 04 (ghi nhận limitation, không vá được nhanh — cần cross-user spawn) |
| S6 | So token `-ceq` không constant-time (ps1) | 04 |
| S7 | `/api/brain` args tuỳ ý → `python3 -c`, `find -exec`… = exec code; `terminal` không validate regex → `%BRAIN_TERM%` unquoted trong `.cmd` = cmd injection | 02 (denylist+regex) + 03 (gate custom cmd) + 04 (quote cmd) |
| S8 | `options.html` persist token trước khi verify — phá invariant | 06 |
| S9 | Token lộ qua argv `ttyd -a` → `ps` | 06 (tài liệu accepted-risk) |
| S10 | `term-gate.sh` `read -t` non-POSIX (Linux dash chết); docs nói 3 lần thử, code 1 lần | 06 |
| S11 | `instructions` dict của bot import không kẹp độ dài | 02 |
| S12 | `:8080` GET mở → đọc được `permissions/connections/config/bots.json` | 02 (blocklist JSON nhạy) + đã documented |
| S13 | Robustness: WS unmasked frame, IMPORT_STAGES temp leak, CI không pin SHA | 02, 06 |
| S14 | `fetch` action URL tuỳ ý + credentials → đọc mọi site đã login | 05 (same-site guard) |
| P1 | `serve.ps1` đơn luồng + `ReadAllBytes` (kể cả Range) | 05 |
| P2 | `hist_write` fopen/fclose mỗi event | 05 |
| P3 | `rotate_history` chỉ lúc boot → file phình trong session | 05 |
| P4 | `actClick` 6000×innerText; P5 `assets` 5000×getComputedStyle | 05 |
| P6 | `tinsert` char 35ms/ký tự cứng | 05 |
| C1 | `.logs/*.log` không rotate | 05 |
| C2 | Binary bundle `my-course` 4.4MB (gồm clone-work DOM site thật bên thứ 3) | 05 |
| C3 | Không guard nào chặn bind non-loopback khi code đổi (relay sau này) | 05 |
| C4 | Nợ parity ps1 (history persist, bot endpoints, long-poll) | ghi nhận — không vá trong plan này, chỉ vá phần security trong phase 04 |

## Nguyên tắc vá

1. **Fail-closed**: mọi đường mới mặc định deny; không làm kẹt boot khi
   thiếu tool (giữ pattern hiện tại "lỗi → chạy thường").
2. **Parity**: đổi gì ở `.py` thì port sang `.ps1` cho phần security;
   endpoint không mới → `test-parity.py` không đổi.
3. **Không phá UX học viên**: thẻ xác nhận tái dùng UI perm card có sẵn;
   onboarding vẫn chạy được end-to-end.
4. **Mỗi phase chạy được test độc lập** — `tools/test-bridges.py` mở rộng
   theo từng vá.

## Phases

1. **phase-01** — Sandbox write-model: allowlist ghi thay vì cwd+deny
2. **phase-02** — Bridge hardening: probe schema, secrets url-wipe, cmd
   denylist, S11/S12/S13 nhỏ (chat-bridge.py + serve.py)
3. **phase-03** — Consent gate cho write APIs đặc quyền (`local_pending`
   + portal UX + ps1 port)
4. **phase-04** — Windows parity: RNG, FixedTimeEquals, ps1 port của
   phase-02, term-gate.cmd
5. **phase-05** — Perf & scale: serve.ps1 async+stream, history buffered,
   logs rotate, content.js, seed trim, bind assert
6. **phase-06** — Edge cases + docs + tests + verify toàn bộ

## Acceptance

- Agent trong Seatbelt không ghi được: `tools/`, `brain.json`,
  `AGENTS.md`, `permissions/connections/bots/config.json`, `.devin/agent.sb`.
- `POST /api/permissions` từ agent → tạo card xác nhận, quyền chưa áp
  cho tới khi học viên bấm.
- Probe `file://`/`evil.com` trong connections → 400.
- Đổi `wordpress.url` qua `/api/secrets` → `app_password` bị xoá theo.
- `chat-bridge.ps1` token dùng CSPRNG + so token constant-time.
- `serve.ps1` phục vụ song song + Range không đọc full file.
- `python tools/test-bridges.py` xanh toàn bộ trên macOS; test parity pass.
