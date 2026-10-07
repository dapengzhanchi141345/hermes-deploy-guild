# Ensures RDP is enabled and port 3389 is allowed through the firewall.
# Usage: powershell -ExecutionPolicy Bypass -File fix_rdp_fw.ps1
$fdeny = (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server').fDenyTSConnections
if ($fdeny -ne 0) {
    Set-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server' -Name fDenyTSConnections -Value 0
    Write-Output 'RDP_ENABLED=True (was disabled, now enabled)'
} else {
    Write-Output 'RDP_ENABLED=True (already)'
}
$rules = Get-NetFirewallRule | Where-Object { $_.DisplayName -match '远程桌面|Remote Desktop|RDP 3389' }
if (-not ($rules | Where-Object { $_.Enabled -eq 'True' })) {
    New-NetFirewallRule -DisplayName 'RDP 3389 Allow TCP' -Direction Inbound -Protocol TCP -LocalPort 3389 -Action Allow -Profile Any | Out-Null
    New-NetFirewallRule -DisplayName 'RDP 3389 Allow UDP' -Direction Inbound -Protocol UDP -LocalPort 3389 -Action Allow -Profile Any | Out-Null
    Write-Output 'FW=created new allow rules'
}
$active = Get-NetFirewallRule | Where-Object { $_.DisplayName -match '远程桌面|Remote Desktop|RDP 3389' -and $_.Enabled -eq 'True' } | Measure-Object
Write-Output ("ACTIVE_RULES=" + $active.Count)
Write-Output ("PORT_LISTEN=" + ((Get-NetTCPConnection -LocalPort 3389 -State Listen -ErrorAction SilentlyContinue) -ne $null))
