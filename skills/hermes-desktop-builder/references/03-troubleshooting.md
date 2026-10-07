# 03 · 故障速查与实战实录

## 故障树（按出现顺序排查）

### A. 安装阶段

| 现象 | 原因 | 修法 |
|---|---|---|
| `hermes desktop` 报 "Desktop GUI source not found" | pip 版无 apps/desktop | 官方 install.ps1 装源码版；桌面端必须源码构建 |
| PortableGit 镜像 404 | 官方镜像失效 | 用 npmmirror 静默装 Git for Windows |
| 残留目录报 `not a git checkout` | 旧安装残留 | `Move-Item` 挪开旧目录重跑安装 |
| registry.npmmirror.com ENOTFOUND | 写成了裸 npmmirror.com | **铁律**：必须带 `registry.` 前缀 |

### B. 构建阶段（按报错文本对号入座）

| 报错 | 根因 | 修法 |
|---|---|---|
| `ChecksumMismatchError: 7zip-win-x64.tar.gz` | npmmirror 的 7zip@1.0.1 与 @electron/get 内置官方 sha256 不符，sumchecker 硬校验 | 打 dir-only 补丁跳过 7zip（--dir 用 JS 解压，不需要 7za） |
| gh-proxy 下载得到 9/581 字节错误页 | 镜像对二进制文件不可靠/仓库路由错 | 死心：icons/winCodeSign 不走 gh-proxy，靠补丁跳过+本地拼装 |
| `Missing Windows tool selection; run preparation again`（prepared-packaging.mjs:130） | readPackagingInputs 硬要求 win32 的 `windows`+`toolsets.winCodeSign`+`windows.dotnetRoot` 非空；补丁只给了 winCodeSign 漏了 windows | 用技能版补丁（伪造 windows 对象）；**注意 prepared.json 可能是旧代码写的**——先杀旧构建进程再重跑 |
| `ToolsetCustom.checksum is required for url toolsets (url: file://...)` | 设了 `ELECTRON_BUILDER_DANGEROUSLY_ALLOW_HTTP=true`，file:// 被当 url 类型强制要 checksum | **删掉该环境变量**。file:// 走 directory 类型免 checksum |
| electron 下载卡住/404 | ELECTRON_MIRROR 没设或指到 GitHub | `ELECTRON_MIRROR=https://registry.npmmirror.com/-/binary/electron/` |
| SHASUMS 404 | npmmirror 无 SHASUMS 文件 | 无害：@electron/get 自动 unsafelyDisableChecksums（软失败），下载照常完成 |
| 构建进程中途消失 | SSH 断开杀会话进程树 | 计划任务（schtasks /Run）或本机后台任务挂住；**别用 Start-Process 分离**（会话关它也死） |
| `npm run pack` 后 pack.log 出现 "working tree is dirty" | 补丁改了仓库文件 | 无害提示，忽略 |
| vite 阶段 7-8 分钟没动静 | 正常（渲染层全量编译） | 等后续：prepare→electron-builder→release\win-unpacked |

### C. 落地阶段

| 现象 | 原因 | 修法 |
|---|---|---|
| 用户说"桌面端没有" | 产物在但没建快捷方式 | make_shortcut.ps1 建到 **Public Desktop**；提醒 F5 |
| RDP 连不上 | 防火墙没放行（Server 常见） | fix_rdp_fw.ps1（补 TCP+UDP 3389 两条规则） |
| mstsc 提示证书不受信任 | 无 CA 签名，正常 | 点"是"继续；可保存 .rdp 一键连 |
| exe 双击闪退 | 缺渲染层产物/杀软拦 | 先 CLI 启动冒烟定位；查杀软隔离区 |

### D. 配置阶段

| 现象 | 原因 | 修法 |
|---|---|---|
| `no API key` | 没跑过 hermes model 或 .env 丢了 | 重跑 `hermes model` |
| 请求 404 | 端点写进了 .env 的 OPENAI_BASE_URL | 端点必须写 config.yaml 的 `model.base_url`（custom provider 不读 OPENAI_BASE_URL） |
| 401 | key 错/过期 | 重填 key |
| 手改 config.yaml 不生效 | 0.19.0 schema 旧 | 只走 `hermes model` 向导 |
| UnicodeEncodeError | 控制台编码 | `$env:PYTHONUTF8=1` |
| 桌面端卡 90% | 多实例抢 8787 端口 | 清 hermes/electron 进程再启动 |

