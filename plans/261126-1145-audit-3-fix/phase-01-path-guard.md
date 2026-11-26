# Phase 01 — Tách `tools/path_guard.py` (policy đường dẫn dùng chung)

## Vá

**Nền cho CAO-2 + L2.** Hiện `path_sensitive`/`_SENSITIVE_DIRS`/
`_SENSITIVE_ROOTS`/`rw_grant_ok` chỉ sống trong `chat-bridge.py`
(~906–978). Fix CAO-2 ở phase-03 cần **cùng một policy** được kiểm ở cả
3 điểm: request-time (chat-bridge), apply-time (chat-bridge), và
profile-build (gen-sandbox). Nhân bản list qua hai file = chắc chắn
drift — phải một module chung.

## File mới `tools/path_guard.py`

Tên **underscore** — bắt buộc: `gen-sandbox.py` gạch ngang không
`import` được; `content_guard` đã làm tiền lệ. Module thuần hàm, không
state, không import gì ngoài `os`.

Move nguyên văn từ chat-bridge.py (~906–978):

- `_SENSITIVE_DIRS`, `_SENSITIVE_ROOTS`, `_SENSITIVE_ROOTS_L`,
  `_SENSITIVE_DIRS_L`
- `path_sensitive(p)` — giữ nguyên logic so hai chiều + case-insensitive
- `rw_grant_ok(p)` — đổi chữ ký: hiện đọc module-global `CWD` của
  chat-bridge → chuyển thành `rw_grant_ok(p, cwd)`; chat-bridge gọi
  `rw_grant_ok(p, CWD)`, gen-sandbox gọi `rw_grant_ok(p, cwd)` của nó.
  Vùng writable mặc định (`my-course/`, `.devin/skills/`, `.logs/`)
  giữ nguyên, resolve từ `cwd` truyền vào.

## Mở rộng `_SENSITIVE_DIRS` (L2) — làm luôn trong phase này

List hiện thiên macOS. Bổ sung:

```
# credential cloud/devops còn sót
"~/.docker", "~/.azure", "~/.config/gcloud", "~/.password-store",
# Firefox trên Linux + password manager phổ biến
"~/.mozilla", "~/Library/Application Support/1Password",
"~/.config/1Password",
# Windows browser profile/credential (APPDATA/LOCALAPPDATA resolve qua
# expanduser trên win — list này check được cả khi bridge chạy Windows)
"~\\AppData\\Local\\Google\\Chrome", "~\\AppData\\Local\\Microsoft\\Edge",
"~\\AppData\\Local\\BraveSoftware", "~\\AppData\\Roaming\\Mozilla",
"~\\AppData\\Roaming\\1Password",
```

(Đã verify semantics: trên Windows `ntpath.expanduser` nhận cả `~\` lẫn
`~/` → resolve đúng; trên POSIX `~\` không phải sep nên entry giữ
nguyên literal → không match gì, vô hại — comment rõ trong code.)

## Sửa `chat-bridge.py`

- Xoá block `_SENSITIVE_*` + `path_sensitive` + `rw_grant_ok` (~70 dòng).
- Thêm import bên cạnh `content_guard`:

```python
from path_guard import path_sensitive, rw_grant_ok
```

- Mọi call site `rw_grant_ok(p)` → `rw_grant_ok(p, CWD)`.

## Sửa `gen-sandbox.py` — BẮT BUỘC thêm sys.path bootstrap

`runpy.run_path` KHÔNG add script-dir vào `sys.path` (đã test thật).
`gen-sandbox.py` hiện không có dòng bootstrap — ba đường chạy của nó:

| Đường chạy | sys.path có tools/? |
|---|---|
| `python3 tools/gen-sandbox.py` | có (script dir tự add) |
| `runpy.run_path` từ `gen_sandbox_profile()` trong chat-bridge | có (kế thừa `chat-bridge.py:30`) |
| `troly gen-sandbox` / launcher `run_tool` frozen | **KHÔNG — sys.path=_MEIPASS, không có _MEIPASS/tools** |

→ BẮT BUỘC thêm trước import, theo convention `chat-bridge.py:30`,
`ext-bridge.py:44`, `sign-release.py:23`:

```python
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from path_guard import path_sensitive, rw_grant_ok   # noqa: E402
```

⚠ Hệ quả nếu quên dòng này: `launcher.supervisor()` bọc
`run_tool("gen-sandbox")` trong `try/except: pass`, và
`gen_sandbox_profile()` trả `None` khi runpy raise → **import hỏng =
spawn não KHÔNG Seatbelt, fail-open âm thầm trong bản đóng gói.** Test
frozen path là bắt buộc, không phải nice-to-have.

- Phase này CHƯA dùng — chỉ import sẵn, phase-03 mới gọi trong
  `build_profile`. (Hoặc gộp luôn — quyết định lúc viết; ưu tiên commit
  "move thuần" riêng để diff dễ đọc.)

## Kiểm packaging — đã verify, không cần sửa

- `launcher.py` `CODE_DIRS` chứa `"tools"` → bootstrap copy sang DATA.
- `troly.spec` `datas=[… ('tools','tools') …]` → bundle frozen có sẵn.
- `update.py` `ALLOW_DIRS` chứa `"tools/"` → update đẩy file mới.
- `build-release.sh` test-loop `tools/test-*.py` — không xung đột tên.

## Test

- `python3 -c "import sys; sys.path.insert(0,'tools'); import path_guard;
  assert path_guard.path_sensitive('~/.ssh'); assert
  path_guard.path_sensitive('~/Library')"` (chiều chứa) 
- `rw_grant_ok('<cwd>/tools', cwd)` → False; `rw_grant_ok('/tmp/x',
  cwd)` → True; `rw_grant_ok('<cwd>/my-course/x', cwd)` → True.
- `python3 tools/gen-sandbox.py` chạy bình thường (import không lỗi).
- **Giả lập frozen path** (đây là regression dễ sót nhất — fail-open):
  `cd /tmp && python3 -c "import runpy; runpy.run_path(
  '/path/to/tools/gen-sandbox.py', run_name='not_main')"` → import
  `path_guard` phải resolve được NHỜ dòng sys.path.insert trong
  gen-sandbox (không nhờ cwd, không nhờ sys.path có sẵn). Trước khi
  thêm dòng → ModuleNotFoundError; sau → chạy được.
- `python3 tools/test-gates.py && python3 tools/test-parity.py` PASS —
  không endpoint nào đổi.

## Done khi

`path_sensitive`/`rw_grant_ok` chỉ còn MỘT định nghĩa trong repo;
chat-bridge và gen-sandbox cùng đọc từ `path_guard`; sensitive list mở
rộng áp dụng ngay cho request-time check.
