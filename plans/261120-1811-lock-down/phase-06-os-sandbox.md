# Phase 6 — OS sandbox: biến permissions.json thành enforcement thật

## Mục tiêu

Hiện `permissions.json` là **policy** — agent được dặn tôn trọng nhưng
không gì cản về kỹ thuật (não chạy shell full quyền user → đọc được
`~/.ssh`, `~/Documents`, Keychain...). Phase này bọc process não trong
sandbox tầng OS:

- **macOS (thực thi trong phase này):** `sandbox-exec` (Seatbelt) —
  đã verify còn hoạt động trên Darwin 27. Đây cũng là cách Claude
  Code sandbox agent trên macOS.
- **Windows (thiết kế + script khung, chờ máy verify):** user account
  hạn chế `troly-agent` + NTFS ACL — không cần VM/hypervisor.

**Đã kiểm chứng trên máy dev:**

```
sandbox-exec -p '(version 1)(deny default)(allow process* file-read*)
  (deny file-read* (subpath "~/Documents"))' /bin/ls ~/Documents
→ ls: Operation not permitted     ← deny thắng allow, đúng cơ chế dùng
```

## Mô hình áp dụng

Whitelist đúng semantics `permissions.json`: **deny default**, rồi cho:

| Tài nguyên | Rule | Lý do |
|---|---|---|
| `ai-assistant/` (CWD) | `file-read* file-write*` | lessons, .devin/skills, logs, manifest |
| Folder `access:"read"` | `file-read*` | đúng quyền đã cấp |
| Folder `access:"read-write"` | `file-read* file-write*` | đúng quyền đã cấp |
| System/tool paths | `file-read*` | `/usr /System /bin /sbin /Library /opt /private/etc /dev` + tool dirs: `~/.nvm ~/.npm ~/.local ~/.cache ~/Library/Caches ~/Library/pnpm` — não/npx/python sống đây |
| `/tmp`, `$TMPDIR` | `file-read* file-write*` | temp |
| `.devin/bridge.token` | **deny write** (read vẫn cho — agent cần để gọi bridge) | agent bị lừa không đổi được chìa khoá |
| `.devin/secrets.local.json` | **deny read + write** | chỉ bridge/probe đọc, agent không cần |
| `.devin/mcp_config.local.json` | **deny read + write** | MCP env có thể chứa API key; agent không cần đọc (`session/new` truyền `mcpServers:[]` từ bridge) |
| `process*`, `mach*`, `sysctl-read` | allow | fork/exec/IPC — Seatbelt enforce ở FS+net, không cần siết exec |
| `network-outbound` | allow | não BẮT BUỘC gọi API LLM (devin.ai, anthropic...) + bridge localhost |
| `network-bind` | **deny** | não không được mở server — mọi dịch vụ hợp lệ do start script mở, không phải não |

Residual ghi rõ: exfil qua `network-outbound` vẫn được (không siết
được host vì mỗi preset não một endpoint khác nhau) — sandbox chặn
**đọc/ghi file trái phép**, không chặn não gửi data nó đã đọc hợp lệ
ra internet. Đó là giới hạn cố hữu của "não phải có internet mới sống".

## File động

