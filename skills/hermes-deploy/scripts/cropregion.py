"""cropregion.py - Crop an arbitrary screen region and upscale it.

Companion tool of the "Hermes Deploy Guild" expert team. Coordinates are given in
the LOGICAL desktop space reported by GetSystemMetrics (e.g. 1280x720 for a
1280x720 remote desktop) and are scaled to the real grabbed image automatically.

Usage:
  python cropregion.py x1 y1 x2 y2 [scale]

Output: crop.png inside GUI_SHOT_DIR (default: this script's directory)
Requires: Pillow
"""
import ctypes
import os
import sys

from PIL import ImageGrab

user32 = ctypes.windll.user32
SHOT_DIR = os.environ.get("GUI_SHOT_DIR") or os.path.dirname(os.path.abspath(__file__))

sw, sh = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)

im = ImageGrab.grab()
sx, sy = im.width / sw, im.height / sh

if len(sys.argv) < 5:
    print("Usage: python cropregion.py x1 y1 x2 y2 [scale]")
    sys.exit(1)

x1, y1, x2, y2 = [float(v) for v in sys.argv[1:5]]
scale = float(sys.argv[5]) if len(sys.argv) > 5 else 3.0
box = (int(x1 * sx), int(y1 * sy), int(x2 * sx), int(y2 * sy))
crop = im.crop(box)
crop = crop.resize((int(crop.width * scale), int(crop.height * scale)))
out = os.path.join(SHOT_DIR, "crop.png")
crop.save(out)
print("saved", out, crop.size, "screen", sw, sh, "grab", im.size)
