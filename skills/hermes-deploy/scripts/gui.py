"""gui.py - Remote-control GUI automation helper (ctypes only, Python stdlib).

Companion tool of the "Hermes Deploy Guild" expert team. Drives a Sunlogin/AweSun
remote-desktop window from the LOCAL machine: window enumeration, focus, keyboard
and mouse injection, clipboard read/write, and no-focus screenshots.

Requires: Pillow (only for `shot` / `fshot`).

Output directory (screenshots) resolution order:
  1. environment variable  GUI_SHOT_DIR
  2. directory of this script
Filenames: fs.png (full screen), crop.png (see cropregion.py)

Usage examples:
  python gui.py list
  python gui.py rect 123456789
  python gui.py shot
  python gui.py setc cmd.txt          # set local clipboard only
  python gui.py pastein 123456789    # focus remote window + Ctrl+V
  python gui.py ft 123456789 cmd.txt enter
  python gui.py fhk 123456789 win+r
  python gui.py fkN 123456789 backspace 60
  python gui.py wiggle 300 300
"""
import ctypes, ctypes.wintypes as wt, time, sys, json, os

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

SHOT_DIR = os.environ.get("GUI_SHOT_DIR") or os.path.dirname(os.path.abspath(__file__))
FS_PNG = os.path.join(SHOT_DIR, "fs.png")

# --- input constants ---
INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
KEYEVENTF_KEYUP = 0x0002
VK_MAP = {
    'enter': 0x0D, 'tab': 0x09, 'esc': 0x1B, 'backspace': 0x08, 'space': 0x20,
    'shift': 0x10, 'ctrl': 0x11, 'alt': 0x12, 'win': 0x5B, 'delete': 0x2E,
    'home': 0x24, 'end': 0x23, 'left': 0x25, 'up': 0x26, 'right': 0x27, 'down': 0x28,
    'a': 0x41, 'b': 0x42, 'c': 0x43, 'd': 0x44, 'e': 0x45, 'f': 0x46, 'g': 0x47,
    'h': 0x48, 'i': 0x49, 'j': 0x4A, 'k': 0x4B, 'l': 0x4C, 'm': 0x4D, 'n': 0x4E,
    'o': 0x4F, 'p': 0x50, 'q': 0x51, 'r': 0x52, 's': 0x53, 't': 0x54, 'u': 0x55,
    'v': 0x56, 'w': 0x57, 'x': 0x58, 'y': 0x59, 'z': 0x5A,
}


def enum_windows():
    res = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
    def cb(hwnd, lparam):
        if user32.IsWindowVisible(hwnd):
            n = user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, buf, n + 1)
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, cls, 256)
            if buf.value.strip():
                res.append({"hwnd": hwnd, "title": buf.value, "class": cls.value})
        return True

    user32.EnumWindows(cb, 0)
    return res


def find_window(substr):
    for w in enum_windows():
        if substr.lower() in w["title"].lower():
            return w
    return None


def focus(hwnd):
    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    time.sleep(0.3)
    # ALT key trick to bypass SetForegroundWindow lock
    user32.keybd_event(0x12, 0, 0, 0)
    user32.SetForegroundWindow(hwnd)
    user32.keybd_event(0x12, 0, 0x0002, 0)
    time.sleep(0.4)
    if user32.GetForegroundWindow() != hwnd:
        # fallback: minimize then restore
        user32.ShowWindow(hwnd, 6)  # SW_MINIMIZE
        time.sleep(0.3)
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        time.sleep(0.5)
    return user32.GetForegroundWindow() == hwnd


def click(x, y):
    user32.SetCursorPos(int(x), int(y))
    time.sleep(0.08)
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.05)
    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    time.sleep(0.15)


def rightclick(x, y):
    user32.SetCursorPos(int(x), int(y))
    time.sleep(0.08)
    user32.mouse_event(0x0008, 0, 0, 0, 0)  # RIGHTDOWN
    time.sleep(0.05)
    user32.mouse_event(0x0010, 0, 0, 0, 0)  # RIGHTUP
    time.sleep(0.3)


