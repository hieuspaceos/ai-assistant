# Ma trận website — trợ lý kết nối được tới đâu

Cập nhật: 2026-11-19. Test thật trên Chrome đã đăng nhập
`phantronghieu1@gmail.com` + phiên Microsoft/Zalo của user.

**Cơ chế:** một extension lái phiên đăng nhập SẴN trong trình duyệt —
mở tab, đọc DOM, click/gõ, scroll, chụp ảnh, fetch cùng origin.
Khi app bỏ qua sự kiện giả (`isTrusted`) → nhóm action `t*` (CDP)
bắn chuột/phím THẬT — đã chứng minh ghi được cả vào grid Sheets.

Ký hiệu: ✅ đã test thật · 🟡 vào được, thao tác chưa test sâu ·
⬜ chưa test · 🔒 cần credential/user login tay trước · 🚫 không nên/không lái

## Tier 1 — đã verify end-to-end (23 site)

| Site | Đọc | Click/gõ | Ghi/sửa | Ghi chú |
|---|---|---|---|---|
| Zalo Web | ✅ tin nhắn, list ảo hoá (scroll s1) | ✅ | ✅ soạn+gửi qua `ttype`/`tclick` | `#richInput` cần click thật |
| Outlook Web | ✅ inbox, mail | ✅ | ✅ soạn thư + Discard (dialog cần `tclick`) | phiên MS sẵn |
| Canva | ✅ danh sách thiết kế | ✅ | ✅ search template hoạt động | Canva Pro |
| Google Sheets | ✅ gviz CSV private | ✅ | ✅ **ghi ô được** (`tinsert` char mode) | bulk → MCP/import |
| Google Docs | ✅ `/mobilebasic` private | ✅ | ✅ **gõ được vào canvas** + xoá qua File menu | editor canvas |
| Google Drive | ✅ file list | ✅ | — | |
| Gmail | ✅ inbox, sender, subject | ✅ | ✅ soạn To/Subject/body + Discard | compose cần `tclick` nút |
| Google Calendar | ✅ lịch, nút tạo | ✅ | ✅ **tạo + xoá event** | ô "Add title" nên dùng `ttype` |
| Google Forms | ✅ danh sách form | 🟡 | 🟡 | |
| YouTube Studio | ✅ metric kênh | 🟡 | — | cần selector riêng |
| GA4 | ✅ số liệu dashboard | ✅ | — | |
| Search Console | ✅ property + nav | ✅ | — | |
| Microsoft 365 | ✅ dashboard | 🟡 | — | cookie banner |
| Word online | ✅ file list thật | ✅ | 🟡 | tài khoản cty imagetraveldmc |
| OneDrive Business | ✅ file list + libraries | ✅ | — | imagetraveldmc sharepoint |
| Google Slides | ✅ home + templates | — | — | user chưa có file |
| Google Trends | ✅ bảng trend VN (26 dòng) | ✅ | — | không cần login |
| Google Ads | ✅ dashboard, 3 account | ✅ | 🟡 | account 262-673-9409 |
| Notion | ✅ workspace đầy đủ | ✅ | ✅ **tạo page + gõ + Move to Trash** | menu Actions = `click` text |
| Pinterest | ✅ feed + boards | ✅ | 🟡 | login Google SSO |
| Figma | ✅ files team | ✅ | 🟡 | login Google SSO |
| LinkedIn | ✅ feed, noti, messaging | ✅ | ✅ **soạn post draft + huỷ** | nút Google trong iframe — bấm theo tọa độ |
| Trello | ✅ boards page + inbox | ✅ | ✅ **thêm thẻ được** | signup mới qua Google OAuth; UI tiếng Việt |

## Tier 2 — văn phòng & mạng xã hội (chưa test)

| Site | Ưu tiên | Đường dự kiến |
|---|---|---|
| Facebook cá nhân + Messenger | cao | ⬜ cần login |
| Meta Business Suite | cao — marketing VN | ⬜ cần login |
| Facebook Ads Manager | cao | ⬜ theo sau Business Suite |
| Instagram | trung | ⬜ |
| TikTok Studio / TikTok Shop Seller | cao — bán hàng | ⬜ |
| WhatsApp Web / Telegram Web | thấp ở VN | ⬜ cần quét QR tay |
| Excel/PPT online | trung | 🔵 cùng phiên MS (Word+OneDrive đã xong) |
| Asana / Monday | trung | ⬜ SSO Google được |
| CapCut web | trung — dân content | ⬜ ByteDance SSO |
| Buffer / Mailchimp | trung | ⬜ SSO Google được |

## Tier 3 — sàn & POS Việt Nam

| Site | Đường | Ghi chú |
|---|---|---|
| Pancake (pos.pancake.vn) | 🔒 | đa kênh bán online |
| Shopee Seller Center | 🔒 | |
| TikTok Shop Seller | 🔒 | |
| Lazada / Tiki Seller | 🔒 | |
| KiotViet | 🔒 | chuẩn POS SME |
| Sapo / iPOS / Haravan / Nhanh.vn | 🔒 | |
| Shopify Admin | 🔒 | SSO Google được |
| Sendo | 🔒 | ít dùng dần |

## Tier 4 — kế toán / HRM / hoá đơn

| Site | Đường | Ghi chú |
|---|---|---|
| MISA AMIS | 🔒 | |
| Base.vn | 🔒 | |
| FastWork / Checkin | 🔒 | |
| meInvoice / S-Invoice / MISA e-invoice | 🔒 | |
| VssID / Thuế điện tử / Dịch vụ công | 🔒 | định danh cá nhân — user tự login |

## Tier 5 — marketing / SEO / thiết kế

| Site | Đường | Ghi chú |
|---|---|---|
| Ahrefs / SEMrush / Keywordtool | 🔒 paid | đọc số liệu |
| Freepik / Envato / Pexels | ⬜ | SSO Google được |
| WordPress | 🔒 | có skill sẵn, user test sau |

## Không lái — nói rõ với user

- 🚫 App desktop thuần (Zalo PC, CapCut máy): không phải trang web.
- 🚫 Ngân hàng/ví điện tử: rủi ro bảo mật, nhiều app chặn automation.

## Quirk kỹ thuật đã học được

- `contenteditable="false"` cho tới click THẬT (Zalo): dùng `ttype`.
- Grid canvas check `isTrusted` (Sheets, Docs): synthetic fail →
  `tinsert mode=char` + `tkey` ghi được ô đơn; bulk vẫn nên MCP/import.
- Nút "Continue with Google" thường cần `tclick` (OAuth popup check trusted).
- Google One Tap iframe (LinkedIn): content script không thọc vào →
  `tclick` theo tọa độ lấy từ screenshot.
- gviz `range` phải tường minh `Z100:Z100`; `gid` để chọn đúng sheet.
