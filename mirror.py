"""Presenter mirror (Windows): project ONE chosen window to the projector display, with a big pointer.

Nothing else on the presenter display (terminals, the private panel, other windows) ever
reaches the projector.

Source window
  - At start: the first window whose title contains an entry of ``source_title_contains``;
    if that list is empty, the foreground window at start (unless it is a terminal).
  - Press the "pick" hotkey (default F7) to project the current foreground window.
  - The window itself (HWND) is locked: tab or title changes do not lose it; moves and
    resizes are followed. Minimised or closed → the projector holds the last frame.
Capture (``capture_backend``)
  - "wgc": Windows Graphics Capture, a new frame only when the window changes; works when covered.
  - "printwindow": PrintWindow(PW_RENDERFULLCONTENT); works when covered.
  - "mss": screen copy, only while the window is not covered (otherwise freezes).
  - "auto" (default): wgc → printwindow (skipped if black) → mss.

Hotkeys are configurable (``hotkeys`` in config); defaults are listed in README.md.
Options: --cleanup (after a forced kill: release AppBar and cursor clip), --windowed (test in a
window), --selfcheck (import dependencies and parse config, then exit; opens no window).
"""
from __future__ import annotations

import ctypes
import json
import os
import sys
import threading
import time
import urllib.request
from pathlib import Path

from presenter_sidecar import MIRROR_TITLE, PANEL_TITLE, __version__
from presenter_sidecar.config import load_config
from presenter_sidecar.geometry import (arrow_polygons, contains, crop_in_window, fit_letterbox,
                                        frame_margins as calc_margins, intersects, map_point, mostly_black,
                                        outer_rect_for, panel_and_work_rects, panel_width, ripple_radius,
                                        sample_grid)
from presenter_sidecar.hotkeys import hotkey_table
from presenter_sidecar.i18n import t
from presenter_sidecar.windows import WindowInfo, auto_pick, newest, popup_eligible, source_allowed

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
HERE = Path(__file__).resolve().parent
LOGS = HERE / "logs"
CFG: dict = {}
LANG = "en"

if sys.platform != "win32":  # pragma: no cover - the mirror is Windows-only by design
    raise ImportError("mirror.py runs on Windows only (panel_server.py is cross-platform)")

from ctypes import wintypes  # noqa: E402

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
shell32 = ctypes.windll.shell32
dwmapi = ctypes.windll.dwmapi
kernel32 = ctypes.windll.kernel32

# ---- Win32 declarations
H = wintypes.HWND
user32.GetForegroundWindow.restype = H
user32.SetWindowPos.argtypes = [H, H, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.GetWindowLongPtrW.argtypes = [H, ctypes.c_int]
user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.SetWindowLongPtrW.argtypes = [H, ctypes.c_int, ctypes.c_ssize_t]
user32.GetWindowRect.argtypes = [H, ctypes.POINTER(wintypes.RECT)]
user32.GetWindowTextW.argtypes = [H, wintypes.LPWSTR, ctypes.c_int]
user32.GetClassNameW.argtypes = [H, wintypes.LPWSTR, ctypes.c_int]
for _fn in ("IsWindowVisible", "IsIconic", "IsZoomed", "IsWindow"):
    getattr(user32, _fn).argtypes = [H]
user32.ShowWindow.argtypes = [H, ctypes.c_int]
user32.SetLayeredWindowAttributes.argtypes = [H, wintypes.COLORREF, ctypes.c_ubyte, wintypes.DWORD]
user32.WindowFromPoint.argtypes = [wintypes.POINT]
user32.WindowFromPoint.restype = H
user32.GetAncestor.argtypes = [H, ctypes.c_uint]
user32.GetAncestor.restype = H
user32.GetWindowThreadProcessId.argtypes = [H, ctypes.POINTER(wintypes.DWORD)]
user32.PrintWindow.argtypes = [H, wintypes.HDC, ctypes.c_uint]
user32.GetDC.argtypes = [H]
user32.GetDC.restype = wintypes.HDC
user32.ReleaseDC.argtypes = [H, wintypes.HDC]
gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
gdi32.CreateCompatibleDC.restype = wintypes.HDC
gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
gdi32.SelectObject.restype = wintypes.HGDIOBJ
gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
gdi32.DeleteDC.argtypes = [wintypes.HDC]
gdi32.GetDIBits.argtypes = [wintypes.HDC, wintypes.HBITMAP, ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p,
                            ctypes.c_void_p, ctypes.c_uint]
dwmapi.DwmGetWindowAttribute.argtypes = [H, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]

HWND_TOPMOST = H(-1)
SWP_NOACTIVATE, SWP_SHOWWINDOW, SWP_NOZORDER, SWP_FRAMECHANGED = 0x10, 0x40, 0x4, 0x20
GWL_EXSTYLE, GWL_STYLE = -20, -16
WS_EX_TOPMOST, WS_EX_TRANSPARENT, WS_EX_TOOLWINDOW = 0x8, 0x20, 0x80
WS_EX_LAYERED, WS_EX_NOACTIVATE, WS_EX_APPWINDOW = 0x80000, 0x08000000, 0x40000
WS_CAPTION = 0x00C00000
LWA_ALPHA = 2
VK_LBUTTON, VK_RBUTTON = 0x01, 0x02
MOD_NOREPEAT = 0x4000
WM_HOTKEY, WM_QUIT = 0x0312, 0x0012
ABM_NEW, ABM_REMOVE, ABM_QUERYPOS, ABM_SETPOS = 0, 1, 2, 3
ABE_RIGHT = 2
DWMWA_EXTENDED_FRAME_BOUNDS, DWMWA_CLOAKED = 9, 14
SW_MAXIMIZE, SW_RESTORE, SW_SHOWNOACTIVATE = 3, 9, 4
GA_ROOT = 2
PW_RENDERFULLCONTENT = 2


class MONITORINFOEXW(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT),
                ("dwFlags", wintypes.DWORD), ("szDevice", wintypes.WCHAR * 32)]


