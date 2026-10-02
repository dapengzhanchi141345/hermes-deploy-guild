# 06 · 苹果电脑（macOS）安装 Hermes 路线

> 适用：用户的 Mac（本机操作，或同局域网远程 SSH）。
> 依据：官方安装文档 zh-Hans（2026-10 核对）+ Windows 侧实战经验外推。
> ⚠️ 标注「待实测」的条目为按官方文档推理、尚未在真机复现，首次执行请以实际输出为准。

---

## 一、一分钟决策

| 场景 | 走哪条 |
|:---|:---|
| Mac 能开终端、有管理员密码 | **路线 1：官方一行 `install.sh`**（推荐） |
| 想同局域网从别的电脑远程装 | **路线 2：SSH 远程安装**（比远控稳得多） |
| 只想用图形界面、不碰终端 | **路线 3：DMG 桌面包**（⚠️ 受 macOS 版本/架构限制，见 §四） |
| Mac 是 2012 年前后老机型 | **优先 CLI**，桌面端大概率不支持 |

---

## 二、路线 1：官方一行安装（CLI，最稳）

```bash
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
source ~/.zshrc          # 或 source ~/.bashrc
hermes                   # 验收：能启动
```

**它会做什么**：克隆仓库 → 由 PM 准备 Python 3.14、Node.js、npm、ripgrep、FFmpeg 与 Python 依赖。

**前置条件**：`git`、`curl`、`tar`、`shasum`（SHA-256）。
- macOS 自带 `curl` / `tar` / `shasum`；`git` 缺失时先装：
  ```bash
  xcode-select --install                       # 最省事（弹窗点安装）
  # 或：brew install git
  ```
- Python 版本要求 **`>=3.14,<3.15`**（PM 会自行准备三代环境；不必手动装）。

**默认目录（POSIX 与 Windows 不同，别混）**：

| 项 | 路径 |
|:---|:---|
| 代码 | `~/.hermes/hermes-agent/` |
| 命令 | `~/.local/bin/hermes`（包装器） |
| 数据/配置 | `~/.hermes/` |
| 覆盖数据目录 | `HERMES_HOME=<path>` |
| 覆盖源码目录 | `--dir <path>` |

**验收**：
```bash
hermes --version
hermes doctor
hermes            # 发 hi 看回复
```

---

## 三、路线 2：局域网 SSH 远程安装（推荐给"隔着一台电脑装"）

比向日葵远控稳 10 倍——没有剪贴板失效、没有丢字、没有视频帧滞后。

**Mac 侧开启**：系统设置 → 通用 → 共享 → **远程登录（Remote Login）** 打开，记下 `用户@IP`。

**从局域网另一台机器执行**：
```bash
ssh <mac用户>@192.168.1.9
# 登录后，直接在 Mac 上跑官方一行
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
source ~/.zshrc && hermes --version
```

**非交互式一把梭**（一条命令装完）：
```bash
ssh <mac用户>@192.168.1.9 'curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash -s -- --non-interactive'
```
> `--non-interactive` 参数名以 `install.sh --help` 实际输出为准（待实测）；不支持时先 `bash -s -- --help` 看选项。

**内网 + 国内网络**：Mac 若走代理才能连 GitHub，先给 shell 设：
```bash
export https_proxy=http://<proxy_host>:<port> http_proxy=http://<proxy_host>:<port>
```

---

## 四、路线 3：桌面端 GUI（DMG）

官方桌面端分发方式：
- **macOS：DMG 包** —— 下载后把 App 拖进 `Applications` 启动；自动更新走"含已签名应用的 ZIP"。
- **Windows：MSIX / App Installer** —— 自包含包，要求 **Windows 11 22H2 或更新**，首启无需克隆源码/编译运行时（与源码脚本完全不同的一条路）。
- Windows `Hermes-Setup.exe` —— 引导安装程序，本质是"下载并配置源码"。

> ⚠️ **老 Mac 注意**：桌面端 DMG 对 **macOS 版本**与 **CPU 架构（Intel / Apple Silicon）** 有要求。
> 例：MacBookPro9,2（2012 款，Ivy Bridge）最高只能到 macOS 10.15 Catalina，新版 DMG 很可能不支持。
> **决策**：老机型直接走 CLI（§二）；桌面端先下 DMG 试装，失败就退回 CLI，不要死磕。

---

## 五、Mac 上的模型配置（与 Windows 完全一致）

```bash
hermes model          # 选 Custom endpoint (0)
#   base_url : https://api.agnes-ai.cn/v1
#   api key  : <你的 key>
#   model    : agnes-2.0-flash
#   兼容模式 : Chat Completions
hermes config set ... # 单改某项
```

- 端点/模型 → `~/.hermes/config.yaml` 的 `model.base_url`（**铁律：custom 端点不认 `OPENAI_BASE_URL`**）
- key → `~/.hermes/.env` 的 `OPENAI_API_KEY`
- 会话内切换：`/model custom:agnes-2.0-flash`

---

## 六、macOS 专属避坑

| 坑 | 现象 | 解法 |
|:---|:---|:---|
| shell 是 zsh | 改完配置没生效 | `source ~/.zshrc`（不是 `.bashrc`） |
| 命令找不到 | `hermes: command not found` | `~/.local/bin` 不在 PATH → `echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc && source ~/.zshrc` |
| 无 git | 安装脚本前置失败 | `xcode-select --install` 或 `brew install git` |
| Gatekeeper 拦截 | 打开 DMG 里 App 提示"来自身份不明的开发者" | 右键 → 打开；或 系统设置 → 隐私与安全性 → 仍要打开 |
| 老机型架构 | Intel 装 Apple Silicon 包报错 | 下 **Intel/x86_64** 版本；或退回 CLI |
| 国内 GitHub 慢 | clone 卡住 | 设 shell 代理；或改用国内镜像的 `install.sh`（若镜像站提供，**需先验证 URL 可达**） |
| 更新后配置丢失 | 升级后 provider 没了 | `hermes config check` → `hermes config migrate` |

---

## 七、验收 5 项（与 Windows 同标准）

1. `hermes --version` 出版本号 ✅
2. 新终端直接 `hermes` 可启动 ✅
3. 发 `hi` 正常回复（无 401/403/context）✅
4. `hermes doctor` 无致命项 ✅
5. 截图 `hi` 对话存档 ✅

---

## 八、远程装 Mac 的通道对比

| 通道 | 可靠性 | 适用 |
|:---|:---|:---|
| **SSH（局域网）** | ★★★★★ | 首选。Mac 开"远程登录"即可，纯文本、可脚本化 |
| 屏幕共享 / VNC | ★★★☆ | Mac 原生 VNC 可脚本化程度低，但比向日葵稳 |
| 向日葵远控 | ★★☆ | 剪贴板慢一拍、丢字、帧滞后 → 走 `references/03` / `05` 的通道策略 |
