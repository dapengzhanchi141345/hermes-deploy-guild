# Fix: Hermes desktop boots but no window appears / backend times out
# (SECOND occurrence 2026-10-07 — root causes fully mapped this time)
#
# Symptom: Hermes.exe processes alive (4-5) but no window; desktop.log shows either
#   "no usable Hermes install ... Waiting for first-run setup choice"  or
#   "completing source-update dependencies..." -> "Timed out waiting for Hermes
#   backend port announcement (90000ms)"
#
# Root cause chain (all three must be cleared):
#   1. `source-completion-pending` marker (at %LOCALAPPDATA%\hermes\installs\<hash>\)
#      -> EVERY CLI launch (incl. backend serve + venv import probe) first runs
#      "completing source-update dependencies..." (uv/pip sync + product builds),
#      exceeding the desktop's 90s backend timeout. NOTE: `hermes --version` does NOT
#      trigger this (bypasses prepare_launch) — CLI looks healthy, extremely misleading.
#   2. Stale locks: `.hermes-update-in-progress` / `.hermes-update-in-progress.lock`
#      in %LOCALAPPDATA%\hermes\ (left by killed processes) — block any new completion
#      attempt forever ("an update is still running" / silent idle).
#   3. venv Python version gate: desktop source-install check only accepts 3.11/3.12/
#      3.13 (e.g. 3.14.6 -> "broken/partial venv" -> "no usable Hermes install" ->
#      stuck on first-run setup). BUT once marker+locks are cleared the probe passes
#      and even 3.14 gets accepted via "Using existing Hermes Python".
#
# Fix (this script): kill stuck processes -> delete pending marker + stale locks ->
#   set HERMES_DESKTOP_HERMES (belt) + HERMES_DISABLE_LAZY_INSTALLS (braces, skips
#   prepare_launch entirely per venv_sync.py:364) -> ready for relaunch.
#
# Usage: powershell -ExecutionPolicy Bypass -File fix_backend_boot.ps1
# Relaunch the desktop afterwards and verify desktop.log reaches
#   "HERMES_BACKEND_READY port=<n>" + "Hermes backend is ready" (boot ~60s).

$ErrorActionPreference = "Continue"
$root = "$env:LOCALAPPDATA\hermes\hermes-agent"
$home2 = "$env:LOCALAPPDATA\hermes"
$hermes = "$root\venv\Scripts\hermes.exe"
if (-not (Test-Path $hermes)) { Write-Output "FATAL: $hermes not found"; exit 1 }

Write-Output "=== 1. kill stuck processes (desktop + completion pythons) ==="
Get-ScheduledTask -TaskName HermesFinish -ErrorAction SilentlyContinue | Stop-ScheduledTask -ErrorAction SilentlyContinue
Get-Process Hermes -ErrorAction SilentlyContinue | Stop-Process -Force
Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "$root\venv*" } | Stop-Process -Force
Start-Sleep -Seconds 2

Write-Output "=== 2. delete pending completion marker + stale update locks ==="
foreach ($m in @(
    "$home2\.hermes-update-in-progress",
    "$home2\.hermes-update-in-progress.lock",
    "$root\.update-incomplete",
    "$root\.lazy-refresh-incomplete"
)) {
    if (Test-Path $m) { Remove-Item $m -Force; Write-Output ("DELETED " + $m) }
}
Get-ChildItem $home2 -Recurse -Force -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -match '^source-completion-pending$|completion-pending|update-incomplete|lazy-refresh-incomplete' } |
    ForEach-Object { Write-Output ("DELETED " + $_.FullName); Remove-Item $_.FullName -Force }

Write-Output "=== 3. env switches (user scope) ==="
setx HERMES_DESKTOP_HERMES "$hermes" | Out-Null
setx HERMES_DISABLE_LAZY_INSTALLS 1 | Out-Null
Write-Output ("OVERRIDE=" + [Environment]::GetEnvironmentVariable('HERMES_DESKTOP_HERMES', 'User'))
Write-Output ("SKIP_LAZY=" + [Environment]::GetEnvironmentVariable('HERMES_DISABLE_LAZY_INSTALLS', 'User'))

Write-Output "=== 4. verify CLI healthy ==="
$env:HERMES_DISABLE_LAZY_INSTALLS = "1"
$sw = [System.Diagnostics.Stopwatch]::StartNew()
& $hermes --version 2>&1 | Out-String
$sw.Stop()
Write-Output ("PROBE_EXIT=" + $LASTEXITCODE + " ELAPSED_S=" + [int]$sw.Elapsed.TotalSeconds)

Write-Output "=== DONE. Now relaunch the desktop (double-click or shortcut), then check ==="
Write-Output '%LOCALAPPDATA%\Hermes\logs\desktop.log must reach: HERMES_BACKEND_READY port=<n> + "Hermes backend is ready"'
Write-Output 'If a brand-new window still fails: log off/on once so Explorer picks up the new env vars.'