class APPBARDATA(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("hWnd", H), ("uCallbackMessage", wintypes.UINT),
                ("uEdge", wintypes.UINT), ("rc", wintypes.RECT), ("lParam", wintypes.LPARAM)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", ctypes.c_long), ("biHeight", ctypes.c_long),
                ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", ctypes.c_long),
                ("biYPelsPerMeter", ctypes.c_long), ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]


shell32.SHAppBarMessage.argtypes = [wintypes.DWORD, ctypes.POINTER(APPBARDATA)]
shell32.SHAppBarMessage.restype = ctypes.c_size_t


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def set_dpi_aware():
    """Must run before any window call: from here on every coordinate is in physical pixels."""
    try:
        user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))  # PER_MONITOR_AWARE_V2
    except Exception:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    os.environ.setdefault("SDL_WINDOWS_DPI_AWARENESS", "permonitorv2")
    os.environ.setdefault("SDL_VIDEO_MINIMIZE_ON_FOCUS_LOSS", "0")
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")


def rect_tuple(r: wintypes.RECT):
    return (r.left, r.top, r.right, r.bottom)


def monitors() -> list[dict]:
    out = []

    def cb(hmon, hdc, lprc, lparam):
        mi = MONITORINFOEXW()
        mi.cbSize = ctypes.sizeof(mi)
        user32.GetMonitorInfoW(hmon, ctypes.byref(mi))
        out.append({"name": mi.szDevice, "rect": rect_tuple(mi.rcMonitor), "work": rect_tuple(mi.rcWork),
                    "primary": bool(mi.dwFlags & 1)})
        return 1

    proc = ctypes.WINFUNCTYPE(ctypes.c_int, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(wintypes.RECT),
                              wintypes.LPARAM)
    user32.EnumDisplayMonitors(None, None, proc(cb), 0)
    return out


def cursor_pos():
    p = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(p))
    return p.x, p.y


def window_text(hwnd) -> str:
    buf = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(hwnd, buf, 512)
    return buf.value


def class_name(hwnd) -> str:
    buf = ctypes.create_unicode_buffer(128)
    user32.GetClassNameW(hwnd, buf, 128)
    return buf.value


def is_cloaked(hwnd) -> bool:
    v = ctypes.c_int(0)
    dwmapi.DwmGetWindowAttribute(hwnd, DWMWA_CLOAKED, ctypes.byref(v), 4)
    return v.value != 0


def window_pid(h) -> int:
    pid = wintypes.DWORD(0)
    user32.GetWindowThreadProcessId(h, ctypes.byref(pid))
    return pid.value


def top_windows() -> list[int]:
    """Visible, uncloaked, titled top-level windows in z-order (topmost first)."""
    found = []

    def cb(hwnd, lparam):
        if user32.IsWindowVisible(hwnd) and not is_cloaked(hwnd) and window_text(hwnd):
            found.append(hwnd)
        return 1

    proc = ctypes.WINFUNCTYPE(ctypes.c_bool, H, wintypes.LPARAM)
    user32.EnumWindows(proc(cb), 0)
    return found


def find_windows(title_part: str, cls: str | None = None) -> list[int]:
    return [h for h in top_windows() if title_part in window_text(h) and (cls is None or class_name(h) == cls)]


def frame_rects(hwnd):
    """``GetWindowRect`` includes invisible resize borders; returns (margins, visible frame, window rect)."""
    wr, fr = wintypes.RECT(), wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(wr))
    if dwmapi.DwmGetWindowAttribute(hwnd, DWMWA_EXTENDED_FRAME_BOUNDS, ctypes.byref(fr), ctypes.sizeof(fr)) != 0:
        return (0, 0, 0, 0), rect_tuple(wr), rect_tuple(wr)
    w, f = rect_tuple(wr), rect_tuple(fr)
    return calc_margins(w, f), f, w


def window_info(h) -> WindowInfo:
    exists = bool(h) and bool(user32.IsWindow(h))
    if not exists:
        return WindowInfo(hwnd=int(h or 0), exists=False)
    _, fr, _ = frame_rects(h)
    return WindowInfo(
        hwnd=int(h), title=window_text(h), cls=class_name(h), pid=window_pid(h), exists=True,
        visible=bool(user32.IsWindowVisible(h)), minimized=bool(user32.IsIconic(h)), cloaked=is_cloaked(h),
        toolwindow=bool(user32.GetWindowLongPtrW(h, GWL_EXSTYLE) & WS_EX_TOOLWINDOW),
        has_caption=(user32.GetWindowLongPtrW(h, GWL_STYLE) & WS_CAPTION) == WS_CAPTION, frame=fr)


