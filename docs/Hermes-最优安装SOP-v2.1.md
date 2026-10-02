# Hermes 最优安装 SOP v2.1（2026-10-01 全网沉淀 + 2026-10-02 桌面端实战修正）
> 依据：官方 install.ps1 / install.sh（含国内镜像）+ 官方 Windows/macOS 原生指南 + 中文社区镜像 + 实战踩坑（远程 Windows 机桌面端已装通验证）。
> v2.1 修订：**桌面端真相**（`-IncludeDesktop`）、**国内镜像域名实测**、**macOS 路线**、**MSIX 自包含包**、`hermes config migrate`。

---

## 0. 一页结论（先看这里）

| 项 | 结论 |
|:---|:---|
| 最快路径（CLI） | 一行：`irm https://res1.hermesagent.org.cn/install.ps1 \| iex`（国内镜像，自动装 uv+Py3.11+Node+Git+venv+PATH+setup） |
| 官方原生 | `iex (irm https://hermes-agent.nousresearch.com/install.ps1)`（海外/直连时用） |
| **要桌面端（GUI）** | **必须** `& ([scriptblock]::Create((irm https://hermes-agent.nousresearch.com/install.ps1))) -IncludeDesktop -NonInteractive` —— **`hermes desktop` 与 pip 路线都装不出** |
| macOS | `curl -fsSL https://hermes-agent.nousresearch.com/install.sh \| bash` → `source ~/.zshrc` |
| 最低要求 | 远程机只需 PowerShell/终端可执行、有网；**无需预装 Python/Node/Git**（安装器自带 uv 引导） |
| **昨日翻车根因** | **Custom endpoint 端点必须写进 `config.yaml` 的 `model.base_url`；`OPENAI_BASE_URL` 只对 `openai-api` 生效，对 custom 无效** |
| **国内镜像铁律** | 用 `registry.npmmirror.com`（裸 `npmmirror.com` 会 `ENOTFOUND`） |
| 模型配置 | 用 `hermes model` 向导选 `Custom endpoint` → 输入 base_url / key / 模型名 / 兼容模式（Chat Completions）→ 自动写 `config.yaml` + `.env` |
| 验收 | `hermes --version` + 启动 `hermes` 发 `hi` 能正常回复（+ 桌面端能启动） |

---

## 1. 三大安装路线（按"国内、快、稳"排序）

### 路线 A（强烈推荐）：国内镜像一行
```powershell
irm https://res1.hermesagent.org.cn/install.ps1 | iex
```
- 中文社区维护，**优先走国内可直连链路**；默认精简浏览器/Chromium/WhatsApp 等外网依赖，核心安装最稳。
- 自动：装 uv、Python 3.11（免预装）、Node、PortableGit、克隆仓库、建 venv、分层 `pip install`、把 `hermes` 加进用户 PATH、跑 `hermes setup`。
- 装完**关闭当前 PowerShell，重开一个**，输入 `hermes` 验证。

### 路线 B：官方原生一行（海外/直连或国内镜像不可用时）
```powershell
iex (irm https://hermes-agent.nousresearch.com/install.ps1)
```
- 官方入口，功能最全（含浏览器工具、消息网关依赖按需安装）。
- GFW 下 GitHub 限速时，安装器有"分层回退"（`.[all]`→`[messaging,dashboard,ext]`→`[messaging]`→`.`），但**国内首选仍是路线 A**。

### 路线 C：pip 手动（可控但慢，昨天用的就是它）
```powershell
pip install hermes-agent
hermes setup
```
- 优点：不走 git clone，受 GitHub 限速影响小。
- 缺点：不自动装 Python/Node/PortableGit，**依赖远程机已有 Python≥3.11 与 pip**；缺工具时要用 `hermes doctor`/`dep_ensure` 补。
- ⚠️ **此路线只有 CLI，永远装不出桌面端**（pip 包不含 `apps/desktop`）。要 GUI 请走 §7.3 官方安装器 + `-IncludeDesktop`。
- 国内可用清华源加速：`pip install hermes-agent -i https://pypi.tuna.tsinghua.edu.cn/simple`。

