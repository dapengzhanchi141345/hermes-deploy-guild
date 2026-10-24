# 07 - bots 配置分发与路径自适应（bot-shuffler 专章 · v2 全远程机版）

> 适用：用户明说"装 bots / 装专家 / 配 bots"时才走本页。**只装 Hermes 时不用翻这页。**
> 目标：把主理人本机 `~/.workbuddy/plugins/marketplaces/my-experts/plugins/`（41 个 expert，109M）
> 脱敏后分发到**任意一台客户远程机**（Win/mac/Linux、装法不定、路径不定），远程显示的**功能/技能/架构与本机一致**，但**不含任何 key/手机号/识别码/学校/账号**。

## 一、三件套脚本（在 `skills/hermes-deploy/scripts/`）

| 脚本 | 在哪跑 | 作用 |
|------|--------|------|
| `pack_bots.py` | 主理人本机 | 脱敏打包全部 expert → `bots-clean.zip` + manifest（`--scan-only` 审计 / `--exclude` 排除） |
| `ship_cmd.py` | 主理人本机 | 推 ntfy topic，生成本机推送 + 远程取包命令（**Win/mac/Linux 三段**） |
| `path_map.py` | **客户远程机** | 多源探测 Hermes 真实位置 + 反向映射重写 + 按客户系统生成 .ps1/.sh |

## 二、脱敏铁律（打包前必扫，pack_bots.py 自动处理）

- **剔除**：`.env`、`auth.json`、`*.db`、明文 key（`sk-`/`ghp_`/`github_pat_`）、手机号、识别码、学校名、邮箱、个人账号、真人八字示例
- **保留**：skills / agents / 能力架构 / 模型档位与端点（占位符 `<API_KEY>` `<BASE_URL>`）
- 脱敏命中统计写进 `bots-manifest.json`（每 expert + 总计），交付前可审
- 头像默认剔除（客户只要功能/架构）；要头像加 `--keep-avatars`（原图）或 `--compress-avatars`（压到 ~30M）

**审计模式（不打包，只看命中分布，排查"有没有漏脱敏"）：**
```bash
python pack_bots.py --scan-only --out /tmp/bots-audit   # → /tmp/bots-audit.scan.json
```

交付前自查（对解压后的干净包跑，期望 0）：
```bash
grep -riE "sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}|1[3-9][0-9]{9}|<USER>|greenszs" <解压目录>/ | wc -l
```
> 注：占位符 `<API_KEY>`/`<PLACE>`/`<USER>` 与示例 `sk-xxxx` 属预期保留（非真值）。

## 二·补 精准点单（客户不一定全装，点哪个装哪个）

客户可能只要其中几个 bot，不必全装 41 个。`pack_bots.py` 支持点单：

```bash
python pack_bots.py --list                  # 看全部可点单的 bot（中文名/目录名/团队or单体/核心成员数）
python pack_bots.py --only "金策宗师团" --out jince.zip      # 只打金策（团队整包：主理人+全部核心成员一起装）
python pack_bots.py --only "金策宗师团,万物生" --out a.zip   # 点单多个
python pack_bots.py --only "金策" ...        # 中文/英文/目录名均可，支持模糊匹配
```

**团队 bot 点单 = 整包一起装（是一个整体）**：如"只装金策宗师团"，会把它的**主理人策金尊 + 3 个核心角色（猎场司/算天机/金刚卫）共 4 位智能体 + 5 个子 agent** 全部打进同一个 expert 包，客户装完即得完整金策团队，**不会漏任何成员**。单体 bot（如命理排盘师）点单就是它自己。

| 客户要 | 命令 | 打进包的 |
|--------|------|----------|
| 全装 | `pack_bots.py`（不传 --only） | 41 个 |
| 只要金策 | `--only 金策宗师团` | 仅 goldstrategy-guild（含 4 核心 + 5 子 agent 整包） |
| 金策 + 天机阁 | `--only 金策宗师团,天机阁` | 这两个 expert 包 |

> 点单名映射靠 `bots-catalog.json`（各 expert 的 `plugin.json` 里 displayName.zh/teamInfo 自动生成）；`--list` 是它的人读版。

## 三、全远程机路径自适应（核心，解决"路径和我的不一样"）

**核心原则：任何一台远程电脑都能接住，不预设装法、不预设路径、不预设系统。**
客户远程机可能是 Windows/macOS/Linux，装法可能是 官方 install.sh·ps1 / pip 手动 / MSIX / 自定义 `-InstallDir` / `HERMES_HOME` / 客户任意自定义目录。`path_map.py` 全都不写死：

