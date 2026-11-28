"""Menu overlay and region mode (pure): which windows to paste onto the projected frame, and where.

Right-click menus, Win11 context menus, tray menus, many drop-downs and tooltips are separate
top-level windows, so a window capture (WGC / PrintWindow) of the projected window never shows them.
The mirror lists the visible top-level windows (:class:`TopWin`), :func:`pick_menus` keeps the
menu-like ones over the projected frame, and :func:`overlay_blits` maps each one from screen
coordinates onto the projector with the same letterbox mapping as the frame (and the pointer).

All rects are ``(left, top, right, bottom)`` in physical pixels, like :mod:`.geometry`. The mirror is
per-monitor DPI aware, so window rects, mss screen grabs and the frame rect share one coordinate space
and no extra DPI factor is needed: the only scale is the frame → projector letterbox scale.

Clipping: a menu is cut to the projected window's visible frame. Nothing outside the window's own
rectangle reaches the projector (the same promise as region mode), and a menu that sticks out of the
window is shown only up to the window edge.

Whose menus (:func:`context_ok`): a window capture keeps projecting a window that another program
covers, so a menu over the frame may belong to that other program. A menu is pasted when it belongs to
the projected program (same process as the source or the followed popup), or when the user is working
in the projected window, the taskbar or the tray (:class:`Foreground`). Menus of a program that has the
focus over the projected window are not pasted.
"""
from __future__ import annotations

from dataclasses import dataclass

from .geometry import Rect, intersects

WS_POPUP = 0x80000000
WS_CAPTION = 0x00C00000
WS_EX_TOPMOST = 0x8
WS_EX_TOOLWINDOW = 0x80

# Window classes of menus and menu-like popups (config "menu_overlay_classes").
DEFAULT_MENU_CLASSES = (
    "#32768",                                       # Win32 menus: classic context menus, tray and taskbar menus
    "Chrome_WidgetWin_2",                           # Chrome / Edge / Chromium apps: context menus, drop-downs
    "Xaml_WindowedPopupClass",                      # Windows 11 XAML context menus (Explorer, taskbar)
    "Microsoft.UI.Content.PopupWindowSiteBridge",   # WinUI 3 popups and context menus
    "DropDown",                                     # shell drop-downs
    "ComboLBox",                                    # the open list of a classic combo box
    "tooltips_class32",                             # common-control tooltips
    "MozillaDropShadowWindowClass",                 # Firefox menus and drop-downs
    "Net UI Tool Window",                           # Office menus and galleries
)
# Never pasted, whatever the config says: drop shadows drawn as separate windows.
IGNORED_CLASSES = frozenset({"SysShadow"})
# The taskbar and the tray: a menu opened from there belongs to whatever program owns the icon.
SHELL_CLASSES = frozenset({"Shell_TrayWnd", "Shell_SecondaryTrayWnd", "NotifyIconOverflowWindow",
                           "TopLevelWindowForOverflowXamlIsland"})


@dataclass(frozen=True)
class TopWin:
    """Facts about one visible top-level window, gathered by the mirror with Win32 calls."""

    hwnd: int
    cls: str
    rect: Rect
    pid: int = 0
    style: int = 0
    exstyle: int = 0


@dataclass(frozen=True)
class Foreground:
    """The foreground window at a scan: its root window, process, class and visibility."""

    root: int = 0
    pid: int = 0
    cls: str = ""
    visible: bool = True


@dataclass(frozen=True)
class OverlaySettings:
    enabled: bool = True
    classes: frozenset = frozenset(DEFAULT_MENU_CLASSES)
    heuristic: bool = False        # also paste unknown captionless popups (WS_POPUP + tool window / topmost)
    margin: int = 8                # "adjacent": within this many pixels of the frame
    max_size: tuple[int, int] = (1600, 1400)   # heuristic only: bigger popups are not menus
    interval: float = 0.1          # seconds between full window scans (positions are re-checked every frame)


def flag(v, default: bool) -> bool:
    """A config on/off value. JSON booleans and numbers as usual; the strings "false", "0", "no", "off"
    and "" are false ("true", "1", "yes", "on" true); anything else falls back to ``default``."""
    if isinstance(v, str):
        x = v.strip().lower()
        if x in ("false", "0", "no", "off", ""):
            return False
        if x in ("true", "1", "yes", "on"):
            return True
        return default
    if v is None:
        return default
    return bool(v)


def _num(v, default, lo, hi, cast=float):
    try:
        x = cast(v)
    except (TypeError, ValueError):
        return default
    return min(hi, max(lo, x))


