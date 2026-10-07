# 01 · GitHub 被墙环境桌面端构建破局原理

> 2026-10-07 实战验证于 Windows Server 2022（101.35.12.205），Hermes 源码 commit 3f62bc5。
> 耗时 4 小时踩坑后收敛为本方案；构建成功率 100%，重打 62 秒。

## 1. 桌面端是什么

`apps/desktop` 是 monorepo 里的独立 Electron 应用：

```
npm run pack = npm run build（vite 渲染层，~7-8 分钟）
             + npm run builder -- --dir --publish never（electron-builder 产出 release\win-unpacked）
```

electron-builder 27(alpha) 的打包管线：
`scripts/run-electron-builder.mjs` → `prepare-packaging-tools.mjs`（acquirePackagingTools）→ 下载工具链 → 写 `build\packager\win32-x64\prepared.json` → run-electron-builder 消费 prepared.json → `-c.toolsets.<name>.url=file://...` 传给 electron-builder。

## 2. 为什么被墙就死

| 工具集 | 用途 | 来源 | 被墙时 |
|---|---|---|---|
| electron | JS 解包（--dir 必需） | GitHub releases | ✅ 可绕（npmmirror 有镜像） |
| 7zip (7za) | zip 解压 | GitHub electron-builder-binaries | ❌ npmmirror 的 7zip@1.0.1 sha256 与官方不符，sumchecker 硬校验炸 |
| icons | 图标转换 | GitHub electron-builder-bin（ICONS_LATEST=1.2.1） | ❌ npmmirror 无此仓库，gh-proxy 对二进制返回错误页 |
| winCodeSign | rcedit/signtool/makeappx/Azure dlib/.NET（WIN_CODESIGN_LATEST=1.3.0） | GitHub electron-builder-bin | ❌ 同上 |

**关键洞察**：`--dir` 不签名、不打安装包 → 实际只执行 rcedit（改 exe 图标/元数据）。signtool/makeappx/dlib/.NET 只是被 `readPackagingInputs` **校验存在**，不被运行。

## 3. 破局三步

### 步骤① dir-only 补丁（跳过 7zip/icons，伪造 winCodeSign+windows）

`isDirOnly = formats == ['dir']` 时：
- 跳过 `sevenZip.getPath7za()` 和 `icons.getIconsToolsetPath()`（返回 null，不写进 toolsets）
- winCodeSign 工具集：从 `node_modules/rcedit/bin` 拷 `rcedit-x64.exe`/`rcedit-x86.exe` 到工具集根，并在 `x64\` 子目录放 `signtool.exe`（从 `@electron/windows-sign/vendor` 或 `electron-winstaller/vendor` 拷）+ `makeappx.exe`（占位空文件）
- **伪造 `windows` 对象**：`{ dotnetRoot: <真实目录>, signtool: <真实文件>, makeappx: <占位>, dlib: <占位> }` —— 因为 `prepared-packaging.mjs` 的 `readPackagingInputs`（第 130 行附近）对 win32 硬性要求 `result.windows`、`result.toolsets.winCodeSign`、`result.windows.dotnetRoot` 三者非空，缺一报 `Missing Windows tool selection`

运行时行为差异（为什么伪造能过）：
- `ensureWindowsBundleTools` 只在**签名/MSIX 任务**（batch-sign-binaries.mjs、sign-msix.mjs）被调用，`--dir` 不走 → 假工具不会被真用
- electron-builder 自定义 winCodeSign 工具集只要求 root 有 rcedit-x64/x86.exe（目录型 toolset）

### 步骤② electron 走 npmmirror

`ELECTRON_MIRROR=https://registry.npmmirror.com/-/binary/electron/`
- `@electron/get` 在无校验和时自动 `unsafelyDisableChecksums`（SHASUMS 404 无碍，软失败）
- npmmirror 的 electron zip 经 cdn 302 可用（实测 ~614KB/s 起步）

### 步骤③ 删掉 ELECTRON_BUILDER_DANGEROUSLY_ALLOW_HTTP（最反直觉的一步）

`validateSecuredUrl`（app-builder-lib/dist/util/envUtil.js）逻辑：
- 设了该变量 → `file://` 被接受为合法 **url 类型** toolset → url 类型强制要 `checksum` → 报 `ToolsetCustom.checksum is required for url toolsets`
- 不设 → `file://` 走 **directory 类型** → 不需要 checksum，路径直接用

教训：这个变量本是当年给 http 镜像兜底的，在"本地 file:// 工具集"场景下是**反向毒药**。

## 4. 校验链全景（出问题按此排查）

```
prepare 阶段：
  prepare-packaging-tools.mjs（补丁版）
    → electron.zip 下载（npmmirror）✅
    → 伪造 toolsets{winCodeSign, [无 sevenZip, 无 icons]} + windows{dotnetRoot,...}
    → 写 build\packager\win32-x64\prepared.json
消费阶段：
  run-electron-builder.mjs:143 readPackagingInputs(prepared.json)
    → 校验 windows/winCodeSign/dotnetRoot 非空（步骤①伪造过关）
    → 校验 toolsets.sevenZip / toolsets.icons 引用（dir-only 时 undefined，代码路径天然跳过）
  electron-builder -c.toolsets.winCodeSign.url=file://...
    → 无 DANGEROUSLY_ALLOW_HTTP → directory 类型 → 直接用 ✅
    → rcedit-x64.exe 嵌图标 ✅
```

## 5. 提速原理（457s → 62s）

vite 渲染层构建占 ~85% 时间且**产物在 `apps\desktop\dist`（builder 不清除它）**。只要前端源码没改：
`npm run builder -- --dir --publish never` 单跑 = prepare(~20s) + electron-builder(~40s)。

经验法则：
- 改打包补丁/配置 → builder-only
- 改前端源码/升级仓库 → 全量 pack
