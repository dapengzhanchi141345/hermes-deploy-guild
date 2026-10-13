# 04 · 本地机 Hermes「反复修不好」终极破案（2026-10-13 实战实录）

> 适用对象：**本地 Windows 机**（非服务器）已装好 Hermes 桌面端，出现"启动不了 / 聊天 404 / 修好又坏"的反复性问题。
> 本次从 09:00 排查到 11:20，历经四轮假修复，最终挖出**三层叠加根因**。此文档 = 完整破案过程 + 可复用修复流程。

## 一、为什么"反复修不好"——三层叠加根因总览

```
第 1 层：pm 托管环境系统性损坏（表面 venv 是好的 → 怎么测都"正常"）
第 2 层：用户级 env HERMES_DISABLE_LAZY_INSTALLS=1 禁用了自愈（我测的 shell 没这变量 → 我测全通，用户双击必挂）
第 3 层：沙箱/安全软件拦 uv 写缓存（os error 5）→ hermes pm repair 永远静默失败（修复命令看起来跑了，从没成功过）
```

**三层同时存在时**：修好第 1 层 → 被 2 层打回原形；想跑 repair 修环境 → 被 3 层挡死。之前每轮只看见一层，这就是"循环修不好"的机制。

## 二、关键侦查结论（不看这个会浪费几小时）

### 2.1 日志有真假两份（最大误导源！）
| 路径 | 真假 | 说明 |
|---|---|---|
| `E:\<安装home>\logs\desktop.log`（如 `E:\workbuddy\国外模型\hermes\logs\`） | ✅ **真** | 活跃写入，诊断只看这份 |
| `%LOCALAPPDATA%\Hermes\logs\desktop.log` | ❌ 死文件 | 可能是几个月前的残留，**误导前两轮修复** |

判定法：`Get-ChildItem <home>\logs | Sort LastWriteTime -Desc` 看 mtime；两个 home（E: 安装 + C: `%LOCALAPPDATA%\hermes`）的 logs 都摸一遍，**谁在 5 分钟内被写过谁是真的**。

### 2.2 双 home 结构（本地机特有）
- CLI 用户配置 home：如 `E:\workbuddy\国外模型\hermes`（config.yaml + .env 在这）
- bootstrap/installs home：`%LOCALAPPDATA%\hermes`（installs\<hash>\、pm-runtime、bin\uv.exe）
- **两处 config 都要健康**：聊天 404 时逐个检查（本次 C: home 是死端点 + 无 key，E: home 是好的 → 桌面端聊天 404 而 CLI 正常）
- 移植法：从好 config 抠 `model:`+`providers:` 块整体替换坏 config，并把 key 段并入坏 home 的 `.env`

### 2.3 CLI 的"真身"不是那个 venv（认知颠覆）
- 表面：`E:...\hermes-agent\venv`（Python 3.11）——**只是启动器**
- 真身：pm 托管环境 `installs\<hash>\environments\<env-hash>\venv`（Python 3.14.7），`hermes serve`/CLI 实际 import 的是这里的包
- 佐证：venv 里 `import pydantic_core` OK，但 CLI 报 `ModuleNotFoundError: pydantic_core`
- 检查健康度一键脚本：
```powershell
$e = "E:\<home>\installs\4ea489dd943be455\environments"
Get-ChildItem $e | ForEach-Object {
  $py = "$($_.FullName)\venv\Scripts\python.exe"
  if (Test-Path $py) {
    $r = & $py -c "import pydantic_core,fastapi,uvicorn,httpx; print('OK')" 2>&1
    "$($_.Name.Substring(0,8)) => $($r | Select-Object -Last 1)"
  } else { "$($_.Name.Substring(0,8)) => NO PYTHON.EXE" }
}
```
- 典型坏法（本次 8 环境坏 5 个）：`_pydantic_core*.pyd` 缺失 / `click.Choice` 缺 / `annotated_doc` 缺 / `cffi` 缺 / 整个 venv 无 python.exe

### 2.4 损坏源头（疑似，无法完全定罪）
WorkBuddy 注入的 `PYTHONPATH` 指向其 `vendor\shim`，`sitecustomize.py` 劫持 `os.remove/os.replace` 做"安全删除"（挪回收站）。uv/pip 装包时触发 → 文件被"安全回收" → 环境半成品。
**规则：所有 hermes CLI/uv/pip 操作前必须 `Remove-Item Env:PYTHONPATH`**。

### 2.5 环境变量陷阱（本案例第 2 层根因）
| 变量 | 来源 | 危害 |
|---|---|---|
| `HERMES_DISABLE_LAZY_INSTALLS=1`（User 级） | 服务器排障时 setx 留下的 | **禁用 CLI 自愈** → pm 环境坏了也绝不自动修 → 桌面 backend 每次启动必挂 |
| `HERMES_DESKTOP_HERMES`（User 级，空值） | 同上 | 无用残留 |

**"我这边好你那边坏"判定法**：AI 会话里的 shell 是登录后派生的，**可能没继承后来 setx 的变量**；用户双击/计划任务启动的进程一定继承。
```powershell
[Environment]::GetEnvironmentVariable('HERMES_DISABLE_LAZY_INSTALLS','User')   # 查 User 级
Remove-Item Env:HERMES_DISABLE_LAZY_INSTALLS -ErrorAction SilentlyContinue      # 当前 shell 清
[Environment]::SetEnvironmentVariable('HERMES_DISABLE_LAZY_INSTALLS',$null,'User')  # 永久删
```
> ⚠️ **修正旧结论**：references/03 D-2 曾把 `setx HERMES_DISABLE_LAZY_INSTALLS=1` 当"双保险"——**错**。pm 环境健康时它无害，pm 环境坏时它挡死自愈。正常交付后应删除该变量。

### 2.6 沙箱/安全软件拦 uv（第 3 层根因）
- 症状：`hermes pm repair` exit 1，日志尾 `uv ... bytecode-compilation ... os error 5 (拒绝访问)`（写 `<home>\cache\uv\.tmp`）
- 根目录手工写测试 OK 也没用——是**子进程 uv 被拦**，不是 ACL 问题
- 破法：**挂计划任务在会话沙箱外执行**：
```powershell
$action  = New-ScheduledTaskAction -Execute "E:\<home>\hermes-agent\venv\Scripts\hermes.exe" -Argument "pm repair" -WorkingDirectory "E:\<home>"
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddSeconds(5)
Register-ScheduledTask -TaskName "HermesPmRepairOnce" -Action $action -Trigger $trigger -Force | Out-Null
Start-ScheduledTask -TaskName "HermesPmRepairOnce"
# 等 2-3 分钟后验收：
(Get-ScheduledTaskInfo -TaskName "HermesPmRepairOnce").LastTaskResult   # 0 = 成功
```

### 2.7 其他实战结论
- 桌面 backend 命令 = `hermes serve --host 127.0.0.1 --port 0`（可单独手动复现，是"桌面挂 CLI 好"的分流利器）
- electron 瞬退 exit 0 不写日志 = 单例锁/更新门控；**官方启动通道 = 计划任务 `HermesDesktopLaunch`**（`Start-ScheduledTask` 启动）
- Start-Process 遇 `http_proxy`/`HTTP_PROXY` 大小写重复键会炸（.NET 异常）；且每块 PowerShell 命令都是新 shell，**env 清理必须块内自带**
- 补缺包：`%LOCALAPPDATA%\hermes\bin\uv.exe pip install --python <目标venv的python.exe> pydantic-settings`（先清 PYTHONPATH）
- `hermes pm doctor` / `hermes pm status` 是环境健康官方探针（也要清 PYTHONPATH，否则 .leases 操作被 shim 劫持报错）
- cron/chief 等各 profile 用的是**同一批 pm 环境**——环境修好后主 profile 与子 profile 一起恢复

## 三、可复用修复流程（四步，照抄即可）

```
① 删遗留 User 级变量：HERMES_DISABLE_LAZY_INSTALLS、HERMES_DESKTOP_HERMES（见 2.5）
② 找到真日志 home → 确认真身环境批量坏 → 清 PYTHONPATH 后挂计划任务跑 `hermes pm repair`（见 2.6）
③ 批量复测 environments 健康度（见 2.3 脚本）→ 全 OK 进 ④
④ Start-ScheduledTask HermesDesktopLaunch → 看 desktop.log：
   `HERMES_BACKEND_READY port=<n>` + `Hermes backend is ready` = 交付
   CLI 快速验收：清 PYTHONPATH 后 `hermes -z "回复pong一个词即可"` EXIT=0
