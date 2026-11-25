# CHECKLIST cài máy — in 1 trang mang theo

Bộ cài cần có: ☐ folder ai-assistant  ☐ `deploy/company/license.json`
☐ `deploy/company/fleet.json`  ☐ link/ID extension  ☐ não (devin CLI)

---

| # | Bước | Máy / Nhân viên | Kết quả | Ghi chú |
|---|------|-----------------|---------|---------|
| 1 | Chạy install.ps1 / install.sh (admin) | | ☐ | |
| 2 | User sandbox troly-agent tạo (nếu chọn) | | ☐ | |
| 3 | license.json + fleet.json vào `.devin/` | | ☐ | |
| 4 | Extension cài (store link / force-install) | | ☐ | |
| 5 | Mở "Trợ Lý AI" → portal :8080 hiện | | ☐ | |
| 6 | Onboarding: chọn não + đặt tên trợ lý | | ☐ | |
| 7 | Chat thử một câu → trả lời được | | ☐ | |
| 8 | Extension chấm xanh (token tự nhận) | | ☐ | |
| 9 | `localhost:7682/api/health` → version đúng | | ☐ | |
| 10 | Sau 15': máy hiện dashboard collector | | ☐ | |
| 11 | Dashboard: license org đúng, ghế chưa vượt | | ☐ | |
| 12 | Dặn nhân viên: mở portal mỗi sáng / autostart | | ☐ | |

---

## Bảng theo dõi nhiều máy

| STT | Máy | Nhân viên | Ngày cài | Ext | Portal | Dashboard | Ghi chú |
|-----|-----|-----------|----------|-----|--------|-----------|---------|
| 1 | | | | ☐ | ☐ | ☐ | |
| 2 | | | | ☐ | ☐ | ☐ | |
| 3 | | | | ☐ | ☐ | ☐ | |
| 4 | | | | ☐ | ☐ | ☐ | |
| 5 | | | | ☐ | ☐ | ☐ | |
| 6 | | | | ☐ | ☐ | ☐ | |
| 7 | | | | ☐ | ☐ | ☐ | |
| 8 | | | | ☐ | ☐ | ☐ | |

Lỗi gặp → tra `docs/troubleshooting-runbook.md` mục "Triển khai cty".