### D-2. ⚠️ 高频坑（两次踩坑，每次部署必查）：进程在但窗口不出现

**症状**：`Hermes.exe` 进程活着（4-5 个）但双击"没反应"，无窗口、无崩溃转储、无事件日志报错。

**诊断一招**：看 `%LOCALAPPDATA%\Hermes\logs\desktop.log` tail。

**根因链（2026-10-07 二次踩坑后完全摸清，三杀手叠加）**：
```
杀手① source-completion-pending 标记（%LOCALAPPDATA%\hermes\installs\<hash>\ 下）
  → CLI 每次启动（含 backend serve、venv import 探测）都先跑
    "completing source-update dependencies..."（uv/pip 同步+构建）
  → 超过桌面端 90 秒端口播报超时 → "Timed out waiting for Hermes backend port announcement"
  ⚠️ `hermes --version` 走捷径不触发此步（6 秒完事）→ CLI 看起来健康，极难排查
杀手② 陈旧锁：%LOCALAPPDATA%\hermes\.hermes-update-in-progress(.lock)（被杀进程遗留）
  → 新的补依赖尝试永远拿不到锁 → python 子进程零 CPU 零磁盘写入假死
杀手③ venv Python 版本门：源码安装判定只认 3.11/3.12/3.13（3.14 报 "broken/partial venv"）
  → "no usable Hermes install" → 卡 first-run setup → 主窗口永不创建
  （①②清掉后探测可通过，3.14 也会被 "Using existing Hermes Python" 接受）
```

**一键修复**：`scripts/fix_backend_boot.ps1`（杀卡死进程 → 删 pending 标记+陈旧锁 → `setx HERMES_DESKTOP_HERMES` + `setx HERMES_DISABLE_LAZY_INSTALLS=1` 双保险）。

**修复验证标准**（缺一不可）：
- desktop.log：`Using existing Hermes Python` → `Starting Hermes backend` → **`HERMES_BACKEND_READY port=<n>`** → `Hermes backend is ready. Finalizing desktop startup`（全程约 60 秒）
- **不再出现** `completing source-update dependencies` / `Waiting for first-run setup choice`
- 环境变量 setx 后若新进程没读到，注销重登一次

**预防规则（写进每个部署的验收）**：装完桌面端只算 50%，必须再看一眼 desktop.log 确认后端起来（`HERMES_BACKEND_READY`）才算交付。

## 实战时间线（2026-10-07，101.35.12.205）

| 时间 | 动作 | 结果 |
|---|---|---|
| 早 | 判定"GitHub 被墙→桌面端不可行"（v1 结论） | ❌ 后被推翻 |
| 16:02 | dir-only 补丁 v1（只给 winCodeSign） | ❌ Missing Windows tool selection |
| 16:2x | 读 readPackagingInputs 源码，补丁 v2 伪造 windows+dotnetRoot | ✅ 过校验 |
| 16:2x | 首跑撞 `ToolsetCustom.checksum is required` | 定位 envUtil.validateSecuredUrl |
| 16:3x | 删 DANGEROUSLY_ALLOW_HTTP 重跑 | ✅ 全量构建成功（457s） |
| 16:39-16:43 | 提速脚本+计划任务 | ✅ 重打 61.97s（7×） |
| 17:27 | 终局校验：exe 204MB+启动存活 130MB | ✅ |
| 17:47 | 用户"桌面没有"→补公共桌面快捷方式 | ✅ LNK_CREATED=True |
| 18:49 | 用户嫌网页控制台→RDP 三件套 | ✅ 3389 放行+2 条规则 |

核心教训：**"环境限制不可行"的结论要先穷尽"源码级补丁"手段再下**。本次三步破局法（伪造工具集过校验 / npmmirror 镜像 / 删反直觉环境变量）可复用到任何 electron-builder 被墙场景。
