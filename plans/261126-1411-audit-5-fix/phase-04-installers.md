# Phase 04 — `deploy/install.sh` + `install.ps1`: ACL đích + không đè data

## Vá

**F1 — `C:\TroLyAI` không writable cho user thường (CAO).**
install.ps1 cần admin, Dest mặc định `C:\TroLyAI` — ACL mặc định chỉ
cho `BUILTIN\Users:(OI)(CI)RX`. App chạy non-elevated cần ghi
`.devin/` (bridge.token, machine.id…), `my-course/`, `.logs/` →
**toàn bộ bridge chết** trên máy nhân viên không phải admin.
DEPLOY.md tuyên bố "không cần admin lúc chạy" — đây là blocker
tiềm tàng chưa ai chạy thử (CI `test-windows` luôn elevated).

Sau robocopy, grant Modify cho user sẽ chạy app. User cài ≠ user chạy
(IT cài hộ) — grant cho `BUILTIN\Users` là đúng mặc định SMB:

```powershell
# user thường chạy app cần ghi .devin + my-course + .logs —
# C:\<dir> mặc định chỉ cho Users RX → app chết khi non-elevated
icacls $Dest /grant "BUILTIN\Users:(OI)(CI)M" /T /Q | Out-Null
```

⚠ **Grant này phải đi kèm re-seal agent trong phase-03** —
`troly-agent` cũng thuộc `BUILTIN\Users` → được M toàn cây, gồm
`.devin\exec-allowlist.json` (tự duyệt exec — `exec_allowed` chỉ lọc
metachar), `.devin\update-stage`+`update-pending.json` (RCE quyền
owner lúc boot), `start.bat`/`AGENTS.md`/`collector-web`/`templates`
(chưa nằm trong Deny-Write). Không có bước deny-W trên `$Root` +
`/remove:d` trong 3 dir writable (phase-03 F6b) thì vá này TẠO lỗ
sandbox escape mới — hai phase phải đi cùng nhau.

Cân nhắc: `BUILTIN\Users` hơi rộng (mọi user local sửa được app) —
máy SMB một-user là chuẩn; nếu muốn siết hơn có thể grant theo
`$env:USERNAME` kèm switch `-ForUser`. Chọn `BUILTIN\Users` làm mặc
định, ghi nhận trong DEPLOY.md cho môi trường multi-user.

**F7 — re-install đè `my-course/` data.** Cả hai script copy trọn
`my-course` → ghi đè `config.json` (mất learner_name → máy thành
"mới" → pack re-áp permissions_template + exec_allowlist),
`manifest.json`, `bots.json`, `connections.json`, `permissions.json`
— mất hết consent đã duyệt.

- `install.sh`: chia my-course thành 2 phần — **6 file state**
  (`config.json`, `manifest.json`, `bots.json`, `permissions.json`,
  `connections.json`, `bot.md`) là của học viên → chỉ copy nếu đích
  chưa có; phần còn lại (lessons, workflows, intro seed) copy /XO để
  nâng cấp vẫn nhận seed mới. Implement: vẫn một tar nhưng build
  exclude-list động — nếu `$DEST/my-course` đã tồn tại thì thêm
  `--exclude='my-course/config.json' --exclude='my-course/manifest.json'
  ...` cho 6 file đó; lần đầu thì không exclude gì. KHÔNG skip cả
  my-course khi reinstall (như bản nháp trước) — mất cập nhật seed.
  Thêm `--exclude='my-course/.trash'`.
- `install.ps1`: tương tự — robocopy my-course với `/XF` 6 file state
  khi `$Dest\my-course` đã có, rồi `Copy-Item` từng file nếu thiếu.
  `/XO` (chỉ đè khi nguồn mới hơn) cho phần còn lại để giữ chỉnh sửa
  của học viên trong lesson khi package không mới hơn.

**F13 — nuốt lỗi + dev artifacts.**
- `install.sh`: bỏ `2>/dev/null` trên tar (hoặc kiểm `PIPESTATUS`/
  exit của tar cf — pipeline POSIX sh check exit của lệnh cuối;
  đơn giản: tách `tar cf` vào biến rồi `tar xf` hai bước, hoặc giữ
  pipe nhưng `set -o pipefail` không có trên sh → kiểm thủ công:
  `tar cf - … | tar xf - … || { echo "copy loi"; exit 1; }`).
  Thêm `--exclude='my-course/.trash'`.
- `install.ps1`: sau mỗi robocopy check `$LASTEXITCODE -ge 8` →
  báo lỗi + exit 1 (robocopy 0–7 = ok theo convention).
- Cả hai: dev artifacts `trang-*.html`, `e2e-clone.html`,
  `my-course/.trash`, `my-course/clone-work` — clone-work đã exclude;
  thêm `.trash`. Các `trang-*.html`/`e2e-clone.html` là demo seed —
  quyết định giữ hay exclude khi implement (hỏi owner nếu cần).

## File

| File | Việc |
|---|---|
| `deploy/install.ps1` | F1 icacls Users:M; F7 skip my-course đã có; F13 robocopy exit check |
| `deploy/install.sh` | F7 my-course chỉ seed lần đầu; F13 lỗi tar + exclude .trash |
| `deploy/DEPLOY.md` | ghi chú quyết định ACL (BUILTIN\Users vs -ForUser) |

## Verify

- Windows thật (hoặc runner): cài vào `C:\TroLyAI` dưới admin →
  đăng nhập user thường (hoặc runas /trustlevel:0x20000) →
  `start.bat` → `localhost:8080` portal mở + `.devin\bridge.token`
  được tạo. CI hiện không có step non-elevated — thêm step trong
  `test-windows` nếu khả thi (`runas` cần password → skip CI, verify
  tay; hoặc tạo user thứ hai + `runas /user:stduser`).
- Re-run installer trên install cũ → `my-course/config.json` giữ
  nguyên learner_name.
- `install.sh` trên macOS với DEST mới → copy đủ; DEST cũ →
  my-course giữ nguyên.
