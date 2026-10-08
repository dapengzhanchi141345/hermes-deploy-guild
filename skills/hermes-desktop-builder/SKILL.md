---
name: hermes-desktop-builder
description: 在 GitHub 被墙的 Windows 服务器/电脑上，从源码构建并落地 Hermes（hermes-agent）桌面端 GUI 的固定流程。覆盖：SSH 通道建立 → CLI 安装 → 桌面端源码构建（跳过被墙工具链破局法）→ 渲染层缓存提速 7 倍 → 桌面快捷方式/RDP/登录自重建 → 模型配置与验收。触发词：装 Hermes 桌面端、构建桌面 GUI、Hermes.exe、桌面端打不开、winCodeSign 报错、electron-builder 被墙、Missing Windows tool selection。
---

# Hermes 桌面端构建师（GitHub 被墙环境）

## 适用场景与判定

| 用户需求 | 走哪条路线 |
|---|---|
| 只要 CLI（国内） | `irm https://res1.hermesagent.org.cn/install.ps1 \| iex` 一行装完（自动 uv+Py3.11+Node+Git+PATH）；海外 `iex (irm https://hermes-agent.nousresearch.com/install.ps1)`；macOS `curl -fsSL https://hermes-agent.nousresearch/install.sh \| bash` |
| **要桌面端 GUI，机器能连 GitHub** | 官方 `install.ps1 -IncludeDesktop`（pip 包装不出桌面端） |
| **要桌面端 GUI，GitHub 被墙**（国内服务器常态） | **本技能核心流程**（Phase 1→7 全走） |
| 桌面端已构建但用户看不到图标 | Phase 5（快捷方式+RDP） |
| 桌面端重打太慢 | Phase 4（提速到 ~62 秒） |
| 桌面端进程在但窗口不出 | **先跑 `scripts/fix_backend_boot.ps1`**（三杀手，见 references/03 D-2） |
| 没有 SSH，只有向日葵/AweSun 远控 | references/03 F 节 ntfy 黄金通道（脚本必须压单行） |
| 服务器磁盘/内存吃紧，要深度清理 | Phase 7（`scripts/clean_server.ps1`） |
| 部署完要把技能包/产物传 GitHub | git 直连被墙时走 gh API 通道（references/03 F 节） |

## 核心认知（先读这个，避免重蹈 4 小时覆辙）

1. **桌面端只能从 monorepo 源码构建**：`apps/desktop` 是 Electron 应用，`npm run pack` = vite 前端(~8min) + electron-builder `--dir`。pip 包没有 `apps/desktop`，`hermes desktop` 必报 "Desktop GUI source not found"。
2. **win32 上 `--dir` 模式仍强制要工具集**：electron(zip)、7zip、icons、winCodeSign 全来自 GitHub——被墙时 3/4 拿不到。
3. **破局三步**（详见 references/01）：
   - ① 给 `apps/desktop/scripts/prepare-packaging-tools.mjs` 打 dir-only 补丁（本技能 `scripts/prepare-packaging-tools.mjs` 是成品）：跳过 7zip/icons 下载，用 node_modules 自带 rcedit/signtool 拼最小 winCodeSign 工具集 + 伪造 `windows{dotnetRoot,...}` 过校验
   - ② electron 本体走 npmmirror：`ELECTRON_MIRROR=https://registry.npmmirror.com/-/binary/electron/`
   - ③ **必须删掉** `ELECTRON_BUILDER_DANGEROUSLY_ALLOW_HTTP`——设了它 file:// 工具集会被当 url 类型强制要 checksum 报 `ToolsetCustom.checksum is required`