| File | Action | Việc |
|---|---|---|
| `tools/gen-sandbox.py` | create | đọc `permissions.json` → sinh `.devin/agent.sb` (stdlib, không dep) |
| `tools/chat-bridge.py` | modify | `spawn_brain()` trên darwin: regen profile + wrap `sandbox-exec -f` |
| `tools/chat-bridge.py` | modify | `POST /api/permissions` **và `/api/remove-permission`** → regen profile (áp spawn kế tiếp) — draft đầu chỉ nhắc add, quên remove |
| `start.sh` + `tools/launcher.py` | modify | gen profile lúc boot (launcher: trong `supervisor()`/`ensure_token()` trước spawn — term-gate cần file có sẵn) |
| `tools/term-gate.sh` | modify | `exec sandbox-exec -f "$SB" $BRAIN_TERM` khi darwin + file tồn tại |
| `tools/setup-agent-user.ps1` | create | Windows: tạo `troly-agent` + icacls theo permissions.json |
| `tools/chat-bridge.ps1` | modify | (chờ Windows) spawn não qua `runas /savecred` |
| `tools/test-bridges.py` | modify | case: não qua sandbox không đọc được ~/Documents (mac-only) |
| `docs/SECURITY.md` | modify | permissions.json: "policy" → "enforced trên macOS; Windows đang triển khai" |
| `docs/troubleshooting-runbook.md` | modify | mục "não không chạy tool X trong sandbox → escape hatch" |

## Chi tiết macOS

### Profile sinh động

`tools/gen-sandbox.py` sinh `.devin/agent.sb` mỗi lần spawn (thay vì
file tĩnh) — số folder quyền biến động, và `/api/permissions` mới cấp
phải có hiệu lực spawn kế tiếp mà không sửa profile tay:

```scheme
(version 1)
(deny default)
(allow process* mach* sysctl-read)
(allow file-read-metadata)
(allow network-outbound)
(deny network-bind network-inbound)
(allow file-read* file-write* (subpath "<CWD>"))
(allow file-read* file-write* (subpath "/tmp") (subpath "/private/tmp")
       (subpath "<TMPDIR>"))
(allow file-read* (subpath "/usr") (subpath "/System") (subpath "/bin")
       (subpath "/sbin") (subpath "/Library") (subpath "/opt")
       (subpath "/private/etc") (subpath "/dev")
       (subpath "~/.nvm") (subpath "~/.npm") (subpath "~/.local")
       (subpath "~/.cache") (subpath "~/Library/Caches"))
;; từ permissions.json:
(allow file-read* (subpath "<dir-1>"))            ;; access=read
(allow file-read* file-write* (subpath "<dir-2>")) ;; access=read-write
;; carve-out trong CWD — đặt SAU allow (deny thắng):
(deny file-write* (literal "<CWD>/.devin/bridge.token"))
(deny file-read* file-write* (literal "<CWD>/.devin/secrets.local.json"))
(deny file-read* file-write* (literal "<CWD>/.devin/mcp_config.local.json"))
```

### Áp vào spawn

```python
# chat-bridge.py — Acp.__init__, darwin only
if sys.platform == "darwin" and os.environ.get("TROLY_NO_SANDBOX") != "1":
    sb = gen_sandbox_profile()        # gọi gen-sandbox.py inline
    argv = ["/usr/bin/sandbox-exec", "-f", sb, brain["cmd"], *args]
else:
    argv = [brain["cmd"], *args]
```

`TROLY_NO_SANDBOX=1` là escape hatch debug — ghi rõ trong runbook,
KHÔNG set mặc định.

`term-gate.sh`: `exec` qua `sandbox-exec -f "$ROOT/.devin/agent.sb"`
khi `uname = Darwin` và file tồn tại — Terminal mode cũng được bọc.
`$ROOT` = thư mục chứa gate (`dirname "$0"`/..) — trong packaged layout
đó là `~/TroLyAI` (DATA), khớp với chỗ launcher gen profile. Nếu file
chưa kịp sinh (race boot) → gate chạy unsandboxed: chấp nhận, hoặc gọi
`gen-sandbox.py` lazy ngay trong gate trước khi exec.

### Chỗ dễ hỏng (test kỹ)

- **Tool path lạ**: não cài ở `~/something/bin` không có trong list →
  không exec được → brain dead. Mitigation: profile thêm
  `(allow file-read* (subpath "<dirname của shutil.which(cmd)>"))`
  — gen-sandbox resolve path não đang dùng rồi auto-allow cha nó.
  Cộng thêm allow read `~/Library/Python`, `~/.pyenv`, `/usr/local`.
