# Phase 06 — (tuỳ chọn, commit riêng) `do_POST` elif chain → route table

## Vá

**Refactor thuần — không đổi hành vi, làm SAU khi phase 01–05 merge.**
`Handler.do_POST` là elif chain ~660 dòng qua ~25 endpoint (1298–2112).
Bản thân độ dài không phải lỗi, nhưng nó là nơi các audit phải đếm tay
"endpoint nào gate, endpoint nào không" — drift gate chính là kiểu bug
chain này giấu. Route table biến danh sách endpoint thành dữ liệu đọc
được bằng code.

## Thiết kế

```python
# trong Handler hoặc module-level
def _h_prompt(self, data): ...
def _h_permissions(self, data): ...

POST_ROUTES = {                        # literal key — test-parity grep
    "/api/prompt":           "_h_prompt",        # được như cũ
    "/api/respond":          "_h_respond",
    "/api/permissions":      "_h_permissions",   # gate trong _apply
    ...
}
```

- `do_POST` giữ phần chung: auth, body cap, parse JSON →
  `h = getattr(self, POST_ROUTES.get(path), None)` → `h(data)` hoặc 404.
- Mỗi `_h_*` là method nhỏ — body elif hiện tại nhấc nguyên sang, đổi
  `return` sau `self._json(...)` giữ nguyên semantics.
- `do_GET` tương tự (`GET_ROUTES`) — chain nhỏ hơn nhưng đồng nhất.
- Giữ comment bảo mật ở đầu mỗi `_h_*` — không gom chung, comment giải
  thích "vì sao endpoint này gate/không gate" phải đi theo hàm.

## Cập nhật `test-gates.py` — đây là phần có giá trị thật

Hiện test regex-parse `^\s+(elif|if) path == "(/api/…)"` rồi quét block
cho `gate_local(`. Sau refactor:

- Parse `POST_ROUTES` dict (regex literal vẫn đủ, hoặc ast-lite).
- Map route → method name → quét **source của method đó** cho
  `gate_local(` — coverage chính xác hơn: gate trong helper `_apply`
  closure vẫn match, không bị nhiễu bởi code endpoint kề.
- GATED/OPEN_OK dict không đổi (cập nhật theo phase-04).

`test-parity.py` grep literal `"/api/…"` — key dict vẫn literal → PASS
không sửa.

## Không làm trong phase này

- Không tách file thêm (`bridge_bots.py`…) — state đan chặt
  (`perm_pending`, `local_pending`, lock, `Acp`), mỗi file thêm là một
  thứ update.py phải ship; 2 module (`path_guard` + main) là đủ cho
  project này. Nếu sau này file vượt ~2800 dòng thì bàn lại: ứng viên
  tách tiếp theo là block bots (~190 dòng, độc lập nhất).
- Không đổi signature/hành vi endpoint nào.

## Test

- `python3 tools/test-gates.py && tools/test-parity.py &&
  tools/test-bridges.py` PASS — đây chính là kiểm chứng "không đổi
  hành vi".
- Diff review: mọi comment trong elif cũ phải xuất hiện trong `_h_*`
  tương ứng (grep đếm comment anchor).

## Done khi

`do_POST`/`do_GET` còn ~40 dòng dispatch; thêm endpoint mới = thêm key
dict + một method; test-gates đọc ROUTES thay regex chain.
