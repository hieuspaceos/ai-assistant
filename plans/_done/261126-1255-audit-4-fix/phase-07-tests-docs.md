# Phase 07 — docs, messages, ghi nhận không vá, full test loop

## Vá

Phần dọn đuôi: hai chỗ docs/messages khuyên sai, LAN-plaintext ghi rõ,
và các finding nhỏ quyết định KHÔNG vá thì phải ghi nhận có chủ đích.

## 1.6 — `?key=` trong boot message (`collector.py:843`)

Dashboard đã có ô "Dán key" gửi `X-Admin-Key` header
(`collector-web/index.html:627`, sessionStorage) — chỉ cần đừng khuyên
đưa key vào URL (browser history, proxy log, Referer):

```python
print(f"  dashboard: http://<ip>:{PORT}/  (mở → tab 'Dán key', "
      f"nhập admin_key)")
```

## S5 — doc drift `deploy/vendor-infra.md`

- `:97` ghi `tools/collector.py --org <slug> --data ...` — parser không
  có flag `--org` (một org = một config = một process). Sửa thành:
  `tools/collector.py --config <slug>.json --data /srv/fleet/<slug>`.
- `:18` nhắc `?key=` — đổi thành "mở dashboard → tab Dán key".

## DEPLOY.md — LAN tier plaintext

Ghi rõ threat model (cũng là Option B của phase-05 nếu chọn B):

> LAN tier chạy `http://<ip>:8790` plaintext — `beacon_secret`,
> `machine_key`, `admin_key` đều đi cleartext trên dây. Chỉ deploy trên
> LAN tin cậy vật lý (switch của cty, không guest-wifi). Org nhạy cảm
> hoặc LAN không kiểm soát → customer-hosted `https://fleet.<cty>` sau
> nginx (TLS + X-Forwarded-For — bật `trust_proxy` khi đó).

## SECURITY.md — ghi nhận có chủ đích (không vá)

- **Slow-loris slot exhaustion:** mọi conn giữ 1/64 slot, read timeout
  30s → ~65 conn nhỏ giọt tê liệt 30s/vòng. Chấp nhận LAN tier;
  customer-hosted để nginx chịu (worker pool + limit_req).
- **Zip 200MB nạp RAM** khi máy tải `/releases/<f>`: giới hạn bởi
  slot + LAN trusted; stream khi nào thấy đau.
- **`/api/license` aggregate:** seats/expiry lấy từ license hợp lệ đầu
  tiên — machines license khác nhau thì sai. Đếm-gentle nên chấp nhận;
  sửa khi license per-seat thật.
- **`?key=` còn hoạt động** ở dashboard (sessionStorage seed từ URL) —
  chỉ gỡ khỏi docs/messages, không xoá code path (dự phòng nhập key).
- **Message params không validate kiểu** (ext): bridge là nguồn lệnh
  duy nhất, giá trị lệch rơi vào try/catch → `err`; nếu mở nguồn lệnh
  thứ hai thì cần schema.
- **`tabs` trả url+title mọi tab** — by design (agent cần thấy trạng
  thái); nằm trong phạm vi "dữ liệu lọt ra ngoài" đã chấp nhận.
- **paste synthetic ClipboardEvent** — hầu hết app bỏ qua, đã ghi docs.

## Full test loop

```bash
python3 tools/test-fleet.py        # contract beacon↔collector + case mới
python3 tools/test-gates.py        # gate/permissions không đổi
python3 tools/test-parity.py       # parity .py/.ps1
python3 tools/test-bridges.py      # bridge không đụng — chạy cho chắc
python3 tools/test-packs.py        # skill packs (không liên quan — quick)
```

Re-PoC tay hai phát audit:

```bash
# 1) traversal — mong 400, không file ngoài DATA/
curl -X POST localhost:8790/api/packs -H "X-Admin-Key: $VENDOR_OR_READ" \
  -d '{"org":"../../esc2","pack_version":9,"payload":"x"}'
# 2) list body — mong 400 JSON, connection sống
curl -X POST localhost:8790/api/beacon -H "X-Beacon-Key: $MK" -d '[1,2,3]'
```

Extension: reload unpacked → chạy checklist test trong phase-02/03
trên trang lab (`data-tlai` mồi, form hidden+csrf meta, action
`__proto__`, tclick → idle detach).

## Done khi

Không docs nào khuyên `?key=` hay flag không tồn tại; DEPLOY.md nói rõ
LAN trust; SECURITY.md liệt kê mục "không vá" có lý do; toàn bộ test
xanh + PoC trả 400.
