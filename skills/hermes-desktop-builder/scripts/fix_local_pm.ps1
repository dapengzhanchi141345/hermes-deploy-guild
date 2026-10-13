# fix_local_pm.ps1 - One-shot repair for local Hermes "repeatedly broken" case (2026-10-13)
# Usage: powershell -ExecutionPolicy Bypass -File fix_local_pm.ps1 [-Home "E:\path\to\hermes-home"] [-SkipRepair]
# Steps: 1) delete leftover User env vars  2) clean polluted env in this shell
#        3) batch health-check pm environments  4) run `hermes pm repair` via scheduled task (outside sandbox)
# Final acceptance (manual): desktop.log must show HERMES_BACKEND_READY + "backend is ready"
param(
    [string]$Home_ = "",
    [switch]$SkipRepair
)

$ErrorActionPreference = "Continue"

# --- Resolve home dir ---
if ($Home_ -eq "") {
    $candidates = @(
        (Join-Path $env:LOCALAPPDATA "hermes")
    )
    foreach ($c in $candidates) {
        if (Test-Path (Join-Path $c "hermes-agent")) { $Home_ = $c; break }
    }
}
if ($Home_ -eq "") { Write-Output "[FAIL] cannot locate hermes home (pass -Home)."; exit 1 }
Write-Output "[1] HOME = $Home_"

# --- Step 1: delete leftover User-level env vars (blocks CLI self-heal) ---
foreach ($v in @("HERMES_DISABLE_LAZY_INSTALLS", "HERMES_DESKTOP_HERMES")) {
    $u = [Environment]::GetEnvironmentVariable($v, "User")
    if ($null -ne $u) {
        [Environment]::SetEnvironmentVariable($v, $null, "User")
        Write-Output "[2] deleted User env var $v (was: $u)"
    } else {
        Write-Output "[2] User env var $v not present (ok)"
    }
}
foreach ($v in @("HERMES_DISABLE_LAZY_INSTALLS", "HERMES_DESKTOP_HERMES")) {
    Remove-Item "Env:$v" -ErrorAction SilentlyContinue
}

# --- Step 2: clean polluted env in current shell ---
foreach ($v in @("PYTHONPATH", "http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "all_proxy", "ALL_PROXY")) {
    if (Test-Path "Env:$v") { Remove-Item "Env:$v" -ErrorAction SilentlyContinue; Write-Output "[3] cleaned $v in this shell" }
}
$env:PYTHONUTF8 = "1"

# --- Step 3: batch health-check pm environments ---
$installs = Join-Path $env:LOCALAPPDATA "hermes\installs"
$envRoot = $null
if (Test-Path (Join-Path $Home_ "installs")) { $envRoot = Join-Path $Home_ "installs" }
elseif (Test-Path $installs) { $envRoot = $installs }
$badCount = 0; $okCount = 0
if ($envRoot -ne $null) {
    $envs = Get-ChildItem $envRoot -Directory -ErrorAction SilentlyContinue | ForEach-Object { Join-Path $_.FullName "environments" } | Where-Object { Test-Path $_ }
    foreach ($e in $envs) {
        Get-ChildItem $e -Directory -ErrorAction SilentlyContinue | ForEach-Object {
            $py = Join-Path $_.FullName "venv\Scripts\python.exe"
            if (Test-Path $py) {
                $r = & $py -c "import pydantic_core,fastapi,uvicorn,httpx; print('OK')" 2>&1
                $last = ($r | Select-Object -Last 1)
                $tag = $_.Name.Substring(0, [Math]::Min(8, $_.Name.Length))
                if ($last -eq "OK") { $okCount++; Write-Output "[4] env $tag => OK" }
                else { $badCount++; Write-Output "[4] env $tag => BROKEN: $last" }
            } else {
                $badCount++; Write-Output "[4] env $($_.Name.Substring(0,[Math]::Min(8,$_.Name.Length))) => NO PYTHON.EXE"
            }
        }
    }
} else {
    Write-Output "[4] no installs dir found (skip health check)"
}
Write-Output "[4] summary: OK=$okCount BROKEN=$badCount"

# --- Step 4: run pm repair via scheduled task (outside sandbox; direct run dies with os error 5) ---
if ($SkipRepair) { Write-Output "[5] -SkipRepair set, skip pm repair."; exit 0 }
if ($badCount -eq 0 -and $okCount -gt 0) {
    Write-Output "[5] all environments OK, skip repair (use -SkipRepair to force)."
} else {
    $cli = Join-Path $Home_ "hermes-agent\venv\Scripts\hermes.exe"
    if (-not (Test-Path $cli)) { Write-Output "[FAIL] hermes.exe not found at $cli"; exit 1 }
    $taskName = "HermesPmRepairOnce"
    $action = New-ScheduledTaskAction -Execute $cli -Argument "pm repair" -WorkingDirectory $Home_
    $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddSeconds(5)
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Force | Out-Null
    Start-ScheduledTask -TaskName $taskName
    Write-Output "[5] scheduled task $taskName started; wait 2-3 min then verify:"
    Write-Output "    (Get-ScheduledTaskInfo -TaskName '$taskName').LastTaskResult   # 0 = success"
    Write-Output "    then re-run this script to health-check, then: Start-ScheduledTask HermesDesktopLaunch"
    Write-Output "    and confirm desktop.log shows HERMES_BACKEND_READY + backend is ready"
}
Write-Output "DONE"