- **客户指定 `--target`（最高优先）**：客户说"我 Hermes 装 X"，直接落 X，不存在则自动 `mkdir -p`。
- **自动多源探测（客户没给 --target 时）**：按可信度排 `HERMES_HOME env > hermes 命令真实所在 > pip Location > 扫描候选目录`，跨 Win/mac/Linux 各系统默认位都扫。
- **expert 落点识别**：在 Hermes 根下找客户实际的 `my-experts/plugins`、`my-experts`、`bots`、`experts` 目录名，没有就按约定建 `my-experts/plugins`。
- **反向路径映射表**：生成 `<HERMES_ROOT>`/`<BOTS_DIR>`/`<HOME>` 占位符，并把干净包里写死的绝对路径自动重写为客户实际路径（彻底消除机器绑定）。
- **按客户系统生成安装脚本**：Windows→`install-bots.ps1`，mac/linux→`install-bots.sh`。
- **机器指纹**：PATH_MAP.json 含 `machine_fingerprint`（OS|arch|user|root 的 sha1），便于审计/排障。

**客户多实例并存场景（同机既有 pip 版又有 install.ps1 版）**：取 `hermes` 命令真实所在（最可信，即客户当前在跑的那个），随机扫描到的候选目录只作兜底，避免误装到非当前实例。

识别后 key/端点保持占位符，交 model-configurator 在远程机填。

### 编码健壮性（客户机路径常含中文）
`path_map.py` 跑命令时按 `utf-8→gbk→latin-1` 多编码兜底解码，客户路径是中文（如"国外模型"）也不会崩。

### 路径候选清单（多几条，宁多勿漏）
探测的 Hermes 根候选按系统列出，**存在几条取几条，全部参与兜底**（客户 `--target` 永远最高）：

| 系统 | 候选路径（存在即参与） |
|------|------------------------|
| Windows | `%LOCALAPPDATA%\hermes`、`…\hermes\hermes-agent`、`…\hermes\bin`、`~\.hermes`、`%ProgramData%\hermes`、`~\Hermes`、`~\hermes`、`D:\Hermes\Python`、`E:\Hermes\Python`、`C:\Hermes\Python`、`F:\Hermes\Python`、`G:\Hermes\Python`、`D:\Hermes`、`E:\Hermes`、`C:\hermes`、`F:\hermes`、`G:\hermes`、`D:\Program Files\Hermes` 等、`%LOCALAPPDATA%\Programs\hermes`、`%LOCALAPPDATA%\Microsoft\Hermes`、`HERMES_HOME env`、`where hermes` 所在、`pip show` Location |
| macOS | `~/.hermes`、`~/Library/Application Support/hermes`、`/usr/local/hermes`、`~/.local/share/hermes`、`~/.local/bin`、`~/hermes`、`~/Hermes`、`/opt/hermes`、`/Applications/Hermes.app`、`HERMES_HOME`、`which hermes` 所在 |
| Linux | `~/.hermes`、`~/.local/share/hermes`、`~/.local/bin`、`~/hermes`、`~/Hermes`、`/usr/local/hermes`、`/opt/hermes`、`/usr/local/bin`、`~/.venvs/hermes`、`~/venv/hermes`、`HERMES_HOME`、`which hermes` 所在 |

**expert/bots 落点候选**（在选定的 Hermes 根下，存在即取）：`my-experts/plugins`、`plugins/my-experts/plugins`、`.workbuddy/plugins/my-experts/plugins`、`~/.workbuddy/plugins/marketplaces/my-experts/plugins`、`~/.workbuddy/plugins/my-experts/plugins`、`.workbuddy/plugins/marketplaces/my-experts`、`my-experts`、`plugins`、`bots`、`experts`、`skills`、`agents`、`~/my-experts/plugins`。

### 安装环节 5 重保险（务必不能装出问题）
`path_map.py` 生成的 `install-bots.ps1` / `.sh` 都带 5 重保险，落地失败必报错、不静默：
1. **中文/特殊字符路径安全**（Win 用 PowerShell 原生 `Copy-Item`，sh 用 `cp -a`，不用易崩的 `unzip`/`*` 通配）
2. **每步显式校验**（包存在 / 解压成功 / 落地数）
3. **落盘完整性自检**（包内 expert 数 == 落地 expert 数，不等即非零退出）
4. **失败不静默**（`$ErrorActionPreference=Stop` + 明确抛错 + 非零码）
5. **装后输出"已装清单 + 下一步"**（可追溯）

