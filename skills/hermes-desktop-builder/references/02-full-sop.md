# 02 · 端到端 SOP（固定流程，命令原文）

> 前提：远程 Windows 机器，SSH 22 可达，知道 Administrator 密码。
> 全程不需要 GitHub；只需 npmmirror 与 HTTPS 可达。

## Phase 1 · 通道建立（本机操作）

```bash
# 一次性：确认 venv 有 paramiko（本机已有 E:\Hermes专用工作区\venv_ssh）
# 技能自带脱敏驱动：scripts/ssh_exec.py，凭据走环境变量
export SS_HOST=<服务器IP> SS_USER=Administrator SS_PASS='<密码>'
python ssh_exec.py run "hostname && whoami"
```

经验：
- 多行 PS 脚本 → 本地写好 .ps1 → `ssh_exec.py putrun x.ps1`（SFTP 传上去 -File 执行）
- 禁止往 `powershell -Command -` stdin 写脚本（paramiko 报 OSError: File not open for writing）

## Phase 2 · CLI 安装（若服务器还没有 hermes）

服务器 PowerShell 执行：

```powershell
irm https://res1.hermesagent.org.cn/install.ps1 | iex
```

自动装 uv + Python3.11 + Node（放 `%LOCALAPPDATA%\hermes\node`）+ Git（npmmirror 源）+ 仓库源码到 `%LOCALAPPDATA%\hermes\hermes-agent`。

验收：新开终端 `hermes --version`。

## Phase 3 · 桌面端首次构建（~10 分钟）

### 3.1 打补丁

```bash
python ssh_exec.py put prepare-packaging-tools.mjs "C:/Users/Administrator/AppData/Local/hermes/hermes-agent/apps/desktop/scripts/prepare-packaging-tools.mjs"
```

### 3.2 传构建脚本

```bash
python ssh_exec.py put pack_run.ps1 "C:/Users/Administrator/pack_run.ps1"
```

pack_run.ps1 做的事：设 npmmirror 环境变量（无 DANGEROUSLY_ALLOW_HTTP）→ 清 `build\packager\win32-x64` → `npm run pack` 全量 → 写 `%LOCALAPPDATA%\hermes\pack.log`（含 PACK_EXIT / ELAPSED_S / HERMES_EXE_EXISTS）。

### 3.3 跑构建（二选一）

**方式 A · 计划任务（最稳，SSH 断了照跑）**：

```powershell
schtasks /Create /TN HermesPack /TR "powershell -ExecutionPolicy Bypass -File C:\Users\Administrator\pack_run.ps1" /SC ONCE /ST 23:59 /F
schtasks /Run /TN HermesPack
```

**方式 B · 本机后台任务直跑**（build_once.py 模式：exec_command 前台跑脚本、脚本内部 npm，本机 Bash 工具 run_in_background=true 挂住等待）。

### 3.4 轮询验收

```bash
python ssh_exec.py run "Get-Content $env:LOCALAPPDATA\hermes\pack.log -Tail 30"
```

成功标志（缺一不可）：

```
PACK_EXIT=0
ELAPSED_S=<几百秒>
WIN_UNPACKED_EXISTS=True
HERMES_EXE_EXISTS=True
```

产物：`%LOCALAPPDATA%\hermes\hermes-agent\apps\desktop\release\win-unpacked\Hermes.exe`（~204MB）。

### 3.5 启动冒烟

```powershell
$p = Start-Process -FilePath <exe路径> -PassThru; Start-Sleep 6
Get-Process -Id $p.Id   # 活着即通过；WS ~130MB 正常
Stop-Process -Id $p.Id
```

## Phase 4 · 后续重打提速（~62 秒）

改过补丁/打包配置后：

```bash
python ssh_exec.py put pack_builder_only.ps1 "C:/Users/Administrator/pack_builder_only.ps1"
python ssh_exec.py run "powershell -ExecutionPolicy Bypass -File C:\Users\Administrator\pack_builder_only.ps1" 300
```