def key(vk, shift=False):
    if shift:
        user32.keybd_event(0x10, 0, 0, 0)
    user32.keybd_event(vk, 0, 0, 0)
    time.sleep(0.03)
    user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
    if shift:
        user32.keybd_event(0x10, 0, KEYEVENTF_KEYUP, 0)
    time.sleep(0.05)


def type_text(s):
    for ch in s:
        vk = user32.VkKeyScanW(ord(ch))
        if vk == -1:
            continue
        shift = bool(vk & 0x100)
        vk = vk & 0xFF
        if shift:
            user32.keybd_event(0x10, 0, 0, 0)
        user32.keybd_event(vk, 0, 0, 0)
        time.sleep(0.02)
        user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
        if shift:
            user32.keybd_event(0x10, 0, KEYEVENTF_KEYUP, 0)
        time.sleep(0.04)


def hotkey(*vks):
    for v in vks:
        user32.keybd_event(v, 0, 0, 0)
        time.sleep(0.05)
    for v in reversed(vks):
        user32.keybd_event(v, 0, KEYEVENTF_KEYUP, 0)
        time.sleep(0.05)


def set_clipboard(text):
    CF_UNICODETEXT = 13
    GMT_MEMMOVE = 0x2002
    # 64-bit safety: set argtypes/restype so handles are not truncated
    kernel32.GlobalAlloc.restype = ctypes.c_void_p
    kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
    data = text.encode("utf-16-le") + b"\x00\x00"
    if not user32.OpenClipboard(0):
        raise OSError("OpenClipboard failed")
    user32.EmptyClipboard()
    h = kernel32.GlobalAlloc(GMT_MEMMOVE, len(data))
    p = kernel32.GlobalLock(h)
    ctypes.memmove(ctypes.c_void_p(p), data, len(data))
    kernel32.GlobalUnlock(h)
    user32.SetClipboardData(CF_UNICODETEXT, h)
    user32.CloseClipboard()


def get_clipboard():
    CF_UNICODETEXT = 13
    if not user32.OpenClipboard(0):
        return None
    try:
        h = user32.GetClipboardData(CF_UNICODETEXT)
        if not h:
            return None
        kernel32.GlobalLock.restype = ctypes.c_void_p
        kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
        p = kernel32.GlobalLock(h)
        if not p:
            return None
        s = ctypes.wstring_at(p)
        kernel32.GlobalUnlock(h)
        return s
    finally:
        user32.CloseClipboard()


def windows_json(substr=None):
    ws = enum_windows()
    if substr:
        ws = [w for w in ws if substr.lower() in w["title"].lower()]
    return json.dumps(ws, ensure_ascii=False)


