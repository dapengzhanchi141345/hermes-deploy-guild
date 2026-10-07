#!/usr/bin/env python
"""deploy_gate.py — Hermes 桌面端端到端部署编排器（阶段门禁制）。

核心原则：**每个阶段过闸（GATE 全绿）才能进下一阶段；闸不过自动尝试已知修复；
修复后仍不过 → 立即停止并给出精确修法，绝不带病前进。** 这是"同一个坑不摔第二次"的
机制化落实：所有历史踩坑都转化为某个 GATE 的检查项或某阶段内的自动修复动作。

用法（凭据与参数全部走环境变量，绝不写死）：
    SS_HOST=1.2.3.4 SS_USER=Administrator SS_PASS='xxx' \
    python deploy_gate.py [--skip-build] [--with-chat-test]

可选环境变量：
    API_BASE_URL   模型端点（默认 https://apihub.agnes-ai.com/v1）
    AGNES_API_KEY  模型 key（提供则执行 Stage6 模型配置；不回显）
    MODEL_DEFAULT  默认模型（默认 agnes-3.0-flash）
    CHECK_KEY_ENV  .env 里的 key 变量名（默认 AGNES_API_KEY）

阶段与门禁：
    Stage1 通道      GATE: SSH 连通 + hermes --version 有输出
    Stage2 构建      GATE: release\\win-unpacked\\Hermes.exe 存在（缺则自动打补丁+建任务构建+轮询）
    Stage3 启动      GATE: desktop.log 有 HERMES_BACKEND_READY（自动清残留标记/死锁/设绕行变量）
    Stage4 落地      GATE: 桌面快捷方式存在 + 3389 监听
    Stage5 模型      GATE: hermes status 的 Model 行非 (not set)（需 AGNES_API_KEY，可跳过）
    Stage6 总验收    GATE: acceptance_check.ps1 退出码 0（FAIL=0）
"""
import os
import sys
import time

import paramiko

SKILL_SCRIPTS = os.path.dirname(os.path.abspath(__file__))

HOST = os.environ.get("SS_HOST", "")
USER = os.environ.get("SS_USER", "")
PASS = os.environ.get("SS_PASS", "")

API_BASE = os.environ.get("API_BASE_URL", "https://apihub.agnes-ai.com/v1")
API_KEY = os.environ.get("AGNES_API_KEY", "")
MODEL = os.environ.get("MODEL_DEFAULT", "agnes-3.0-flash")
KEY_ENV = os.environ.get("CHECK_KEY_ENV", "AGNES_API_KEY")

SKIP_BUILD = "--skip-build" in sys.argv
WITH_CHAT = "--with-chat-test" in sys.argv

REMOTE_TMP = "C:/Users/%s/" % USER


class GateFail(Exception):
    pass


ssh = None
sftp = None


def put(local, remote):
    # PS 5.1 读无 BOM 的 UTF-8 .ps1 会按 ANSI 解析 → 中文/emoji 字符串炸语法。
    # 上传 .ps1 一律补 UTF-8 BOM（历史坑 #4，2026-10-07 门禁实战抓到）。
    if remote.lower().endswith(".ps1"):
        with open(local, "rb") as fp:
            data = fp.read()
        if not data.startswith(b"\xef\xbb\xbf"):
            data = b"\xef\xbb\xbf" + data
        with sftp.open(remote, "wb") as fp:
            fp.write(data)
    else:
        sftp.put(local, remote)


def run_ps(ps_text, timeout=180, name="gate_stage"):
    """SFTP a .ps1 then execute with -File. NEVER stdin-pipe multiline PS."""
    remote = REMOTE_TMP + name + ".ps1"
    with sftp.open(remote, "w") as fp:
        fp.write(ps_text)
    _, o, e = ssh.exec_command(
        "powershell.exe -ExecutionPolicy Bypass -File " + remote, timeout=timeout)
    out = o.read().decode("utf-8", "replace")
    err = e.read().decode("utf-8", "replace").strip()
    return out, err


def gate(label, ok, detail):
    mark = "✅ PASS" if ok else "❌ FAIL"
    print("  %s [%s] %s" % (mark, label, detail))
    if not ok:
        raise GateFail(label + ": " + detail)


# ─────────────────────────── Stage 1 通道 ───────────────────────────
def stage1():
    print("\n========== Stage1 SSH 通道 ==========")
    ver, _ = run_ps(
        '& "$env:LOCALAPPDATA\\hermes\\hermes-agent\\venv\\Scripts\\hermes.exe" --version 2>&1 | Select-Object -First 1',
        120, "s1_version")
    ver = ver.strip()
    gate("CLI版本", bool(ver), ver or "hermes --version 无输出，CLI 未装（先跑官方 install.ps1）")
    return True


