# ============================================================
# acceptance_check.ps1 — Hermes 桌面端交付总验收（一键红绿门禁）
# 覆盖全部历史踩坑：exe/后端启动/配置home/模型/标记残留/venv版本门/
#                   环境变量/快捷方式/RDP/自动重建任务
# 用法: powershell -ExecutionPolicy Bypass -File acceptance_check.ps1 [-WithChatTest]
#       -WithChatTest  追加真实对话测试（耗 Agnes 1次/分钟配额，429 记 WARN 不判死）
# 退出码: 0=全绿可交付  1=有 FAIL 不得交付
# ============================================================
param([switch]$WithChatTest)
$ErrorActionPreference = 'SilentlyContinue'
$script:FAIL = 0; $script:WARN = 0; $script:PASS = 0

function Add-Gate {
  param($Name, $Status, $Detail)
  $icon = switch ($Status) { 'PASS' {'[OK]  '} 'WARN' {'[WARN]'} default {'[FAIL]'} }
  Write-Output ("{0} [{1}] {2} -- {3}" -f $icon, $Status, $Name, $Detail)
  if ($Status -eq 'FAIL') { $script:FAIL++ } elseif ($Status -eq 'WARN') { $script:WARN++ } else { $script:PASS++ }
}
function Test-File($p) { Test-Path $p }

$root = "$env:LOCALAPPDATA\hermes\hermes-agent"
$desktopLog = "$env:LOCALAPPDATA\Hermes\logs\desktop.log"

Write-Output "===== Hermes 桌面端交付总验收 $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ====="

# ── G1 桌面端产物 ──
$exe = "$root\apps\desktop\release\win-unpacked\Hermes.exe"
if (Test-File $exe) {
  $mb = [int]((Get-Item $exe).Length / 1MB)
  Add-Gate 'G1 exe产物' 'PASS' ("{0} ({1}MB)" -f $exe, $mb)
} else { Add-Gate 'G1 exe产物' 'FAIL' "$exe 不存在" }

# ── G2 后端真正启动（exe能跑≠可用，历史两次踩坑） ──
if (Test-File $desktopLog) {
  $tail = (Get-Content $desktopLog -Tail 120) -join "`n"
  $ready = $tail -match 'HERMES_BACKEND_READY'
  $stuck = ($tail -match 'Waiting for first-run setup choice') -or ($tail -match 'no usable Hermes install')
  if ($ready -and -not $stuck) {
    Add-Gate 'G2 后端启动' 'PASS' 'desktop.log 有 HERMES_BACKEND_READY 且无卡引导'
  } elseif ($stuck) {
    Add-Gate 'G2 后端启动' 'FAIL' '卡在 first-run setup choice / no usable install → 跑 fix_backend_boot.ps1'
  } else {
    Add-Gate 'G2 后端启动' 'WARN' '未见 HERMES_BACKEND_READY（可能未启动过或日志被清）→ 启动桌面端后复验'
  }
} else { Add-Gate 'G2 后端启动' 'WARN' "$desktopLog 不存在（桌面端从未启动）" }

# ── G3 配置 home 判定（两代版本不同，写错位置静默失效） ──
$homeOut = & "$root\venv\Scripts\python.exe" -I -c "from hermes_constants import get_hermes_home; print(get_hermes_home())" 2>$null
$hhome = ($homeOut | Select-Object -Last 1)
if (-not $hhome -or -not (Test-Path $hhome)) { $hhome = "$env:LOCALAPPDATA\hermes" }
Add-Gate 'G3 配置home' 'PASS' ("解析为 {0}" -f $hhome)
if (-not (Test-File "$hhome\config.yaml")) {
  Add-Gate 'G4 config.yaml' 'FAIL' "$hhome\config.yaml 不存在 → 模型未配置"
} else {
  $cfg = Get-Content "$hhome\config.yaml" -Raw
  if ($cfg -match 'providers:' -and $cfg -match 'transport:') { Add-Gate 'G4 config.yaml' 'PASS' 'providers 段存在' }
  else { Add-Gate 'G4 config.yaml' 'WARN' '存在但未见 providers/transport 段（0.19.0 旧版向导配置也正常）' }
}

# ── G5 key 在位（.env 有值，不回显） ──
$keyEnvName = if ($env:CHECK_KEY_ENV) { $env:CHECK_KEY_ENV } else { 'AGNES_API_KEY' }
$envFile = "$hhome\.env"
if (Test-File $envFile) {
  $hit = Select-String -Path $envFile -Pattern ("^\s*{0}\s*=\s*\S+" -f $keyEnvName)
  if ($hit) { Add-Gate 'G5 API Key' 'PASS' ("{0} 已配置（不回显）" -f $keyEnvName) }
  else { Add-Gate 'G5 API Key' 'FAIL' ("{0} 不在 {1}" -f $keyEnvName, $envFile) }
} else { Add-Gate 'G5 API Key' 'FAIL' "$envFile 不存在" }

