---
name: hermes-desktop-builder
description: 在 GitHub 被墙的 Windows 服务器/电脑上，从源码构建并落地 Hermes（hermes-agent）桌面端 GUI 的固定流程。覆盖：SSH 通道建立 → CLI 安装 → 桌面端源码构建（跳过被墙工具链破局法）→ 渲染层缓存提速 7 倍 → 桌面快捷方式/RDP/登录自重建 → 模型配置与验收。触发词：装 Hermes 桌面端、构建桌面 GUI、Hermes.exe、桌面端打不开、winCodeSign 报错、electron-builder 被墙、Missing Windows tool selection。
---

# Hermes 桌面端构建师（GitHub 被墙环境）

## 适用场景与判定

| 用户需求 | 走哪条路线 |
|---|---|
| 只要 CLI | 官方镜像一行命令，不走本技能（见 references/02 Phase 2） |
| **要桌面端 GUI，机器能连 GitHub** | 官方 `install.ps1 -IncludeDesktop`（pip 包装不出桌面端） |
| **要桌面端 GUI，GitHub 被墙**（国内服务器常态） | **本技能核心流程**（Phase 1→6 全走） |
| 桌面端已构建但用户看不到图标 | Phase 5（快捷方式+RDP） |
| 桌面端重打太慢 | Phase 4（提速到 ~62 秒） |

## 核心认知（先读这个，避免重蹈 4 小时覆辙）

1. **桌面端只能从 monorepo 源码构建**：`apps/desktop` 是 Electron 应用，`npm run pack` = vite 前端(~8min) + electron-builder `--dir`。pip 包没有 `apps/desktop`，`hermes desktop` 必报 "Desktop GUI source not found"。
2. **win32 上 `--dir` 模式仍强制要工具集**：electron(zip)、7zip、icons、winCodeSign 全来自 GitHub——被墙时 3/4 拿不到。
3. **破局三步**（详见 references/01）：
   - ① 给 `apps/desktop/scripts/prepare-packaging-tools.mjs` 打 dir-only 补丁（本技能 `scripts/prepare-packaging-tools.mjs` 是成品）：跳过 7zip/icons 下载，用 node_modules 自带 rcedit/signtool 拼最小 winCodeSign 工具集 + 伪造 `windows{dotnetRoot,...}` 过校验
   - ② electron 本体走 npmmirror：`ELECTRON_MIRROR=https://registry.npmmirror.com/-/binary/electron/`
   - ③ **必须删掉** `ELECTRON_BUILDER_DANGEROUSLY_ALLOW_HTTP`——设了它 file:// 工具集会被当 url 类型强制要 checksum 报 `ToolsetCustom.checksum is required`
4. **SSH 断开会杀进程树**：>10 分钟的构建必须挂计划任务（HermesPack）或用前台 exec_command+后台任务跑，别用 `Start-Process` 分离（会话关了它也死）。
5. **模型配置只有一条路**：`hermes model` 向导 → Custom endpoint → Chat Completions 兼容；手写 config.yaml 不生效（0.19.0 schema 旧）；key 放 `~/.hermes/.env`。
6. **⚠️ 构建≠能启动（两次踩坑，必查）**：exe 能跑不等于桌面端能用。**每次装完必须验证 `%LOCALAPPDATA%\Hermes\logs\desktop.log` 里后端真正起来**（看到 `Starting Hermes backend` 且无 `Waiting for first-run setup choice`）。已知杀手：venv Python 版本不受支持（只认 3.11/3.12/3.13，如 3.14 会被判 "no usable Hermes install"）+ "source-update completion" 挂起标记让后端 90 秒超时。**一键修复：`scripts/fix_backend_boot.ps1`**（详见 references/03 D-2 节）。

## 固定流程（六阶段，照做即可）

### Phase 1 通道建立
- SSH 22 直连（paramiko，用 `scripts/ssh_exec.py`，凭据走 `SS_HOST/SS_USER/SS_PASS` 环境变量）。
- 首选 `putrun` 模式：SFTP 传 .ps1 → `powershell -File` 执行。**禁止**往 `powershell -Command -` 的 stdin 写多行脚本（paramiko 报 OSError）。

### Phase 2 CLI 与依赖安装
- 国内镜像一行：`irm https://res1.hermesagent.org.cn/install.ps1 | iex`（自动装 uv+Py3.11+Node+Git+PATH）。
- 验收：`hermes --version`。仓库源码在 `apps/desktop` 已随安装就位。

