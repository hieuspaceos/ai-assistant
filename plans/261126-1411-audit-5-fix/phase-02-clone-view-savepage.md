# Phase 02 — clone-view srcdoc + save-page ps1 reparse

## Vá

**F4 — `<object data="javascript:…">` sống trong srcdoc.**
`prepareEditable` neutralize `on*` + `javascript:` trong
`href|src|action|formaction|xlink:href` — nhưng `<object data>` không
nằm trong list, và `<object>`/`<embed>` là nested browsing context
không bị ép `sandbox=""` như `<iframe>`. srcdoc cùng origin portal →
script trong object đọc được `localStorage.bridge_token`.

Hai hướng, chọn hướng rẻ-an toàn:

- **A (khuyến nghị):** xử `<object>`/`<embed>`/`<frame>`/`<frameset>`
  giống iframe — đổi tên sang placeholder vô hại trong lúc sửa rồi
  serialize gắn lại. Đơn giản hơn: vòng quét attr thêm `data` vào danh
  sách javascript:-check CHỈ trên thẻ `object` (`embed` dùng `src` đã
  cover), cộng thêm ép `typemustmatch`? — cân nhắc lúc implement:
  phương án chắc nhất là replace `<object>` bằng
  `<div data-cs-obj="…">` placeholder trong srcdoc + restore trong
  `serialize()` (giống scriptsStore).
- Verify bằng tay trên Chrome: trang clone chứa
  `<object data="javascript:alert(document.domain)">` → vào chế độ
  Sửa → KHÔNG có alert.

**F3 — save-page ps1 không resolve junction.**
`[IO.Path]::GetFullPath` là lexical; `.py` dùng `realpath`. Trên
Windows: `troly-agent` có Modify trên `my-course\` → tạo junction
`mklink /J my-course\link C:\target` được (junction không cần admin)
→ `POST /api/save-page {"file":"my-course/link/x.html"}` →
`$target.StartsWith($course)` pass → ghi `C:\target\x.html` với
quyền owner.

Fix trong `chat-bridge.ps1` nhánh save-page: sau khi có `$target`,
resolve parent dir qua `Resolve-Path` (Resolve-Path trên Windows
**không** resolve junction → phải dùng API khác). Cách đúng:

```powershell
# resolve reparse: check từng segment từ $course xuống gồm cả leaf —
# file .html symlink cũng phải chặn (parity realpath của .py).
# Segment chưa tồn tại (subdir mới) → Get-Item trả $null → bỏ qua.
$p = $course; $reparse = $false
$segs = $rel -split '/'
foreach ($seg in $segs[1..($segs.Count-1)]) {
    $p = Join-Path $p $seg
    $it = Get-Item $p -Force -ErrorAction SilentlyContinue
    if ($it -and ($it.Attributes -band
        [IO.FileAttributes]::ReparsePoint)) { $reparse = $true; break }
}
if ($reparse) { Send-Json $ctx @{ err = "…" } 400; continue }
```

(`$rel.StartsWith("my-course/")` đảm bảo luôn ≥2 segment → `1..(Count-1)`
không rỗng. `Resolve-Path` KHÔNG resolve junction — nó chỉ resolve
PSDrive path, đừng nhầm.)

So sánh `.py`: `os.path.realpath` resolve junction → target thật ngoài
`course` → 400. Bản ps1 chọn **chặn mọi reparse point dưới
my-course** — hơi chặt hơn .py (folder symlink hợp lệ bên py được
resolve vào trong vẫn qua) nhưng fail-closed và đơn giản; ghi khác
biệt vào SECURITY.md parity note. Nếu muốn parity đúng, dùng
`[TroLy.AgentSpawn]`-style P/Invoke `GetFinalPathNameByHandle` — quá
phức tạp cho endpoint này, không đáng.

⚠ Viết lại file .ps1 kèm BOM (chủ đề parity đợt 1).

**F12 — SRC regex cho `..`.** `[\w.\-\/]+` nuốt `..` — view-only,
server vẫn chặn write; siết cho đúng nghĩa "chỉ file trong
my-course/intro":

```js
if (!/^\/(my-course|intro)\/[\w.\-\/]+\.html?$/i.test(SRC)
    || SRC.split('/').includes('..')) SRC = '';
```

## File

| File | Việc |
|---|---|
| `web/clone-view.html` | F4 neutralize object/embed; F12 SRC `..` |
| `tools/chat-bridge.ps1` | F3 save-page reparse-point check (+BOM) |

## Verify

- Tay trên Chrome (macOS): clone-view mở `?src=` trang chứa
  `<object data="javascript:…">` và `javascript:` href — vào Sửa →
  không alert; serialize() gắn lại nguyên bản khi Lưu.
- CI test-windows: thêm case save-page qua junction vào
  `test-agent-spawn.ps1` hoặc test riêng — `mklink /J` trong
  `my-course\` → POST save-page → 400. (Nếu CI khó tạo junction thì
  ít nhất unit-test hàm check: path có reparse → reject.)
- `test-bridges.py` (.py path) không đổi — .py đã đúng.
