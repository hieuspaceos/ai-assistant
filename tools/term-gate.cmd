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
"%BRAIN_TERM%"