### 路线 D：macOS（苹果电脑）
```bash
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
```
- 详见 §8。

> 决策规则：**远程机"什么都能装"→ 路线 A；要桌面端 → §7.3（必须 `-IncludeDesktop`）；网络一般/已装 Python → 路线 B 或 C；Mac → 路线 D；已装好要补模型 → 直接跳到第 3 节。**

---

## 2. 安装器实际做了什么（避免"卡住半天"是正常还是坏了）

顺序：引导 uv → 装 Python 3.11 → 装 Node.js 22（winget 或便携包）→ 装/复用 Git → 克隆到 `%LOCALAPPDATA%\hermes\hermes-agent` → 建 venv → 分层 `pip install` → 自动装 `.env` 里出现的消息 SDK → 设 `HERMES_GIT_BASH_PATH` → 把 `%LOCALAPPDATA%\hermes\bin` 加进用户 PATH → 跑 `hermes setup`。

安装器选项（需 scriptblock 形式传参）：
```powershell
& ([scriptblock]::Create((irm https://hermes-agent.nousresearch.com/install.ps1))) -IncludeDesktop -SkipSetup -Branch main
```
- `-IncludeDesktop`：**构建桌面端（GUI）**——默认不构建，只有 CLI。要桌面端必加。
- `-NonInteractive`（别名 `-SkipSetup`）：跳过 setup 向导（模型要单独配时用它，走第 3 节）。
- `-NoVenv`：跳过 venv（自己管 Python 才用，一般不用）。
- `-HermesHome` / `-InstallDir`：自定义数据/代码目录（默认都进 `%LOCALAPPDATA%\hermes`，**不在 C 盘用户文档区**）。
- `-SkipBrowser` / `-SkipComputerUse`：跳过浏览器内核 / computer-use，提速。
- `-Manifest` / `-ShowResolvedPaths`：打印阶段清单 / 解析出的路径（排障用）。

依赖懒加载（`dep_ensure`）：首次启动或检测到缺失时才装 Node/ffmpeg/ripgrep 等，缺了会提示 `this feature needs <dep>`，**不影响核心 CLI 对话**。

---

## 3. 模型/端点配置（★ 昨日翻车核心，务必照做）

### 3.1 铁律（血泪教训）
- **Custom endpoint（OpenAI 兼容）的端点与 key 写到 `~/.hermes/config.yaml` 的 `model` 块，不是 `.env`。**
- `OPENAI_BASE_URL` **只对 `provider: openai-api` 生效**（即官方 OpenAI 直连）。对 custom 端点无效。
- 旧文档里的 `OPENAI_BASE_URL`/`LLM_MODEL` 写 `.env` 的写法在 0.19.x 起对 custom 已失效，下次 `hermes setup`/迁移会自动清理陈旧项。

### 3.2 推荐：向导一步到位
```powershell
hermes model
```
1. 选 **Custom endpoint (self-hosted / VLLM / etc.)**（编号 0）
2. 依次输入：
   - API base URL：`https://api.agnes-ai.cn/v1`（或你的 OpenAI 兼容端点）
   - API key：你的 key（**不要在聊天里回显明文**）
   - Model name：如 `agnes-2.0-flash`
   - **API 兼容模式：选 Chat Completions（标准 OpenAI 兼容）**
3. 向导会自动把 **key 写进 `~/.hermes/.env`、端点+模型写进 `~/.hermes/config.yaml`**，无需手改文件。

### 3.3 手动（不想跑向导时）
编辑 `~/.hermes/config.yaml`：
```yaml
model:
  provider: custom
  default: agnes-2.0-flash
  base_url: https://api.agnes-ai.cn/v1
  api_mode: chat_completions
  api_key: <你的key或留空走env>
```
或在 `.env` 放 key：
```
OPENAI_API_KEY=<你的key>
```
> key 放 `.env` 也行（向导就是这么写的）；**但 base_url 一定在 config.yaml**。

