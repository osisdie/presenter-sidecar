import pytest

from presenter_sidecar.config import DEFAULTS, load_config
from presenter_sidecar.geometry import fit_letterbox, map_point
from presenter_sidecar.overlay import (DEFAULT_MENU_CLASSES, WS_CAPTION, WS_EX_TOOLWINDOW, WS_EX_TOPMOST, WS_POPUP,
                                       Foreground, OverlaySettings, TopWin, clip, context_ok, flag, map_rect,
                                       menu_allowed, menu_like, near, over_any, overlay_action, overlay_blits,
                                       overlay_settings, panel_windows, pick_menus, popup_style, private_masks,
                                       region_grab, unknown_popups)

FRAME = (100, 50, 1700, 950)      # projected window, 1600 x 900
S = OverlaySettings()


def win(hwnd, cls, rect, pid=10, style=WS_POPUP, exstyle=0):
    return TopWin(hwnd=hwnd, cls=cls, rect=rect, pid=pid, style=style, exstyle=exstyle)


def test_settings_defaults_and_config_keys():
    s = overlay_settings(DEFAULTS)
    assert s.enabled is True and s.heuristic is False
    assert s.classes == frozenset(DEFAULT_MENU_CLASSES)
    off = overlay_settings({"menu_overlay": False, "menu_overlay_classes": ["#32768", "SysShadow", ""],
                            "menu_overlay_margin": 20, "menu_overlay_heuristic": True})
    assert off.enabled is False and off.heuristic is True and off.margin == 20
    assert off.classes == frozenset({"#32768"})  # shadows are never pasted


def test_example_config_ships_the_default_classes():
    cfg = load_config()  # config.example.json in a fresh clone
    assert cfg["menu_overlay"] is True
    assert tuple(cfg["menu_overlay_classes"]) == DEFAULT_MENU_CLASSES
    assert cfg["hotkeys"]["region"] == "Ctrl+Alt+R"


@pytest.mark.parametrize("bad", [{"menu_overlay_classes": "#32768"}, {"menu_overlay_margin": "x"},
                                 {"menu_overlay_max_size": [1]}, {"menu_overlay_interval_sec": None}])
def test_malformed_settings_fall_back(bad):
    s = overlay_settings(bad)
    d = OverlaySettings()
    assert (s.classes, s.margin, s.max_size) == (d.classes, d.margin, d.max_size)
    assert s.interval == d.interval or "menu_overlay_interval_sec" not in bad


def test_interval_is_clamped():
    assert overlay_settings({"menu_overlay_interval_sec": 0}).interval == 0.02
    assert overlay_settings({"menu_overlay_interval_sec": 99}).interval == 2.0


def test_near_overlap_and_adjacency():
    assert near((200, 200, 400, 400), FRAME, 0)
    assert near((1700, 100, 1900, 300), FRAME, 0) is False  # touching edge only
    assert near((1705, 100, 1900, 300), FRAME, 8)
    assert near((1709, 100, 1900, 300), FRAME, 8) is False


def test_menu_like_by_class_and_heuristic():
    assert menu_like(win(1, "#32768", (0, 0, 10, 10), style=0), S)
    assert not menu_like(win(1, "SysShadow", (0, 0, 10, 10)), OverlaySettings(classes=frozenset({"SysShadow"})))
    tool = win(1, "SomeMenuClass", (0, 0, 200, 300), exstyle=WS_EX_TOOLWINDOW)
    assert not menu_like(tool, S)  # heuristic off by default
    h = OverlaySettings(heuristic=True)
    assert menu_like(tool, h)
    assert menu_like(win(1, "X", (0, 0, 200, 300), exstyle=WS_EX_TOPMOST), h)
    assert not menu_like(win(1, "X", (0, 0, 200, 300), exstyle=0), h)                     # not tool / topmost
    assert not menu_like(win(1, "X", (0, 0, 200, 300), style=WS_POPUP | WS_CAPTION,
                             exstyle=WS_EX_TOOLWINDOW), h)                                   # has a caption
    assert not menu_like(win(1, "X", (0, 0, 2000, 300), exstyle=WS_EX_TOOLWINDOW), h)     # too big
    assert not menu_like(win(1, "X", (0, 0, 0, 300), exstyle=WS_EX_TOOLWINDOW), h)        # empty


