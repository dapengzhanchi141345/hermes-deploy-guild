# ============================================================
#  第 3 个客户端 (223.109.49.0 / LAVM-BPOD1H2TUW) 装 OpenSSH Server
#  Windows Server 2022 · 不依赖 Windows Update
#  用法：管理员 PowerShell 里粘贴执行
# ============================================================
$ErrorActionPreference = "Continue"
$zip = "$env:TEMP\openssh.zip"
$dst = "C:\Program Files\OpenSSH"

$urls = @(
  "https://github.com/PowerShell/Win32-OpenSSH/releases/download/v9.5.0.0p1-Beta/OpenSSH-Win64.zip",
  "https://github.com/PowerShell/Win32-OpenSSH/releases/download/v9.4.0.0p1-Beta/OpenSSH-Win64.zip",
  "https://github.com/PowerShell/Win32-OpenSSH/releases/download/v9.2.2.0p1-Beta/OpenSSH-Win64.zip"
)
$ok = $false
foreach ($u in $urls) {
  try {
    Write-Output ("try: " + $u)
    Invoke-WebRequest -Uri $u -OutFile $zip -UseBasicParsing -TimeoutSec 180
    if ((Get-Item $zip).Length -gt 1000000) { $ok = $true; break }
  } catch { Write-Output ("  fail: " + $_.Exception.Message) }
}
if (-not $ok) { Write-Output "DOWNLOAD_FAILED"; exit 1 }
Write-Output ("downloaded " + [int]((Get-Item $zip).Length/1MB) + "MB")

if (Test-Path $dst) { Remove-Item $dst -Recurse -Force -EA SilentlyContinue }
if (Test-Path "$env:TEMP\ossh") { Remove-Item "$env:TEMP\ossh" -Recurse -Force -EA SilentlyContinue }
Expand-Archive -Path $zip -DestinationPath "$env:TEMP\ossh" -Force
Move-Item "$env:TEMP\ossh\OpenSSH-Win64" $dst -Force

& "$dst\install-sshd.ps1"
Set-Service sshd -StartupType Automatic -EA SilentlyContinue
Start-Service sshd -EA SilentlyContinue

New-NetFirewallRule -Name "OpenSSH-Server-In-TCP" -DisplayName "OpenSSH Server (sshd)" `
  -Enabled True -Direction Inbound -Protocol TCP -Action Allow -LocalPort 22 -EA SilentlyContinue | Out-Null

$sd = "$env:ProgramData\ssh"
New-Item -ItemType Directory -Force -Path $sd | Out-Null
Set-Content "$sd\administrators_authorized_keys" "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIJ0xGFAwdm3HNkYIg7Il8p3+koMzFGyd35rEQbYrBSON hermes-kimi-vps" -Encoding ASCII
icacls "$sd\administrators_authorized_keys" /inheritance:r /grant "Administrators:F" /grant "SYSTEM:F" | Out-Null

& "$dst\ssh-keygen.exe" -A 2>$null
Restart-Service sshd -EA SilentlyContinue
Start-Sleep 3

Write-Output "=== RESULT ==="
Get-Service sshd | Select-Object -ExpandProperty Status
Write-Output ("22listen=" + (Get-NetTCPConnection -State Listen -LocalPort 22 -EA SilentlyContinue | Measure-Object).Count)
Write-Output ("host=" + $env:COMPUTERNAME)
