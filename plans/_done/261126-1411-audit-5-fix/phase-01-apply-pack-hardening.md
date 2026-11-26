# Phase 01 — `apply-pack.py` + `update.py`: bịt các cửa vòng quanh gate

## Vá

**F2 — pack `connections` bypass open_url check.** `_h_connections`
(chất lượng tốt — chat-bridge.py:1910) ép `open_url` `^https?://` +
consent card khi đổi; `apply()` merge thẳng vào `connections.json`
không qua lưới đó. Pack độc cài `open_url: "javascript:…"` → nút
"Mở trang" trong portal → `window.open` chạy script trong origin
portal → trộm `bridge_token`.

Trong `lint()`: với mọi entry `pack["connections"]`, reject pack nếu
`open_url` có giá trị và không khớp `^https?://` (case-insensitive).

```python
for c in (pack.get("connections") or []):
    ou = str(c.get("open_url") or "")
    if ou and not re.match(r"^https?://", ou, re.I):
        raise ValueError(f"connections[{c.get('id')}]: open_url chỉ nhận http(s)")
```

`probe` KHÔNG bắt buộc lint: `run_probe` (chat-bridge.py:1046) re-validate
lại probe ngay trước khi chạy → probe độc cài qua pack chỉ cho kết quả
"kiểu kết nối lạ", không phải lỗ hổng sống. Muốn defense-in-depth thì
trích `validate_probe` sang module chung — `chat-bridge.py` tên gạch
ngang không import được (đúng lý do path_guard.py tách ra).

**F5 — path drive-absolute Windows.** `skills` filenames,
`workflows` names, `mycourse_files` lint chặn `/`-đầu + `..` + `\\`
nhưng `"C:/x.md"` hay `"C:x.md"` (drive-relative) qua hết →
`os.path.join(dir, "C:/x.md")` trên Windows = absolute → ghi ra ngoài
`.devin/skills`/`my-course`.

Thêm helper dùng chung trong apply-pack:

```python
def _bad_relpath(fn):
    return (fn.startswith("/") or ".." in fn.split("/")
            or "\\" in fn or re.match(r"^[A-Za-z]:", fn))
```

