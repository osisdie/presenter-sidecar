import pytest

from presenter_sidecar.config import DEFAULTS, load_config
from presenter_sidecar.geometry import fit_letterbox, map_point
from presenter_sidecar.overlay import (DEFAULT_MENU_CLASSES, WS_CAPTION, WS_EX_TOOLWINDOW, WS_EX_TOPMOST, WS_POPUP,
                                       OverlaySettings, TopWin, clip, map_rect, menu_like, near, over_any,
                                       overlay_blits, overlay_settings, pick_menus, popup_style, private_masks,
                                       unknown_popups)

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