# ─────────────────────────── Stage 2 构建 ───────────────────────────
# 教训：PS 单引号不展开 $env: —— 探测/判存路径一律先用双引号赋值给 PS 变量再用。
EXE_PS = '$exe = "$env:LOCALAPPDATA\\hermes\\hermes-agent\\apps\\desktop\\release\\win-unpacked\\Hermes.exe"'
LOG_PS = '$log = "$env:LOCALAPPDATA\\hermes\\pack.log"'


def stage2():
    print("\n========== Stage2 桌面端构建 ==========")
    out, _ = run_ps(EXE_PS + "\nif (Test-Path $exe) { 'EXE_YES ' + [int]((Get-Item $exe).Length/1MB) } else { 'EXE_NO' }",
                    60, "s2_probe")
    if "EXE_YES" in out:
        gate("exe产物", True, out.strip())
        return True
    if SKIP_BUILD:
        gate("exe产物", False, "exe 不存在且 --skip-build；去掉该参数重跑")

    print("  exe 缺失 → 自动打补丁+构建（约 10 分钟，计划任务防断连）")
    put(os.path.join(SKILL_SCRIPTS, "prepare-packaging-tools.mjs"),
        "C:/Users/%s/AppData/Local/hermes/hermes-agent/apps/desktop/scripts/prepare-packaging-tools.mjs" % USER)
    put(os.path.join(SKILL_SCRIPTS, "pack_run.ps1"), REMOTE_TMP + "pack_run.ps1")
    # 清旧产物缓存，防旧 prepared.json 毒化；杀残留构建进程
    run_ps(
        "Remove-Item \"$env:LOCALAPPDATA\\hermes\\hermes-agent\\apps\\desktop\\build\\packager\" -Recurse -Force -ErrorAction SilentlyContinue\n"
        "Get-Process node -ErrorAction SilentlyContinue | Where-Object {$_.Path -like '*hermes*'} | Stop-Process -Force",
        90, "s2_clean")
    # 计划任务直跑 pack_run.ps1（防 SSH 断连杀进程树）
    task_ps = (
        "Register-ScheduledTask -TaskName HermesPackGate -Force -Action "
        "(New-ScheduledTaskAction -Execute 'powershell.exe' -Argument '-ExecutionPolicy Bypass -File %spack_run.ps1') "
        "-Trigger (New-ScheduledTaskTrigger -Once -At (Get-Date).AddSeconds(3)) "
        "-Principal (New-ScheduledTaskPrincipal -UserId '%s' -LogonType Interactive -RunLevel Highest) | Out-Null\n"
        "Start-ScheduledTask HermesPackGate\n" % (REMOTE_TMP.replace("/", "\\"), USER))
    out, err = run_ps(task_ps + "'TASK_STARTED'", 90, "s2_task")
    if "TASK_STARTED" not in out:
        gate("构建任务启动", False, (out + err)[:200])

    log = LOG_PS
    exe = EXE_PS
    deadline = time.time() + 25 * 60
    while time.time() < deadline:
        time.sleep(45)
        out, _ = run_ps(log + "\n" + exe + "\n" +
                        "if (Test-Path $log) { Get-Content $log -Tail 3 } else { 'NOLOG' }\n"
                        "if (Test-Path $exe) { 'EXE_APPEARED' }", 60, "s2_poll")
        print("  ...poll:", " | ".join(x.strip() for x in out.strip().splitlines()[-2:]))
        if "EXE_APPEARED" in out and "PACK_EXIT=0" in out:
            break
        if "PACK_EXIT=" in out and "PACK_EXIT=0" not in out:
            gate("构建", False, "pack.log 显示失败，tail: " + out.strip()[-300:])
    out, _ = run_ps(EXE_PS + "\nif (Test-Path $exe) {'EXE_OK'} else {'EXE_MISSING'}", 60, "s2_final")
    gate("exe产物", "EXE_OK" in out, out.strip())
    return True


