@echo off
setlocal EnableExtensions
title Campus Platform Launcher

REM ============================================================
REM  Start both projects:
REM    UIS API        http://localhost:8000
REM    UIS UI         http://localhost:3000
REM    Campus-GPT API http://localhost:8002
REM    Campus-GPT UI  http://localhost:3001
REM ============================================================

set "ROOT=%~dp0"
set "UIS_BE=%ROOT%campus-platform\university-information-system\backend"
set "UIS_FE=%ROOT%campus-platform\university-information-system\frontend"
set "CGPT_BE=%ROOT%backend"
set "CGPT_FE=%ROOT%frontend"

echo.
echo [Campus Platform] Starting UIS + Campus-GPT ...
echo Root: %ROOT%
echo.

if not exist "%UIS_BE%\venv\Scripts\python.exe" (
  echo ERROR: UIS backend venv not found:
  echo   %UIS_BE%\venv\Scripts\python.exe
  pause
  exit /b 1
)
if not exist "%CGPT_BE%\venv\Scripts\python.exe" (
  echo ERROR: Campus-GPT backend venv not found:
  echo   %CGPT_BE%\venv\Scripts\python.exe
  pause
  exit /b 1
)

echo [1/4] UIS backend :8000
start "UIS API :8000" /D "%UIS_BE%" cmd /k ".\venv\Scripts\python.exe run.py"

echo [2/4] Campus-GPT backend :8002
start "Campus-GPT API :8002" /D "%CGPT_BE%" cmd /k "set PORT=8002&& .\venv\Scripts\python.exe run.py"

echo [3/4] UIS frontend :3000
start "UIS UI :3000" /D "%UIS_FE%" cmd /k "call npm.cmd run dev"

echo [4/4] Campus-GPT frontend :3001
start "Campus-GPT UI :3001" /D "%CGPT_FE%" cmd /k "call npm.cmd run dev"

echo.
echo Waiting for APIs to become healthy ...
powershell -NoProfile -Command ^
  "$ok=$false; for($i=0;$i -lt 40;$i++){ " ^
  "  Start-Sleep -Seconds 2; " ^
  "  try { $u=(Invoke-RestMethod http://127.0.0.1:8000/health -TimeoutSec 2).status } catch { $u=$null }; " ^
  "  try { $c=(Invoke-RestMethod http://127.0.0.1:8002/health -TimeoutSec 2).status } catch { $c=$null }; " ^
  "  Write-Host ('  try {0}: UIS={1} Campus-GPT={2}' -f ($i+1), $u, $c); " ^
  "  if($u -eq 'healthy' -and $c -eq 'healthy'){ $ok=$true; break } " ^
  "}; if(-not $ok){ Write-Host 'WARNING: APIs not healthy yet — check the server windows.'; exit 2 }"

echo.
echo ============================================================
echo  Ready (or starting):
echo    UIS UI          http://localhost:3000
echo    Campus-GPT UI   http://localhost:3001
echo    UIS API         http://localhost:8000
echo    Campus-GPT API  http://localhost:8002
echo ============================================================
echo.
echo Opening apps in your browser ...
start "" "http://localhost:3001"
ping -n 3 127.0.0.1 >nul
start "" "http://localhost:3000"

echo.
echo Leave the four server windows open. Close this launcher window anytime.
echo Double-click start-all.bat anytime to start again.
if /I "%~1"=="/nopause" goto :eof
pause
endlocal
