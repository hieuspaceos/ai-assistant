# Phase 3 — Smoke test cho bridges (stdlib, chạy tay)

## Mục tiêu

Có bộ test tối thiểu chạy được `python3 tools/test-*.py` trên máy dev —
không framework, không dep ngoài (đúng triết lý project). Mục đích không
phải coverage cao mà là **bắt regression ở đúng chỗ đã từng hỏng**: auth,
save-page sandbox, parity giữa các con đường chạy.

## File động

| File | Action | Việc |
|---|---|---|
| `tools/test-bridges.py` | create | test endpoint-level của chat-bridge.py + ext-bridge.py |
| `tools/test-parity.py` | create | diff tập `/api/*` giữa `.py` và `.ps1` |
| `tools/test-packs.py` | create | diff `.devin/skills/` vs `skill-packs/` |
| `docs/troubleshooting-runbook.md` | modify | thêm mục "chạy test trước release" |

## Chi tiết

### 3a. `tools/test-bridges.py`

Spawn bridge THẬT trên port lạ + CWD tạm (tempdir có `brain.json` giả
trỏ `cmd` không tồn tại → não "dead" nhưng bridge vẫn sống — đúng thiết
kế, test được mọi endpoint không cần não).

```
TMP/
├── brain.json          {"id":"none","cmd":"__no_such_brain__"}
├── brain preset đảm bảo shutil.which fail → Acp.dead, bridge vẫn nghe
├── .devin/bridge.token  (test tự sinh, biết giá trị)
├── my-course/{permissions,connections,config,manifest}.json (seed tối thiểu)
└── extension/manifest.json
```

`subprocess.Popen(["python3","tools/chat-bridge.py","<port>","<TMP>"])`,
poll `/api/health` tới khi 200, chạy case, `terminate()`.

Test case (mỗi case một hàm, `unittest` hoặc runner tay in PASS/FAIL):

| # | Case | Kỳ vọng |
|---|---|---|
| 1 | `GET /api/health` không token | 200 |
| 2 | `GET /api/poll` không token | 401 |
| 3 | `GET /api/poll?token=<đúng>` | 200, có `events`/`next` |
| 4 | `X-Bridge-Token: <đúng>` trên `/api/permissions` | 200 |
| 5 | `OPTIONS /api/prompt` không token | 204 + `Allow-Headers` chứa `X-Bridge-Token` |
| 6 | Origin `http://evil.example` → GET health | 403 |
| 7 | save-page `{"file":"../x.html"}` | 400 |
| 8 | save-page `{"file":"my-course/x.txt"}` | 400 |
| 9 | save-page `{"file":"my-course/a.html","html":"<p>xin chào</p>"}` | 200; file đúng nội dung UTF-8; POST lần 2 → có `a.html.bak` |
| 10 | POST `/api/brain` `{"cmd":"/bin/evil"}` | 400 (chặn path) |
| 11 | POST `/api/brain` `{"cmd":"__no_such__"}` | 404 (chưa cài) |
| 12 | ext-bridge: `GET /api/browser/status` không token | 401 |
| 13 | ext-bridge: status có token | 200 `{"connected":false}` (không ext) |
| 14 | serve.py: `GET /.devin/bridge.token` | 404/403 (dotfile bị chặn) |
| 15 | POST `/api/prompt` khi não dead | 503 + bridge tự spawn lại (self-heal path) |
| 16 | POST `/api/setup` `{"language":"vi"}` | `.devin/skills/` được tạo = nội dung `skill-packs/vi` |

Chú ý regex parity: pattern `"/api/[a-z-]+"` chỉ khớp literal có nháy —
chuỗi URL như `"http://127.0.0.1:7684/api/browser"` (trong `run_probe`)
KHÔNG khớp ở cả 2 file nên không gây nhiễu. Đã verify trên code thật.

### 3b. `tools/test-parity.py` — chống drift (lỗi A)

Parse tĩnh cả 2 bridge:

```python
py_eps  = set(re.findall(r'"/api/[a-z-]+"', open("tools/chat-bridge.py").read()))
ps_eps  = set(re.findall(r'"/api/[a-z-]+"', open("tools/chat-bridge.ps1").read()))
assert py_eps == ps_eps, f"drift: only-py={py_eps-ps_eps} only-ps1={ps_eps-py_eps}"
```

Chỉ diff TẬP endpoint — không so implementation (giòn vừa đủ, R3).
**Test này đỏ ngay hôm nay** (save-page) → chỉ chạy sau khi phase 1 xong,
hoặc viết sẵn và để fail chứng tỏ bug.

### 3c. `tools/test-packs.py` — chống drift (lỗi B)

- Mọi dir trong `.devin/skills/` mà có skill được `manifest.json` recipes
  nhắc tới (`/clone-trang`) hoặc README nhắc → phải có bản trong
  `skill-packs/vi/`.
- **Diff NỘI DUNG** `diff -r` giữa `.devin/skills/<x>` và
  `skill-packs/vi/<x>` với mọi skill có ở cả hai — bắt lỗi "sửa bản
  active quên sửa pack" (root cause của B; `skills-system.md` cho phép
  sửa ở active dir nên drift này sẽ tái diễn).
- Mọi dir trong `skill-packs/vi/` phải có bản tương ứng trong
  `skill-packs/en/` (ánh xạ tên vi→en khai báo tường minh trong một dict
  ở đầu file — thêm skill mới thì thêm 1 dòng dict).
- Frontmatter mọi SKILL.md có `name:` + `description:` không rỗng.

### 3d. Cách chạy

```bash
python3 tools/test-bridges.py   # cần python3 — đã có sẵn yêu cầu project
python3 tools/test-parity.py
python3 tools/test-packs.py
```

In `PASS n/n` hoặc liệt kê case fail, exit code khác 0 khi fail — sau này
gắn CI chỉ cần gọi 3 lệnh này.

## Acceptance

- `test-bridges.py`: 16 case xanh trên macOS.
- `test-parity.py`: xanh sau phase 1 (đỏ nếu revert phase 1).
- `test-packs.py`: xanh sau phase 2 (đỏ nếu xoá clone-trang khỏi pack).
- Chạy được trên `py tools\test-*.py` Windows (không lệnh unix nào trong
  test — spawn `sys.executable`, không `python3` hardcode… sửa: dùng
  `sys.executable` cho mọi subprocess).

## Rủi ro

- Spawn bridge trong test để lại port/token rác → mọi thứ trong tempdir,
  port chọn động (`bind 0` rồi đọc số port), `finally: proc.terminate()`.
- `chat-bridge.py` spawn não khi import → test dùng brain giả, dead-brain
  không giết bridge (đã verify bằng đọc code — vẫn chạy thử trước khi
  chốt test).
- PowerShell 5.1 vs pwsh 7 cú pháp khác nhau ở `.ps1` — test-parity chỉ
  đọc text nên không ảnh hưởng; hành vi thật kiểm ở phase 5.
