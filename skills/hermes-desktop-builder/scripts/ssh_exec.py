#!/usr/bin/env python
"""Generic SSH driver for Windows servers (paramiko).

Usage (credentials via env vars, never hardcoded):
    SS_HOST=1.2.3.4 SS_USER=Administrator SS_PASS='xxx' python ssh_exec.py put <local> <remote>
    SS_HOST=1.2.3.4 SS_USER=Administrator SS_PASS='xxx' python ssh_exec.py run <command>
    SS_HOST=1.2.3.4 SS_USER=Administrator SS_PASS='xxx' python ssh_exec.py putrun <local.ps1> [timeout_sec]

putrun: uploads the .ps1 to the user's home dir, then executes
        powershell -ExecutionPolicy Bypass -File <remote>.
NOTE (lesson learned):
  - Do NOT pipe multiline scripts into `powershell -Command -` via exec_command stdin;
    paramiko raises "OSError: File not open for writing". Always SFTP a .ps1 file
    and run it with -File.
  - Long builds: run via foreground exec_command with a generous timeout from a
    background task, or install a scheduled task (see install_build_task.ps1) so
    the build survives SSH disconnects (SSH close kills the process tree on Windows).
"""
import os
import sys

import paramiko

HOST = os.environ.get("SS_HOST", "")
USER = os.environ.get("SS_USER", "")
PASS = os.environ.get("SS_PASS", "")


def connect():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, 22, USER, PASS, timeout=20)
    return c


def put_bom(c, local, remote):
    """SFTP upload; prepend UTF-8 BOM if missing (PS 5.1 reads non-BOM files as ANSI)."""
    with open(local, "rb") as fp:
        data = fp.read()
    if not data.startswith(b"\xef\xbb\xbf"):
        data = b"\xef\xbb\xbf" + data
    sftp = c.open_sftp()
    with sftp.open(remote, "wb") as fp:
        fp.write(data)
    sftp.close()


def main():
    if not HOST or not USER:
        print("ERROR: set SS_HOST / SS_USER / SS_PASS env vars first")
        sys.exit(2)
    mode = sys.argv[1]
    c = connect()
    try:
        if mode == "put":
            local, remote = sys.argv[2], sys.argv[3]
            put_bom(c, local, remote)
            print("uploaded ->", remote)
        elif mode == "run":
            cmd = sys.argv[2]
            to = int(sys.argv[3]) if len(sys.argv) > 3 else 120
            _, o, e = c.exec_command(cmd, timeout=to)
            print("OUT:\n" + o.read().decode("utf-8", "replace").strip()[-5000:])
            err = e.read().decode("utf-8", "replace").strip()
            if err:
                print("ERR:\n" + err[:1500])
        elif mode == "putrun":
            local = sys.argv[2]
            to = int(sys.argv[3]) if len(sys.argv) > 3 else 300
            remote = "C:/Users/%s/%s" % (USER, os.path.basename(local))
            put_bom(c, local, remote)
            print("uploaded ->", remote)
            _, o, e = c.exec_command(
                "powershell.exe -ExecutionPolicy Bypass -File " + remote, timeout=to
            )
            print("OUT:\n" + o.read().decode("utf-8", "replace").strip()[-5000:])
            err = e.read().decode("utf-8", "replace").strip()
            if err:
                print("ERR:\n" + err[:1500])
        else:
            print("unknown mode:", mode)
            sys.exit(2)
    finally:
        c.close()


if __name__ == "__main__":
    main()
