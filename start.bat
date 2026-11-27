@echo off
rem ============================================================
rem  TRO LY AI - mo khoa hoc cua ban
rem  Double-click file nay de bat dau hoc.
rem  File nay mo toi 4 thu: trang web khoa hoc + chat bridge +
rem  cau noi extension + terminal (neu ban bat trong Cai dat).
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

rem --- "Chia khoa nha" dung chung cho cac bridge ---
if not exist .devin mkdir .devin

rem Dang chay san? → mo lai portal bang token CU ma bridge dang giu
rem trong memory. Rotate cho nay ghi de file → portal ?t=T2 vs bridge
rem giu T1 = 401, beacon doc lazy → bridge_get fail mai.
curl -sf -o nul http://127.0.0.1:7682/api/health >nul 2>nul
if not errorlevel 1 (
  for /f "usebackq delims=" %%i in (".devin\bridge.token") do set "BRIDGE_TOKEN=%%i"
  start http://localhost:8080/web/?t=%BRIDGE_TOKEN%
  echo  Tro Ly AI dang chay san - da mo lai portal.
  timeout /t 8 >nul
  exit /b 0
)

rem sinh MOI moi lan start that su (rotate mien phi, giam thoi gian song
rem neu token lo), truoc khi launch de tranh race giua cac process;
rem set env de ttyd/nao ke thua ---
powershell -NoProfile -Command "[IO.File]::WriteAllText('.devin\bridge.token', ([BitConverter]::ToString([System.Security.Cryptography.RandomNumberGenerator]::GetBytes(24))).Replace('-','').ToLower())"
for /f "usebackq delims=" %%i in (".devin\bridge.token") do set "BRIDGE_TOKEN=%%i"

rem --- Terminal trong portal la TUY CHON (Cai dat - Hien che do Terminal),
rem mac dinh TAT — doc workspace\config.json giong launcher.py:terminal_enabled().
rem Parse qua ConvertFrom-Json (config do hoc vien sua trong portal) thay vi
rem for /f tho — gia tri la vao env la injection trong batch.
set "TERM_ON=false"
if exist workspace\config.json (
  for /f "usebackq delims=" %%i in (`powershell -NoProfile -Command "try{(Get-Content 'workspace\config.json' -Raw | ConvertFrom-Json).terminal}catch{'false'}"`) do set "TERM_ON=%%i"
)

rem --- Mo tro ly AI: chat-bridge (cong 7682), che do "Chat" kieu tin nhan ---
start "Tro ly AI chat - dung dong cua so nay" /min powershell -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0tools\chat-bridge.ps1"

rem --- ttyd (cong 7681) CHI khi hoc vien da bat Terminal trong Cai dat ---
rem Khong tu cai ttyd bang winget nua — cai phan mem im lang ngoai y muon
rem la vi pham niem tin; thieu thi goi y cai tay.
if /i "%TERM_ON%"=="True" (
  where ttyd >nul 2>nul
  if not errorlevel 1 (
    start "Tro ly AI terminal - dung dong cua so nay" /min powershell -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0tools\chat-terminal.ps1"
  ) else (
    echo  [!] Terminal dang bat nhung chua co ttyd.
    echo      Cai tay: winget install --id tsl0922.ttyd -e
  )
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

rem --- Beacon (chi khi may thuoc fleet cty): day snapshot len collector ---
if exist .devin\fleet.json (
  start "Tro ly AI beacon - dung dong cua so nay" /min powershell -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0tools\beacon.ps1"
)

rem --- Mo trang web khoa hoc (cong 8080) ---
start "Khoa hoc - dung dong cua so nay" /min powershell -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0tools\serve.ps1"

timeout /t 2 /nobreak >nul
start http://localhost:8080/web/?t=%BRIDGE_TOKEN%

echo  Xong! Trang web khoa hoc da mo trong trinh duyet.
echo  Muon tat: dong cac cua so "Tro ly AI ..." dang chay nen la duoc.
echo.
timeout /t 8
