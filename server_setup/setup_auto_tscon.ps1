# setup_auto_tscon.ps1
# Run once on the server as Administrator.
# Creates a scheduled task that runs auto_tscon.bat at user logon,
# which redirects the session to console so GUI automation keeps working
# after RDP disconnects.
# Usage: right-click PowerShell -> Run as Administrator, then:
#   .\setup_auto_tscon.ps1

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$batPath   = Join-Path $scriptDir "auto_tscon.bat"
$taskName  = "ZCY_AutoTsconOnLogon"

if (-not (Test-Path $batPath)) {
    Write-Host "[ERROR] auto_tscon.bat not found next to this script: $batPath"
    exit 1
}

# Remove old task if exists (idempotent)
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

$trigger = New-ScheduledTaskTrigger -AtLogOn

$action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c ""$batPath"""

$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 2)

$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Highest

Register-ScheduledTask -TaskName $taskName -Trigger $trigger -Action $action -Settings $settings -Principal $principal -Force

Write-Host ""
Write-Host "[OK] Scheduled task created: $taskName"
Write-Host "     Runs at logon for user: $env:USERNAME"
Write-Host "     Command: $batPath"
Write-Host ""
Write-Host "Verify with:"
Write-Host "  Get-ScheduledTask -TaskName $taskName | Select-Object TaskName,State"