def _focus_or_die(title):
    w = find_window(title)
    if not w or not focus(w["hwnd"]):
        print("focus-fail")
        sys.exit(1)
    return w


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    if cmd == "list":
        print(windows_json())
    elif cmd == "find":
        print(json.dumps(find_window(sys.argv[2]), ensure_ascii=False))
    elif cmd == "focus":
        w = find_window(sys.argv[2])
        print("focused" if w and focus(w["hwnd"]) else "fail")
    elif cmd == "click":
        click(float(sys.argv[2]), float(sys.argv[3]))
        print("clicked")
    elif cmd == "rightclick":
        rightclick(float(sys.argv[2]), float(sys.argv[3]))
        print("rightclicked")
    elif cmd == "type":
        type_text(sys.argv[2])
        print("typed")
    elif cmd == "typefile":
        with open(sys.argv[2], "r", encoding="utf-8") as f:
            type_text(f.read())
        print("typed-file")
    elif cmd == "key":
        key(VK_MAP[sys.argv[2].lower()])
        print("keyed")
    elif cmd == "hotkey":
        hotkey(*[VK_MAP[v.lower()] for v in sys.argv[2].split("+")])
        print("hotkeyed")
    elif cmd == "ft":
        # focus window then TYPE file content in the same process
        _focus_or_die(sys.argv[2])
        with open(sys.argv[3], "r", encoding="utf-8") as f:
            txt = f.read()
        if len(sys.argv) > 4 and sys.argv[4] == "enter":
            type_text(txt.rstrip("\n"))
            key(VK_MAP["enter"])
        else:
            type_text(txt)
        fg = user32.GetForegroundWindow()
        n = user32.GetWindowTextLengthW(fg)
        buf = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(fg, buf, n + 1)
        print("typed-in:", buf.value)
    elif cmd == "fhk":
        # focus window then send hotkey combo
        _focus_or_die(sys.argv[2])
        hotkey(*[VK_MAP[v.lower()] if v.lower() in VK_MAP else int(v)
                 for v in sys.argv[3].split("+")])
        print("hotkey-in")
    elif cmd == "fpaste":
        # focus window, set clipboard, wait, paste via Ctrl+V (one-shot; prefer setc+pastein)
        _focus_or_die(sys.argv[2])
        with open(sys.argv[3], "r", encoding="utf-8") as f:
            txt = f.read().rstrip("\n")
        set_clipboard(txt)
        time.sleep(2.5)
        hotkey(VK_MAP["ctrl"], 0x56)  # Ctrl+V
        time.sleep(0.5)
        print("pasted")
    elif cmd == "fk":
        # focus window then press one key
        _focus_or_die(sys.argv[2])
        key(VK_MAP[sys.argv[3].lower()])
        print("keyed-in")
    elif cmd == "fkN":
        # focus window then press a key N times (e.g. backspace 60 to clear a line)
        _focus_or_die(sys.argv[2])
        vk = VK_MAP[sys.argv[3].lower()]
        n = int(sys.argv[4])
        for _ in range(n):
            key(vk)
        print("keyed-in-x", n)
    elif cmd == "wiggle":
        # move cursor around to force video frame updates
        cx, cy = int(float(sys.argv[2])), int(float(sys.argv[3]))
        for dx, dy in ((-40, 0), (40, 0), (-30, 20), (30, -20), (0, 0)):
            user32.SetCursorPos(cx + dx, cy + dy)
            time.sleep(0.15)
        print("wiggled")
    elif cmd == "readclip":
        print(json.dumps(get_clipboard(), ensure_ascii=False))
    elif cmd == "setc":
        # set clipboard from file only (no focus, no paste)
        with open(sys.argv[2], "r", encoding="utf-8") as f:
            set_clipboard(f.read().rstrip("\n"))
        print("clip-set")
    elif cmd == "pastein":
        # focus window and send Ctrl+V only (clipboard must be set beforehand)
        _focus_or_die(sys.argv[2])
        time.sleep(0.5)
        hotkey(VK_MAP["ctrl"], 0x56)
        time.sleep(0.4)
        print("pasted-in")
    elif cmd == "rect":
        w = find_window(sys.argv[2])
        if not w:
            print("notfound")
            sys.exit(1)

        class RECT(ctypes.Structure):
            _fields_ = [("l", ctypes.c_long), ("t", ctypes.c_long),
                        ("r", ctypes.c_long), ("b", ctypes.c_long)]

        rc = RECT()
        user32.GetWindowRect(w["hwnd"], ctypes.byref(rc))
        print(json.dumps({"l": rc.l, "t": rc.t, "r": rc.r, "b": rc.b}))
    elif cmd == "shot":
        # no-focus screenshot
        time.sleep(0.3)
        from PIL import ImageGrab
        ImageGrab.grab().save(FS_PNG)
        print("shot", FS_PNG)
    elif cmd == "fshot":
        # focus window, wait, screenshot
        _focus_or_die(sys.argv[2])
        time.sleep(0.8)
        from PIL import ImageGrab
        ImageGrab.grab().save(FS_PNG)
        print("shot", FS_PNG)
    else:
        print("unknown command:", cmd)
        sys.exit(2)
