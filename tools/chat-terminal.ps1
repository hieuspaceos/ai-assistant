# chat-terminal.ps1 — chạy ttyd bọc CLI "não" cho tab "Hỏi trợ lý"
# Đọc brain.json ở gốc project lấy lệnh terminal — mặc định devin, đổi não
# trong onboarding thì chế độ Terminal cũng mở đúng CLI đó.
# Theme sáng + chữ to giãn dòng cho người quen đọc Word. Devin CLI tự
# nhận theme sáng và đổi màu chữ cho hợp (nó hỏi 1 lần, chọn
# "always auto-detect"). Muốn nền tối lại: bỏ hết phần -t '...' là xong.

$theme = 'theme={' +
  '"background":"#f6f8fa","foreground":"#24292f",' +
  '"cursor":"#24292f","selectionBackground":"#b6d7ff",' +
  '"black":"#24292f","red":"#d1242f","green":"#116329",' +
  '"yellow":"#9a6700","blue":"#0969da","magenta":"#8250df",' +
  '"cyan":"#1b7c83","white":"#6e7781",' +
  '"brightBlack":"#57606a","brightRed":"#a40e26","brightGreen":"#1a7f37",' +
  '"brightYellow":"#7d4e00","brightBlue":"#218bff","brightMagenta":"#a475f9",' +
  '"brightCyan":"#3192aa","brightWhite":"#24292f"' +
'}'

# Ghi chú: KHÔNG truyền fontFamily — khi truyền, xterm đo sai độ rộng ô
# chữ và chữ bị giãn khoảng. Font mono mặc định của từng OS đủ rõ.
$brain = "devin"
try {
    $b = Get-Content (Join-Path (Split-Path -Parent $PSScriptRoot) "brain.json") -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($b.terminal) { $brain = [string]$b.terminal }
} catch {}
ttyd -p 7681 -i 127.0.0.1 -W `
  -t $theme `
  -t fontSize=17 `
  -t lineHeight=1.45 `
  $brain
