# Hermes速装团（Hermes Rapid Deploy Guild）

> 在远程电脑（**Windows / macOS**）上把 Hermes（hermes-agent）**装好、配好、跑通、桌面端也装上**——环境探测、镜像极速安装、模型配置、远控自动化到独立验收，全程可验证。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](#许可)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS-blue)

---

## 这是什么

一套**经过真机实战**的 Hermes 部署作战手册 + 多角色专家团配置。核心价值：把"装了一整天没装好"的坑全部前置解决。

三条最重要的经验（血泪换来，别再踩）：

1. **桌面端（GUI）不是 CLI 的次生功能**。`hermes desktop` 和 pip 路线**都装不出桌面端**（pip 包不含 `apps/desktop`）。唯一正解：官方安装器 + `-IncludeDesktop`。
2. **Custom 端点的 `base_url` 必须写在 `~/.hermes/config.yaml` 的 `model.base_url`**。`OPENAI_BASE_URL` 只对 `provider: openai-api` 生效，对 custom **无效**——这是"装好了却连不上模型"的头号原因。
3. **国内镜像只认能解析的域名**：`registry.npmmirror.com` ✅，裸 `npmmirror.com` ❌（`getaddrinfo ENOTFOUND`）。

---

## 团队构成

| 角色 | Agent ID | 名字 | 职业 | 职责 |
|------|----------|------|------|------|
| 主理人 | `hermes-deploy-guild-team-lead` | 毕速达 | 部署总监 | 任务分级、编排调度、最终汇编交付 |
| 团员 | `env-scout` | 甄探明 | 环境侦察官 | 远程环境探测与路线判定 |
| 团员 | `install-engineer` | 安立成 | 安装工程师 | Python 静默安装、镜像装 hermes-agent、配 PATH |
| 团员 | `remote-operator` | 陆远遥 | 远控操盘手 | 向日葵 GUI 自动化、三条输入通道、验证闭环 |
| 团员 | `model-configurator` | 裴准齐 | 模型配置师 | hermes model 向导、`.env`、模型选型 |
| 团员 | `acceptance-verifier` | 阎验真 | 验收官 | 独立复验、对话冒烟、证据固化 |

## 覆盖能力

1. **环境侦察** — OS/架构/PowerShell 版本、Python 与 pip 是否存在、镜像与网络连通性、磁盘与权限、残留目录检查。
2. **装 CLI** — Windows 国内镜像一行 / 官方 `install.ps1`；macOS `install.sh`；pip 手动路线（仅 CLI）。
3. **装桌面端（GUI）** — 官方 `install.ps1 -IncludeDesktop`；MSIX / DMG / Hermes-Setup.exe 形态对照；镜像三件套；残留目录与 8787 端口排障。
4. **远控自动化** — 内置 `gui.py`（纯标准库 ctypes）：窗口枚举/聚焦、键鼠注入、剪贴板读写、免聚焦截图、区域放大；三条输入通道（ntfy 中转 / 剪贴板 / 直接键入）+ 画面刷新技巧。
5. **模型配置** — `hermes model` 向导配任意 OpenAI 兼容端点，写 `~/.hermes/.env`，选模型与上下文。
6. **独立验收** — `hermes --version`、启动器核查、启动验证、`hi` 对话冒烟、桌面端启动、截图取证。

## 内置技能包

`skills/hermes-deploy/`

| 文件 | 内容 |
|:---|:---|
| `scripts/gui.py` | 远控 GUI 自动化工具（ctypes，标准库；截图需 Pillow） |
| `scripts/cropregion.py` | 屏幕区域截取并放大（看提示符/向导文字） |
| `references/01-国内快速安装路线.md` | Python + hermes-agent 最快安装路线与命令 |
| `references/02-Hermes配置指南.md` | 向导配置全流程与配置词汇 |
| `references/03-远控坑与应对.md` | 向日葵远控九大坑与应对手册 |
| `references/04-多机速查与桌面端手册.md` | 环境要求 / 安装路径 / 故障速查表（Windows + macOS） |
| `references/05-桌面端安装实战与国内镜像.md` | **桌面端装不上专治**；国内镜像实测对照；注入通道 |
| `references/06-macOS安装路线.md` | **苹果电脑专章**：install.sh / SSH 远程 / DMG / 避坑 |

## 速查：三条命令

```powershell
# A. Windows 装 CLI（国内镜像首选）
irm https://res1.hermesagent.org.cn/install.ps1 | iex

# B. Windows 装【桌面端 GUI】（唯一正解，缺 -IncludeDesktop 就只有 CLI）
& ([scriptblock]::Create((irm https://hermes-agent.nousresearch.com/install.ps1))) -IncludeDesktop -NonInteractive

# C. 模型配置（Custom endpoint：端点写 config.yaml，key 写 .env）
hermes model
```

```bash
# macOS / Linux / WSL2
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
```

## 五步主线

`1 侦察 → 2 装 CLI → 3 装桌面端 → 4 配模型 → 5 验收`（详见 `skills/hermes-deploy/SKILL.md`）

## 预设 Workflow

- **Workflow A 全新部署**：侦察 → 装 CLI → 装桌面端 → 配模型 → 验收 → 交付。
- **Workflow B 健康检查 / 故障修复**：诊断现状 → 按需补装（含桌面端）或修配置 → 复验。
- **Workflow C 仅配置模型**：只跑配置师 + 冒烟验证。

## 使用示例

- 远程电脑上一键装好 Hermes 并配好模型。
- 远程电脑 Hermes 装好了，但桌面端一直装不上，帮我装。
- 远程 Hermes 报没有 API key，帮我修配置。
- 我这台苹果电脑怎么装 Hermes？

## 安装到 WorkBuddy

本专家包目录：

```
<plugins>/marketplaces/my-experts/plugins/hermes-deploy-guild/
```

注册 / 打包（WorkBuddy 内置脚本）：

```bash
python scripts/register_expert.py <expert-dir>
python scripts/package_expert.py  <expert-dir>
```

## 许可

MIT