### Phase 3 桌面端构建（首次，~10 分钟）
1. 上传 `scripts/prepare-packaging-tools.mjs` 覆盖 `apps\desktop\scripts\prepare-packaging-tools.mjs`
2. 上传 `scripts/pack_run.ps1` 到 `C:\Users\<user>\`
3. 建/启动计划任务 HermesPack 跑它（防 SSH 断连），或前台后台任务直跑
4. 轮询 `%LOCALAPPDATA%\hermes\pack.log`，成功标志：`PACK_EXIT=0` + `HERMES_EXE_EXISTS=True`
5. 产物：`apps\desktop\release\win-unpacked\Hermes.exe`（~204MB）

### Phase 4 提速（后续重打 ~62 秒，7×）
- `scripts/pack_builder_only.ps1`：跳过 vite、复用已编译渲染层，只跑 prepare+electron-builder。
- 触发条件：仅改了打包配置/补丁时用；改了前端源码则必须回 Phase 3 全量。

### Phase 5 落地（用户"看不到"的三大补法）
1. `scripts/make_shortcut.ps1` → 建到**公共桌面** `C:\Users\Public\Desktop\Hermes.lnk`（所有会话可见；建完提醒用户 F5 刷新）
2. `scripts/fix_rdp_fw.ps1` → 确保 RDP 开启 + 3389 防火墙放行（用户在网页控制台里难受时，教他 Win+R → mstsc → 服务器 IP）
3. `scripts/install_build_task.ps1` → 登录时自动重建计划任务（保底，防误删产物）

### Phase 6 模型配置与验收
- `hermes model` 向导：Custom endpoint → 端点 `https://<host>/v1` → Chat Completions 模式 → 填 key → 选模型/上下文。
- 验收 5 项：`hermes --version` / 新终端 `hermes` 启动 / 发 `hi` 有回复 / `hermes doctor` / 桌面端双击能开。**绝不回显明文 Key。**

## 脚本清单

| 文件 | 用途 | 部署位置 |
|---|---|---|
| `ssh_exec.py` | 通用 SSH/SFTP 驱动（凭据走环境变量） | 本机 |
| `prepare-packaging-tools.mjs` | **核心补丁**：dir-only 跳过被墙工具链 | 覆盖 `apps\desktop\scripts\` 同名文件 |
| `pack_run.ps1` | 全量构建（vite+builder，~10min），写 pack.log | `C:\Users\<user>\` |
| `pack_builder_only.ps1` | 快速重打（~62s，复用渲染层），写 pack-builder.log | `C:\Users\<user>\` |
| `install_build_task.ps1` | 登录自重建计划任务 HermesDesktopBuild | `C:\Users\<user>\` |
| `make_shortcut.ps1` | 建公共桌面快捷方式 | 任意，putrun 即可 |
| `fix_rdp_fw.ps1` | RDP 开启 + 3389 放行 | 任意，putrun 即可 |

## 故障速查

| 报错/现象 | 原因 | 修法 |
|---|---|---|
| `Missing Windows tool selection` (prepared-packaging.mjs:130) | 补丁没打或 prepared.json 是旧代码产物 | 传新补丁→杀旧构建进程→清 `build\packager` 重跑 |
| `ToolsetCustom.checksum is required` | 设了 `ELECTRON_BUILDER_DANGEROUSLY_ALLOW_HTTP` | **删掉该变量**，file:// 按 directory 类型直接用 |
| `ChecksumMismatchError: 7zip-win-x64` | npmmirror 的 7zip 与官方 sha256 不符 | dir-only 补丁已跳过 7zip；出现即说明补丁未生效 |
| 构建跑一半没了 | SSH 断开杀进程树 | 挂计划任务/后台任务重跑 |
| `npm run pack` vite 卡 8 分钟 | 正常，首次全量 | 用 pack_builder_only.ps1 快速重打 |
| "not a git checkout" | 残留目录冲突 | `Move-Item` 挪开重跑安装 |
| 桌面看不到图标 | 快捷方式没建/没刷新 | make_shortcut.ps1 + 提醒 F5 |

## 红线

- 不在技能/脚本/日志里留明文密码与 API Key
- 覆盖服务器上仓库文件前，确认是官方源码路径且改动能被 `git diff` 识别（会在 pack.log 出现 dirty 提示，无害）
- 构建产物路径一切以 `release\win-unpacked\Hermes.exe` 存在为准，不以日志"成功"字样为准

## 详细文档

- `references/01-gfw-desktop-build-principles.md` — 破局原理与校验机制逐条拆解
- `references/02-full-sop.md` — 端到端 SOP（含每步命令原文）
- `references/03-troubleshooting.md` — 完整故障树与本案例实录
