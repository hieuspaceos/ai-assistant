---
title: "Vá findings audit đợt 5 — open_url bypass qua pack, save-page ps1 không resolve junction, object data=javascript: trong clone-view, install.ps1 C:\\TroLyAI không writable cho user thường, agent đọc được fleet creds"
description: "Audit đợt 5 chấm 4 vùng (clone-view+save-page, update/apply-pack, setup-agent-user ACL, installer). Nền tốt: save-page .py chặn realpath+..+.html+.bak (148 test xanh), chuỗi release ký ed25519→sha256→whitelist→stage→rollback end-to-end PASS, CSP sandbox opaque-origin đúng, consent gate + re-validate ở enforcement point (gen-sandbox) đúng mô-típ. Nhưng tìm 4 đáng vá: (1) pack merge connections đè open_url không qua check https?:// + consent → pack độc cài nút 'Mở trang' javascript: → XSS portal, trộm bridge token; (2) save-page ps1 dùng GetFullPath lexical — junction trong my-course cho agent ghi .html bất cứ đâu với quyền owner (.py dùng realpath, không lỗi — parity gap); (3) prepareEditable sót <object data='javascript:'> — chạy same-origin trong srcdoc khi sửa → đọc localStorage token; (4) install.ps1 → C:\\TroLyAI ACL mặc định chỉ RX cho user thường → app không ghi được .devin/my-course khi chạy không-elevated — trái tuyên bố 'không cần admin lúc chạy'. Kèm hàng loạt low: pack path drive-absolute Windows, fetch_pack follow redirect, ALLOWLIST_DENY thiếu interpreter, agent đọc được machine.key/fleet.json/license.json, re-install đè my-course data."
status: implemented
priority: P1
effort: M
branch: main
tags: [security, windows, acl, pack, xss, deploy]
created: 2026-11-26
depends-on: 261126-1145-audit-3-fix (đã xong), 261126-1255-audit-4-fix (đã xong)
---

# Vá findings audit đợt 5

## Bối cảnh

Audit bao phủ: `web/app.js` + `web/clone-view.html` (~1800 dòng) +
`_h_save_page` cả hai bridge, `tools/update.py` + `tools/apply-pack.py`
(kèm `launcher.apply_pending`, `content_guard.exec_allowed`,
`gen-sandbox._grant_ok`, `path_guard`), `tools/setup-agent-user.ps1`,
`deploy/install.sh` + `install.ps1`. Đã chạy thật
`test-distribution.py` (35 xanh) + `test-bridges.py` (148 xanh).

Mô-típ lỗi đợt này: **mỗi đường ghi có một cửa vòng không qua gate mà
đường chính có** — pack ghi `connections.json`/`permissions.json` trực
tiếp file, ps1 enforce yếu hơn py ở cùng endpoint, installer ghi đè
data user. Khác đợt 3 (TOCTOU request↔enforce), đợt này là "đường tắt
chưa đi qua lưới".

## Bản đồ finding → phase