def place_window(hwnd, rect, topmost=False):
    margins, _, _ = frame_rects(hwnd)
    x, y, w, h = outer_rect_for(rect, margins)
    after = HWND_TOPMOST if topmost else H(0)
    flags = SWP_NOACTIVATE | (0 if topmost else SWP_NOZORDER)
    user32.SetWindowPos(hwnd, after, x, y, w, h, flags)


def root_at(x, y):
    h = user32.WindowFromPoint(wintypes.POINT(x, y))
    return user32.GetAncestor(h, GA_ROOT) if h else None


def keyname(action: str) -> str:
    return str((CFG.get("hotkeys") or {}).get(action) or "-")


# ---------------------------------------------------------------- source window and capture
class Source:
    """Locks one HWND; found by title rules or the foreground window, changed with the pick hotkey."""

    def __init__(self, own: set[int]):
        self.own = own
        self.hwnd = None
        self.title = ""
        self.manual = False
        self.patterns = [p for p in (CFG.get("source_title_contains") or []) if p]
        self.never_cls = set(CFG.get("never_source_classes") or [])
        self.last_search = 0.0

    def allowed(self, h) -> tuple[bool, str]:
        ok, why = source_allowed(WindowInfo(hwnd=int(h or 0), title=window_text(h) if h else "",
                                            cls=class_name(h) if h else ""), self.own, self.never_cls)
        return ok, (t(LANG, f"why.{why}") if why else "")

    def auto_find(self):
        if not self.patterns:
            return None
        wins = [window_info(h) for h in top_windows() if self.allowed(h)[0]]
        return auto_pick(wins, self.patterns)

    def initial(self):
        """Title rules first; with no rules, the foreground window at start (if allowed)."""
        h = self.auto_find()
        if h:
            return h
        if not self.patterns:
            fg = user32.GetForegroundWindow()
            if fg and self.allowed(fg)[0]:
                return fg
        return None

    def set(self, h, manual=False):
        self.hwnd, self.manual = h, manual
        self.title = window_text(h) if h else ""
        log("source ->", f"{self.title!r}" if h else "(none)", "(manual)" if manual else "")

    def state(self) -> str:
        if not self.hwnd:
            return "none"
        if not user32.IsWindow(self.hwnd):
            return "closed"
        if user32.IsIconic(self.hwnd):
            return "minimized"
        return "ok"

    def tick(self, now):
        """While the source is missing, retry the title rules every 2 s."""
        st = self.state()
        if st in ("none", "closed") and now - self.last_search > 2.0:
            self.last_search = now
            h = self.auto_find()
            if h:
                self.set(h)
                return self.state()
        if st == "ok":
            self.title = window_text(self.hwnd) or self.title
        return st


class PopupFollower:
    """Follow NEW top-level windows of the source's process (e.g. an OAuth sign-in popup);
    switch back to the source when the popup closes. Rules: presenter_sidecar.windows.popup_eligible."""

    def __init__(self, own: set[int], src_mon_rect, never_cls: set[str]):
        self.enabled = bool(CFG.get("follow_popups", True))
        self.min_size = tuple((CFG.get("popup_min_size") or [320, 240])[:2])
        self.own, self.mon, self.never_cls = own, src_mon_rect, never_cls
        self.src = None
        self.pid = None
        self.baseline: set[int] = set()
        self.seen: dict[int, float] = {}
        self.hwnd = None
        self.title = ""
        self.last_scan = 0.0

    def reset(self, src_hwnd):
        self.src = src_hwnd
        self.pid = window_pid(src_hwnd) if src_hwnd else None
        self.baseline = {h for h in top_windows() if self.pid and window_pid(h) == self.pid}
        self.seen.clear()
        self.hwnd = None

    def eligible(self, h) -> bool:
        return popup_eligible(window_info(h), source=self.src, pid=self.pid, own=self.own,
                              never_classes=self.never_cls, min_size=self.min_size, monitor=self.mon)

    def tick(self, now):
        if not self.enabled or not self.pid:
            self.hwnd = None
            return None
        if self.hwnd and not self.eligible(self.hwnd):
            log("popup closed, back to source:", repr(self.title))
            self.hwnd = None
        if now - self.last_scan > 0.25:
            self.last_scan = now
            for h in top_windows():
                if h not in self.baseline and h not in self.seen and window_pid(h) == self.pid:
                    self.seen[h] = now
            alive = [h for h in self.seen if self.eligible(h)]
            for h in list(self.seen):
                if not user32.IsWindow(h):
                    del self.seen[h]
            nh = newest(self.seen, alive)
            if nh and nh != self.hwnd:
                self.hwnd = nh
                self.title = window_text(nh)
                log("following popup:", repr(self.title))
        if self.hwnd:
            self.title = window_text(self.hwnd) or self.title
        return self.hwnd


