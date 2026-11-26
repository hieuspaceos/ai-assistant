# Phase 04 — Medium hardening: option pick, BRAIN_CMD_DENY, bot preview, brain gate, kẹp title

## Vá

### M1 — pick `allow_once` trước `allow_always`

Hai chỗ `next(o for o in opts if kind.startswith("allow"))`:
`_perm_native_confirm` (~544) và `_allow_match` auto-approve (~781).
Một cú bấm "Đồng ý" → não sắp `["allow_always","allow_once"]` trước =
quyền vĩnh viễn, trong khi học viên nghĩ "lần này".

Helper dùng chung — chú ý bẫy `"once" in kind` phải kèm
`startswith("allow")`: não xếp `reject_once` lên đầu mà không lọc
allow trước thì pick nhầm option TỪ CHỐI gửi cho não:

```python
def _pick_allow(opts):
    """Ưu tiên allow_once — một lần đồng ý không được trở thành quyền
    vĩnh viễn. Không có thì allow* bất kỳ, cuối cùng mới opts[0]."""
    kind = lambda o: str(o.get("kind", "")).lower()
    allows = [o for o in opts if kind(o).startswith("allow")]
    return (next((o for o in allows if "once" in kind(o)), None)
            or (allows or opts or [{}])[0]).get("optionId")
```

Thay cả hai site. Lưu ý `kind` của não không chuẩn hoá — match "once"
substring thay vì equality, nhưng LUÔN trong tập allow*.

### M3 — BRAIN_CMD_DENY: deny theo regex, không exact-match

`python3.12`, `perl5.40`, `php8.2`, `pip3.11`, `ruby3.3` đều qua được
vì không trùng string. Đổi check (~1625–1631) thành: basename →
exact-set `BRAIN_CMD_DENY` (giữ nguyên) HOẶC match `_BRAIN_CMD_DENY_RE`:

```python
_BRAIN_CMD_DENY_RE = re.compile(r"""^(?:
    (i?python|pypy|jython|micropython|pyspark)[\d.]*w? | py |
    perl[\d.]* | ruby[\d.]* | php[\d.]* | pip[\d.]* | node(js)?[\d.]* |
    (ba|z|fi|da|k|c|tc)?sh\d* |
    lua(jit)?[\d.]* | tclsh[\d.]* | r(script)?[\d.]* |
    java\w* | jshell | groovy\w* | scala | kotlin\w* | dotnet | mono |
    brew | gh | go | cargo | xcodebuild | plutil | shortcuts |
    bundle | irb | pry | julia | gjs | qjs | runghc | ghci
)$""", re.X | re.I)
```

(Bản nháy đầu sót `ksh`/`csh`/`tcsh` — shell prefix phải đủ
`(ba|z|fi|da|k|c|tc)?`; sót `ipython`/`pypy`/`jython`/`micropython`/
`pyspark` — python clone phổ biến trên máy data-science.)

Bổ sung exact-set: `brew`, `gh`, `java`, `jshell`, `dotnet`, `mono`,
`lua`, `luajit`, `r`, `rscript`, `tclsh`, `groovy`, `scala`, `kotlin`,
`xcodebuild`, `plutil`, `go`, `cargo`, `julia`, `ipython`, `pypy`,
`micropython`, `gjs`, `qjs` (mỗi cái = exec-qua-args hoặc build+run).
Comment trong code nói thẳng: denylist không bao giờ đầy đủ — custom
brain = chạy lệnh tuỳ ý sau consent; sửa text card thành
`f"Chạy lệnh tùy ý \"{disp}\" làm não?"` thay `"Đổi não sang lệnh tự
nhập"` — học viên thấy đúng bản chất, không tưởng là đã được lọc.

### M2 — `/api/bot` create: preview instructions trong card activate