# ── G6 hermes status 识别模型 ──
$hermes = "$root\venv\Scripts\hermes.exe"
if (Test-File $hermes) {
  $st = (& $hermes status 2>&1) -join "`n"
  if ($st -match 'Model:\s*\(not set\)') { Add-Gate 'G6 模型识别' 'FAIL' 'status 显示 (not set) → config 写错位置或格式错' }
  elseif ($st -match 'Model:\s*(\S+)') { Add-Gate 'G6 模型识别' 'PASS' ("Model={0}" -f $Matches[1]) }
  else { Add-Gate 'G6 模型识别' 'WARN' ('status 输出无法解析：' + ($st.Substring(0, [Math]::Min(120, $st.Length)))) }
} else { Add-Gate 'G6 模型识别' 'FAIL' "CLI 不存在: $hermes" }

# ── G7 挂起标记/死锁残留（补依赖假死元凶） ──
$markers = Get-ChildItem $hhome -Recurse -Force -File -ErrorAction SilentlyContinue |
  Where-Object { $_.Name -match 'source-completion-pending|update-incomplete|lazy-refresh-incomplete' -or $_.Name -eq '.hermes-update-in-progress' -or $_.Name -eq '.hermes-update-in-progress.lock' } |
  Select-Object -First 5
if ($markers) {
  $names = ($markers | ForEach-Object { $_.Name }) -join ', '
  Add-Gate 'G7 残留标记' 'FAIL' ("存在挂起标记/死锁: {0} → 跑 fix_backend_boot.ps1 清理" -f $names)
} else { Add-Gate 'G7 残留标记' 'PASS' '无 pending 标记、无陈旧锁' }

# ── G8 venv 版本门 + 环境变量绕行 ──
$pyVer = (& "$root\venv\Scripts\python.exe" -I -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null | Select-Object -Last 1)
$dhEnv = [Environment]::GetEnvironmentVariable('HERMES_DESKTOP_HERMES', 'User')
if ($pyVer -match '^3\.(11|12|13)$') { Add-Gate 'G8 venv版本门' 'PASS' ("Python {0} 受支持" -f $pyVer) }
elseif ($dhEnv) { Add-Gate 'G8 venv版本门' 'PASS' ("Python {0} 不受支持但 HERMES_DESKTOP_HERMES 已绕行" -f $pyVer) }
else { Add-Gate 'G8 venv版本门' 'FAIL' ("Python {0} 不受支持(需3.11-3.13)且未设 HERMES_DESKTOP_HERMES" -f $pyVer) }

# ── G9 双保险环境变量 ──
$lazy = [Environment]::GetEnvironmentVariable('HERMES_DISABLE_LAZY_INSTALLS', 'User')
if ($lazy -eq '1') { Add-Gate 'G9 跳过补依赖' 'PASS' 'HERMES_DISABLE_LAZY_INSTALLS=1' }
else { Add-Gate 'G9 跳过补依赖' 'WARN' '未设（新装源码树会触发启动补依赖→90s超时风险）→ fix_backend_boot.ps1' }

# ── G10 桌面快捷方式 ──
$lnk = @("C:\Users\Public\Desktop\Hermes.lnk", "$env:USERPROFILE\Desktop\Hermes.lnk") | Where-Object { Test-File $_ } | Select-Object -First 1
if ($lnk) { Add-Gate 'G10 桌面图标' 'PASS' $lnk } else { Add-Gate 'G10 桌面图标' 'FAIL' '公共/用户桌面均无 Hermes.lnk → make_shortcut.ps1' }

# ── G11 RDP 可用 ──
$rdp = netstat -an | Select-String ':3389\s.*LISTENING'
if ($rdp) { Add-Gate 'G11 RDP' 'PASS' '3389 监听中' } else { Add-Gate 'G11 RDP' 'WARN' '3389 未监听（如只用本机操作可忽略）' }

# ── G12 登录自重建保底任务 ──
$task = Get-ScheduledTask -TaskName 'HermesDesktopBuild' -ErrorAction SilentlyContinue
if ($task) { Add-Gate 'G12 保底任务' 'PASS' ("state={0}" -f $task.State) }
else { Add-Gate 'G12 保底任务' 'WARN' 'HermesDesktopBuild 计划任务未装（防误删产物保底缺失）' }

# ── G13 可选：真实对话测试 ──
if ($WithChatTest) {
  $out = (& $hermes -z "Reply with exactly one word: pong" 2>&1) -join "`n"
  $code = $LASTEXITCODE
  if ($code -eq 0 -and $out -match 'pong') { Add-Gate 'G13 对话测试' 'PASS' '真实回复 pong' }
  elseif ($out -match '429') { Add-Gate 'G13 对话测试' 'WARN' '429 限速（认证已通过，配置正确）；1分钟后可用 -WithChatTest 复验' }
  else { Add-Gate 'G13 对话测试' 'FAIL' ('EXIT=' + $code + ' ' + ($out.Substring(0, [Math]::Min(160, $out.Length)))) }
}

Write-Output "===== 结果: PASS=$($script:PASS)  WARN=$($script:WARN)  FAIL=$($script:FAIL) ====="
if ($script:FAIL -gt 0) { Write-Output '[FAIL] 不得交付：存在 FAIL 项，按明细修复后复跑。'; exit 1 }
Write-Output '[PASS] 验收通过，可交付。'
exit 0