### 3.4 会话内切换
```
/model custom:agnes-2.0-flash     # 当前 custom 端点切模型
/model openai:gpt-4o              # 切回某内置 provider
```

---

## 4. 验收清单（逐项 ✅/❌，缺一项=没装好）

1. `hermes --version` 输出版本号（如 `Hermes Agent v0.19.x`）✅
2. 新终端能直接敲 `hermes`（PATH 生效）✅
3. 启动 `hermes` / `hermes --tui`，发 `hi` 收到正常回复（无 401/403/context 报错）✅
4. `hermes doctor` 无致命项 ✅
5. 截一张 `hi` 对话回复图存档 ✅

常见报错定位：
| 现象 | 原因 | 处置 |
|:---|:---|:---|
| `no API key` / provider not found | key 没进 `.env` 或端点没进 `config.yaml` | 重跑 `hermes model` 向导；确认 base_url 在 config.yaml |
| 401 Unauthorized | key 错/过期 | 核对 `.env` 的 key |
| 连不上端点 | base_url 写错或写成 `OPENAI_BASE_URL` 进 .env | 按 3.1 把端点写进 config.yaml |
| context length 报错 | 模型上下文 <64K | 换更大上下文的模型 |
| `hermes` 找不到 | 没重开终端 / PATH 没刷新 | 重开 PowerShell，或手动把 `%LOCALAPPDATA%\hermes\bin` 加入用户 PATH |

---

## 5. 远控（向日葵/AweSun）专用注意
- 远控窗口标题 = 识别码；本机 `E:\Hermes专用工作区\gui.py` 走 ctypes 键鼠/窗口/剪贴板 + 免聚焦截图。
- 剪贴板本机→远程不推送时：**改用直接键入 + ntfy base64 中转**（详见技能 `sunlogin-remote-install` 与 references `03-远控坑与应对.md`）。
- 装前截图确认行内容，**不盲按回车**。

---

## 6. 与旧 SOP 的差异（修订点）
**v2（2026-10-01）**
1. 最快路径改为**国内镜像 `install.ps1`（路线 A）**，不再首选"npmmirror 装 Python + 清华 pip"（后者降级为路线 C 备选）。
2. 明确 **Custom endpoint 端点写 `config.yaml`，`OPENAI_BASE_URL` 对 custom 无效**（昨日根因）。
3. 明确安装器"依赖懒加载"——缺 Node/ffmpeg 不阻断核心对话。
4. 验收加 `hermes doctor` 与 5 项清单。

**v2.1（2026-10-02，桌面端实战修正）**
5. **纠正桌面端认知**：`hermes desktop` 与 pip 路线**都装不出桌面端**；唯一正解 = 官方 `install.ps1` + `-IncludeDesktop`（§7.3）。
6. 桌面端坑从 3 个扩到 **5 个**（新增：漏 `-IncludeDesktop`、GitHub 二进制源不通），并给出成功标志四行（§7.3a）。
7. **国内镜像域名实测**：`registry.npmmirror.com` ✅ / 裸 `npmmirror.com` ❌（ENOTFOUND）；Electron 二进制必须走镜像。
8. 新增 **§8 macOS 路线**（install.sh / SSH 远程 / DMG / 专属避坑）。
9. 补充官方形态：**MSIX/App Installer（Win11 22H2+）**、`Hermes-Setup.exe`、macOS DMG。
10. 补 `hermes config check` → `hermes config migrate`（升级后配置迁移）。

---

## 7. 多机配置 / 安装路径 / 桌面端（速查，详见团队技能 references/04）

### 7.1 不同电脑环境要求
- **Win10/11 原生即可**（无需 WSL/Docker）；非管理员可装；**可不预装** Python/Node/Git（安装器自带 uv 引导）。
- 预留 ≥1–2GB 磁盘；数据默认 `%LOCALAPPDATA%\hermes`，配置默认 `~\.hermes`。
- 要 dashboard 内嵌终端 → 上 WSL2；纯 CLI/TUI/网关/MCP/本地 Ollama 原生全可用。

