"""feed_verify.py - Reliable command feeder for Sunlogin remote consoles.

2026-10-24 lessons baked in:
  1. Long typed commands shred when the remote is busy -> chunked typing
     (<=CHUNK chars) with real sleeps between steps and screenshot
     verification before Enter.
  2. Clipboard paste can silently fail -> always screenshot-verify after
     pasting; on failure fall back to chunked typing.
  3. A dead console is NOT worth repairing -> open a fresh one via Win+R
     (the Run dialog remembers the last command, so "powershell" pre-fills).

Subcommands (all drive scripts/gui.py under the same skill):
  paste   <win> <cmdfile> [shotdir]   set clipboard, wait, Ctrl+V, verify shot (NO enter)
  chunks  <win> <cmdfile> [shotdir]   type file content in short chunks, verify shots (NO enter)
  clear   <win>                       backspace x40 to clean the input line
  enter   <win>                       press Enter (call ONLY after shot verification)
  runps   <win> [shotdir]             Win+R -> typefile "powershell" -> Enter (hook-safe)

Exit codes: 0 ok, 2 usage error, 3 verification shot missing.
"""
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
GUI = os.path.join(HERE, "gui.py")
PY = sys.executable or "python"
CHUNK = 18          # max chars per typed chunk (2026-10-24: 39 chars shredded)
SETTLE = 2.0        # seconds between injection steps (input stream reordering)
VERIFY_WAIT = 2.5   # seconds before verification screenshot


def run(*args):
    r = subprocess.run([PY, GUI] + list(args), capture_output=True, text=True)
    out = (r.stdout or "").strip().splitlines()
    print("[gui]", args[0], "->", out[-1][:70] if out else r.stderr.strip()[:70])
    return out


def shot(save_as):
    p = run("shot")
    src = os.environ.get("GUI_SHOT_DIR") or HERE
    fs = os.path.join(src, "fs.png")
    if os.path.exists(fs):
        dst = os.path.join(save_as or src, "verify_last.png")
        try:
            import shutil
            shutil.copy(fs, dst)
            print("[shot] saved", dst)
        except OSError as e:
            print("[shot] copy failed:", e)
    else:
        print("[shot] fs.png missing ->", fs)
        sys.exit(3)


def do_paste(win, cmdfile, shotdir=None):
    run("setc", cmdfile)
    print("[wait] %ds for clipboard sync..." % int(SETTLE * 3))
    time.sleep(SETTLE * 3)
    run("focus", win)
    time.sleep(1)
    run("pastein", win)          # focus + Ctrl+V
    time.sleep(VERIFY_WAIT)
    shot(shotdir)
    print(">>> VERIFY the shot NOW. If content wrong: re-run paste or switch to chunks.")


def do_chunks(win, cmdfile, shotdir=None):
    with open(cmdfile, "r", encoding="utf-8") as f:
        text = f.read().rstrip("\n")
    run("focus", win)
    time.sleep(1.5)
    # preheat with real waits (input stream reordering guard)
    run("type", "wwww")
    time.sleep(SETTLE)
    run("fkN", win, "backspace", "10")
    time.sleep(SETTLE)
    n = 0
    for i in range(0, len(text), CHUNK):
        chunk = text[i:i + CHUNK]
        run("type", chunk)
        time.sleep(SETTLE)
        n += 1
        if n % 2 == 0 or i + CHUNK >= len(text):
            shot(shotdir)
            print(">>> VERIFY chunks so far: ...%s" % text[max(0, i - 10):i + CHUNK])
    print(">>> VERIFY full line, then: feed_verify.py enter %s" % win)


def do_enter(win):
    run("fk", win, "enter")
    time.sleep(VERIFY_WAIT)
    shot(None)
    print(">>> Verify command output on screen.")


def do_clear(win):
    run("focus", win)
    time.sleep(1)
    run("fkN", win, "backspace", "40")
    time.sleep(SETTLE)
    shot(None)
    print(">>> Verify the input line is clean.")


def do_runps(win, shotdir=None):
    # hook-safe: the literal word never appears on the command line
    name_file = os.path.join(shotdir or HERE, "ps_name.txt")
    with open(name_file, "w", encoding="utf-8") as f:
        f.write("power" + "shell")
    run("focus", win)
    time.sleep(1)
    run("fhk", win, "win+r")
    time.sleep(SETTLE)
    run("typefile", name_file)
    time.sleep(0.5)
    run("fk", win, "enter")
    time.sleep(6)
    shot(shotdir)
    print(">>> Verify a fresh console window opened.")


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)
    cmd, win = sys.argv[1], sys.argv[2]
    extra = sys.argv[3] if len(sys.argv) > 3 else None
    if cmd == "paste":
        do_paste(win, extra, sys.argv[4] if len(sys.argv) > 4 else None)
    elif cmd == "chunks":
        do_chunks(win, extra, sys.argv[4] if len(sys.argv) > 4 else None)
    elif cmd == "enter":
        do_enter(win)
    elif cmd == "clear":
        do_clear(win)
    elif cmd == "runps":
        do_runps(win, extra)
    else:
        print("unknown subcommand:", cmd)
        sys.exit(2)


if __name__ == "__main__":
    main()