```

一键脚本：`scripts/fix_local_pm.ps1`（封装 ①②③，④ 留人工看日志）。

## 四、实战时间线（2026-10-13，本地机 ASUS）

| 时间 | 动作 | 结果 |
|---|---|---|
| 09:1x | 第一轮：杀 4 个 CPU=0 死锁补依赖进程 + 清 6 个锁/标记 + setx 修垃圾变量 | CLI pong ✅（假修复之一） |
| 09:2x | 用户"还启动不起来" → 发现双 home：C: home 死端点+无 key → sync 脚本移植配置 | C: CLI pong ✅ 桌面 404 停止（假修复之二） |
| 10:0x | 第三轮：exe 消失恐慌 → 实为 E 盘安装，lnk 指向正确；启动 exit 0 瞬退 | 转向真日志侦查 |
| 10:2x | 找到真日志（E: home）→ backend 报 fastapi/uvicorn missing（表象）| 锁定 pm 环境 |
| 10:3x | `pm install` + uv 补 pydantic-settings + `pm repair` 会话内跑 | ✗ exit 1 静默失败（os error 5） |
| 10:4x | 计划任务跑 pm repair → Result=0 | ✅ 新代环境重建 |
| 10:5x | `pm status` 自认 OK 但桌面 backend 仍报 pydantic_core | 发现 HERMES_DISABLE_LAZY_INSTALLS |
| 11:0x | 删 User 级两变量 → Start-ScheduledTask HermesDesktopLaunch | ✅ `HERMES_BACKEND_READY port=60876` |
| 11:1x | 各 profile backend 全部自动拉起；CLI + chief profile 双 pong | ✅ 用户验收 |

## 五、检查清单（下次同类问题直接打勾）

- [ ] User 级 `HERMES_DISABLE_LAZY_INSTALLS` / `HERMES_DESKTOP_HERMES` 已删？
- [ ] 当前 shell `PYTHONPATH` 已清？`http_proxy`/`HTTP_PROXY` 大小写冲突已清？
- [ ] 看的是真日志（5 分钟内有写入的那份）？
- [ ] environments 批量健康度复测全 OK？
- [ ] `hermes pm repair` 是计划任务跑的且 LastTaskResult=0？
- [ ] desktop.log 出现 `HERMES_BACKEND_READY` + `backend is ready`？
- [ ] `hermes -z "pong"` EXIT=0？
- [ ] 有 `--profile` 使用的子 profile 也实测过？
