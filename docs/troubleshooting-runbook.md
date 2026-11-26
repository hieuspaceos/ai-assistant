# ai-assistant — Troubleshooting Runbook

Sự cố đã gặp thật + cách xử lý. Cập nhật khi gặp lỗi mới.

## 0. Chạy test trước khi release/sửa bridge

Ba script stdlib, không cần dep — chạy trên máy dev trước khi đóng gói
hoặc sau khi đụng `tools/*.py`, `tools/*.ps1`, `.devin/skill*/`:

```bash
python3 tools/test-bridges.py   # endpoint-level: auth, save-page, brain…
python3 tools/test-parity.py    # endpoint .py ↔ .ps1 phải khớp
python3 tools/test-packs.py     # skill active ↔ packs ↔ recipes
python3 tools/test-gates.py     # endpoint POST phải khai GATED/OPEN_OK
```

Sau khi đụng phần fleet: `test-fleet.py` (collector thật + parity
collector↔worker), `test-distribution.py` (ký→verify→apply→rollback),
và `test-worker.py` (wrangler dev + D1 local — cần `worker/.dev.vars`;
chạy trong CI).

Bất kỳ test nào đỏ → KHÔNG release. `test-parity` đỏ thường là quên port
endpoint sang bản bridge kia; `test-packs` đỏ là skill mới/sửa chưa đồng
bộ vào `skill-packs/`; `test-gates` đỏ là thêm endpoint POST mới mà chưa
khai vào `GATED`/`OPEN_OK` trong `tools/test-gates.py` — bắt buộc quyết
định "agent tự gọi được endpoint này có an toàn không" ngay lúc viết.

## 0.5. Release một phiên bản mới (CI)

```bash
# 1. sửa VERSION (vd 1.0.1) → commit → tag cùng số
git tag v1.0.1 && git push --tags
# 2. CI (.github/workflows/build.yml) tự chạy:
#    test (các script mục 0 + test-worker qua wrangler, fail → không build) → build troly (macOS) +
#    TroLyAI.exe (Windows) → attach vào Release của tag
```

Tag **phải** bằng `v` + `VERSION` — job release kiểm `v$(cat VERSION)`
và chết nếu lệch (banner "có bản mới" trên portal so VERSION với release
mới nhất). Chạy thử build không release: Actions → build → Run workflow
(`workflow_dispatch`, không cần tag).

Sự cố CI thường gặp:
- Build Windows chết `ModuleNotFoundError` khi chạy exe → thiếu
  `--hidden-import` trong `tools/build.sh` (children chạy qua runpy nên
  PyInstaller không tự thấy import của chúng).
- `--hidden-import winreg` trên macOS cảnh báo "not found" — bình
  thường, bỏ qua.
- SmartScreen chặn `TroLyAI.exe` trên máy học viên → hướng dẫn "More
  info → Run anyway" (chưa ký code trong pilot).

## 1. Health check nhanh

```bash
TOKEN=$(cat .devin/bridge.token)                     # "mã kết nối" dùng chung
curl -s http://localhost:8080/web/ | head -1         # portal sống
curl -s http://localhost:7682/api/health             # chat-bridge {"ok":true} — health miễn token
curl -s -X POST "http://localhost:7684/api/browser?token=$TOKEN" \
  -d '{"action":"status"}'                           # ext-bridge {"connected":true}
```

Mọi call bridge khác đều cần `?token=$TOKEN` hoặc header
`X-Bridge-Token: $TOKEN` — thiếu → `401 {"err":"thiếu hoặc sai mã kết nối"}`.

**401 toàn bộ sau khi update?** Kiểm portal có mở bằng file `start`
không — URL phải có `?t=` (portal tự nhớ vào localStorage). Mở tay
`localhost:8080` trần → không có mã → mọi API 401.

**Đổi khoá (rotation):** token tự rotate mỗi lần `start` chạy mà không
có instance đang sống (health-check trước — đang chạy thì tái dùng
token cũ, không ghi đè). Muốn ép rotate tay: `rm .devin/bridge.token`
+ chạy lại `start`; portal/extension cũ hết hạn — extension tự pair
lại khi mở portal, hoặc dán mã mới trong trang options của nó.

Log: `.logs/{portal,chat-bridge,ext-bridge,ttyd}.log` dưới root.

## 2. Khởi động