`create` mở trần (đã khai OPEN_OK? — kiểm test-gates: `/api/bot` nằm
trong GATED cho activate/delete nhưng `create` đi thẳng). Payload độc
≤500 chữ chỉ lộ khi activate — card hiện `f"Đặt {name} làm trợ lý đang
làm việc?"` (~2028) không preview.

- Card activate: title kèm trích instructions —
  `f"Đặt {name} làm trợ lý? Lời dặn: \"{ins[:80]}…\""` (title đã có
  clamp — kiểm clamp 200 ở broadcast, kẹp ins cho vừa).
- `create` giữ ungated (không ghi gì nguy hiểm — bots.json deny-write
  sẵn nên endpoint là cửa hợp lệ duy nhất; ghi bots.json không kích
  hoạt gì), NHƯNG kẹp `recipes` — hiện nhận list tuỳ ý không giới hạn
  kích thước/phần tử → cap len≤20, mỗi entry dict {command,label} str
  ≤60.
- **Deferred**: deny-write `my-course/bot.md` trong gen-sandbox + route
  ghi qua bridge — phỏng vấn ghi bot.md trực tiếp nên phải thêm
  endpoint /api/bot-md trước; để plan sau, ghi nhận SECURITY.md.

### M5 — gate preset `/api/brain`

`{"id":"gemini"}` đổi thẳng (~1618–1663) — agent tự kill session, spawn
churn, ghi brain.json (file agent không ghi được trong sandbox → đây là
cửa vòng duy nhất). Gate luôn preset: title `f"Đổi não sang {id}?"`.

Hệ quả UX — **hai call site portal phải sửa** (đã verify):

- `web/app.js` `sel.onchange` (~622): hiện chỉ check `r.ok` — 202 sẽ
  rơi vào nhánh `r.err || brainFail` = báo "đổi não thất bại" dù card
  đã gửi. Thêm `if (r.pending) → hiện r.msg` (toast "vào tab Hỏi trợ
  lý duyệt"); sau approve brain mới đổi → sel nên re-sync từ GET
  /api/brain thay vì tin giá trị đã chọn.
- `web/onboarding.html` POST /api/brain (~376): 202 vẫn `r.ok` →
  `go(4)` luôn mà não chưa đổi. Thêm `d.pending → needConfirm = true`
  (cơ chế có sẵn — đã dùng cho permissions/setup ở dòng ~452/458, màn
  cuối hiện `pendingNote`).

Cập nhật `test-gates.py` GATED["/api/brain"] comment → "mọi lần".

### L6 — kẹp title tool events

`tool`/`tool_call_update` title không kẹp (~849, ~767–770) trong khi
perm title kẹp 200 — não bơm title MBs vào event_store/history. Kẹp
`title[:200]` ngay khi nhận event, đồng nhất với perm.

## Test

- Não phát options `[{"optionId":"a","kind":"allow_always"},
  {"optionId":"b","kind":"allow_once"}]` → duyệt → não nhận `"b"`.
- `/api/brain {"cmd":"python3.12"}` → 400/202-gate? (custom cmd → gate;
  sau duyệt phải bị deny bởi list mới — verify deny chạy TRƯỚC gate:
  deny trước gate, không để card duyệt rồi mới reject).
- `{"cmd":"brew"}`, `{"cmd":"gh"}`, `{"cmd":"Rscript"}` → reject ngang
  `python3`.
- `/api/brain {"id":"gemini"}` → 202 pending; portal sel.onchange hiện
  toast đúng; duyệt → não đổi.
- `create` bot với instructions độc → activate → card hiện trích đoạn;
  `create` với recipes 200 phần tử → bị cắt/reject.
- `python3 tools/test-gates.py` PASS với GATED comment mới.

## Done khi

Một cú đồng ý không bao giờ cấp `allow_always` khi có `allow_once`;
mọi interpreter version đều bị deny; mọi đổi não đều qua card; card
activate bot cho học viên đọc được lời dặn trước khi duyệt.