> ⚠️ 关键 bug 已堵：**安装脚本必须整目录拷贝（`Copy-Item $e.FullName` / `cp -a $d/.`），不能用 `*` 通配**——`*` 漏掉 `.workbuddy-plugin`/`.codebuddy-plugin` 等隐藏目录，客户装完 expert 缺 `plugin.json` 就注册不上。这是"装出问题"的头号隐患，已修复并实测 5 重保险全绿。

### 工具随包落地（取到包就能装，不缺工具）
干净包内置 `_tools/`（`path_map.py` + `dispatch.py` + `README.txt`），安装脚本落地时同步拷到客户机 `_bots-tools/`。客户机取包后**不需要额外下载任何工具**就能跑全链路。

## 四、全通道分发（防后续出问题：一条断了自动切下一条）

`dispatch.py` 一次推 **3 条通道**，生成客户机**自动降级取包脚本**（`remote-fetch.sh` / `remote-fetch.ps1`）：

```
通道① GitHub（gh-proxy.com 镜像）  ← GFW 下直连 github.com 不稳，走 gh-proxy 稳
   ↓ 拉不到
通道② ntfy.sh 私有 topic            ← 黄金通道，二进制 /raw 直下，topic 自毁 15min
   ↓ 拉不到
通道③ 本地目录 / 网络共享           ← 客户机直接拷包，零网络依赖，最终兜底
```

**客户机只跑一句 `sh ./remote-fetch.sh`**（Windows 跑 `remote-fetch.ps1`），三条通道按序轮询，哪条通走哪条，彻底防"后续出问题拉不到"。拉到手后接 `path_map.py`（路径自适应）→ `install-bots`（落地）。

```bash
# 本机
python pack_bots.py --out bots-clean.zip
python dispatch.py --zip bots-clean.zip --repo <owner>/hermes-bots-port
#   → 推 GitHub(gh-proxy) + ntfy + 生成 remote-fetch.sh/.ps1（三通道自动降级）
```

> GitHub 通道前置：干净包已脱敏，仓库可 public；客户机 `git clone --depth 1 https://gh-proxy.com/https://github.com/<owner>/<repo>` 即可拉。本机 `gh` 已登录，`dispatch.py` 自动复用/建仓 + 推 assets/。

## 四·旧（单通道 ntfy 速记）
仅当只用 ntfy 时（不用全通道），`ship_cmd.py` 一条出"推送 + 取包"。全通道用上面的 `dispatch.py`。

## 五、标准操作流（全通道版）

**本机（主理人）：**
```bash
cd ~/.workbuddy/plugins/marketplaces/my-experts/plugins/hermes-deploy-guild/skills/hermes-deploy/scripts
python pack_bots.py --only "金策宗师团" --out jince.zip    # 精准点单（不传 --only = 全量）
python dispatch.py --zip jince.zip --repo <owner>/hermes-bots-port
# 生成 remote-fetch.sh/.ps1（GitHub/ntfy/本地三通道自动降级）
```
**远程机（客户按系统跑取包 + 安装）：**

Windows：
```powershell
powershell -ExecutionPolicy Bypass -File .\remote-fetch.ps1   # 三通道自动取包
python path_map.py --apply                                     # 路径自适应（或 --target 客户指定）
powershell -ExecutionPolicy Bypass -File .\install-bots.ps1    # 落地 expert
# 再： hermes model 向导填客户自己的 key/端点 → 发 hi 验收
```
macOS / Linux：
```sh
sh ./remote-fetch.sh      # 三通道自动取包
python3 path_map.py --apply
sh ./install-bots.sh
# 再： hermes model 向导填 key/端点 → 发 hi 验收
```

## 六、触发纪律（再强调）

| 用户说法 | 动作 |
|----------|------|
| "帮我装 Hermes" / "一键部署" | **只走 Workflow A，绝不装 bots** |
| "装好了，给他配 bots / 装专家 / 只装金策" | 走本页 Workflow D（精准点单用 `--only`） |
| "换模型 / 换端点 / 配 key" | model-configurator，**不归 bot-shuffler** |
| 拿不准 | 回报主理人确认，不擅自扩 |

## 七、体积与分发稳定性

109M 大头是 133 张 avatar PNG。默认剔除头像 → 干净包 **2.5M**；`--only` 点单更小（金策单包 0.1M）。
`dispatch.py` 的 `--size-limit` 可设体积上限；三通道降级使 ntfy topic 过期/限流不再致命（GitHub/本地兜底）。
