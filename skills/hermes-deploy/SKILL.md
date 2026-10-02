---
name: hermes-deploy
description: 在远程 Windows / macOS 电脑（尤其向日葵/AweSun 远控）上快速安装并配置 Hermes（hermes-agent）智能体的完整作战手册：国内镜像极速安装路线、CLI 与桌面端（GUI）分离安装法、远控 GUI 自动化通道、hermes 模型配置向导、故障速查与验收清单。触发词：装Hermes、远程装hermes-agent、向日葵远程装、hermes桌面端装不上、hermes配key、hermes no API key、hermes desktop、远程部署智能体。
---

# Hermes 远程极速部署手册（v1.1）

「Hermes速装团」的作战手册。目标：**在远程电脑（Windows / macOS）上把 Hermes 装好、配好、跑通，桌面端也装上，且全程可验证。**

## 何时用

- 用户要求在某台（远程）Windows / macOS 电脑上安装 Hermes / hermes-agent
- **Hermes CLI 装好了，但桌面端（GUI）一直装不上 / 卡 90% / 报 `Desktop GUI source not found`**
- 需要隔着向日葵（AweSun）远控窗口自动操作远程电脑
- Hermes 装好了但报 `no API key` / 连不上模型 / 命令找不到
- 需要用国内网络最快速度装 Python 与 pip 包

## 目录

```
skills/hermes-deploy/
├── SKILL.md
├── scripts/
│   ├── gui.py          # 远控 GUI 自动化（ctypes，标准库；截图需 Pillow）
│   └── cropregion.py   # 屏幕区域截取放大（需 Pillow）
└── references/
    ├── 01-国内快速安装路线.md
    ├── 02-Hermes配置指南.md
    ├── 03-远控坑与应对.md
    ├── 04-多机速查与桌面端手册.md      # 环境/路径/故障速查表
    ├── 05-桌面端安装实战与国内镜像.md  # ★ 桌面端装不上专治
    └── 06-macOS安装路线.md             # ★ 苹果电脑专章
```

## 五步主线（记这五步就够）

| 步 | 名称 | 关键产出 |
|----|------|---------|
| 1 | 环境侦察 | 环境快照表 + 路线建议（有无 Python、镜像通不通、残留目录） |
| 2 | 装 CLI | Windows：镜像一行 / 官方 install.ps1；macOS：`install.sh` |
| 3 | 装桌面端 | **必须走官方安装器 + `-IncludeDesktop`**（见下方专章） |
| 4 | 模型配置 | `hermes model` 向导配 provider + 写 `~/.hermes/.env` |
| 5 | 验收 | `hermes --version` + 发 `hi` 有回复 + 桌面端能启动 + 截图 |

## 一句话速查

```powershell
# ===== A. Windows 装 CLI（二选一）=====
irm https://res1.hermesagent.org.cn/install.ps1 | iex          # 国内镜像（首选，最快）
& ([scriptblock]::Create((irm https://hermes-agent.nousresearch.com/install.ps1))) -NonInteractive  # 官方原生

# ===== B. Windows 装【桌面端】GUI（唯一正解，必须带 -IncludeDesktop）=====
& ([scriptblock]::Create((irm https://hermes-agent.nousresearch.com/install.ps1))) -IncludeDesktop -NonInteractive
# 产物：%LOCALAPPDATA%\hermes\hermes-agent\apps\desktop\release\win-unpacked\Hermes.exe
#       + 桌面/开始菜单 Hermes.lnk

# ===== C. pip 手动路线（仅 CLI；★ 永远装不出桌面端）=====
python -m pip install hermes-agent -i https://pypi.tuna.tsinghua.edu.cn/simple
```

```bash
# ===== macOS / Linux / WSL2（一行）=====
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
source ~/.zshrc && hermes        # 代码 ~/.hermes/hermes-agent/，命令 ~/.local/bin/hermes
```

```powershell
# ===== 国内镜像环境变量（装桌面端前必设，否则 Electron 拉不动）=====
$reg='https://registry.npmmirror.com'
$env:npm_config_registry=$reg
$env:ELECTRON_MIRROR='https://registry.npmmirror.com/-/binary/electron/'
$env:ELECTRON_BUILDER_BINARIES_MIRROR='https://registry.npmmirror.com/-/binary/electron-builder-binaries/'
```

## ★ 桌面端（GUI）专章：三个必踩坑

> 结论先行：**桌面端只能由官方 `install.ps1` 带 `-IncludeDesktop` 装出来**。`hermes desktop` 与 pip 路线都装不出。

| 坑 | 现象 | 解法 |
|:---|:---|:---|
| **pip 版无桌面端源码** | `hermes desktop` 报 `Desktop GUI source not found ...\site-packages\apps\desktop` | pip 包不含 `apps/desktop`，**换官方安装器**，别在 pip 上死磕 |
| **漏 `-IncludeDesktop`** | 装完只有 CLI，没有 Hermes.exe | 安装器**默认不构建桌面端**，重跑并显式加 `-IncludeDesktop` |
| **镜像域名解析失败** | `getaddrinfo ENOTFOUND npmmirror.com` / Electron 卡住 | 用 `registry.npmmirror.com`（**不是**裸 `npmmirror.com`），并设 `ELECTRON_*` 镜像 |
| **残留目录拦路** | `...hermes-agent exists and is not a Hermes git checkout` | `Move-Item` 改名挪开再重跑 |
| **多实例抢 8787** | 卡 "Waiting for Hermes backend" / `ECONNREFUSED 8787` | 杀光 `*hermes*`+`*electron*` 进程，单实例启动 |