class PrintWindowCapture:
    """PrintWindow(PW_RENDERFULLCONTENT): asks the window to render itself, so covering it does not matter."""

    name = "printwindow"

    def __init__(self):
        self.size = (0, 0)
        self.mdc = self.bmp = self.old = None
        self.buf = None
        self.bih = BITMAPINFOHEADER()

    def _alloc(self, w, h):
        self.free()
        sdc = user32.GetDC(None)
        self.mdc = gdi32.CreateCompatibleDC(sdc)
        self.bmp = gdi32.CreateCompatibleBitmap(sdc, w, h)
        user32.ReleaseDC(None, sdc)
        self.old = gdi32.SelectObject(self.mdc, self.bmp)
        self.bih = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
        self.buf = (ctypes.c_ubyte * (w * h * 4))()
        self.size = (w, h)

    def free(self):
        if self.mdc:
            gdi32.SelectObject(self.mdc, self.old)
            gdi32.DeleteObject(self.bmp)
            gdi32.DeleteDC(self.mdc)
        self.mdc = self.bmp = self.old = None

    def grab(self, hwnd, wr):
        w, h = wr[2] - wr[0], wr[3] - wr[1]
        if w <= 0 or h <= 0:
            return None
        if (w, h) != self.size:
            self._alloc(w, h)
        if not user32.PrintWindow(hwnd, self.mdc, PW_RENDERFULLCONTENT):
            return None
        gdi32.GetDIBits(self.mdc, self.bmp, 0, h, self.buf, ctypes.byref(self.bih), 0)
        return self.buf, (w, h)


class WGCCapture:
    """Windows Graphics Capture (windows-capture package): frames only arrive when the window changes."""

    name = "wgc"

    def __init__(self, fps):
        self.lock = threading.Lock()
        self.fps = fps
        self.ctl = None
        self.hwnd = None
        self.frame = None
        self.seq = 0
        self.t_start = 0.0

    def start(self, hwnd):
        self.stop()
        import windows_capture as wc
        kw = dict(cursor_capture=False, draw_border=False, window_hwnd=int(hwnd))
        try:
            cap = wc.WindowsCapture(minimum_update_interval=max(1, int(1000 / self.fps)), **kw)
        except Exception:
            cap = wc.WindowsCapture(**kw)

        @cap.event
        def on_frame_arrived(frame, ctl):
            fb = frame.frame_buffer
            data = fb.tobytes()
            with self.lock:
                self.frame = (data, (fb.shape[1], fb.shape[0]))
                self.seq += 1

        @cap.event
        def on_closed():
            pass

        with self.lock:
            self.frame = None
        self.ctl = cap.start_free_threaded()
        self.hwnd = hwnd
        self.t_start = time.perf_counter()

    def stop(self):
        if self.ctl:
            try:
                self.ctl.stop()
            except Exception:
                pass
        self.ctl = self.hwnd = None

    def latest(self):
        with self.lock:
            return self.frame, self.seq


def unobscured(hwnd, fr) -> bool:
    """All 5×5 probe points inside the visible frame belong to this window (mss fallback)."""
    return all(root_at(x, y) == hwnd for x, y in sample_grid(fr))


# ---------------------------------------------------------------- hotkey thread
class Hotkeys(threading.Thread):
    def __init__(self, table: dict[str, tuple[int, int]]):
        super().__init__(daemon=True)
        self.keys = {i + 1: (mods, vk, action) for i, (action, (mods, vk)) in enumerate(table.items())}
        self.events: list[str] = []
        self.lock = threading.Lock()
        self.tid = None
        self.failed: list[str] = []
        self.ready = threading.Event()

    def run(self):
        self.tid = kernel32.GetCurrentThreadId()
        for hid, (mods, vk, name) in self.keys.items():
            if not user32.RegisterHotKey(None, hid, mods | MOD_NOREPEAT, vk):
                self.failed.append(name)
        self.ready.set()
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == WM_HOTKEY and msg.wParam in self.keys:
                with self.lock:
                    self.events.append(self.keys[msg.wParam][2])
        for hid in self.keys:
            user32.UnregisterHotKey(None, hid)

    def pop(self) -> list[str]:
        with self.lock:
            ev, self.events = self.events, []
        return ev

    def stop(self):
        if self.tid:
            user32.PostThreadMessageW(self.tid, WM_QUIT, 0, 0)


