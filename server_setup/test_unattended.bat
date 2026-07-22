@echo off
REM ============================================================
REM  Unattended test helper. Right-click -> Run as administrator.
REM  1) applies no-lock / no-idle-disconnect registry settings
REM  2) creates a one-shot scheduled task 2 minutes from now
REM     that runs run_zcy_download.py
REM  After it finishes, follow the on-screen instruction to tscon.
REM ============================================================

REM --- resolve project root (parent of this server_setup folder) ---
pushd "%~dp0.."
set "ROOT=%CD%"
popd

echo Project root: %ROOT%
echo.

REM --- 1) registry: no idle disconnect, no lock ---
reg add "HKLM\SYSTEM\CurrentControlSet\Control\Terminal Server\WinStations\RDP-Tcp" /v MaxIdleTime /t REG_DWORD /d 0 /f >nul
reg add "HKLM\SYSTEM\CurrentControlSet\Control\Terminal Server\WinStations\RDP-Tcp" /v MaxDisconnectionTime /t REG_DWORD /d 0 /f >nul
powercfg /change monitor-timeout-ac 0
echo [OK] registry / power settings applied
echo.

REM --- 2) compute time 2 minutes from now (HH:mm) ---
for /f %%i in ('powershell -NoProfile -Command "(Get-Date).AddMinutes(2).ToString('HH:mm')"') do set "T=%%i"

schtasks /Create /TN "ZCY_TEST" /SC ONCE /ST %T% /F /TR "cmd /c cd /d %ROOT% && python run_zcy_download.py"
echo.
echo [OK] test task ZCY_TEST will run at %T% (about 2 minutes from now)
echo.
echo ============================================================
echo  NEXT STEP - do this now:
echo    open a CMD window and type:   tscon 2 /dest:console
echo    (your remote desktop will disconnect - that is expected)
echo  Then wait 3-4 minutes, reconnect, and open the newest file
echo  in %ROOT%\logs\  named zcy_download_*.log
echo ============================================================
echo.
pause
