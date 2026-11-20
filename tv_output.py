"""Windows multi-monitor enumeration for the external TV."""
import ctypes
from ctypes import wintypes

class RECT(ctypes.Structure):
    _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG),
                ("right", wintypes.LONG), ("bottom", wintypes.LONG)]

def get_monitors():
    """Returns [{'x','y','w','h','primary'}] for every connected display."""
    monitors = []
    MonitorEnumProc = ctypes.WINFUNCTYPE(
        ctypes.c_int, wintypes.HMONITOR, wintypes.HDC,
        ctypes.POINTER(RECT), wintypes.LPARAM)

    def cb(hmon, hdc, lprect, data):
        r = lprect.contents
        monitors.append({"x": r.left, "y": r.top,
                         "w": r.right - r.left, "h": r.bottom - r.top,
                         "primary": r.left == 0 and r.top == 0})
        return 1

    ctypes.windll.user32.EnumDisplayMonitors(0, 0, MonitorEnumProc(cb), 0)
    monitors.sort(key=lambda m: not m["primary"])   # primary first
    return monitors

def place_fullscreen(win, monitor):
    win.overrideredirect(True)
    win.geometry(f"{monitor['w']}x{monitor['h']}+{monitor['x']}+{monitor['y']}")
    win.attributes("-topmost", True)