def overlay_settings(cfg: dict) -> OverlaySettings:
    """Read the ``menu_overlay*`` keys; anything malformed falls back to the default."""
    d = OverlaySettings()
    classes = cfg.get("menu_overlay_classes")
    if not isinstance(classes, (list, tuple)):
        classes = DEFAULT_MENU_CLASSES
    size = cfg.get("menu_overlay_max_size")
    if not (isinstance(size, (list, tuple)) and len(size) >= 2):
        size = d.max_size
    return OverlaySettings(
        enabled=flag(cfg.get("menu_overlay", d.enabled), d.enabled),
        classes=frozenset(str(c) for c in classes if c) - IGNORED_CLASSES,
        heuristic=flag(cfg.get("menu_overlay_heuristic", d.heuristic), d.heuristic),
        margin=_num(cfg.get("menu_overlay_margin", d.margin), d.margin, 0, 200, int),
        max_size=(_num(size[0], d.max_size[0], 1, 100000, int), _num(size[1], d.max_size[1], 1, 100000, int)),
        interval=_num(cfg.get("menu_overlay_interval_sec", d.interval), d.interval, 0.02, 2.0),
    )


def expand(r: Rect, m: int) -> Rect:
    return (r[0] - m, r[1] - m, r[2] + m, r[3] + m)


def clip(r: Rect, bound: Rect) -> Rect | None:
    """``r`` ∩ ``bound``, or None when they do not overlap."""
    c = (max(r[0], bound[0]), max(r[1], bound[1]), min(r[2], bound[2]), min(r[3], bound[3]))
    return c if c[0] < c[2] and c[1] < c[3] else None


def near(r: Rect, frame: Rect, margin: int) -> bool:
    """``r`` overlaps ``frame`` or lies within ``margin`` pixels of it."""
    return intersects(r, expand(frame, margin))


def popup_style(w: TopWin) -> bool:
    """A captionless popup window: what menus, drop-downs and tooltips look like."""
    return bool(w.style & WS_POPUP) and (w.style & WS_CAPTION) != WS_CAPTION


def menu_like(w: TopWin, s: OverlaySettings) -> bool:
    if w.cls in IGNORED_CLASSES:
        return False
    if w.cls in s.classes:
        return True
    if not s.heuristic or not popup_style(w) or not (w.exstyle & (WS_EX_TOOLWINDOW | WS_EX_TOPMOST)):
        return False
    width, height = w.rect[2] - w.rect[0], w.rect[3] - w.rect[1]
    return 0 < width <= s.max_size[0] and 0 < height <= s.max_size[1]


def _skipped(w: TopWin, skip_hwnds, skip_pids, private: list[Rect]) -> bool:
    if w.hwnd in skip_hwnds or w.pid in skip_pids:
        return True
    # A menu opened in the private panel contains the click point, so it overlaps the panel.
    return any(intersects(w.rect, p) for p in private)


def context_ok(fg: Foreground, owner_hwnds, owner_pids, s: OverlaySettings, prev_ok: bool) -> bool:
    """May menus of OTHER processes than the projected program be pasted at this scan?

    Yes while the user works in the projected program or the shell:

    - (b) the foreground root is the source or the followed popup, or belongs to their process. Win32
      ``#32768`` menus never take the foreground, so the owner stays foreground while one is open;
    - (c) the foreground is the taskbar or the tray (:data:`SHELL_CLASSES`): tray and taskbar menus;
    - (c) right after such a scan (``prev_ok``), the foreground is a menu window itself (a menu host
      that took the focus when it opened) or an invisible window (a tray program brings its hidden
      window to the front before it opens its tray menu).

    A visible window of another program in front (a chat window over the slides) makes it False, so
    that program's menus, drop-downs and autofill lists are not pasted.
    """
    if fg.root and fg.root in owner_hwnds:
        return True
    if fg.pid and fg.pid in owner_pids:
        return True
    if fg.cls in SHELL_CLASSES:
        return True
    return prev_ok and (not fg.visible or (fg.cls in s.classes and fg.cls not in IGNORED_CLASSES))


def menu_allowed(w: TopWin, owner_pids, ctx_ok: bool) -> bool:
    """(a) a menu of the projected program itself (same process as the source or the followed popup)
    is always pasted; any other process's menu only while :func:`context_ok`."""
    return w.pid in owner_pids or ctx_ok


def pick_menus(wins: list[TopWin], frame: Rect, s: OverlaySettings, *, skip_hwnds=frozenset(),
               skip_pids=frozenset(), private: list[Rect] | None = None, owner_pids=None,
               ctx_ok: bool = True) -> list[TopWin]:
    """Menu-like windows over (or next to) ``frame``, bottom-most first so later ones are pasted on top.

    ``wins`` comes from EnumWindows, which lists top-level windows topmost first. Other processes count
    (Explorer menus belong to explorer.exe) under :func:`menu_allowed`: ``owner_pids`` are the projected
    program's processes (None: no check), ``ctx_ok`` is :func:`context_ok`. ``skip_hwnds`` are the
    tool's own windows and the projected window itself, ``skip_pids`` the panel browser's process,
    ``private`` the panel's rect.
    """
    if not s.enabled:
        return []
    private = private or []
    out = [w for w in wins
           if w.rect[0] < w.rect[2] and w.rect[1] < w.rect[3] and near(w.rect, frame, s.margin)
           and menu_like(w, s) and not _skipped(w, skip_hwnds, skip_pids, private)
           and (owner_pids is None or menu_allowed(w, owner_pids, ctx_ok))]
    out.reverse()
    return out


