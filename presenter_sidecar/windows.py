"""Window-selection rules (pure): which windows may be projected and which popups to follow.

The mirror gathers facts about a window with Win32 calls and passes them in as a
:class:`WindowInfo`, so these rules can be tested without Windows.
"""
from __future__ import annotations

from dataclasses import dataclass

from . import MIRROR_TITLE, PANEL_TITLE
from .geometry import Rect, intersects

OWN_TITLES = (PANEL_TITLE, MIRROR_TITLE)
SHELL_CLASSES = ("Shell_TrayWnd", "Progman", "WorkerW", "Shell_SecondaryTrayWnd")


@dataclass
class WindowInfo:
    hwnd: int
    title: str = ""
    cls: str = ""
    pid: int = 0
    exists: bool = True
    visible: bool = True
    minimized: bool = False
    cloaked: bool = False
    toolwindow: bool = False
    has_caption: bool = True
    frame: Rect = (0, 0, 0, 0)


def source_allowed(w: WindowInfo, own: set[int], never_classes: set[str] | frozenset = frozenset()) -> tuple[bool, str]:
    """May this window become the projected source? Returns ``(ok, reason_key)``."""
    if not w.hwnd or w.hwnd in own:
        return False, "own_window"
    if any(x in w.title for x in OWN_TITLES):
        return False, "panel_window"
    if w.cls in never_classes:
        return False, "blocked_class"
    if w.cls in SHELL_CLASSES:
        return False, "desktop"
    return True, ""


def auto_pick(windows: list[WindowInfo], patterns: list[str]) -> int | None:
    """First pattern wins; among its hits a non-minimized window wins; then z-order."""
    for pat in patterns:
        hits = [w for w in windows if pat in w.title]
        hits.sort(key=lambda w: w.minimized)  # stable: keeps z-order within each group
        if hits:
            return hits[0].hwnd
    return None


def popup_eligible(w: WindowInfo, *, source: int | None, pid: int | None, own: set[int],
                   never_classes: set[str] | frozenset, min_size: tuple[int, int], monitor: Rect) -> bool:
    """Is ``w`` a real popup of the source's process worth projecting?

    Follows only: same PID, visible, not minimized/cloaked, titled, not a terminal or the
    tool itself, not ``WS_EX_TOOLWINDOW``, has a caption bar, at least ``min_size`` and on
    the source monitor. Menus, tooltips and omnibox drop-downs fail at least one test.
    """
    if not w.hwnd or w.hwnd == source or w.hwnd in own or not w.exists:
        return False
    if w.pid != pid or not w.visible or w.minimized or w.cloaked:
        return False
    if not w.title or any(x in w.title for x in OWN_TITLES) or w.cls in never_classes:
        return False
    if w.toolwindow or not w.has_caption:
        return False
    fr = w.frame
    if fr[2] - fr[0] < min_size[0] or fr[3] - fr[1] < min_size[1]:
        return False
    return intersects(fr, monitor)


def newest(seen: dict[int, float], alive: list[int]) -> int | None:
    """The most recently first-seen window among ``alive``."""
    return max(alive, key=lambda h: seen[h]) if alive else None


def focus_target(popup: int | None, source: int | None, alive) -> int | None:
    """The window to bring to the front when the panel's projector preview is clicked: the followed popup
    while one is projected, else the source. ``alive(hwnd)`` says whether a window still exists."""
    for h in (popup, source):
        if h and alive(h):
            return h
    return None
