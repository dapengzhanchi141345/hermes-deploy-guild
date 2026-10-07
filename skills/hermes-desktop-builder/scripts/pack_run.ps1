$ErrorActionPreference = "Continue"
$nodeDir = "$env:LOCALAPPDATA\hermes\node"
$env:PATH = "$nodeDir;" + $env:PATH
$env:ELECTRON_MIRROR = "https://registry.npmmirror.com/-/binary/electron/"
$env:ELECTRON_BUILDER_BINARIES_DOWNLOAD_OVERRIDE_URL = "https://registry.npmmirror.com/-/binary/electron-builder-binaries/"
$env:npm_config_registry = "https://registry.npmmirror.com/"
$root = "$env:LOCALAPPDATA\hermes\hermes-agent"
$d = Join-Path $root "apps\desktop"
Set-Location $d
$out = Join-Path $d "build\packager\win32-x64"
if (Test-Path $out) { Remove-Item $out -Recurse -Force; "REMOVED stale out" }
$pf = "$env:LOCALAPPDATA\hermes\pack.log"
if (Test-Path $pf) { Remove-Item $pf -Force }
"=== npm run pack (start) ===" | Out-File -FilePath $pf -Encoding utf8
$sw = [System.Diagnostics.Stopwatch]::StartNew()
npm run pack 2>&1 | Out-File -FilePath $pf -Append -Encoding utf8
$sw.Stop()
"PACK_EXIT=$LASTEXITCODE" | Out-File -FilePath $pf -Append -Encoding utf8
"ELAPSED_S=$($sw.Elapsed.TotalSeconds)" | Out-File -FilePath $pf -Append -Encoding utf8
$rel = Join-Path $d "release\win-unpacked"
"WIN_UNPACKED_EXISTS=$(Test-Path $rel)" | Out-File -FilePath $pf -Append -Encoding utf8
if (Test-Path $rel) { "HERMES_EXE_EXISTS=$(Test-Path (Join-Path $rel 'Hermes.exe'))" | Out-File -FilePath $pf -Append -Encoding utf8 }