4. **SSH 断开会杀进程树**：>10 分钟的构建必须挂计划任务（HermesPack）或用前台 exec_command+后台任务跑，别用 `Start-Process` 分离（会话关了它也死）。
5. **模型配置分版本两路线**：git 新版（install.ps1 装，2026.9+）**直接写 config.yaml 全自动**（home 是 `%LOCALAPPDATA%\hermes`，不是 `~\.hermes`！写错位置静默不生效）；0.19.0 pip 版**只能 `hermes model` 交互向导**（手写 config.yaml 不生效，OPENAI_BASE_URL 对 custom provider 无效）。key 放同目录 `.env`。详见 references/02 Phase 6。
6. **⚠️ 构建≠能启动（两次踩坑，必查）**：exe 能跑不等于桌面端能用。**每次装完必须验证 `%LOCALAPPDATA%\Hermes\logs\desktop.log` 里后端真正起来**（看到 `Starting Hermes backend` 且无 `Waiting for first-run setup choice`）。已知杀手：venv Python 版本不受支持（只认 3.11/3.12/3.13，如 3.14 会被判 "no usable Hermes install"）+ "source-update completion" 挂起标记让后端 90 秒超时。**一键修复：`scripts/fix_backend_boot.ps1`**（详见 references/03 D-2 节）。

## 固定流程（六阶段门禁制，照做即可）

> 🚦 **部署一律走 `scripts/deploy_gate.py` 编排器**（凭据走 `SS_HOST/SS_USER/SS_PASS` 环境变量）：六阶段每阶段过闸才进下一阶段，闸不过自动执行已知修复，修复后仍不过立即停止给修法。**交付判定只认 `scripts/acceptance_check.ps1` 全绿（FAIL=0, EXIT=0）**，禁止凭日志"成功"字样或"进程存在"报交付。编排器幂等：失败修复后直接重跑，已过阶段自动跳过。

### Phase 1 通道建立
- SSH 22 直连（paramiko，用 `scripts/ssh_exec.py`，凭据走 `SS_HOST/SS_USER/SS_PASS` 环境变量）。
- 首选 `putrun` 模式：SFTP 传 .ps1 → `powershell -File` 执行。**禁止**往 `powershell -Command -` 的 stdin 写多行脚本（paramiko 报 OSError）。
- **PS 5.1 四铁律**（每条都真实炸过一次，详见 references/03 E 节）：
  1. .ps1 必须 UTF-8 BOM（无 BOM 按 ANSI 解析，中文/emoji 炸语法；ssh_exec.py / deploy_gate.py 的 put 均已自动补）
  2. 单引号内 `$env:` 不展开——路径判存先双引号赋值给变量再用（deploy_gate 曾因此误判 exe 缺失触发伪构建）
  3. 禁多行管道续行（行尾 `|` 接下一行在 LF 文件里可能解析失败）——**全部单行语句 + foreach + -LiteralPath 最稳**
  4. 禁内嵌 here-string（`@"..."@`）写 C#/多行文本——单独 .cs 文件 `Add-Type -Path` 或单行字符串

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
- **先判定配置主目录**：git 新版（install.ps1 装）= `%LOCALAPPDATA%\hermes`；0.19.0 pip 版 = `~\.hermes`。写错位置静默失效（`hermes config get providers` 返回 `{}` 即信号）。
- git 新版直接写 config.yaml（`model:` + `providers:` 段，key 走 `.env` 的 `key_env` 引用）；0.19.0 只能 `hermes model` 向导。详见 references/02 Phase 6。
- 验收 5 项：`hermes --version` / `hermes status` Model 行有值 / `hermes -z "…"`（EXIT=0）/ desktop.log 到 `HERMES_BACKEND_READY` / 桌面端双击能开。**绝不回显明文 Key。**
- Agnes 免费档 429≠401（429=认证已过，1 req/min/key，换 key 或等 60s）。多 key 存 `.env`（`AGNES_API_KEY` 主位 + `_2.._N` 备用）。

