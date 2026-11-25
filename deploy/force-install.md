# Force-install extension — IT đẩy, nhân viên không bấm gì

Sau khi extension lên Chrome Web Store (unlisted), IT có thể bắt máy
tự cài + tự update qua policy. ID extension:

```
mdalidmkajiinlpdefjchbgcejjjmpeh
```

(ID này derive từ `key` trong manifest.json — giữ key là giữ ID.
Đường update luôn là `https://clients2.google.com/service/update2/crx`.)

## Windows — Registry (một máy) hoặc GPO (cả domain)

### Registry tay (test một máy trước)

```powershell
New-Item -Path "HKLM:\SOFTWARE\Policies\Google\Chrome\ExtensionInstallForcelist" -Force
New-ItemProperty -Path "HKLM:\SOFTWARE\Policies\Google\Chrome\ExtensionInstallForcelist" `
  -Name "1" -PropertyType String `
  -Value "mdalidmkajiinlpdefjchbgcejjjmpeh;https://clients2.google.com/service/update2/crx"
```

### GPO (nhiều máy)

1. Tải Chrome ADMX templates → import vào Central Store.
2. Computer Config → Admin Templates → Google → Google Chrome →
   Extensions → **Configure the list of force-installed apps and
   extensions** → Enabled → thêm dòng:
   `mdalidmkajiinlpdefjchbgcejjjmpeh;https://clients2.google.com/service/update2/crx`
3. `gpupdate /force` trên máy đích.

## macOS — plist (MDM hoặc tay)

```sh
defaults write com.google.Chrome ExtensionInstallForcelist -array \
  "mdalidmkajiinlpdefjchbgcejjjmpeh;https://clients2.google.com/service/update2/crx"
```

Với MDM (Jamf/Intune/Kandji): đẩy configuration profile cùng key
`ExtensionInstallForcelist` cho `com.google.Chrome`.

## Edge

Cùng pattern, key khác:

```powershell
New-Item -Path "HKLM:\SOFTWARE\Policies\Microsoft\Edge\ExtensionInstallForcelist" -Force
New-ItemProperty -Path "HKLM:\SOFTWARE\Policies\Microsoft\Edge\ExtensionInstallForcelist" `
  -Name "1" -PropertyType String `
  -Value "mdalidmkajiinlpdefjchbgcejjjmpeh;https://clients2.google.com/service/update2/crx"
```

(Extension Edge cài từ Chrome Web Store hoạt động bình thường.)

## Kiểm chứng

1. `chrome://policy` (hoặc `edge://policy`) → thấy
   `ExtensionInstallForcelist` giá trị đúng.
2. Mở lại trình duyệt → extension "Trợ Lý AI" tự hiện, không gỡ được
   (force-installed).
3. Nhân viên mở portal lần đầu → portal tự đẩy mã kết nối cho
   extension (`set-token` qua externally_connectable — đã có sẵn
   trong web/app.js). Không cần copy token tay.

## Gỡ

Xoá giá trị registry/policy → extension tự biến mất ở lần khởi động
trình duyệt kế tiếp.

## Lưu ý

- Force-install chỉ hoạt động với extension **từ store** — self-hosted
  CRX không được Chrome Windows/Edge chấp nhận (Linux mới được).
  Đây là lý do bắt buộc publish lên Web Store.
- Unlisted = không tìm thấy trên store, chỉ ai có link/policy mới cài
  được — vẫn đủ cho force-install.
