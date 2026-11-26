# Phase 4 — Hardening nhỏ + sửa doc lệch + commit work đang dở

## Mục tiêu

Dọn các lỗi nhỏ còn lại của audit: secret file không `chmod 600`, doc ghi
sai port, và 8 file sửa dở (tính năng `extVersion`) chưa commit.

## File động

| File | Action | Việc |
|---|---|---|
| `tools/chat-bridge.py` | modify | `chmod 600` sau khi ghi `secrets.local.json` |
| `tools/chat-bridge.ps1` | modify | ACL tương đương trên Windows (ghi chú, không chmod) |
| `PLAN.md` | modify | ext-bridge `:7683` → `:7684` |
| `docs/*` | check | grep `7683` toàn repo, sửa chỗ còn sót |
| working tree | commit | tính năng `extVersion` đang dở → commit riêng |

## Chi tiết

### 4a. `secrets.local.json` chmod 600

`.py` — trong nhánh `/api/secrets`, sau `save_json(fp, creds)`:

```python
try:
    os.chmod(fp, 0o600)          # token được chmod 600 thì secret cũng vậy
except OSError:
    pass                          # Windows không có chmod — bỏ qua
```

`.ps1` — Windows không có chmod; thêm ACL chỉ-owner nếu đơn giản, hoặc ghi
chú trong code chấp nhận (threat model: cùng user account trên máy học
viên đã đọc được file anyway — khác với bridge.token cần 600 vì process
KHÁC user? không — cùng user. Thật ra `chmod 600` trên unix chặn user
khác trên máy; Windows tương đương là ACL mặc định `~/` đã chỉ-owner).
**Quyết định khi implement**: nếu ACL phức tạp >10 dòng thì bỏ, ghi
vào SECURITY.md là "Windows: ACL thư mục home mặc định đủ".

### 4b. Doc lệch

- `PLAN.md` Phase 1 mục 5: `ext-bridge.py (:7683)` → `:7684`.
- `grep -rn "7683" .` — sửa mọi chỗ còn sót (docs, comments).
- `docs/skills-system.md`: sửa số đếm "en 17 skill" (thực tế 18, sau
  phase 2 là 20) + bảng skill cập nhật theo phase 2.
- `start.bat`: comment đầu file "mo 2 thu" → mở tới 4 process.
- `docs/api-reference.md`: đã kiểm — `save-page` + `extVersion` đều đã
  được ghi đúng (doc không thiếu; chỉ `.ps1` thiếu code).

### 4c. Commit work `extVersion` đang dở

Working tree có 8 file modified (tính năng extension version reporting:
`ext-bridge.py` `?v=`, `background.js` gửi version, `app.js` chip
"Extension bản cũ", health `extVersion`). Đây là feature hoàn chỉnh
đang chạy — commit riêng TRƯỚC khi bắt đầu phase 1 để diff sau đó sạch.
Message gợi ý: `Báo version extension qua WS + chip cảnh báo bản cũ`.

Lưu ý: `my-course/connections.json` diff chỉ là trạng thái runtime
(`connected`→`not-connected`) — KHÔNG commit, đây là dữ liệu máy dev.

## Acceptance

- `stat -f %A .devin/secrets.local.json` = `600` sau khi ghi secret mới
  (macOS/Linux).
- `grep -rn "7683" .` = 0 kết quả sai (comment lịch sử trong plans/ cũ
  giữ nguyên — doc lịch sử không sửa).
- `git status` sạch sau khi commit extVersion (trừ `connections.json`
  runtime diff — cân nhắc gitignore hoặc chấp nhận).

## Rủi ro

- `connections.json` bị commit nhầm trạng thái máy dev → trong khi commit
  extVersion, stage từng file tên, bỏ `connections.json` ra.