def unknown_popups(wins: list[TopWin], frame: Rect, s: OverlaySettings, *, skip_hwnds=frozenset(),
                   skip_pids=frozenset(), private: list[Rect] | None = None) -> list[str]:
    """Classes of popup-looking windows over the frame that are NOT pasted: logged once each, so a menu
    that is still missing on the projector can be added to ``menu_overlay_classes``."""
    private = private or []
    seen: list[str] = []
    for w in wins:
        if (w.cls and w.cls not in seen and w.cls not in IGNORED_CLASSES and popup_style(w)
                and intersects(w.rect, frame) and not menu_like(w, s)
                and not _skipped(w, skip_hwnds, skip_pids, private)):
            seen.append(w.cls)
    return seen


def map_rect(r: Rect, frame: Rect, ox: int, oy: int, tw: int, th: int) -> tuple[int, int, int, int]:
    """A screen rect inside ``frame`` → ``(x, y, w, h)`` on the projector.

    Same mapping as :func:`.geometry.map_point` (frame → letterboxed ``tw`` × ``th`` at ``ox, oy``). Both
    edges are rounded, so neighbouring rects (a menu and its submenu) meet without a gap.
    """
    fw, fh = max(1, frame[2] - frame[0]), max(1, frame[3] - frame[1])
    x0 = round(ox + (r[0] - frame[0]) * tw / fw)
    y0 = round(oy + (r[1] - frame[1]) * th / fh)
    x1 = round(ox + (r[2] - frame[0]) * tw / fw)
    y1 = round(oy + (r[3] - frame[1]) * th / fh)
    return x0, y0, max(1, x1 - x0), max(1, y1 - y0)


def overlay_blits(rects: list[Rect], frame: Rect, ox: int, oy: int, tw: int, th: int
                  ) -> list[tuple[Rect, tuple[int, int, int, int]]]:
    """For each menu rect: ``(screen rect to grab, projector (x, y, w, h))``, clipped to ``frame``.
    Menus entirely outside the frame are dropped."""
    out = []
    for r in rects:
        c = clip(r, frame)
        if c:
            out.append((c, map_rect(c, frame, ox, oy, tw, th)))
    return out


def panel_windows(wins: list[TopWin], panel_pids, keep_hwnds=frozenset()) -> list[Rect]:
    """Region mode: rects of every visible top-level window of the panel browser's process. The panel
    window itself, and its own popups (context menu, ``<select>`` list, autofill, permission bubble),
    are separate windows of that process; all of them are painted black. ``keep_hwnds`` (the projected
    window) are never masked. The panel runs in its own browser profile, so that process holds nothing
    else."""
    return [w.rect for w in wins
            if w.pid and w.pid in panel_pids and w.hwnd not in keep_hwnds
            and w.rect[0] < w.rect[2] and w.rect[1] < w.rect[3]]


def overlay_action(*, live: bool, region: bool, enabled: bool, frozen: bool) -> str:
    """What the menu overlay does this frame: "update" (scan and grab the menus), "keep" (frozen: the
    menus pasted when F8 was pressed stay) or "clear" (blank screen, no live frame, region mode — which
    shows the menus itself — or overlay off)."""
    if live and not region and enabled:
        return "update"
    return "keep" if frozen else "clear"


def region_grab(src_state: str) -> bool:
    """Region mode copies the screen: never while the projected window lies on the projector itself
    (it would copy its own output, a feedback loop). The panel shows the "on_projector" warning."""
    return src_state == "ok"


def private_masks(frame: Rect, private: list[Rect], ox: int, oy: int, tw: int, th: int
                  ) -> list[tuple[int, int, int, int]]:
    """Region mode: projector ``(x, y, w, h)`` areas to paint black because one of the panel's windows
    (:func:`panel_windows`) lies over the captured rectangle."""
    out = []
    for p in private:
        c = clip(p, frame)
        if c:
            out.append(map_rect(c, frame, ox, oy, tw, th))
    return out


def over_any(rects: list[Rect], x: float, y: float) -> bool:
    """Is the point inside one of ``rects`` (the pasted menus)? The pointer is drawn over them too."""
    return any(r[0] <= x < r[2] and r[1] <= y < r[3] for r in rects)