| # | Finding (mức) | Phase |
|---|---|---|
| F1 | `install.ps1` → `C:\TroLyAI`: ACL mặc định chỉ cho Users RX → app non-elevated không ghi `.devin/`/`my-course` (trái DEPLOY.md "không cần admin lúc chạy") — CI chạy admin nên không bắt được. **Vá = grant `Users:M` nhưng troly-agent ∈ Users → BẮT BUỘC đi kèm re-seal agent ở phase-03, nếu không tự tạo sandbox escape** (CAO — cần verify Windows thật) | 04 (+03) |
| F2 | Pack `connections` merge ghi thẳng `open_url` — bypass check `^https?://` + consent card của `_h_connections` → `javascript:` open_url → `window.open` XSS trong origin portal → trộm `bridge_token` (CAO theo mô hình pack=trusted-channel, MEDIUM thực tế) | 01 |
| F3 | `chat-bridge.ps1` `_h_save_page` dùng `GetFullPath` (lexical, không resolve junction/reparse) — agent tạo junction `my-course\link` rồi save-page ghi `.html` ra ngoài với quyền owner; `.py` `realpath` không lỗi (MED) | 02 |
| F4 | `clone-view prepareEditable` chỉ neutralize `href\|src\|action\|formaction\|xlink:href` — `<object data="javascript:…">` sống trong srcdoc same-origin → script đọc `localStorage.bridge_token` khi học viên mở chế độ sửa (MED) | 02 |
| F5 | `apply-pack lint` sót path drive-absolute Windows (`C:/x`, `C:x`) trong skills filenames / workflows names / mycourse_files → `os.path.join` escape khỏi dir đích trên Windows (MED) | 01 |
| F6 | Agent (troly-agent) đọc được `.devin\machine.key`, `fleet.json` (`beacon_secret` org), `license.json` — RX thừa hưởng từ $Root; agent chỉ cần `bridge.token`. Kèm F6b: `my-course\manifest.json` chưa có Deny-Write (agent sửa được ngay hôm nay) (MED-LOW) | 03 |
| F7 | Re-install (`install.sh`/`install.ps1`) đè `my-course/` — reset `config.json` (learner_name rỗng → máy thành "mới" → pack re-áp `permissions_template` + `exec_allowlist`), `manifest.json`, `bots.json` (MED) | 04 |
| F8 | `fetch_pack` dùng `urlopen` mặc định → follow redirect (khác chủ đích `NoRedirect` của update.py); sha256 hint optional → pack qua redirect không có integrity binding ngoài TLS (LOW) | 01 |
| F9 | `ALLOWLIST_DENY` thiếu interpreter (`pwsh`, `cmd`, `zsh`, `find`, `git`, `tar`, `docker`, `uv`, `conda`…) — pattern `pwsh *` qua lint → auto-duyệt `pwsh -c <bất kỳ>`. Vá = trích `BRAIN_CMD_DENY` ra module chung + so **first-token** (substring-match không dùng được — `r`/`at`/`go`/`env` khớp mọi pattern) + đồng bộ `exec_allowed` enforcement (LOW) | 01 |
| F10 | `permissions_template` không lint — pack cấp `/` read-write cho máy mới; macOS được cứu bởi `gen-sandbox._grant_ok` re-check, Windows KHÔNG có lớp đó (setup-agent-user grant trần) (LOW) | 01 (lint) + 03 (note) |
| F11 | `setup-agent-user.ps1` grant loop theo permissions.json không check sensitive/drive-root — parity gap với `_grant_ok` bên macOS (LOW) | 03 |
| F12 | SRC regex clone-view cho `..` trong `?src=` (view-only — server vẫn chặn write); siết cho rõ nghĩa (LOW) | 02 |
| F13 | `install.sh` `tar 2>/dev/null` nuốt lỗi; robocopy exit ≥8 không check; `.trash` + dev artifacts (`trang-*.html`, `e2e-clone.html`) đi theo gói cài (LOW) | 04 |
| F14 | CSP `allow-top-navigation` — trang clone top-navigate cả tab portal ra site lừa đảo (residual đã ghi nhận audit-3 L5; verify `allow-top-navigation-by-user-activation` trên Chrome/Safari rồi quyết) | 05 |
| F15 | Pack `devin_files` → `mcp_config.json` = kênh exec-từ-xa theo thiết kế (MCP server do org đẩy) — ghi rõ trong SECURITY.md, chưa vá (NOTE) | 05 |
| F16 | `update.py fetch(zip_url, _read(MKEY_FP))` gửi machine.key cả khi tải zip từ vendor ORIGIN — key org lộ cho bên thứ 3 (LOW) | 01 |

## Nguyên tắc vá

1. **Parity .py ↔ .ps1.** Mọi vá ở một bên phải xem bên kia — đợt này
   có 2 parity gap (F3, F11). Sửa `.ps1` xong PHẢI ghi file kèm BOM
   (bài học audit đợt 1: file thiếu BOM làm lệch nội dung ghi ra đĩa).
2. **Pack = trusted-channel nhưng lint vẫn là lưới.** Collector bị
   chiếm là threat model đã khai (SECURITY.md) — lint phía máy là
   lớp cuối, không được lường trước "collector xịn".
3. **Enforce ở đúng điểm enforce.** open_url check phải sống ở cả
   `_h_connections` (API path) và `apply-pack` (file path) — giống
   pattern path_guard của audit-3.
4. **`apply-pack.py` chưa có `sys.path.insert(0, TOOLS)`** — muốn
   import `path_guard` cho F10 phải thêm dòng bootstrap đó (convention
   audit-3 point 4 — `runpy.run_path` không add script-dir).
5. **Installer = file chạy máy người dùng** — vá bằng cách nhỏ nhất:
   grant ACL, skip data-files tồn tại, check exit code. Không cấu
   trúc lại luồng cài.
6. **Test trước docs sau.** Mỗi vá có test tương ứng trong
   test-distribution / test-bridges / test-parity; SECURITY.md cập
   nhật accepted-risk/residual ở phase cuối.
7. **Grant mới không được phá deny cũ.** Vá ACL cho owner
   (`BUILTIN\Users:M`) trao luôn cho troly-agent cùng group — mọi
   grant mới phải đối chiếu danh sách deny hiện có và re-seal nếu
   cần (bài học F1×F6b: installer vá quyền cho owner nhưng mở cửa
   cho agent).

## Done khi

- `python3 tools/test-distribution.py tools/test-bridges.py
  tools/test-parity.py tools/test-packs.py tools/test-gates.py` PASS.
- CI `test-windows` xanh; thêm step mới (nếu có) xanh.
- SECURITY.md ghi đủ residual mới (F14 quyết định xong, F15, F10-note).