| Triệu chứng | Nguyên nhân | Xử lý |
|---|---|---|
| Portal không lên | port 8080 bị chiếm | `lsof -i :8080` (macOS) / `netstat -ano \| findstr 8080` (Win); xem `.logs/portal.log` |
| `{"connected":false}` mọi action | extension chưa nạp | Mở `chrome://extensions` → bật "Trợ Lý AI"; sau khi sửa `extension/*.js` → `{"action":"reload"}` |
| Icon extension hiện `!` | chưa có mã kết nối | Mở portal qua file `start` — auto-pair tự chạy; không được thì ⚙ Cài đặt → "Mã kết nối" → copy → dán vào options của extension |
| Chat không trả lời | não ACP chết / license / chưa đăng nhập | Chạy lệnh não tay (`brain.json` → `cmd`) xem lỗi; xem `.logs/chat-bridge.log`; bridge tự thử bật lại ở lượt gửi sau |
| Chat báo "không chạy được 'X'" | não `X` trong `brain.json` chưa cài | Panel ⚙ Cài đặt → Bộ não → chọn não khác; hoặc cài `X` rồi gửi lại |
| Đổi não mà chat vẫn não cũ | bridge chưa reload | `POST /api/brain` tự restart agent; kiểm `GET /api/health` → trường `brain` |
| Tab Terminal trống | ttyd chưa cài | Chế độ Chat vẫn dùng được; cài ttyd hoặc bỏ qua |

## 3. Extension / lái trình duyệt

| Triệu chứng | Xử lý |
|---|---|
| `No tab with id` | Tab bị đóng hoặc restart → `tabs` lấy ID mới, đừng giữ ID cũ |
| Extension từ chối trang | Trang hệ thống (`chrome://`, newtab, extensions page) không inject content.js được — mở trang web thường |
| `click`/`type` không ăn | App chặn event giả (Zalo, Sheets) → nhóm `t*`: `tclick`/`ttype`/`tinsert` (CDP) |
| Banner "đang gỡ lỗi" kẹt | `tdetach` tháo debugger |
| `screenshot` lỗi `MAX_CAPTURE_..._PER_SECOND` | Chrome giới hạn — `wait` vài giây rồi chụp lại |
| `styles`/`dom` trả ít phần tử | `styles sel=body depth=3` chỉ ~120 phần tử đầu — đo thêm từng section |
| Trang chặn bot | 4 nấc trong skill clone-trang: wait→đo lại, tự bấm checkbox, nhờ học viên bấm, đổi site |
| Tab hiện DOM cũ sau khi sửa file | `open` lại URL kèm `?v=N` chống cache (reload action có lúc không đổi DOM) |

## 4. Clone pipeline

| Triệu chứng | Nguyên nhân | Xử lý |
|---|---|---|
| Accordion thiếu đáp án | Đo DOM tĩnh — chỉ panel đang mở có nội dung | Pha 1a: bấm từng control → `ref-states.md` |
| Menu clone bấm không đi đâu | Site nguồn là SPA/MPA nhiều route, dựng nhầm một trang | Pha 1b khảo sát trước; router băm |
| Section clone sáng thay vì tối | CSS nguồn dùng wrapper nền tối — DOM không nói ra | Audit nền bằng `ref-css` trước khi so |
| Chữ trắng trên nền trắng trong card | Card sáng kế thừa `color` của section tối | Gán lại `color` mực trong card |
| `clone-compare` báo hàng loạt "chỉ có ở nguồn" | Tên class clone ≠ nguồn | Gắn `data-cs-ref` rồi `harvest` thay vì so trực tiếp |
| `shot` báo >50% khác | Section nền là ảnh placeholder ≠ ảnh gốc | Bình thường — pixel-diff chỉ dùng cho khối ít ảnh |
| `PIL` not found | Không cần — clone-compare parse BMP tay qua `sips` | macOS only cho `shot`; styles/harvest chạy mọi nơi |

## 5. Viewer / lưu trang

| Triệu chứng | Xử lý |
|---|---|
| Lưu xong mất bản cũ | `chat-bridge` tạo `<file>.bak` trước khi ghi — **chỉ có sau khi restart bridge** với code mới; kiểm tra file `.bak` tồn tại |
| `save-page` bị 400 | Path phải là `.html` dưới `workspace/`, không `..` — đúng thiết kế sandbox |
| Viewer không sửa được phần tử | Phần tử thiếu marker `data-cs-*` — mở file, gắn marker đúng loại |
| Sửa xong muốn về bản cũ | Copy `<file>.bak` đè lên file chính |

## 6. Sandbox (macOS Seatbelt)

- **Não không đọc/ghi được folder đã cấp quyền**: profile là snapshot
  lúc spawn — sửa `permissions.json` xong phải spawn lại não (đổi não
  trong Cài đặt hoặc restart bridge). `/api/permissions` regen sẵn
  profile nhưng não ĐANG chạy vẫn theo profile cũ.
- **Não chết ngay sau khi bật / báo "Operation not permitted" lạ**:
  tool não cần nằm ngoài whitelist — thường là cache dir của toolchain
  lạ (`~/.something`). Kiểm bằng tay: `sandbox-exec -f .devin/agent.sb
  <lệnh>`; dir thiếu thì thêm vào `sysw`/`sysr` trong `gen-sandbox.py`.