def test_popup_style():
    assert popup_style(win(1, "X", (0, 0, 1, 1)))
    assert not popup_style(win(1, "X", (0, 0, 1, 1), style=0))
    assert not popup_style(win(1, "X", (0, 0, 1, 1), style=WS_POPUP | WS_CAPTION))


def test_pick_menus_filters_and_orders_bottom_first():
    wins = [  # EnumWindows order: topmost first
        win(1, "#32768", (900, 300, 1100, 500), pid=2),          # submenu (explorer.exe: other pid is fine)
        win(2, "SysShadow", (705, 205, 905, 605)),               # shadow: never
        win(3, "#32768", (700, 200, 900, 600)),                  # menu
        win(4, "Chrome_WidgetWin_1", (100, 50, 1700, 950)),      # a normal window
        win(5, "#32768", (3000, 200, 3200, 400)),                # far away
        win(6, "Chrome_WidgetWin_2", (1702, 60, 1900, 300)),     # adjacent (within 8 px)
        win(7, "#32768", (10, 10, 10, 400)),                     # empty rect
    ]
    got = pick_menus(wins, FRAME, S)
    assert [w.hwnd for w in got] == [6, 3, 1]


def test_pick_menus_skips_own_windows_panel_process_and_panel_rect():
    panel = (1750, 0, 2200, 1000)
    wins = [win(1, "#32768", (300, 300, 500, 500)),
            win(2, "Chrome_WidgetWin_2", (300, 300, 500, 500), pid=99),        # panel browser process
            win(3, "Chrome_WidgetWin_2", (1600, 400, 1800, 600), pid=10),      # opened in the panel strip
            win(4, "#32768", (400, 400, 600, 600))]                            # the projected window itself
    got = pick_menus(wins, FRAME, S, skip_hwnds={4}, skip_pids={99}, private=[panel])
    assert [w.hwnd for w in got] == [1]


def test_pick_menus_disabled():
    assert pick_menus([win(1, "#32768", (300, 300, 500, 500))], FRAME, OverlaySettings(enabled=False)) == []


def test_unknown_popups_reports_each_class_once():
    wins = [win(1, "NewMenuClass", (300, 300, 500, 500)),
            win(2, "NewMenuClass", (600, 300, 800, 500)),
            win(3, "#32768", (300, 300, 500, 500)),                    # known
            win(4, "SysShadow", (300, 300, 500, 500)),                 # ignored
            win(5, "Captioned", (300, 300, 500, 500), style=WS_POPUP | WS_CAPTION),
            win(6, "FarAway", (3000, 300, 3100, 500)),
            win(7, "Other", (300, 300, 500, 500), pid=99)]             # panel process
    assert unknown_popups(wins, FRAME, S, skip_pids={99}) == ["NewMenuClass"]


def test_clip():
    assert clip((0, 0, 10, 10), (5, 5, 20, 20)) == (5, 5, 10, 10)
    assert clip((0, 0, 5, 5), (5, 5, 20, 20)) is None


def test_map_rect_matches_the_pointer_mapping_with_letterbox():
    # 1600 x 900 frame onto a 1024 x 768 projector: letterboxed top and bottom.
    scale, ox, oy, tw, th = fit_letterbox(1600, 900, 1024, 768)
    assert (ox, oy, tw, th) == (0, 96, 1024, 576)
    r = (500, 250, 900, 650)
    x, y, w, h = map_rect(r, FRAME, ox, oy, tw, th)
    px0, py0 = map_point(r[0], r[1], FRAME, ox, oy, tw, th)
    px1, py1 = map_point(r[2], r[3], FRAME, ox, oy, tw, th)
    assert (x, y) == (round(px0), round(py0)) and (x + w, y + h) == (round(px1), round(py1))
    assert (x, y, w, h) == (256, 224, 256, 256)
    # The whole frame maps exactly onto the letterboxed picture.
    assert map_rect(FRAME, FRAME, ox, oy, tw, th) == (ox, oy, tw, th)


def test_map_rect_pillarbox_and_upscale():
    # A 1200 x 900 (4:3) popup on a 1920 x 1080 projector: pillarboxed and scaled 1.2x.
    frame = (0, 0, 1200, 900)
    scale, ox, oy, tw, th = fit_letterbox(1200, 900, 1920, 1080)
    assert (ox, oy, tw, th) == (240, 0, 1440, 1080)
    assert map_rect((100, 100, 300, 200), frame, ox, oy, tw, th) == (360, 120, 240, 120)