### Phase 7 服务器深度清理（可选，磁盘/内存吃紧时）
- `scripts/clean_server.ps1`（`-DryRun` 先看计划，实际执行默认全做）：回收站、Temp（>2h）、npm/pip/uv/electron 缓存、WU 缓存、CBS 旧日志、EmptyWorkingSet 内存修剪（只压不杀）。
- `-Pagefile 3072`：2GB 内存服务器把系统托管 pagefile（常 5.5GB+）收紧为固定 3GB——**重启才生效**，会中断交易/常驻服务，必须用户确认时机。
- **绝不触碰**：`MT5*` / `GoldstrategyEngine` / `workbuddy`（含 `~\.workbuddy`）/ `hermes-agent`（桌面端本体）/ `Recovery`。
- 清完必报：C 盘可用、内存可用、pagefile 待重启项。实测：C 盘 11.6→13.9GB，内存 0.09→0.67GB。

## 脚本清单

| 文件 | 用途 | 部署位置 |
|---|---|---|
| `ssh_exec.py` | 通用 SSH/SFTP 驱动（凭据走环境变量） | 本机 |
| `deploy_gate.py` | **🚦 端到端编排器**：六阶段门禁+自动修复+幂等重跑 | 本机 |
| `acceptance_check.ps1` | **🏁 交付总验收**：12 项红绿门禁，EXIT=0 才可交付 | 传到服务器跑 |
| `fix_backend_boot.ps1` | 一键修复"进程在窗口不出"（清标记/死锁+双保险变量） | 传到服务器跑 |
| `prepare-packaging-tools.mjs` | **核心补丁**：dir-only 跳过被墙工具链 | 覆盖 `apps\desktop\scripts\` 同名文件 |
| `pack_run.ps1` | 全量构建（vite+builder，~10min），写 pack.log | `C:\Users\<user>\` |
| `pack_builder_only.ps1` | 快速重打（~62s，复用渲染层），写 pack-builder.log | `C:\Users\<user>\` |
| `install_build_task.ps1` | 登录自重建计划任务 HermesDesktopBuild | `C:\Users\<user>\` |
| `make_shortcut.ps1` | 建公共桌面快捷方式 | 任意，putrun 即可 |
| `fix_rdp_fw.ps1` | RDP 开启 + 3389 放行 | 任意，putrun 即可 |
| `clean_server.ps1` | 服务器深度清理（缓存/Temp/回收站/内存修剪/pagefile），`-DryRun` 预览 | 任意，putrun 即可 |

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
| 桌面端进程在但窗口不出 | 三杀手（pending 标记/陈旧锁/Python 版本门） | **fix_backend_boot.ps1** → 看 desktop.log 到 `HERMES_BACKEND_READY` |
| .ps1 传上去就报语法错 | 无 BOM / 多行管道 / here-string | 按 Phase 1 四铁律改写（单行语句最稳） |
| 探测命令把 `$env:LOCALAPPDATA\...` 当字面量 | PS 单引号不展开变量 | 双引号赋值给变量再用 |
| git push/clone 被墙（SSL 握手失败） | GitHub 直连断 | **gh api 逐文件 PUT contents**（走本地代理，已验证 14/14） |
| 服务器磁盘满/内存枯竭 | 缓存+pagefile 膨胀 | Phase 7 clean_server.ps1 |
| `hermes config get providers` 返回 `{}` 但配置写了 | 配置写错 home（新版=`%LOCALAPPDATA%\hermes`） | 用 venv python 打印 `hermes_cli.config` home 函数确认真实路径 |

## 红线

- 不在技能/脚本/日志里留明文密码与 API Key
- 覆盖服务器上仓库文件前，确认是官方源码路径且改动能被 `git diff` 识别（会在 pack.log 出现 dirty 提示，无害）
- 构建产物路径一切以 `release\win-unpacked\Hermes.exe` 存在为准，不以日志"成功"字样为准

## 详细文档

- `references/01-gfw-desktop-build-principles.md` — 破局原理与校验机制逐条拆解
- `references/02-full-sop.md` — 端到端 SOP（含每步命令原文）
- `references/03-troubleshooting.md` — 完整故障树与本案例实录