- **Debug tắt sandbox tạm**: `TROLY_NO_SANDBOX=1` rồi start lại — não
  chạy thường như cũ. CHỈ dùng để chẩn đoán, không set mặc định.
- **Não không mở được dev-server cho học viên xem preview**: cố ý —
  `network-bind` bị deny. Portal :8080 serve file tĩnh được; nếu skill
  thật sự cần bind, nới `(allow network-bind (local ip "localhost:*"))`
  trong gen-sandbox.
- **`Abort trap: 6` khi chạy sandbox-exec**: profile có `allow process*`
  nhưng thiếu `file-read*` phủ `/` (quirk compiler trên macOS mới) —
  tái sinh profile bằng `tools/gen-sandbox.py`, không sửa tay.

## 7. Emergency

- **Bridge chết giữa chừng**: process không tự restart — chạy lại
  `start.sh`/`start.bat`; file đang sửa không mất (lưu trên đĩa).
- **Học viên sửa hỏng JSON** (`config/permissions/connections`):
  `load_json` có default → bridge không crash; sửa tay file về JSON hợp
  lệ theo mẫu trong `codebase-summary.md`.
- **File clone hỏng không mở được**: về `.bak`; kiểm tĩnh bằng
  `html.parser` đếm thẻ đóng/mở trước khi sửa tiếp.

## 8. Cập nhật

| Triệu chứng | Nguyên nhân | Xử lý |
|---|---|---|
| Banner "Có bản mới" trên portal | GitHub Release có tag mới hơn `VERSION` | Bấm banner → tải file `troly` mới → chạy — code đè, `~/TroLyAI` (workspace/brain/secrets) giữ nguyên |
| Pill vàng "Extension bản cũ" | `extVersion` extension ≠ manifest trong payload | Cập nhật app trước → `brave://extensions` (hoặc `chrome://extensions`) → gỡ "Trợ Lý AI" → Load unpacked lại folder `extension/`; mã kết nối tự ghép lại khi mở portal |
| Banner không hiện dù có release | portal offline / GitHub API timeout 5s | Bình thường — kiểm lại khi có mạng; không ảnh hưởng việc học |
| 401 toàn bộ sau khi đổi máy/xoá token | `bridge.token` mới, phiên cũ hết hạn | Extension tự ghép lại khi portal mở bằng file `start`; khẩn cấp: ⚙ Cài đặt → "Mã kết nối" → dán vào options extension |

## 9. Triển khai cty — lỗi hay gặp khi cài hàng loạt

| Triệu chứng | Nguyên nhân | Cách xử |
|---|---|---|
| Extension không tự cài | Policy `ExtensionInstallForcelist` chưa áp / sai OU | `chrome://policy` kiểm; gpupdate /force; check registry HKLM |
| Extension cài nhưng chấm đỏ | Chưa nhận mã kết nối | Mở portal một lần — set-token tự đẩy qua externally_connectable |
| Máy không hiện dashboard | Beacon chưa được approve / sai fleet.json | Vào dashboard collector → tab Pending → duyệt; check `.devin/fleet.json` URL + secret |
| `pair` báo 401 | `beacon_secret` sai org | Cấp lại fleet.json đúng secret của org đó |
| Beacon 403 revoked | Máy bị revoke trên dashboard | Máy revoked KHÔNG hiện lại ở Pending (list lọc `revoked=0`) — un-revoke bằng API: `curl -X POST -H "X-Admin-Key: <admin_key>" -d '{"machine_id":"<mid>"}' http://collector:8790/api/pair-approve` → máy nhận key mới ở lần pair sau |
| Pending hiện máy đã duyệt (badge "cấp lại key") | Máy re-pair khi đã approved → cờ `repair` (mất/xoá machine.key) | Flow cố ý — admin approve lại → key mới phát qua pair, key cũ chết. Máy lạ tự re-pair nhiều lần mà IT không xoá key → nghi `beacon_secret` lộ → rotate-secret |
| winget không có (máy cũ) | Windows build cũ / LTSC | Cài ttyd tay từ github.com/tsl0922/ttyd/releases vào PATH |
| `ExecutionPolicy` chặn script | Policy mặc định của domain | Chạy `powershell -ExecutionPolicy Bypass -File install.ps1` |
| Proxy cty chặn beacon | Beacon đi HTTP thẳng | Whitelist domain collector trong proxy; tier c dùng HTTPS qua 443 |
| Update không về | Collector chưa mirror / URL upstream sai | Check `collector.json` mục `"upstream"` trên máy collector; xem `mirror` log |
| Pack không áp | pack-version cũ hơn hiện tại | Version pack phải tăng dần — bump rồi đẩy lại |
| Portal trắng trang | serve.py chết / port 8080 bị chiếm | Xem `.devin/*.log`; đổi port trong start script |
