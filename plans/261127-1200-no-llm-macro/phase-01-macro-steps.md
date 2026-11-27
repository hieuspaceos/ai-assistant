# Phase 01 — `steps:` trong workflow + macro runner + `/api/fs-op` guard

## Lý do

`nen-anh-web.json` hiện là **prompt** → não tự chạy ensure-deps +
python nén ảnh. Cùng kết quả đó chạy thẳng được: `fs-op copy` →
gọi tool nén → `count-glob` verify. Trăm mili-giây, không token.
Workflow mới khai thêm field `steps` — giữ `prompt` làm fallback khi
workflow không mô tả được bằng bước.

## Format mở rộng (vẫn `<id>.json`, backward compatible)

```json
{
  "id": "nen-anh-web",
  "prompt": "...(giữ làm fallback khi step engine off)...",
  "steps": [
    {"op": "fs.copy_tree", "src": "{{folder}}", "dst": "{{folder}}/../anh-web-ready"},
    {"op": "tool",        "run": "python3 .venv/bin/python tools/nen-anh.py {{folder}}/../anh-web-ready"},
    {"op": "fs.verify",   "dir": "{{folder}}/../anh-web-ready", "glob": "*", "min_count": 1}
  ]
}
```

- `{{key}}` fill từ `inputs[]` như prompt hiện tại.
- Step `prompt` vẫn hợp lệ (rơi về não cho bước cần nội dung) — macro
  và LLM trộn được trong một workflow.

## Op v1 (chặt, không mở rộng tuỳ tiện)

| Op | Đi qua | Ghi chú |
|---|---|---|
| `fs.copy` / `fs.copy_tree` | `/api/fs-op` mới | chỉ trong `permissions.json` read-write |
| `fs.move` | `/api/fs-op` | — |
| `fs.delete` | `/api/fs-op` | **move vào `.trash/`, không xoá hẳn** — parity với delete-lesson |
| `fs.verify` | `/api/count-glob` | đã có sẵn |
| `tool` | `/api/fs-op` runner | **allowlist cứng**: chỉ script trong `tools/` của repo, qua `.venv/bin/python`; argv đi qua `cmd_deny` + `exec_allowed` giống exec-allowlist |
| `browser.<action>` | proxy `ext-bridge :7684` | cho bước web cố định — giai sau, stub trước |
| `prompt` | `/api/prompt` | fallback LLM cho bước cần não |

## `tools/chat-bridge.py` — `/api/fs-op` (POST, token)

```python
ALLOWED_OPS = {"copy", "copy_tree", "move", "delete", "tool"}
def _p_fs_op(self, d):
    op = d.get("op")
    if op not in ALLOWED_OPS: return err
    for p in paths_of(d):
        # tên thật: rw_grant_ok(p, cwd) từ path_guard + đọc
        # workspace/permissions.json yêu cầu access "read-write"
        if not rw_grant_ok(p, CWD) or not has_rw_grant(p): → 403
    if op == "tool":
        if not exec_allowed(cmd, patterns_tools_only): → 403
        run with scrub_env(...), timeout 120s, capture stdout tail
    ...
```

- Path guard: tái dùng `path_guard` + `permissions.json` — **read-write
  only**; đường `read` không cho ghi.
- **Audit 27-11 — KHÔNG có helper sẵn cho check này**: `rw_grant_ok`
  là guard ÂM ("grant RW trên path này có nguy hiểm không" — trả
  True cho mọi path NGOÀI project), nó KHÔNG đọc `permissions.json`.
  Phải viết helper mới `perm_allows_write(p)`: path resolve được,
  nằm trong `workspace/` (luôn cho phép) hoặc dưới một entry
  `folders[]` có `access=="read-write"` trong `permissions.json`
  (dùng `MC_DIR`/`PERM_FP` + `load_json` có sẵn). `rw_grant_ok` chỉ
  dùng thêm như guard phụ chống ghi vào vùng code.
- `delete` → `.trash`: move vào `workspace/.trash/fs-op-<ts>/` — cùng
  vị trí checkpoint của trust-harness phase-01 (`workspace/.trash/`),
  khác per-course `.trash` của delete-lesson.
- `tool` runner: cwd khoá trong repo; `scrub_env`; giới hạn output
  64KB; **không shell** — argv list thuần.
- `test-gates.py`: thêm `/api/fs-op` POST + token; `test-deny-parity`:
  `rm -rf`, `../`, symlink trỏ ra ngoài → deny.

## `web/app.js` — macro runner

```js
async function runSteps(wf, inputs) {
  for (const [i, s] of wf.steps.entries()) {
    const filled = fillPlaceholders(s, inputs);        // như prompt cũ
    const r = await stepCall(filled);                  // /api/fs-op | /api/browser | /api/prompt | /api/count-glob
    renderStepChip(i, r.ok);                           // step đang chạy → xanh/đỏ từng cái
    if (!r.ok) { showFail(i, r.err); return; }         // dừng ngay, báo step nào
  }
  runVerify(wf);                                       // verify/checklist y hệt cũ
}
```

- UI: card workflow có badge nhỏ "⚡ nhanh" khi `steps` không chứa
  op `prompt` — học viên thấy cái nào miễn phí-não.
- Fallback: workflow không có `steps` → đường prompt cũ nguyên vẹn.

## Migrate đợt đầu (viết steps thật cho 2 workflow)

| Workflow | Steps |
|---|---|
| `nen-anh-web` | copy_tree → tool nén → fs.verify |
| `gom-downloads` | (đọc cấu trúc) — nếu chỉ là move theo loại thì hoàn toàn macro được |

`tom-tat-tuan` giữ prompt — cần não tóm tắt, không macro được.

## Bẫy đã biết

- **`tool` là backdoor nếu lỏng** → allowlist = chỉ file `.py` trong
  `tools/` + `cmd_deny` filter argv + không shell. Đây là phần rủi ro
  nhất của phase — review kỹ trước khi merge.
- `delete` → `.trash` phải dùng cùng helper với delete-lesson (tên
  đích + timestamp, không ghi đè).
- Placeholder `{{folder}}` do người gõ → path_guard soi sau fill —
  `~/Downloads/../../etc` phải fail.
- Step `prompt` trong macro xen giữa step máy: sau prompt xong (event
  done) mới chạy step kế — runner phải chờ long-poll đúng như luồng
  workflow hiện tại.

## Test

- `test-bridges.py`: fs-op copy/move/delete→.trash trong folder
  read-write ok; ngoài → 403; `tool` chạy được script allowlist, từ
  chối path khác + argv deny.
- UI: chạy `nen-anh-web` bằng steps → chips xanh từng step, không
  gọi não (log `.logs/` không có prompt); gỡ 1 step fail → chip đỏ
  đúng step, step sau không chạy.
