# clean_server.ps1 - Deep-clean a small Windows server (2GB RAM class).
# Usage (on server): powershell -ExecutionPolicy Bypass -File clean_server.ps1 [-DryRun] [-Pagefile 3072]
#   -DryRun        : show plan only, delete nothing
#   -Pagefile <MB> : set fixed pagefile size (e.g. 3072); takes effect after REBOOT
# NEVER touches: MT5*, GoldstrategyEngine, workbuddy (~\.workbuddy), hermes-agent, Recovery.
# Style rules: single-line statements only, no here-strings, ASCII only (PS 5.1 safe).
param(
  [switch]$DryRun,
  [int]$Pagefile = 0
)
$ErrorActionPreference = 'SilentlyContinue'
$before = (Get-PSDrive C).Free
$act = { param($script) if ($DryRun) { Write-Output ("DRYRUN: " + $script) } else { Invoke-Expression $script } }

# 1. Recycle Bin
& $act 'Clear-RecycleBin -DriveLetter C -Force -ErrorAction SilentlyContinue; Write-Output RECYCLE_DONE'

# 2. User Temp (>2h old; locked files skipped silently)
& $act '$old = Get-ChildItem "$env:LOCALAPPDATA\Temp" -Force -ErrorAction SilentlyContinue | Where-Object { $_.LastWriteTime -lt (Get-Date).AddHours(-2) }; foreach ($i in $old) { Remove-Item -LiteralPath $i.FullName -Recurse -Force -ErrorAction SilentlyContinue }; Write-Output TEMP_DONE'

# 3. Windows Temp (>2h old)
& $act '$old = Get-ChildItem C:\Windows\Temp -Force -ErrorAction SilentlyContinue | Where-Object { $_.LastWriteTime -lt (Get-Date).AddHours(-2) }; foreach ($i in $old) { Remove-Item -LiteralPath $i.FullName -Recurse -Force -ErrorAction SilentlyContinue }; Write-Output WTEMP_DONE'

# 4. Windows Update download cache
& $act 'Remove-Item C:\Windows\SoftwareDistribution\Download\* -Recurse -Force -ErrorAction SilentlyContinue; Write-Output WU_DONE'

# 5. npm cache
& $act 'Remove-Item "$env:LOCALAPPDATA\npm-cache\*" -Recurse -Force -ErrorAction SilentlyContinue; Write-Output NPM_DONE'

# 6. pip cache
& $act 'Remove-Item "$env:LOCALAPPDATA\pip\cache\*" -Recurse -Force -ErrorAction SilentlyContinue; Write-Output PIP_DONE'

# 7. uv cache
& $act 'Remove-Item "$env:LOCALAPPDATA\uv\cache\*" -Recurse -Force -ErrorAction SilentlyContinue; Write-Output UV_DONE'

# 8. hermes electron/tool download cache (re-downloadable)
& $act 'Remove-Item "$env:LOCALAPPDATA\hermes\cache\*" -Recurse -Force -ErrorAction SilentlyContinue; Write-Output HCACHE_DONE'

# 9. Old CBS logs (>7 days)
& $act '$cbs = Get-ChildItem C:\Windows\Logs\CBS -Force -ErrorAction SilentlyContinue; foreach ($c in $cbs) { if ($c.LastWriteTime -lt (Get-Date).AddDays(-7)) { Remove-Item -LiteralPath $c.FullName -Force -ErrorAction SilentlyContinue } }; Write-Output CBSLOG_DONE'

# 10. Pagefile resize (optional; reboot required)
if ($Pagefile -gt 0) {
  $cs = Get-CimInstance Win32_ComputerSystem
  if ($cs.AutomaticManagedPagefile) { Set-CimInstance -InputObject $cs -Property @{AutomaticManagedPagefile=$false} }
  $pf = Get-CimInstance Win32_PageFileSetting
  if ($pf) { Set-CimInstance -InputObject $pf -Property @{InitialSize=[uint32]$Pagefile; MaximumSize=[uint32]$Pagefile} }
  else { New-CimInstance -ClassName Win32_PageFileSetting -Property @{Name='C:\pagefile.sys'; InitialSize=[uint32]$Pagefile; MaximumSize=[uint32]$Pagefile} | Out-Null }
  Write-Output ("PAGEFILE_SET = {0} MB (REBOOT REQUIRED)" -f $Pagefile)
}

# 11. Working-set trim (memory only, no process killed)
$cs1 = 'using System;using System.Runtime.InteropServices;public class WS{[DllImport("psapi.dll")]public static extern bool EmptyWorkingSet(IntPtr h);}'
if (-not $DryRun) {
  Add-Type -TypeDefinition $cs1 -ErrorAction SilentlyContinue
  Get-Process | Where-Object { $_.Id -ne $PID } | ForEach-Object { [WS]::EmptyWorkingSet($_.Handle) | Out-Null }
  Write-Output WS_TRIM_DONE
} else { Write-Output 'DRYRUN: working-set trim' }

# Summary
$after = (Get-PSDrive C).Free
Write-Output ("FREED_MB = {0}" -f [math]::Round(($after-$before)/1MB,0))
Write-Output ("C_FREE_GB = {0}" -f [math]::Round($after/1GB,2))
$os = Get-CimInstance Win32_OperatingSystem
Write-Output ("MEM_FREE_GB = {0}" -f [math]::Round($os.FreePhysicalMemory/1MB,2))