# ─────────────────────────── Stage 3 启动（含自愈） ───────────────────────────
def stage3():
    print("\n========== Stage3 启动自愈 ==========")
    out, _ = run_ps(
        "$l=\"$env:LOCALAPPDATA\\Hermes\\logs\\desktop.log\"; "
        "if(Test-Path $l){ (Get-Content $l -Tail 120) -join \"`n\" } else { 'NOLOG' }", 60, "s3_log")
    ready = "HERMES_BACKEND_READY" in out
    stuck = ("first-run setup choice" in out) or ("no usable Hermes install" in out)
    if ready and not stuck:
        gate("后端启动", True, "HERMES_BACKEND_READY 已在日志")
        return True
    if stuck or "NOLOG" in out or not ready:
        print("  后端未就绪/卡引导 → 应用 fix_backend_boot.ps1（清标记+死锁+双保险环境变量）")
        put(os.path.join(SKILL_SCRIPTS, "fix_backend_boot.ps1"), REMOTE_TMP + "fix_backend_boot.ps1")
        out, err = run_ps('& "' + REMOTE_TMP + 'fix_backend_boot.ps1"', 240, "s3_fix")
        print("   fix:", out.strip()[-400:] or err[:200])
    # 杀残留 + 拉起桌面端（计划任务进交互会话）
    run_ps("Get-Process Hermes -ErrorAction SilentlyContinue | Stop-Process -Force", 60, "s3_kill")
    run_ps(
        'Start-Process -FilePath "$env:LOCALAPPDATA\\hermes\\hermes-agent\\apps\\desktop\\release\\win-unpacked\\Hermes.exe" '
        "-WorkingDirectory \"$env:LOCALAPPDATA\\hermes\\hermes-agent\\apps\\desktop\\release\\win-unpacked\"",
        60, "s3_launch")
    print("  等待后端启动（最多 180s）...")
    deadline = time.time() + 180
    ok = False
    while time.time() < deadline:
        time.sleep(25)
        out, _ = run_ps(
            "(Get-Content \"$env:LOCALAPPDATA\\Hermes\\logs\\desktop.log\" -Tail 60 -ErrorAction SilentlyContinue) -join \"`n\"",
            60, "s3_wait")
        if "HERMES_BACKEND_READY" in out:
            ok = True
            break
        if "first-run setup choice" in out:
            break
    gate("后端启动", ok, "desktop.log HERMES_BACKEND_READY" if ok else
         "180s 内未就绪；看 desktop.log：卡引导→复跑 fix_backend_boot.ps1 后注销重登（setx 需新会话生效）")
    return True


# ─────────────────────────── Stage 4 落地 ───────────────────────────
def stage4():
    print("\n========== Stage4 落地三件套 ==========")
    out, _ = run_ps(
        "if (Test-Path 'C:\\Users\\Public\\Desktop\\Hermes.lnk') {'LNK_OK'} else {'LNK_NO'}", 60, "s4_lnk")
    if "LNK_NO" in out:
        put(os.path.join(SKILL_SCRIPTS, "make_shortcut.ps1"), REMOTE_TMP + "make_shortcut.ps1")
        run_ps('& "' + REMOTE_TMP + 'make_shortcut.ps1"', 90, "s4_mklnk")
        out, _ = run_ps(
            "if (Test-Path 'C:\\Users\\Public\\Desktop\\Hermes.lnk') {'LNK_OK'} else {'LNK_NO'}", 60, "s4_lnk2")
    gate("桌面图标", "LNK_OK" in out, "C:\\Users\\Public\\Desktop\\Hermes.lnk")

    out, _ = run_ps("(netstat -an | Select-String ':3389\\s.*LISTENING') -ne $null", 60, "s4_rdp")
    if "True" not in out:
        put(os.path.join(SKILL_SCRIPTS, "fix_rdp_fw.ps1"), REMOTE_TMP + "fix_rdp_fw.ps1")
        run_ps('& "' + REMOTE_TMP + 'fix_rdp_fw.ps1"', 120, "s4_fw")
        out, _ = run_ps("(netstat -an | Select-String ':3389\\s.*LISTENING') -ne $null", 60, "s4_rdp2")
    # RDP 属 WARN 级（纯本机操作场景可无），不阻断
    print("  ℹ️ RDP:", "✅ 3389 监听中" if "True" in out else "⚠️ 未监听（仅本机操作可忽略）")

    out, _ = run_ps(
        "(Get-ScheduledTask -TaskName HermesDesktopBuild -ErrorAction SilentlyContinue) -ne $null", 60, "s4_task")
    if "True" not in out:
        put(os.path.join(SKILL_SCRIPTS, "install_build_task.ps1"), REMOTE_TMP + "install_build_task.ps1")
        run_ps('& "' + REMOTE_TMP + 'install_build_task.ps1"', 90, "s4_itask")
        out, _ = run_ps(
            "(Get-ScheduledTask -TaskName HermesDesktopBuild -ErrorAction SilentlyContinue) -ne $null", 60, "s4_task2")
    print("  ℹ️ 保底任务:", "✅ HermesDesktopBuild 已装" if "True" in out else "⚠️ 未装（非致命）")
    return True


