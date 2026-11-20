# Phase 5 — Windows parity

## Mục tiêu

`chat-bridge.ps1`, `start.bat`, `chat-terminal.ps1` tương đương phase 1.
`serve.ps1` không đổi (GET mở giống serve.py).

## File động

| File | Action | Việc |
|---|---|---|
| `tools/chat-bridge.ps1` | modify | token load + check + CORS + env export |
| `start.bat` | modify | sinh token (phase 1 đã ghi) |
| `tools/chat-terminal.ps1` | modify | export `BRIDGE_TOKEN` vào env ttyd |
| `tools/serve.ps1` | — | KHÔNG đổi |

## Chi tiết

### chat-bridge.ps1

```powershell
$TokenFp = Join-Path $Cwd ".devin\bridge.token"
function Get-BridgeToken {
    if (Test-Path $TokenFp) { return (Get-Content $TokenFp -Raw).Trim() }
    $t = -join ((1..48) | ForEach-Object { '{0:x}' -f (Get-Random -Max 16) })
    [IO.File]::WriteAllText($TokenFp, $t)
    return $t
}
$BridgeToken = Get-BridgeToken
$env:BRIDGE_TOKEN = $BridgeToken   # não kế thừa khi Start-Brain
```

Check trong request loop — parse query từ URL + header
`$Request.Headers["X-Bridge-Token"]` (hoặc đọc raw header), so sánh với
`[System.Security.Cryptography.FixedTimeEquals]` nếu có, không thì
`-ceq` (chấp nhận — loopback). Miễn `/api/health` + `OPTIONS`.

CORS: `Access-Control-Allow-Headers: Content-Type, X-Bridge-Token`.

### chat-terminal.ps1

Trước khi chạy ttyd: đọc `.devin\bridge.token` → `$env:BRIDGE_TOKEN`
→ ttyd spawn shell kế thừa → agent trong terminal mode cũng có env.

## Acceptance

- `Invoke-RestMethod http://127.0.0.1:7682/api/poll` không token → 401
- Header `X-Bridge-Token` đúng → 200
- `OPTIONS` → 204 đủ Allow-Headers
- ttyd shell: `$env:BRIDGE_TOKEN` có giá trị

## Rủi ro

- Không có pwsh trên macOS test — review tay + nhờ chạy trên máy Windows
  sau (ghi rõ trong commit message)
