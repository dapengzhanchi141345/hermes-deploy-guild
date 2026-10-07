$ErrorActionPreference = "Continue"
$taskName = "HermesDesktopBuild"
# Run the fast re-pack (reuses cached renderer; ~2 min) each time Administrator logs on.
$action = New-ScheduledTaskAction -Execute "powershell.exe" `
  -Argument "-ExecutionPolicy Bypass -WindowStyle Hidden -File C:\Users\Administrator\pack_builder_only.ps1" `
  -WorkingDirectory "C:\Users\Administrator"
$trigger = New-ScheduledTaskTrigger -AtLogOn
$principal = New-ScheduledTaskPrincipal -UserId "Administrator" -LogonType Interactive -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries `
  -ExecutionTimeLimit (New-TimeSpan -Hours 2)
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force
$t = Get-ScheduledTask -TaskName $taskName
"TASK_INSTALLED state=$($t.State)"
