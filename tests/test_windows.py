from presenter_sidecar import PANEL_TITLE
from presenter_sidecar.windows import WindowInfo, auto_pick, newest, popup_eligible, source_allowed

MON = (0, 0, 1920, 1200)
NEVER = {"ConsoleWindowClass", "CASCADIA_HOSTING_WINDOW_CLASS"}


def popup(**kw):
    base = dict(hwnd=50, title="Sign in", cls="Chrome_WidgetWin_1", pid=7, frame=(200, 100, 720, 720))
    base.update(kw)
    return WindowInfo(**base)


def ok(w, **kw):
    args = dict(source=10, pid=7, own={99}, never_classes=NEVER, min_size=(320, 240), monitor=MON)
    args.update(kw)
    return popup_eligible(w, **args)


def test_real_popup_is_followed():
    assert ok(popup())


def test_popup_filters():
    assert not ok(popup(hwnd=10))                     # the source itself
    assert not ok(popup(hwnd=99))                     # the mirror window
    assert not ok(popup(pid=8))                       # another process
    assert not ok(popup(exists=False))
    assert not ok(popup(visible=False))
    assert not ok(popup(minimized=True))
    assert not ok(popup(cloaked=True))
    assert not ok(popup(title=""))                    # untitled: menus, omnibox drop-downs
    assert not ok(popup(title=PANEL_TITLE))
    assert not ok(popup(cls="ConsoleWindowClass"))
    assert not ok(popup(toolwindow=True))
    assert not ok(popup(has_caption=False))           # tooltips, extension bubbles
    assert not ok(popup(frame=(0, 0, 300, 600)))      # too narrow
    assert not ok(popup(frame=(0, 0, 600, 200)))      # too short
    assert not ok(popup(frame=(2000, 0, 2600, 600)))  # on another monitor


def test_popup_with_no_source_pid():
    assert not ok(popup(), pid=None)


def test_source_allowed():
    assert source_allowed(WindowInfo(1, "Docs - Google Chrome", "Chrome_WidgetWin_1"), {99}, NEVER) == (True, "")
    assert source_allowed(WindowInfo(0), set(), NEVER)[1] == "own_window"
    assert source_allowed(WindowInfo(99, "x"), {99}, NEVER)[1] == "own_window"
    assert source_allowed(WindowInfo(1, PANEL_TITLE + " - Google Chrome"), set(), NEVER)[1] == "panel_window"
    assert source_allowed(WindowInfo(1, "PowerShell", "CASCADIA_HOSTING_WINDOW_CLASS"), set(), NEVER)[1] == "blocked_class"
    assert source_allowed(WindowInfo(1, "Program Manager", "Progman"), set(), NEVER)[1] == "desktop"


def test_auto_pick_pattern_order_and_minimized_last():
    wins = [
        WindowInfo(1, "Notes", minimized=False),
        WindowInfo(2, "Demo (old)", minimized=True),
        WindowInfo(3, "Demo", minimized=False),
        WindowInfo(4, "Slides", minimized=False),
    ]
    assert auto_pick(wins, ["Demo"]) == 3          # visible beats minimized
    assert auto_pick(wins, ["Slides", "Demo"]) == 4  # first pattern wins
    assert auto_pick(wins, ["missing", "Notes"]) == 1
    assert auto_pick(wins, []) is None
    assert auto_pick(wins, ["missing"]) is None


def test_newest():
    seen = {1: 10.0, 2: 12.0, 3: 11.0}
    assert newest(seen, [1, 3]) == 3
    assert newest(seen, []) is None