def test_neighbouring_rects_meet_without_a_gap():
    scale, ox, oy, tw, th = fit_letterbox(1600, 900, 1366, 768)
    a = map_rect((300, 300, 513, 500), FRAME, ox, oy, tw, th)
    b = map_rect((513, 300, 700, 500), FRAME, ox, oy, tw, th)
    assert a[0] + a[2] == b[0]


def test_overlay_blits_clip_to_the_frame():
    _, ox, oy, tw, th = fit_letterbox(1600, 900, 1600, 900)
    blits = overlay_blits([(1600, 800, 1900, 1100),     # sticks out at the bottom right
                           (1702, 60, 1900, 300),       # adjacent only: nothing visible
                           (200, 100, 400, 300)], FRAME, ox, oy, tw, th)
    assert blits == [((1600, 800, 1700, 950), (1500, 750, 100, 150)),
                     ((200, 100, 400, 300), (100, 50, 200, 200))]


def test_private_masks_for_region_mode():
    _, ox, oy, tw, th = fit_letterbox(1600, 900, 800, 450)
    assert private_masks(FRAME, [(1500, 0, 2000, 1000), (3000, 0, 3100, 10)], ox, oy, tw, th) == [(700, 0, 100, 450)]


def test_over_any():
    assert over_any([(0, 0, 10, 10), (20, 20, 30, 30)], 25, 25)
    assert not over_any([(0, 0, 10, 10)], 10, 5)


@pytest.mark.parametrize("v,want", [("false", False), ("False", False), ("0", False), ("off", False), ("", False),
                                    ("true", True), ("on", True), (False, False), (0, False), (1, True),
                                    (True, True), (None, True), ("maybe", True)])
def test_flag(v, want):
    assert flag(v, True) is want


def test_string_false_turns_the_overlay_off():
    s = overlay_settings({"menu_overlay": "false", "menu_overlay_heuristic": "true"})
    assert s.enabled is False and s.heuristic is True


# ---- whose menus are pasted (context_ok / menu_allowed / pick_menus with owner_pids)
CHROME, EXPLORER, CHAT, TEAMS = 100, 200, 300, 400       # process ids
SRC, CHAT_WIN = 1000, 3000                                # window handles


def owners(src_pid):
    return {SRC}, {src_pid}


def scan(src_pid, fg, menu, prev_ok=False):
    hwnds, pids = owners(src_pid)
    ok = context_ok(fg, hwnds, pids, S, prev_ok)
    return [w.hwnd for w in pick_menus([menu], FRAME, S, owner_pids=pids, ctx_ok=ok)], ok


def test_chrome_source_and_chrome_menu_are_pasted():
    # A Chrome menu never takes the foreground: the browser window stays foreground, same process.
    menu = win(1, "Chrome_WidgetWin_2", (300, 300, 500, 500), pid=CHROME)
    assert scan(CHROME, Foreground(root=SRC, pid=CHROME, cls="Chrome_WidgetWin_1"), menu) == ([1], True)


def test_explorer_source_and_explorer_menu_are_pasted():
    # The Win11 XAML menu belongs to explorer.exe, like the Explorer window, and may hold the focus itself.
    menu = win(1, "Xaml_WindowedPopupClass", (300, 300, 500, 500), pid=EXPLORER)
    fg = Foreground(root=7777, pid=EXPLORER, cls="Xaml_WindowedPopupClass")
    assert scan(EXPLORER, fg, menu) == ([1], True)


def test_menu_of_a_covering_app_is_not_pasted():
    # A chat window over the slides has the focus; its right-click menu touches the projected rect.
    fg = Foreground(root=CHAT_WIN, pid=CHAT, cls="Chrome_WidgetWin_1")
    for cls in ("Chrome_WidgetWin_2", "#32768"):
        assert scan(CHROME, fg, win(1, cls, (300, 300, 500, 500), pid=CHAT)) == ([], False)
    # ...even right after the user worked in the source: the covering window is visible and not a menu.
    assert scan(CHROME, fg, win(1, "#32768", (300, 300, 500, 500), pid=CHAT), prev_ok=True) == ([], False)