看 `pack-builder.log`，成功标志 `BUILDER_EXIT=0` + `HERMES_EXE_EXISTS=True` + `ELAPSED_S≈60`。

## Phase 5 · 落地三件套

### 5.1 公共桌面快捷方式

```bash
python ssh_exec.py putrun make_shortcut.ps1
# 输出 LNK_CREATED=True；提醒用户桌面 F5 刷新
```

### 5.2 RDP 打通（用户嫌网页控制台难用时）

```bash
python ssh_exec.py putrun fix_rdp_fw.ps1
```

然后教用户：**Win+R → mstsc → 输服务器 IP → Administrator/密码**；连接时"证书不受信任"点"是"；可在 mstsc"显示选项→另存为"保存 .rdp 文件实现一键直连。

### 5.3 登录自重建保底任务

```bash
python ssh_exec.py put pack_builder_only.ps1 "C:/Users/Administrator/pack_builder_only.ps1"
python ssh_exec.py putrun install_build_task.ps1
# 输出 TASK_INSTALLED state=Ready
```

## Phase 6 · 模型配置与总验收

**先判定配置主目录**（两代不同）：

```powershell
& "$root\venv\Scripts\python.exe" -I -c "import hermes_cli.config as c; cands=[n for n in dir(c) if 'home' in n.lower()]; h=getattr(c,cands[0]); print(h() if callable(h) else h)"
# git 新版（2026.9+）输出 %LOCALAPPDATA%\hermes；0.19.0 pip 版是 ~\.hermes —— 写错位置配置静默不生效
```

### 路线 A：git 新版 CLI（官方 install.ps1 装的）→ 直接写 config.yaml（推荐，可全自动）

config.yaml（放解析出的 home 下）：

```yaml
model:
  default: agnes-3.0-flash
  provider: agnes
providers:
  agnes:
    name: Agnes
    api: https://apihub.agnes-ai.com/v1
    key_env: AGNES_API_KEY          # 引用 .env 里的变量，key 不进 yaml
    transport: chat_completions
    default_model: agnes-3.0-flash
    context_length: 256000
```

同目录 `.env`：`AGNES_API_KEY=sk-...`（多 key 就 `AGNES_API_KEY_2..N` 备用）。

非交互验证（不进 TUI）：

```powershell
& "$root\venv\Scripts\hermes.exe" status        # 应显示 Model/Provider/Providers 三行
& "$root\venv\Scripts\hermes.exe" -z "Reply with exactly one word: pong"   # EXIT=0 且输出 pong 即通
```

### 路线 B：0.19.0 pip 版 → 只能交互向导

```powershell
hermes model
# 向导：Custom endpoint → 端点 https://<host>/v1 → 兼容模式选 Chat Completions → 粘 key → 选模型与上下文
```

- 0.19.0 手写 config.yaml 不生效（schema 旧）；OPENAI_BASE_URL 对 custom provider 无效

### Agnes 免费档限速注意

1 req/min/key：CLI `-z` 内部自动重试 3 次会连续耗光同一窗口，报 429 就换下一个 key（.env 换主位）或等 60s 再试。429≠401——429 说明认证已通过，配置是对的。

总验收 5 项：

1. `hermes --version` 有版本
2. 新终端 `hermes` 能进交互
3. 发 `hi` 有回复（模型通了）
4. `hermes doctor` 无致命项
5. 双击桌面 Hermes 图标能开 GUI

## 交付清单

- ✅ `hermes --version` 输出截图/文本
- ✅ `release\win-unpacked\Hermes.exe` 存在 + 大小 + 启动进程证据
- ✅ 桌面快捷方式 `C:\Users\Public\Desktop\Hermes.lnk` 存在
- ✅ RDPACTIVE_RULES≥1 且 PORT_LISTEN=True
- ✅ 发 hi 回复截图（GUI 需求另加桌面端截图）
- ✅ 模型配置摘要（端点+模型名，**不含明文 key**）
