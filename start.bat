@echo off
rem ============================================================
rem  TRO LY AI - mo khoa hoc cua ban
rem  Double-click file nay de bat dau hoc.
rem  File nay mo toi 4 thu: trang web khoa hoc + chat bridge +
rem  cau noi extension + terminal (neu co ttyd).
rem ============================================================
cd /d "%~dp0"

echo.
echo  Dang mo khoa hoc, cho mot chut nhe...
echo.

rem --- Doc "nao" tu brain.json (mac dinh devin, doi duoc trong onboarding) ---
set "BRAIN_CMD=devin"
set "BRAIN_TERM=devin"
if exist brain.json (
  rem Doc qua read-brain.ps1: validate charset + deny-list TRUOC khi gia
  rem tri vao env — expansion trong batch (&, |) la injection neu doc tho.
  for /f "usebackq tokens=1,2 delims=|" %%i in (`powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\read-brain.ps1"`) do (
    set "BRAIN_CMD=%%i"
    set "BRAIN_TERM=%%j"
  )
)

rem --- Kiem tra CLI cua nao ---
where %BRAIN_CMD% >nul 2>nul
if errorlevel 1 (
  echo  [!] Chua co '%BRAIN_CMD%' - nao tro ly. Che do Chat se khong chay.
  echo      Cai no, hoac mo portal roi doi sang nao khac trong muc thiet lap.
  echo.
)

rem --- "Chia khoa nha" dung chung cho cac bridge — sinh 1 lan truoc khi
rem launch (tranh race giua cac process); set env de ttyd/nao ke thua ---
if not exist .devin mkdir .devin
rem file ton tai nhap nhung rong (ai do tao file trong) thi xoa de sinh lai
if exist .devin\bridge.token (
  for %%A in (.devin\bridge.token) do if %%~zA EQU 0 del .devin\bridge.token
)
if not exist .devin\bridge.token (
  powershell -NoProfile -Command "[IO.File]::WriteAllText('.devin\bridge.token', ([BitConverter]::ToString([System.Security.Cryptography.RandomNumberGenerator]::GetBytes(24))).Replace('-','').ToLower())"
)
for /f "usebackq delims=" %%i in (".devin\bridge.token") do set "BRIDGE_TOKEN=%%i"

rem --- Kiem tra ttyd (de nhung terminal vao trang web) ---
where ttyd >nul 2>nul
if errorlevel 1 (
  echo  Chua co ttyd - dang cai tu dong qua winget...
  winget install --id tsl0922.ttyd -e --accept-source-agreements --accept-package-agreements >nul 2>nul
)

rem --- Mo tro ly AI: 2 dich vu song song ---
rem   1. chat-bridge (cong 7682): che do "Chat" kieu tin nhan, de dung nhu Zalo
rem   2. ttyd (cong 7681): che do "Terminal" - CLI that nhung tren web
start "Tro ly AI chat - dung dong cua so nay" /min powershell -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0tools\chat-bridge.ps1"

where ttyd >nul 2>nul
if not errorlevel 1 (
  start "Tro ly AI terminal - dung dong cua so nay" /min powershell -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0tools\chat-terminal.ps1"
) else (
  echo  [!] Khong cai duoc ttyd. Che do "Terminal" se khong hoat dong,
  echo      nhung che do "Chat" van dung binh thuong.
  echo      Ban cung co the mo Windows Terminal va go "%BRAIN_TERM%" de hoc.
)

rem --- Cau noi cho extension "Tro Ly AI" trong trinh duyet (cong 7684) ---
rem Cho phep tro ly thao tac tren trang web hoc vien dang mo (Zalo, Outlook...).
rem Can Python that su chay duoc - "python" cua Microsoft Store chi la cai
rem stub mo Store nen phai chay thu, khong duoc chi kiem "where".
set PY=
python --version >nul 2>nul && set PY=python
if not defined PY (py -3 --version >nul 2>nul && set PY=py -3)
if defined PY (
  start "Tro ly AI browser - dung dong cua so nay" /min %PY% "%~dp0tools\ext-bridge.py" 7684 "%~dp0."
) else (
  echo  [!] Chua co Python that - cau noi extension se khong chay.
  echo      Cai bang: winget install --id Python.Python.3.12 -e
)

rem --- Mo trang web khoa hoc (cong 8080) ---
start "Khoa hoc - dung dong cua so nay" /min powershell -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0tools\serve.ps1"

timeout /t 2 /nobreak >nul
start http://localhost:8080/web/?t=%BRIDGE_TOKEN%

echo  Xong! Trang web khoa hoc da mo trong trinh duyet.
echo  Muon tat: dong cac cua so "Tro ly AI ..." dang chay nen la duoc.
echo.
timeout /t 8
