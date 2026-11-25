# Phase 04 — Windows parity: RNG, constant-time, probe/denylist port, term-gate.cmd

## Vá

**S4, S6, S10-cmd, port security của phase-02+03 sang .ps1**; **S5** chỉ
ghi nhận limitation (cần cross-user spawn — việc lớn riêng).

## 4.1 — Token CSPRNG (S4)

Hai chỗ dùng `Get-Random` (System.Random — non-CSPRNG, seed ~32bit):

- `start.bat` (~line 38): thay bằng
  `powershell -NoProfile -Command "[BitConverter]::ToString([System.Security.Cryptography.RandomNumberGenerator]::GetBytes(24)).Replace('-','').ToLower()"`
- `chat-bridge.ps1` `Get-BridgeToken` fallback: cùng thay bằng
  `[System.Security.Cryptography.RandomNumberGenerator]::GetBytes(24)`
  → hex.

(Token file cũ do Get-Random sinh vẫn dùng được — rotation = xoá file +
chạy lại start; ghi chú trong SECURITY.md khuyến nghị rotate một lần.)

## 4.2 — So token constant-time (S6)

`Test-Authed`: `-ceq` → so bytes constant-time:

```powershell
$a = [Text.Encoding]::UTF8.GetBytes([string]$tok)
$b = [Text.Encoding]::UTF8.GetBytes($BridgeToken)
if ($a.Length -ne $b.Length) { return $false }
[System.Security.Cryptography.CryptographicOperations]::FixedTimeEquals($a, $b)
```

(`FixedTimeEquals` có từ .NET Core 2.1 / PS 7+. PowerShell 5.1 thiếu →
fallback: XOR loop `for($i=0;$i -lt $a.Length;$i++){$d=$d -bor ($a[$i] -bxor $b[$i])}; return ($d -eq 0)`.)

## 4.3 — Port phase-02 + 03 sang chat-bridge.ps1

- `validate_probe` tương đương (Invoke-RestMethod chủ yếu http(s) nhưng
  vẫn chặn scheme/host cho chắc); `Run-Probe` http → host loopback-only +
  body read giới hạn; `wp` → https-only.
- `/api/secrets`: url-change wipe các field khác.
- `/api/brain`: `BRAIN_CMD_DENY` giống .py + `terminal` regex `^[A-Za-z0-9_.-]+$`.
- `local_pending` gate: `/api/permissions`, `/api/remove-permission`,
  `/api/delete-lesson`, custom `/api/brain` (phase-03).
- `serve.ps1`: blocklist `my-course/{permissions,connections,config,bots}.json`
  + `bot.md` (S12).
- `chat-bridge.ps1` cleanup `troly-bot-*` temp (S13) nếu ps1 có bot-import —
  hiện không có (ps1 frozen) → bỏ qua phần import.

## 4.4 — `term-gate.cmd` (S7-terminal + S10)

- `"%BRAIN_TERM%"` — quote để chuỗi chứa `&`/space không exec thành lệnh
  khác (với terminal đã regex ^[A-Za-z0-9_.-]+$ thì đây là lớp phòng thứ 2).
- Retry 3 lần cho đúng docs (`:retry` loop, đếm sai → exit /b 1).
- `set /p` không timeout được trong cmd — ghi chú "Windows không timeout
  khi hỏi mã" trong SECURITY.md (chấp nhận — shell chờ tới khi đóng WS).

## 4.5 — S5 ghi nhận limitation

- `docs/SECURITY.md` nâng cấp cảnh báo: Windows = primary platform nhưng
  enforcement = 0 (agent đọc được secrets.local.json + mọi file user).
  Khuyến nghị ưu tiên hoàn thiện `setup-agent-user.ps1` (CreateProcessWithLogonW
  hoặc PsExec) trong một plan riêng — KHÔNG nằm trong plan này.

## Test

- Phần .ps1 verify bằng tay trên máy Windows (như phase-05 plan trước);
  các check logic port giữ trong test-bridges.py ở mức "source contains"
  (như test 24 hiện tại — parity heuristics).
- `test-parity.py` không đổi (không endpoint mới).

## Done khi

`bridge.token` Windows sinh bằng CSPRNG; `Test-Authed` constant-time;
4 gate + probe schema + secrets-wipe hoạt động trên Windows như macOS.
