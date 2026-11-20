@echo off
rem term-gate.cmd - ban Windows cua term-gate.sh (ASCII only, khong BOM).
rem %1 = ?arg= tu URL (ttyd -a); nao lay tu %BRAIN_TERM%.
set "t=%~1"
if "%t%"=="" set /p "t=Ma ket noi (xem trong portal > Cai dat): "
if not "%t%"=="%BRIDGE_TOKEN%" (echo Sai ma ket noi.& exit /b 1)
if "%BRAIN_TERM%"=="" set "BRAIN_TERM=devin"
%BRAIN_TERM%
