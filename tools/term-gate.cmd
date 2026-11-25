@echo off
rem term-gate.cmd - ban Windows cua term-gate.sh (ASCII only, khong BOM).
rem %1 = ?arg= tu URL (ttyd -a); nao lay tu %BRAIN_TERM%.
rem Cho nhap sai toi da 3 lan roi thoat (set /p khong co timeout duoc nhu
rem "read -t" tren Unix — ghi nhan han che nay trong docs/SECURITY.md).
set "t=%~1"
set "n=0"
:ask
if not "%t%"=="" goto :check
set /p "t=Ma ket noi (xem trong portal > Cai dat): "
:check
if "%t%"=="%BRIDGE_TOKEN%" goto :go
set /a n+=1
if %n% GEQ 3 (echo Sai ma ket noi qua nhieu lan.& exit /b 1)
echo Sai ma ket noi, thu lai.
set "t="
goto :ask
:go
if "%BRAIN_TERM%"=="" set "BRAIN_TERM=devin"
rem BRAIN_TERM exec truc tiep — brain.json sua tay (terminal:"powershell")
rem mo shell tran trong ttyd. Deny-list giu dong bo BRAIN_CMD_DENY.
for %%B in (powershell cmd pwsh sh bash zsh fish dash python python3 py node deno bun ruby perl php osascript env nice xargs find make rake git awk gawk nawk mawk tar vim vi nvim nano emacs less more most man nohup setsid timeout flock watch parallel shortcuts xcrun docker podman su doas npm npx yarn pnpm gem pip pip3 curl wget nc ncat socat busybox open rundll32 regsvr32 mshta wscript cscript wmic certutil bitsadmin eval exec launchctl security pbcopy pbpaste screencapture ssh scp sftp rsync ftp telnet rlogin rsh tmux screen script expect lldb gdb dtrace automator swift sudo crontab at atq atrm sandbox-exec sqlite3 mysql psql redis-cli mongosh mongo qlmanage spctl codesign) do if /i "%BRAIN_TERM%"=="%%B" set "BRAIN_TERM=devin"
"%BRAIN_TERM%"