### 7.2 安装路径
| 布局 | 代码 | 数据/配置 | hermes 命令 |
|:---|:---|:---|:---|
| 默认 | `%LOCALAPPDATA%\hermes\hermes-agent` | `~\.hermes\` | `%LOCALAPPDATA%\hermes\bin`（加用户 PATH） |
| 自定义 | `-InstallDir` | `-HermesHome` | 随安装器 |
| pip 手动 | `D:\Hermes\Python\...\site-packages` | `~\.hermes\` | `D:\Hermes\Python\Scripts\hermes.exe` |

**配置永远在**：`~/.hermes/config.yaml`（端点+模型，`model.base_url` 在这）+ `~/.hermes/.env`（key）。

### 7.3 桌面端（GUI）★ 2026-10-02 实战修正
- 桌面端与 CLI **共用** `%LOCALAPPDATA%\hermes\hermes-agent`（代码）与配置目录，不用各装一份。
- ❌ **已证伪**：`hermes desktop` 报 `Desktop GUI source not found`；pip 包**不含** `apps/desktop`，永远装不出。
- ✅ **唯一正解**：
  ```powershell
  & ([scriptblock]::Create((irm https://hermes-agent.nousresearch.com/install.ps1))) -IncludeDesktop -NonInteractive
  ```
- 官方其它形态：Windows **MSIX/App Installer**（需 Win11 22H2+，自包含免编译）、`Hermes-Setup.exe`（引导装源码）；macOS 用 **DMG** 拖进 Applications（老机型慎用）。
- 装桌面端前先设国内镜像（否则 Electron 拉不动）：`npm_config_registry` / `ELECTRON_MIRROR` / `ELECTRON_BUILDER_BINARIES_MIRROR` → 全用 `https://registry.npmmirror.com/...`（详见 §7.3a）。

### ⚠️ 7.3a 桌面端"装不上"的 5 个坑（2026-10-02 远程机实测装通）
| 坑 | 现象 | 根因 | 解法 |
|:---|:---|:---|:---|
| **1. pip 装 Hermes 没有桌面端源码** | `hermes desktop` 报 `Desktop GUI source not found: ...\site-packages\apps\desktop` | pip 包不带 `apps/desktop` 目录 | 改走官方 install.ps1 + `-IncludeDesktop`，**别用 pip 装完再补桌面端** |
| **2. 漏 `-IncludeDesktop`** | 装完只有 CLI，无 `Hermes.exe` | 官方安装器**默认不构建桌面端** | 重跑并显式加 `-IncludeDesktop` |
| **3. 镜像域名解析失败** | `npm error RequestError: getaddrinfo ENOTFOUND npmmirror.com` | 裸 `npmmirror.com` 解析不了 | 一律用 `registry.npmmirror.com`（含 `/-/binary/electron/`、`/-/binary/electron-builder-binaries/`） |
| **4. GitHub 二进制源不通** | `objects.githubusercontent.com` 超时，Electron/winCodeSign/nsis 下不来 | GitHub 发布资产被墙 | 设 `ELECTRON_MIRROR` + `ELECTRON_BUILDER_BINARIES_MIRROR` 走国内镜像 |
| **5. 残留目录 / 端口冲突** | `...hermes-agent exists and is not a Hermes git checkout`；或卡 90% / `ECONNREFUSED 8787` | 旧 pip 或"Install locally"残留在位；多实例抢 8787 | 残留：`Move-Item` 改名挪开；端口：`Get-Process \| Where Name -like "*hermes*","*electron*" \| Stop-Process -Force` 后单实例启动 |
| （附）node 不在 PATH | 桌面端起 Electron 报 vite/motion-utils 解析不到 | 安装器未把 node 加进 PATH | `where.exe node` 查到路径 → 加用户 PATH + 当前会话 `$env:Path` |

**成功标志（四行齐了才算成）**：
```
[OK] app products and hermes command ready
[OK] hermes command installed at %LOCALAPPDATA%\hermes\bin
[OK] Desktop ready: ...\apps\desktop\release\win-unpacked\Hermes.exe
[OK] Shortcut created: ...\Desktop\Hermes.lnk
```

**官方 .exe 安装器下载（国内加速，备选路线）**：
```powershell
Invoke-WebRequest -Uri "https://gh-proxy.com/https://github.com/NousResearch/hermes-agent/releases/latest/download/Hermes-Setup.exe" -OutFile "D:\Hermes\Hermes-Setup.exe"
Start-Process -FilePath "D:\Hermes\Hermes-Setup.exe" -ArgumentList "/S" -Wait
```

### 7.4 不同电脑"一键装"最小命令
```powershell
# 国内远程机（只装 CLI，首选）
irm https://res1.hermesagent.org.cn/install.ps1 | iex
# 重开终端后：
hermes model            # 配 Custom endpoint
hermes                  # 发 hi 验收

# 国内远程机（要桌面端 GUI）★
$env:npm_config_registry='https://registry.npmmirror.com'
$env:ELECTRON_MIRROR='https://registry.npmmirror.com/-/binary/electron/'
$env:ELECTRON_BUILDER_BINARIES_MIRROR='https://registry.npmmirror.com/-/binary/electron-builder-binaries/'
& ([scriptblock]::Create((irm https://hermes-agent.nousresearch.com/install.ps1))) -IncludeDesktop -NonInteractive

# 海外/直连
iex (irm https://hermes-agent.nousresearch.com/install.ps1)
```

### 7.5 故障速查（增补）
| 现象 | 解决 |
|:---|:---|
| 中文/Unicode 崩溃 | 安装器已设 CP_UTF8；异常设 `PYTHONUTF8=1` |
| `not a Hermes git checkout` | 直连版 InstallDir 已存在 → `Move-Item` 改名挪开，或换 `-InstallDir` |
| 缺 Node/ffmpeg 提示 | 不影响核心对话；要浏览器/语音再装 |
| `hermes desktop` 报 source not found | pip 无桌面端源码 → 换官方 install.ps1 + `-IncludeDesktop`（§7.3） |
| 桌面端卡 90% / 8787 拒绝连接 | 多实例抢端口 → 杀 `*hermes*`/`*electron*` 后单实例启动 |
| `ENOTFOUND npmmirror.com` | 镜像用裸域名 → 换 `registry.npmmirror.com` |
| 更新后 provider 丢失 | `hermes config check` → `hermes config migrate` |

---

## 8. macOS（苹果电脑）安装路线

### 8.1 一行安装（CLI）
```bash
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
source ~/.zshrc && hermes
```
- 前置：`git`、`curl`、`tar`、`shasum`（macOS 自带后三者）；无 git 先 `xcode-select --install`。
- Python 要求 **`>=3.14,<3.15`**（PM 自动准备，无需手动装）。
- 目录：代码 `~/.hermes/hermes-agent/`、命令 `~/.local/bin/hermes`、数据 `~/.hermes/`（`HERMES_HOME` 可覆盖）。

### 8.2 局域网 SSH 远程安装（推荐，比远控稳）
Mac 开「系统设置 → 通用 → 共享 → 远程登录」，然后从局域网另一台机器：
```bash
ssh <mac用户>@192.168.1.9 'curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash'
```

### 8.3 桌面端（DMG）
官网下 **DMG** → 拖进 `Applications` 启动。⚠️ 受 macOS 版本 + CPU 架构限制；**老机型（如 2012 款 MacBookPro9,2，最高 Catalina）大概率不支持，直接走 CLI**。

### 8.4 macOS 专属避坑
| 坑 | 解法 |
|:---|:---|
| shell 是 zsh | `source ~/.zshrc`（不是 `.bashrc`） |
| `hermes: command not found` | `echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc && source ~/.zshrc` |
| Gatekeeper 拦截 DMG | 右键 → 打开；或 隐私与安全性 → 仍要打开 |
| 国内 GitHub 慢 | 设 shell 代理；或确认镜像站是否提供 `install.sh`（**待验证**） |
| 更新后配置丢失 | `hermes config check` → `hermes config migrate` |

> 详见团队技能 `references/06-macOS安装路线.md`。