# ---------------------------------------------------------------- report to the panel
class Reporter(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.status: dict = {}
        self.url = f"http://{CFG.get('panel_host', '127.0.0.1')}:{CFG.get('panel_port', 8765)}"
        self.outbox: list[dict] = []
        self.lock = threading.Lock()

    def send(self, path, body):
        req = urllib.request.Request(self.url + path, data=json.dumps(body).encode(), method="POST",
                                     headers={"Content-Type": "application/json", "X-Panel": "1"})
        try:
            urllib.request.urlopen(req, timeout=0.8).read()
        except Exception:
            pass

    def cmd(self, body):
        with self.lock:
            self.outbox.append(body)

    def run(self):
        while True:
            with self.lock:
                out, self.outbox = self.outbox, []
            for b in out:
                self.send("/api/cmd", b)
            self.send("/api/mirror", self.status)
            time.sleep(1.0)


# ---------------------------------------------------------------- AppBar (reserve the panel strip)
class AppBar:
    def __init__(self):
        self.hwnd = None
        self.rect = None

    def register(self, hwnd, mon_rect, width) -> tuple | None:
        abd = APPBARDATA(cbSize=ctypes.sizeof(APPBARDATA), hWnd=hwnd, uCallbackMessage=0x8000 + 77)
        if not shell32.SHAppBarMessage(ABM_NEW, ctypes.byref(abd)):
            return None
        self.hwnd = hwnd
        (LOGS / "mirror.appbar").write_text(str(int(hwnd)))
        l, t_, r, b = mon_rect
        abd.uEdge = ABE_RIGHT
        abd.rc = wintypes.RECT(r - width, t_, r, b)
        shell32.SHAppBarMessage(ABM_QUERYPOS, ctypes.byref(abd))
        abd.rc.left = abd.rc.right - width
        shell32.SHAppBarMessage(ABM_SETPOS, ctypes.byref(abd))
        self.rect = rect_tuple(abd.rc)
        return self.rect

    def remove(self):
        if self.hwnd:
            abd = APPBARDATA(cbSize=ctypes.sizeof(APPBARDATA), hWnd=self.hwnd)
            shell32.SHAppBarMessage(ABM_REMOVE, ctypes.byref(abd))
            self.hwnd = None
        try:
            (LOGS / "mirror.appbar").unlink()
        except OSError:
            pass


def cleanup_only():
    """Called by stop.ps1 after a forced kill: release a leftover AppBar and cursor clip."""
    user32.ClipCursor(None)
    f = LOGS / "mirror.appbar"
    if f.exists():
        try:
            abd = APPBARDATA(cbSize=ctypes.sizeof(APPBARDATA), hWnd=int(f.read_text()))
            shell32.SHAppBarMessage(ABM_REMOVE, ctypes.byref(abd))
        except Exception as e:
            log("appbar cleanup:", e)
        f.unlink(missing_ok=True)
    log("cleanup done")


def selfcheck() -> int:
    """Import every dependency and parse the config; opens no window and registers no hotkey."""
    import mss
    import numpy
    import pygame
    import windows_capture  # noqa: F401
    table = hotkey_table(CFG.get("hotkeys") or {})
    print(f"presenter-sidecar {__version__}: mss {getattr(mss, '__version__', '?')}, "
          f"pygame-ce {pygame.version.ver}, numpy {numpy.__version__}, windows-capture ok; "
          f"{len(table)} hotkeys; config {Path(CFG['_path']).name}")
    return 0


# ---------------------------------------------------------------- main
def main():
    global CFG, LANG
    CFG = load_config(root=HERE)
    LANG = CFG.get("ui_lang", "en")
    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if "--selfcheck" in sys.argv:
        return selfcheck()
    LOGS.mkdir(exist_ok=True)
    set_dpi_aware()
    if "--cleanup" in sys.argv:
        return cleanup_only()

    import mss
    import pygame

    mons = monitors()
    log("monitors:", mons)
    src = next((m for m in mons if m["name"] == CFG.get("source_display")), None) \
        or next(m for m in mons if m["primary"])
    dst = None if "--windowed" in sys.argv else (
        next((m for m in mons if m["name"] == CFG.get("target_display") and m is not src), None)
        or next((m for m in mons if m is not src), None))
    windowed = dst is None

    sl, st, sr, sb = src["rect"]
    panel_w = panel_width(src["rect"], CFG.get("panel_width_ratio", 0.26), CFG.get("panel_width_px") or 0)

    pygame.init()
    if windowed:
        W, Hh = 960, 540
        os.environ["SDL_VIDEO_WINDOW_POS"] = "40,40"
        screen = pygame.display.set_mode((W, Hh))
        log("no target display -> windowed mode (testing)")
    else:
        dl, dt, dr, db = dst["rect"]
        W, Hh = dr - dl, db - dt
        os.environ["SDL_VIDEO_WINDOW_POS"] = f"{dl},{dt}"
        screen = pygame.display.set_mode((W, Hh), pygame.NOFRAME)
    pygame.display.set_caption(MIRROR_TITLE)
    hwnd = pygame.display.get_wm_info()["window"]
    (LOGS / "mirror.pid").write_text(str(os.getpid()))

    if not windowed:
        ex = user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
        ex = (ex | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOPMOST) \
            & ~WS_EX_APPWINDOW
        user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, ex)
        user32.SetLayeredWindowAttributes(hwnd, 0, 255, LWA_ALPHA)  # click-through
        user32.SetWindowPos(hwnd, HWND_TOPMOST, dl, dt, W, Hh, SWP_NOACTIVATE | SWP_SHOWWINDOW | SWP_FRAMECHANGED)

    # Panel strip on the right. reserve_work_area=true registers an AppBar so maximised windows
    # avoid the panel; off by default so already-maximised windows are not resized at start/stop.
    appbar = AppBar()
    panel_rect, work_rect = panel_and_work_rects(src["rect"], src["work"][3], panel_w)
    if CFG.get("reserve_work_area", False) and not windowed:
        r = appbar.register(hwnd, (sl, st, sr, sb), panel_w)
        if r:
            panel_rect = r
            work_rect = (sl, st, panel_rect[0], src["work"][3])
            log("AppBar reserved panel strip:", r)
    log("panel:", panel_rect, "work area:", work_rect, "target:", dst and dst["rect"])

    source = Source(own={int(hwnd)})
    popup = PopupFollower({int(hwnd)}, src["rect"], source.never_cls)
    popup_src = None
    h0 = source.initial()
    if h0:
        source.set(h0)
    else:
        log("no source window yet (rules:", source.patterns, ") -> blank screen until", keyname("pick"))

    backend_cfg = CFG.get("capture_backend", "auto")
    pw = PrintWindowCapture()
    wgc = None
    if backend_cfg in ("wgc", "auto"):
        try:
            import windows_capture  # noqa: F401
            wgc = WGCCapture(int(CFG.get("fps", 25)))
        except Exception as e:
            log("WGC unavailable, using PrintWindow:", e)
    wgc_seq = -1

    # ---- pointer assets
    ring_r = int(CFG.get("pointer_ring_radius", 46))
    ring_col = tuple(CFG.get("pointer_ring_color", [255, 214, 0]))

    def make_ring(border_col):
        s = pygame.Surface((ring_r * 2 + 8, ring_r * 2 + 8), pygame.SRCALPHA)
        c = ring_r + 4
        pygame.draw.circle(s, (*ring_col, int(CFG.get("pointer_ring_alpha", 90))), (c, c), ring_r)
        pygame.draw.circle(s, (*border_col, int(CFG.get("pointer_ring_border_alpha", 220))), (c, c), ring_r, 4)
        return s

    ring_idle = make_ring(ring_col)
    ring_l = make_ring(tuple(CFG.get("ripple_left_color", [255, 59, 48])))
    ring_r_btn = make_ring(tuple(CFG.get("ripple_right_color", [0, 122, 255])))

    k = float(CFG.get("pointer_arrow_scale", 2.2))
    ss = 4  # supersample for anti-aliasing
    big = pygame.Surface((int(20 * k * ss), int(28 * k * ss)), pygame.SRCALPHA)
    outer, inner = arrow_polygons(k, ss)
    pygame.draw.polygon(big, (0, 0, 0, 255), outer)
    pygame.draw.polygon(big, (255, 255, 255, 255), inner)
    arrow = pygame.transform.smoothscale(big, (big.get_width() // ss, big.get_height() // ss))

    spot_r = int(CFG.get("spotlight_radius", 170))
    spot = pygame.Surface((W * 2, Hh * 2), pygame.SRCALPHA)
    spot.fill((0, 0, 0, int(CFG.get("spotlight_dim_alpha", 170))))
    for i in range(12, 0, -1):  # soft edge
        a = int(CFG.get("spotlight_dim_alpha", 170) * i / 13)
        pygame.draw.circle(spot, (0, 0, 0, a), (W, Hh), spot_r + i * 3)
    pygame.draw.circle(spot, (0, 0, 0, 0), (W, Hh), spot_r)

    font_path = CFG.get("font_path") or None
    try:
        if not font_path:
            raise OSError("no font_path")
        f_big = pygame.font.Font(font_path, 120)
        f_small = pygame.font.Font(font_path, 44)
    except Exception:
        fonts = "segoeui,microsoftjhengheiui,microsoftjhenghei,yugothicui,malgungothic,arial"
        f_big, f_small = pygame.font.SysFont(fonts, 120), pygame.font.SysFont(fonts, 44)
    blank = pygame.Surface((W, Hh)).convert()
    blank.fill(tuple(CFG.get("blank_bg", [24, 28, 36])))
    t1 = f_big.render(CFG.get("blank_text", "Please wait"), True, (255, 255, 255))
    t2 = f_small.render(CFG.get("blank_subtext", ""), True, (170, 178, 190))
    blank.blit(t1, t1.get_rect(center=(W // 2, Hh // 2 - 40)))
    blank.blit(t2, t2.get_rect(center=(W // 2, Hh // 2 + 70)))

    ripple_ms = int(CFG.get("ripple_ms", 550))
    ripple_max = int(CFG.get("ripple_max_radius", 70))
    ripple_cols = {"L": tuple(CFG.get("ripple_left_color", [255, 59, 48])),
                   "R": tuple(CFG.get("ripple_right_color", [0, 122, 255]))}
    ripple_buf = pygame.Surface((ripple_max * 2 + 8, ripple_max * 2 + 8), pygame.SRCALPHA)

    hot = Hotkeys(hotkey_table(CFG.get("hotkeys") or {}))
    # Reported to the panel so its ⌨ overlay lists the keys registered now, not a later config.json edit.
    hot_specs = {action: str(CFG["hotkeys"][action]) for _, _, action in hot.keys.values()}
    hot.start()
    hot.ready.wait(2)
    if hot.failed:
        log("WARNING: hotkeys already taken by another program (change them in config.json):", hot.failed)
    rep = Reporter()
    rep.start()

    fps = max(5, min(60, int(CFG.get("fps", 25))))
    frame_dt = 1.0 / fps
    smooth = bool(CFG.get("smooth_scale", True))
    clip = CFG.get("clip_cursor_to_source", True) and not windowed
    clip_rect = wintypes.RECT(sl, st, sr, sb)
    style = CFG.get("pointer_style", "ring")
    frozen = blanked = False
    ripples: list[tuple[float, float, float, str]] = []
    prev_btn = {"L": False, "R": False}
    frames, fps_meas, t_fps = 0, 0.0, time.perf_counter()
    cpu_t, cpu_w = time.process_time(), time.perf_counter()
    cap_ms_acc, cap_n = 0.0, 0
    last_panel_fix = 0.0
    stop_flag = LOGS / "mirror.stop"
    stop_flag.unlink(missing_ok=True)
    scaled = None          # last frame, already scaled
    geom = None            # (frame rect, scale, ox, oy, tw, th) matching `scaled`
    backend_used = "-"
    src_state = raw_state = "none"
    notice = ""            # panel only
    notice_until = 0.0
    ph = None
    running = True
    log(f"start: fps cap {fps}, capture {backend_cfg}")

    def note(msg, secs=6.0):
        nonlocal notice, notice_until
        notice, notice_until = msg, time.perf_counter() + secs
        log("panel notice:", msg)

    try:
        with (mss.MSS() if hasattr(mss, "MSS") else mss.mss()) as sct:
            while running:
                t0 = time.perf_counter()
                for e in pygame.event.get():
                    if e.type == pygame.QUIT:
                        running = False
                for ev in hot.pop():
                    if ev == "quit":
                        running = False
                    elif ev == "freeze":
                        frozen = not frozen
                        log("frozen" if frozen else "unfrozen")
                    elif ev == "blank":
                        blanked = not blanked
                        log("blank screen" if blanked else "live again")
                    elif ev == "style":
                        style = "spotlight" if style == "ring" else "ring"
                        log("pointer style:", style)
                    elif ev == "pick":
                        fg = user32.GetForegroundWindow()
                        ok, why = source.allowed(fg)
                        if ok:
                            source.set(fg, manual=True)
                            popup_src = None  # new baseline: popups that were already open are not followed
                            note(t(LANG, "note.source", title=source.title))
                        else:
                            note(t(LANG, "note.refused", why=why))
                    elif ev == "bring":
                        if source.state() in ("ok", "minimized"):
                            user32.ShowWindow(source.hwnd, SW_RESTORE)
                            place_window(source.hwnd, work_rect)
                            if appbar.hwnd:  # with an AppBar, maximised fits beside the panel
                                user32.ShowWindow(source.hwnd, SW_MAXIMIZE)
                            note(t(LANG, "note.brought"))
                    elif ev == "popups":
                        popup.enabled = not popup.enabled
                        if not popup.enabled:
                            popup.hwnd = None
                        note(t(LANG, "note.popups_on") if popup.enabled
                             else t(LANG, "note.popups_off", pick=keyname("pick")))
                    elif ev == "clip":
                        clip = not clip
                        if not clip:
                            user32.ClipCursor(None)
                        note(t(LANG, "note.clip_on") if clip else t(LANG, "note.clip_off"))
                    elif ev in ("next", "prev"):
                        rep.cmd({"nav": 1 if ev == "next" else -1})
                if stop_flag.exists():
                    running = False

                if clip:
                    user32.ClipCursor(ctypes.byref(clip_rect))

                # Every 2 s put the panel window back on the right (just opened, dragged or maximised).
                if t0 - last_panel_fix > 2.0:
                    last_panel_fix = t0
                    for pnl in find_windows(PANEL_TITLE, "Chrome_WidgetWin_1"):
                        if user32.IsIconic(pnl):
                            continue
                        if user32.IsZoomed(pnl):
                            user32.ShowWindow(pnl, SW_SHOWNOACTIVATE)
                        _, fr_p, _ = frame_rects(pnl)
                        topmost = bool(CFG.get("panel_topmost", True))
                        is_top = bool(user32.GetWindowLongPtrW(pnl, GWL_EXSTYLE) & WS_EX_TOPMOST)
                        if fr_p != tuple(panel_rect) or topmost != is_top:
                            place_window(pnl, panel_rect, topmost=topmost)

                # ---- source window
                prev_raw = raw_state
                raw_state = source.tick(t0)  # none / closed / minimized / ok
                if raw_state != prev_raw:
                    log("source state:", prev_raw, "->", raw_state)
                src_state = raw_state
                if popup_src != source.hwnd:
                    popup.reset(source.hwnd if raw_state in ("ok", "minimized") else None)
                    popup_src = source.hwnd
                ph = popup.tick(t0) if raw_state in ("ok", "minimized") else None
                active = ph or source.hwnd
                if ph:
                    src_state = "ok"
                fr = None
                live = False
                if src_state == "ok" and not frozen and not blanked:
                    _, fr, wr = frame_rects(active)
                    if dst and intersects(fr, dst["rect"]):
                        src_state = "on_projector"
                    tc = time.perf_counter()
                    img = None
                    reuse = False
                    if wgc is not None:
                        if wgc.hwnd != active or (prev_raw != "ok" and not ph):
                            try:
                                wgc.start(active)
                                wgc_seq = -1
                            except Exception as e:
                                log("WGC failed to start, using PrintWindow:", e)
                                wgc = None
                    if wgc is not None:
                        frame, seq = wgc.latest()
                        if frame and seq != wgc_seq:
                            wgc_seq = seq
                            img = pygame.image.frombuffer(frame[0], frame[1], "BGRA")
                            backend_used = "wgc"
                        elif frame and scaled is not None:
                            reuse = True  # unchanged: keep the last scaled frame
                            backend_used = "wgc"
                        elif time.perf_counter() - wgc.t_start < 1.5 and scaled is not None and backend_used == "wgc":
                            reuse = True
                    if img is None and not reuse and backend_cfg in ("printwindow", "auto"):
                        got = pw.grab(active, wr)
                        if got and not (backend_cfg == "auto" and mostly_black(got[0])):
                            buf, size = got
                            full = pygame.image.frombuffer(buf, size, "BGRA")
                            img = full.subsurface(pygame.Rect(*crop_in_window(fr, wr)).clip(full.get_rect()))
                            backend_used = "printwindow"
                    if img is None and not reuse and backend_cfg in ("mss", "auto"):
                        if unobscured(active, fr):
                            shot = sct.grab({"left": fr[0], "top": fr[1], "width": fr[2] - fr[0],
                                             "height": fr[3] - fr[1]})
                            img = pygame.image.frombuffer(shot.bgra, shot.size, "BGRA")
                            backend_used = "mss"
                        elif src_state == "ok":
                            src_state = "obscured"
                    if reuse and geom is not None:
                        geom = (fr,) + geom[1:]
                        live = True
                    if img is not None:
                        iw, ih = img.get_size()
                        scale, ox, oy, tw, th = fit_letterbox(iw, ih, W, Hh)
                        if scaled is None or scaled.get_size() != (tw, th):
                            scaled = pygame.Surface((tw, th)).convert()
                        (pygame.transform.smoothscale if smooth else pygame.transform.scale)(img, (tw, th), scaled)
                        geom = (fr, scale, ox, oy, tw, th)  # matches the visible frame fr
                        live = True
                        cap_ms_acc += (time.perf_counter() - tc) * 1000
                        cap_n += 1

                # ---- draw
                if blanked or scaled is None:
                    screen.blit(blank, (0, 0))
                else:
                    screen.fill((0, 0, 0))
                    screen.blit(scaled, geom[2:4])
                    # Pointer: only on a live frame AND when the cursor is really over the source (not covered).
                    if live:
                        gfr, scale, ox, oy, tw, th = geom
                        mx, my = cursor_pos()
                        inside = contains(gfr, mx, my) and root_at(mx, my) == active
                        px, py = map_point(mx, my, gfr, ox, oy, tw, th)
                        now = time.perf_counter()
                        held = {}
                        for b, vk in (("L", VK_LBUTTON), ("R", VK_RBUTTON)):
                            st_ = user32.GetAsyncKeyState(vk)
                            down = bool(st_ & 0x8000)
                            if inside and ((down and not prev_btn[b]) or (st_ & 1 and not down)):
                                ripples.append((px, py, now, b))
                            prev_btn[b] = down
                            held[b] = down
                        if inside:
                            if style == "spotlight":
                                screen.blit(spot, (0, 0), pygame.Rect(W - int(px), Hh - int(py), W, Hh))
                            ring = ring_l if held["L"] else ring_r_btn if held["R"] else ring_idle
                            screen.blit(ring, (int(px) - ring.get_width() // 2, int(py) - ring.get_height() // 2))
                        alive = []
                        for (rx, ry, t_, b) in ripples:
                            age = (now - t_) * 1000 / ripple_ms
                            if age >= 1:
                                continue
                            alive.append((rx, ry, t_, b))
                            ripple_buf.fill((0, 0, 0, 0))
                            c = ripple_buf.get_width() // 2
                            rad = ripple_radius(age, ripple_max)
                            pygame.draw.circle(ripple_buf, (*ripple_cols[b], int(230 * (1 - age))), (c, c), rad, 6)
                            pygame.draw.circle(ripple_buf, (*ripple_cols[b], int(90 * (1 - age))), (c, c),
                                               max(1, rad - 6))
                            screen.blit(ripple_buf, (int(rx) - c, int(ry) - c))
                        ripples = alive
                        if inside:
                            screen.blit(arrow, (int(px) - 2, int(py) - 2))
                pygame.display.flip()

                # ---- stats and report
                frames += 1
                tn = time.perf_counter()
                if tn - t_fps >= 1.0:
                    fps_meas = frames / (tn - t_fps)
                    pc = time.process_time()
                    cpu_pct = (pc - cpu_t) / (tn - cpu_w) * 100
                    cpu_t, cpu_w = pc, tn
                    warn = ""
                    if src_state in ("none", "closed", "minimized", "obscured", "on_projector"):
                        warn = t(LANG, f"warn.{src_state}", pick=keyname("pick"), bring=keyname("bring"))
                    rep.status = {"fps": round(fps_meas, 1), "frozen": frozen, "blank": blanked, "style": style,
                                  "clip": clip, "cpu_pct_one_core": round(cpu_pct, 1),
                                  "cpu_pct_total": round(cpu_pct / (os.cpu_count() or 1), 1),
                                  "capture_scale_ms": round(cap_ms_acc / max(1, cap_n), 1), "backend": backend_used,
                                  "source_title": source.title, "source_state": src_state,
                                  "source_manual": source.manual,
                                  "following_popup": bool(ph), "popup_title": popup.title if ph else "",
                                  "follow_popups": popup.enabled, "source_hwnd": int(source.hwnd or 0),
                                  "source_frame": geom[0] if geom else None,
                                  "scale": round(geom[1], 4) if geom else None,
                                  "offset": list(geom[2:4]) if geom else None, "panel": panel_rect,
                                  "target": dst and dst["rect"], "hotkeys": hot_specs, "hotkeys_failed": hot.failed,
                                  "warning": warn, "notice": notice if tn < notice_until else ""}
                    (LOGS / "mirror.status.json").write_text(json.dumps(rep.status, ensure_ascii=False),
                                                             encoding="utf-8")
                    frames, cap_ms_acc, cap_n, t_fps = 0, 0.0, 0, tn
                spent = time.perf_counter() - t0
                if spent < frame_dt:
                    time.sleep(frame_dt - spent)
    finally:
        user32.ClipCursor(None)
        appbar.remove()
        pw.free()
        if wgc is not None:
            wgc.stop()
        hot.stop()
        rep.send("/api/mirror", {})
        pygame.quit()
        for f in ("mirror.pid", "mirror.stop"):
            (LOGS / f).unlink(missing_ok=True)
        log("stopped")


if __name__ == "__main__":
    sys.exit(main() or 0)
