@echo off
REM Redirect current user session to console so GUI API stays usable
REM after RDP disconnects. Triggered at logon by ZCY_AutoTsconOnLogon task.

REM Wait for desktop to finish loading
timeout /t 10 /nobreak > nul

REM Find current user's active session ID, tscon it to console
for /f "tokens=3" %%i in ('query session %USERNAME% ^| findstr /i "active"') do (
    echo Redirecting session %%i to console...
    tscon %%i /dest:console
)