成功标志（四行齐了才算成）：
```
[OK] app products and hermes command ready
[OK] hermes command installed at %LOCALAPPDATA%\hermes\bin
[OK] Desktop ready: ...\apps\desktop\release\win-unpacked\Hermes.exe
[OK] Shortcut created: ...\Desktop\Hermes.lnk
```

## 远控自动化：gui.py

```bash
# 找远控窗口（标题 = 识别码，形如 123456789）
python scripts/gui.py list
# 免聚焦截图 → $GUI_SHOT_DIR/fs.png（默认：脚本目录）
python scripts/gui.py shot
# 两步粘贴（推荐，避免剪贴板滞后一拍）
python scripts/gui.py setc cmd.txt && sleep 4 && python scripts/gui.py pastein <识别码>
# 直接键入（剪贴板失效时；远程 IME 需先切英文）
python scripts/gui.py ft <识别码> cmd.txt enter
# 清行 / 打开运行框 / 强制刷帧
python scripts/gui.py fkN <识别码> backspace 60
python scripts/gui.py fhk <识别码> win+r
python scripts/gui.py wiggle 300 300
# 区域放大看提示符/向导文字
python scripts/cropregion.py 70 60 370 330 3.5
```

截图输出目录用环境变量指定：`GUI_SHOT_DIR=/path/to/shots`。

## 三条输入通道（按可靠性择优）

1. **ntfy 中转（长脚本首选）**：本机 `curl -X PUT --data-binary @x.ps1 https://ntfy.sh/<topic>` → 远程一句 `iex (irm https://ntfy.sh/<topic>/raw?poll=1)`。`/raw` 会把换行折成空格，**脚本必须压成单行**（`;` 分隔、勿用 `#` 注释）；回传读 `/json?poll=1`（保留换行）。每次换新 topic。
2. **剪贴板**：默认。但向日葵剪贴板可能慢一拍甚至单向失效 → **"设剪贴板 → 等 3-5 秒 → 粘贴 → 截图确认 → 才回车"**，绝不盲按。
3. **直接键入**：前两者都废时用。先切远程 IME 到英文，再 `ft` 逐字键入；约 400 字符以内可靠。

## 铁律（违反必踩坑）

- **不盲按回车**：远控视频帧常滞后 1-2 个动作，必须先截图确认行内容。
- **桌面端 ≠ CLI 的次生功能**：想 GUI 就用官方安装器 `-IncludeDesktop`；pip 路线无解。
- **镜像域名只认能解析的**：`registry.npmmirror.com` ✅ / 裸 `npmmirror.com` ❌（ENOTFOUND）。
- **命令写文件走通道**：远程中文 IME 会把空格变连字符、英文变中文（`FileSystem`→`文件系统`），绝不逐字盲打长命令。
- **API Key 必须放 `~/.hermes/.env`**；只写 `config.yaml` 会报 `no API key`。
- **Custom 端点的 `base_url` 必须写 `~/.hermes/config.yaml` 的 `model.base_url`**；`OPENAI_BASE_URL` 只对 `provider: openai-api` 生效，对 custom **无效**。
- **必须用 `hermes model` 向导**；手写 `config.yaml` 因 schema 版本不匹配常失效（回退内置默认并 401）。
- **不要 pip 装完再补桌面端**；要 GUI 就一开始走 install.ps1。
- **装到 D 盘自建目录**（默认 `D:\Hermes`），除非用户明确要求 C 盘。
- **焦点是丢字真凶**：本机其它窗口（尤其 python 控制台）抢焦点会导致按键只进一半 → 输字前校验 `GetForegroundWindow()==hwnd`，每 15 字符重确认，脚本开头隐藏自身控制台。
- **绝不明文回显用户 API Key**。

## 故障速查（高频）

| 现象 | 处置 |
|:---|:---|
| `no API key` / provider not found | 重跑 `hermes model`；确认 `model.base_url` 在 `config.yaml` |
| 端点 404 / 连不上 | 端点被误塞进 `.env` 的 `OPENAI_BASE_URL` → 改写 `config.yaml` |
| `401` / `403` | key 错 / 无权限 → 核对 `.env` |
| context length 报错 | 换大上下文模型（256K 级） |
| `hermes` 找不到 | 重开终端；或把 `%LOCALAPPDATA%\hermes\bin`（Windows）/ `~/.local/bin`（macOS）加 PATH |
| 中文乱码 / UnicodeEncodeError | 设 `PYTHONUTF8=1`（安装器已设 CP_UTF8） |
| 更新后配置丢失 | `hermes config check` → `hermes config migrate` |
| `not a Hermes git checkout` | 残留目录 → `Move-Item` 挪开，或换 `-InstallDir` |

## 深入材料

- 安装命令与网络判定：`references/01-国内快速安装路线.md`
- 向导配置全流程与词汇：`references/02-Hermes配置指南.md`
- 向日葵远控九大坑与应对：`references/03-远控坑与应对.md`
- 多机环境 / 路径 / 故障速查表：`references/04-多机速查与桌面端手册.md`
- **桌面端装不上专治 + 国内镜像实测**：`references/05-桌面端安装实战与国内镜像.md`
- **苹果电脑（macOS）安装路线**：`references/06-macOS安装路线.md`