def test_source_menu_is_pasted_while_another_app_has_the_focus():
    # (a): the projected program's own menu or tooltip is fine wherever the focus is.
    fg = Foreground(root=CHAT_WIN, pid=CHAT, cls="Chrome_WidgetWin_1")
    assert scan(CHROME, fg, win(1, "tooltips_class32", (300, 300, 500, 500), pid=CHROME)) == ([1], False)


def test_tray_menu_while_the_taskbar_is_foreground_is_pasted():
    menu = win(1, "#32768", (1500, 700, 1700, 950), pid=TEAMS)
    for cls in ("Shell_TrayWnd", "Shell_SecondaryTrayWnd", "NotifyIconOverflowWindow",
                "TopLevelWindowForOverflowXamlIsland"):
        assert scan(CHROME, Foreground(root=5, pid=EXPLORER, cls=cls), menu) == ([1], True)


def test_tray_program_brings_its_hidden_window_to_the_front():
    # SetForegroundWindow(hidden window) + TrackPopupMenu, right after the taskbar click.
    menu = win(1, "#32768", (1500, 700, 1700, 950), pid=TEAMS)
    hidden = Foreground(root=6, pid=TEAMS, cls="TeamsHiddenWnd", visible=False)
    assert scan(CHROME, hidden, menu, prev_ok=True) == ([1], True)
    assert scan(CHROME, hidden, menu, prev_ok=False) == ([], False)


def test_menu_host_taking_the_focus_keeps_the_context_from_the_previous_scan():
    menu = win(1, "Microsoft.UI.Content.PopupWindowSiteBridge", (300, 300, 500, 500), pid=TEAMS)
    host = Foreground(root=8, pid=TEAMS, cls="Microsoft.UI.Content.PopupWindowSiteBridge")
    assert scan(CHROME, host, menu, prev_ok=True) == ([1], True)
    assert scan(CHROME, host, menu, prev_ok=False) == ([], False)


def test_followed_popup_counts_as_the_projected_program():
    popup_hwnd, popup_pid = 1001, 500
    fg = Foreground(root=popup_hwnd, pid=popup_pid, cls="#32770")
    assert context_ok(fg, {SRC, popup_hwnd}, {CHROME, popup_pid}, S, False)
    assert menu_allowed(win(1, "#32768", (0, 0, 1, 1), pid=popup_pid), {CHROME, popup_pid}, False)


def test_no_owner_check_when_owner_pids_is_none():
    assert [w.hwnd for w in pick_menus([win(1, "#32768", (300, 300, 500, 500), pid=CHAT)], FRAME, S,
                                       ctx_ok=False)] == [1]


# ---- region mode: panel process windows, overlay state, feedback guard
def test_panel_windows_masks_every_window_of_the_panel_process():
    wins = [win(1, "Chrome_WidgetWin_1", (1750, 0, 2200, 1000), pid=99),    # the panel
            win(2, "Chrome_WidgetWin_2", (1500, 300, 1800, 600), pid=99),   # its context menu over the source
            win(3, "Chrome_WidgetWin_2", (300, 300, 500, 500), pid=10),     # the source's menu
            win(4, "Chrome_WidgetWin_1", (0, 0, 0, 0), pid=99),             # empty
            win(5, "Chrome_WidgetWin_1", (100, 50, 1700, 950), pid=99)]     # kept (projected window)
    assert panel_windows(wins, {99}, {5}) == [(1750, 0, 2200, 1000), (1500, 300, 1800, 600)]
    assert panel_windows(wins, set()) == []
    win0 = win(6, "X", (1, 1, 2, 2), pid=0)
    assert panel_windows([win0], {0}) == []


@pytest.mark.parametrize("live,region,enabled,frozen,want", [
    (True, False, True, False, "update"),
    (True, True, True, False, "clear"),     # region mode shows the menus itself
    (True, False, False, False, "clear"),   # overlay off
    (False, False, True, True, "keep"),     # F8: the menus pasted when frozen stay
    (False, True, True, True, "keep"),      # region toggled while frozen: the frozen frame keeps its menus
    (False, False, True, False, "clear"),   # blank / no live frame
])
def test_overlay_action(live, region, enabled, frozen, want):
    assert overlay_action(live=live, region=region, enabled=enabled, frozen=frozen) == want


def test_region_grab_skips_the_projector_feedback_loop():
    assert region_grab("ok")
    assert not region_grab("on_projector")
