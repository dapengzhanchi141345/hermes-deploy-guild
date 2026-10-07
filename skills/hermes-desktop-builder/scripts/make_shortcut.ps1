# Creates a desktop shortcut for the built Hermes desktop GUI.
# Place on the PUBLIC desktop so every session (incl. RDP) sees it.
# Usage: powershell -ExecutionPolicy Bypass -File make_shortcut.ps1 [-Exe <path>]
param(
    [string]$Exe = "$env:LOCALAPPDATA\hermes\hermes-agent\apps\desktop\release\win-unpacked\Hermes.exe"
)
$ws = New-Object -ComObject WScript.Shell
$pub = [Environment]::GetFolderPath('CommonDesktopDirectory')
$lnk = Join-Path $pub 'Hermes.lnk'
$s = $ws.CreateShortcut($lnk)
$s.TargetPath = $Exe
$s.WorkingDirectory = Split-Path $Exe
$s.IconLocation = "$Exe,0"
$s.Description = 'Hermes Desktop GUI'
$s.Save()
Write-Output ("SHORTCUT=" + $lnk)
if (Test-Path $lnk) { Write-Output 'LNK_CREATED=True' } else { Write-Output 'LNK_CREATED=False' }