- **npx/brew cache write**: `~/.npm ~/.cache` cho ở nhóm WRITE luôn;
  thêm `~/Library/Caches` write (Homebrew cache nằm đó).
- **deny `network-bind` → não không mở được dev-server tạm**: agent đôi
  khi cần `python -m http.server`/`npm run dev` để preview cho học viên.
  Đây là trade-off có chủ đích (portal :8080 đã serve được file tĩnh);
  nếu skill nào thật sự cần thì nới thành
  `(allow network-bind (local ip "localhost:*"))` — bind loopback vẫn
  an toàn, chỉ cấm bind ra mạng ngoài.
- **skill dùng ffmpeg/ttool ngoài PATH thường**: test `/nen-anh`,
  `/render-video` end-to-end trong sandbox.

## Chi tiết Windows (thiết kế — chờ máy verify)

`tools/setup-agent-user.ps1` (chạy MỘT lần, cần admin):

```powershell
# tạo user hạn chế + cấp ACL theo permissions.json
net user troly-agent <random-pass> /add
icacls "<CWD>" /grant "troly-agent:(OI)(CI)F" /T
# mỗi entry permissions.json:
icacls "<dir>" /grant "troly-agent:(OI)(CI)R" /T    # read
icacls "<dir>" /grant "troly-agent:(OI)(CI)M" /T    # read-write
```

Spawn não dưới user đó — **RÀO KỸ THUẬT LỚN, phải nghiên cứu trước
khi code**: `runas`/`Start-Process -Credential` **không redirect được
stdin/stdout** — mà ACP sống nhờ stdio pipe. `chat-bridge.ps1` không
spawn được não cross-user bằng cách đó. Các hướng thật:

- `CreateProcessWithLogonW` qua `Add-Type` (C#/PInvoke trong .ps1) với
  pipe handles — khả thi nhất, vài chục dòng unmanaged signature.
- `python3 tools/run-as-user.py` dùng ctypes — nhưng Windows có thể
  thiếu Python thật (chính lý do chat-bridge.ps1 tồn tại).
- `PsExec -u troly-agent` (Sysinternals, cần cài ngoài + EULA).

Nếu không hướng nào chạy sạch trên máy thật → chấp nhận nợ parity
"macOS enforced, Windows policy-only" và ghi rõ trong SECURITY.md —
đúng pattern các plan trước, KHÔNG tuyên bố enforcement khi chưa verify.

**Gap thứ hai trên Windows**: terminal-mode (ttyd → `term-gate.cmd` →
não) chạy trong session user thường — não qua cửa ttyd KHÔNG bị ACL
gì cả. Muốn parity thật thì gate.cmd cũng phải chạy não dưới
`troly-agent` (khó: runas trong ttyd không pipe stdio gọn + cần
/savecred). Ghi nhận đây là residual của Windows path, kèm vào nợ
parity nếu không giải được.

## Test

| # | Case | Kỳ vọng |
|---|------|---------|
| 31 | não qua sandbox đọc `~/Documents/x` | Operation not permitted |
| 32 | não đọc/ghi trong `my-course/` | bình thường |
| 33 | não đọc folder `access=read`, ghi thử | đọc được, ghi fail |
| 34 | `TROLY_NO_SANDBOX=1` | spawn như cũ (escape hatch) |
| 35 | `/api/permissions` thêm folder → spawn lại | folder mới đọc được |
| 36 (tay) | `/hoc-bai` + skill `/doc-zalo` end-to-end | bridge call localhost vẫn sống trong sandbox |

## Out of scope

- AppContainer/Windows Sandbox (VM) — nặng, chỉ cân nhắc nếu user-account
  approach chứng minh không khả thi.
- Siết `network-outbound` theo host — fragile với multi-brain.
- Sandbox serve/ext-bridge process — chúng là trust boundary, không
  phải phần mềm độc tiềm năng (não mới là).