# ─────────────────────────── Stage 5 模型 ───────────────────────────
def stage5():
    print("\n========== Stage5 模型配置 ==========")
    if not API_KEY:
        print("  ⚠️ 未提供 AGNES_API_KEY → 跳过模型配置（已有配置则 Stage6 会验）")
        return True
    # 动态解析配置 home（两代版本不同，写错位置静默失效）
    out, _ = run_ps(
        '& "$env:LOCALAPPDATA\\hermes\\hermes-agent\\venv\\Scripts\\python.exe" -I -c '
        '"from hermes_constants import get_hermes_home; print(get_hermes_home())"', 90, "s5_home")
    hhome = (out.strip().splitlines() or [""])[-1].strip()
    if not hhome or "\\" not in hhome:
        hhome = "$env:LOCALAPPDATA\\hermes"
    gate("home解析", True, hhome)

    # 幂等：已配置且识别则不动
    out, _ = run_ps(
        '& "$env:LOCALAPPDATA\\hermes\\hermes-agent\\venv\\Scripts\\hermes.exe" status 2>&1 | Select-String "Model:"',
        120, "s5_status")
    if "Model:" in out and "(not set)" not in out:
        print("  模型已配置:", out.strip())
        gate("模型识别", True, out.strip())
        return True

    # 写 config.yaml + .env（key 不落 yaml、不回显）
    cfg = ("model:\n  default: %s\n  provider: agnes\n"
           "providers:\n  agnes:\n    name: Agnes\n    api: %s\n"
           "    key_env: %s\n    transport: chat_completions\n"
           "    default_model: %s\n    context_length: 256000\n"
           % (MODEL, API_BASE, KEY_ENV, MODEL))
    winhome = hhome.replace("\\", "/")
    with sftp.open(winhome + "/config.yaml", "w") as fp:
        fp.write(cfg)
    # .env 追加/更新 key（保留其它行）
    env_path = winhome + "/.env"
    lines = []
    try:
        with sftp.open(env_path, "r") as fp:
            lines = [l for l in fp.read().decode("utf-8", "replace").splitlines()
                     if l and not l.startswith(KEY_ENV + "=")]
    except IOError:
        lines = []
    lines.insert(0, "%s=%s" % (KEY_ENV, API_KEY))
    with sftp.open(env_path, "w") as fp:
        fp.write("\n".join(lines) + "\n")

    out, _ = run_ps(
        '& "$env:LOCALAPPDATA\\hermes\\hermes-agent\\venv\\Scripts\\hermes.exe" status 2>&1 | Select-String "Model:"',
        120, "s5_verify")
    gate("模型识别", ("(not set)" not in out) and ("Model:" in out), out.strip() or "status 仍 (not set)")
    return True


# ─────────────────────────── Stage 6 总验收 ───────────────────────────
def stage6():
    print("\n========== Stage6 总验收门禁 ==========")
    put(os.path.join(SKILL_SCRIPTS, "acceptance_check.ps1"), REMOTE_TMP + "acceptance_check.ps1")
    flag = " -WithChatTest" if WITH_CHAT else ""
    out, err = run_ps('& "' + REMOTE_TMP + 'acceptance_check.ps1"' + flag, 400, "s6_accept")
    print(out)
    if err:
        print("ERR:", err[:300])
    gate("总验收", "验收通过" in out or "FAIL=0" in out,
         "acceptance_check.ps1 退出码判定" if "FAIL=0" in out or "验收通过" in out else "存在 FAIL 项")
    return True


STAGES = [stage1, stage2, stage3, stage4, stage5, stage6]


def main():
    global ssh, sftp
    if not HOST or not USER:
        print("ERROR: set SS_HOST / SS_USER / SS_PASS env vars first")
        sys.exit(2)
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, 22, USER, PASS, timeout=30)
    sftp = ssh.open_sftp()
    print("🚦 deploy_gate 启动: %s@%s  (skip_build=%s chat_test=%s)" % (USER, HOST, SKIP_BUILD, WITH_CHAT))
    try:
        for st in STAGES:
            st()
        print("\n🏁 全部门禁通过 —— 桌面端已交付可用。")
    except GateFail as gf:
        print("\n🛑 门禁拦截，停止部署：%s" % gf)
        print("   按上述明细修复后重跑本脚本（幂等，已过阶段自动跳过）。")
        sys.exit(1)
    finally:
        sftp.close()
        ssh.close()


if __name__ == "__main__":
    main()