Áp cho: skill filenames (đã có check `startswith("/")`/..`/`\\` — thêm
drive), workflow names, mycourse_files names. Test trên macOS vẫn
được — check là pure-string, không cần Windows.

**F8 — `fetch_pack` follow redirect.** Đổi sang opener `NoRedirect`
giống update.py — kéo class `NoRedirect`/`OPENER` xuống dùng chung
(hoặc copy 6 dòng — module nhỏ, không cần tách file). Kèm đó: nếu
`hint` THIẾU `sha256` thì vẫn áp nhưng in cảnh báo? — KHÔNG: giữ
hành vi hiện tại (pack không-sha256 vẫn áp, TLS+machine.key là đủ
theo threat model), chỉ chặn redirect.

**F9 — `ALLOWLIST_DENY` thiếu interpreter.** Sửa bằng hai bước, KHÔNG
chỉ nối thêm substring:

1. **Trích deny-set ra module chung.** `BRAIN_CMD_DENY` +
   `_BRAIN_CMD_DENY_RE` (chat-bridge.py:161-220) là set ~100 từ đã
   được audit-3 kỹ lưỡng — nhân bản tay vào apply-pack = drift chắc
   chắn (bài học audit-3). Trích ra module importable — gộp vào
   `path_guard.py` (đã là "policy dùng chung") hoặc file mới
   `cmd_deny.py`; chat-bridge import lại.

2. **So first-token, không substring.** Deny-set có tên ngắn (`r`,
   `at`, `su`, `go`, `env`, `man`, `less`, `open`) — substring-match
   khớp mọi pattern → false-positive khắp nơi. Thay vào đó trong
   `lint()`: lấy token đầu của pattern (`str(pat).split()[0].lower()`,
   bóc `./`, `.exe`) → `_brain_cmd_denied()` → reject. Giữ nguyên
   `ALLOWLIST_DENY` substring hiện có cho metachar + tool exfil.

3. **Đồng bộ enforcement.** `exec_allowed` (content_guard.py:217) chỉ
   lọc metachar — yếu hơn lint. Thêm cùng first-token check ở đó để
   `exec-allowlist.json` sửa tay chứa `"pwsh *"` không qua được
   (phòng hờ — file đó agent không ghi được sau re-seal phase-03/04,
   nhưng enforcement-point recheck là đúng mô-típ).

**F10 — `permissions_template` lint nhẹ.** Không cấm quyền rộng (IT
provisioning là chủ đích), nhưng chặn các path mà enforcement bên
macOS cũng drop — để pack sai lộ ngay lúc apply thay vì im lặng:

- Thêm `sys.path.insert(0, TOOLS)` đầu file (chưa có — bắt buộc để
  import sibling, convention audit-3).
- `from path_guard import path_sensitive, rw_grant_ok`.
- Trong `lint()`: `f.get("path")` qua `path_sensitive` → reject pack;
  `access == "read-write"` qua `rw_grant_ok(p, ROOT)` → reject.
- **Reject path chứa `%` env-var**: `%USERPROFILE%` không expand bởi
  `os.path.expanduser` trên POSIX → lọt `path_sensitive` khi lint trên
  mac, nhưng `setup-agent-user.ps1` `ExpandEnvironmentVariables` expand
  trên Windows → grant M trên home. Chặn `"%" in path` (fail-closed,
  pack legit dùng `~` hoặc absolute).
- Lưu ý: `path_sensitive` list là POSIX+Windows-vía-`~\` — entry
  `C:\…` trong pack sẽ resolve theo host chạy lint; đó là đúng ý đồ
  (pack áp trên Windows thì lint theo ngữ cảnh Windows).

**F16 — `update.py` gửi machine.key cho vendor origin.** `fetch(
zip_url, _read(MKEY_FP))` đèo `X-Beacon-Key` kể cả khi zip_url là
ORIGIN vendor → key pairing org lộ cho bên thứ 3 (vendor học được
key → giả máy với collector). Sửa: zip fetch chỉ kèm key của nguồn
manifest đang dùng. Chi tiết implement: `pick_manifest()` hiện chỉ
trả `(man, man_url)` — cần trả thêm `key` nguồn (manifest_sources
đã ghép url↔key sẵn: collector→key, ORIGIN→None), hoặc trong
`main()` so `netloc(zip_url)` với `fleet.collector` rồi mới đọc
MKEY_FP.

## File

| File | Việc |
|---|---|
| `tools/apply-pack.py` | thêm `sys.path.insert` + import `re`, `path_guard`, `cmd_deny`; lint open_url/drive-path/`%`-env/sensitive-perms; first-token deny check; NoRedirect opener |
| `tools/update.py` | zip fetch chỉ kèm key theo nguồn manifest |
| `tools/cmd_deny.py` (mới, hoặc gộp `path_guard.py`) | trích `BRAIN_CMD_DENY` + regex từ chat-bridge |
| `tools/chat-bridge.py` | import deny-set từ module chung, xoá bản nội bộ |
| `tools/content_guard.py` | `exec_allowed` thêm first-token deny (enforcement parity lint) |

## Verify

- `python3 tools/test-distribution.py` — thêm case:
  - pack `connections` `open_url: "javascript:alert(1)"` → reject.
  - pack `skills: {"s": {"C:/evil.md": "x"}}` + workflow `"C:/w.json"`
    + `mycourse_files: {"C:x.md": "x"}` → reject.
  - pack `permissions_template: [{"path": "/", "access": "read-write"}]`
    → reject (path_sensitive bắt root).
  - pack `exec_allowlist: ["pwsh *"]` → reject.
- `test-parity.py` không đụng (không thêm endpoint).
