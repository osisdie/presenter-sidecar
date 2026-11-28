"""Headless browser checks of the panel: projector preview (and clicking it), collapsible blocks.

Skipped unless Playwright and Chromium are installed (dev only, like scripts/media):
    python -m pip install playwright pillow && python -m playwright install chromium
Everything runs on an ephemeral 127.0.0.1 port with the example notes, a fake preview image in a
temporary logs/ folder and a fake mirror status; no real display or window is used.
"""
from __future__ import annotations

import io
import json
import threading
import time

import pytest

import os  # noqa: E402

if os.environ.get("REQUIRE_UI_TESTS"):  # the CI job that installs Playwright: never skip silently
    import playwright.sync_api as sync_api
    from PIL import Image
else:
    sync_api = pytest.importorskip("playwright.sync_api")
    Image = pytest.importorskip("PIL.Image")

import panel_server  # noqa: E402
from presenter_sidecar.config import ROOT  # noqa: E402
from presenter_sidecar.preview import PREVIEW_FILE  # noqa: E402

FOLDS = ["preview", "source", "timer", "nav"]
LAYOUT = """(() => { const n = document.querySelector('#note').getBoundingClientRect(),
  d = document.querySelector('#dock').getBoundingClientRect();
  return { note: n.height, noteBottom: n.bottom, dock: d.height, dockTop: d.top, dockBottom: d.bottom,
           inner: innerHeight }; })()"""


def jpeg(color=(40, 120, 200), size=(480, 270)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "JPEG", quality=70)
    return buf.getvalue()


class FakeMirror:
    """Keeps the mirror status fresh (like mirror.py's 1 s report) until ``connected`` is False."""

    def __init__(self, app):
        self.app, self.connected, self.stop = app, True, False
        self.status = {"fps": 25.0, "frozen": False, "blank": False, "style": "ring", "clip": True,
                       "backend": "wgc", "source_title": "Plant-care App - Google Chrome", "source_state": "ok",
                       "follow_popups": True, "warning": "", "notice": "", "hotkeys_failed": [],
                       "preview": {"enabled": True, "age": 0.5, "seq": 1}}
        threading.Thread(target=self.run, daemon=True).start()

    def run(self):
        while not self.stop:
            if self.connected:
                with self.app.lock:
                    self.app.mirror, self.app.mirror_ts = dict(self.status), time.time()
            time.sleep(0.2)


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as p:
        try:
            b = p.chromium.launch(headless=True)
        except Exception as e:  # noqa: BLE001 - browser not installed
            if os.environ.get("REQUIRE_UI_TESTS"):
                raise
            pytest.skip(f"chromium not available: {e}")
        yield b
        b.close()


def make_env(tmp_path, lang="en", profile=None, **over):
    cfg = json.loads((ROOT / "config.example.json").read_text(encoding="utf-8"))
    cfg["content_root"] = str(ROOT)
    cfg["ui_lang"] = lang
    cfg.update(over)
    p = tmp_path / "config.json"
    p.write_text(json.dumps(cfg), encoding="utf-8")
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / PREVIEW_FILE).write_bytes(jpeg())
    app = panel_server.App(p, logs=logs, profile=profile)
    srv = panel_server.make_server(app, "127.0.0.1", 0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return app, srv, FakeMirror(app)


@pytest.fixture()
def env_factory(tmp_path):
    made = []

    def make(**kw):
        sub = tmp_path / f"env{len(made)}"
        sub.mkdir()
        app, srv, mirror = make_env(sub, **kw)
        made.append((srv, mirror))
        return app, srv.server_address[1], mirror
    yield make
    for srv, mirror in made:
        mirror.stop = True
        srv.shutdown()
        srv.server_close()


@pytest.fixture()
def env(tmp_path):
    app, srv, mirror = make_env(tmp_path)
    yield app, srv.server_address[1], mirror
    mirror.stop = True
    srv.shutdown()
    srv.server_close()


class Panel:
    """One browser context (own localStorage) on the panel, recording console errors and preview fetches."""

    def __init__(self, browser, port, width=400, height=900):
        self.ctx = browser.new_context(viewport={"width": width, "height": height})
        self.page = self.ctx.new_page()
        self.errors: list[str] = []
        self.fetches: list[float] = []
        self.page.on("console", lambda m: m.type == "error" and self.errors.append(m.text))
        self.page.on("pageerror", lambda e: self.errors.append(str(e)))
        self.page.on("request", lambda r: "/api/preview" in r.url and self.fetches.append(time.time()))
        self.url = f"http://127.0.0.1:{port}/"
        self.open()

    def open(self):
        self.page.goto(self.url)
        self.page.wait_for_function("document.querySelector('#secSel').options.length > 0")
        self.page.wait_for_timeout(900)  # first /api/state poll

    def reload(self):
        self.page.reload()
        self.page.wait_for_function("document.querySelector('#secSel').options.length > 0")
        self.page.wait_for_timeout(900)

    def head(self, name):
        return self.page.locator(f'.fold[data-fold="{name}"] > .foldhead')

    def is_open(self, name) -> bool:
        return self.head(name).get_attribute("aria-expanded") == "true"

    def body_visible(self, name) -> bool:
        return self.page.locator(f'.fold[data-fold="{name}"] > .foldbody').is_visible()

    def fetches_during(self, ms) -> int:
        n = len(self.fetches)
        self.page.wait_for_timeout(ms)
        return len(self.fetches) - n

    def set_visibility(self, state):
        self.page.evaluate("""(s) => {
          Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => s });
          document.dispatchEvent(new Event('visibilitychange'));
        }""", state)

    def close(self):
        errors = list(self.errors)
        self.ctx.close()
        assert not errors, f"console errors: {errors}"


def test_preview_collapsed_by_default_then_expands_with_image_and_age(browser, env):
    _, port, _ = env
    pn = Panel(browser, port)
    assert not pn.is_open("preview") and not pn.body_visible("preview")
    assert pn.head("preview").inner_text().startswith("▸")
    for name in ("source", "timer", "nav"):
        assert pn.is_open(name) and pn.body_visible(name) and pn.head(name).inner_text().startswith("▾")
    assert pn.fetches_during(2500) == 0  # closed: never fetched
    pn.head("preview").click()
    assert pn.is_open("preview")
    pn.page.wait_for_function("document.querySelector('#previewImg').naturalWidth === 480", timeout=3000)
    assert pn.page.locator("#previewImg").is_visible()
    assert pn.page.locator("#previewAge").inner_text().endswith("s ago")
    assert "stale" not in pn.page.locator("#preview").get_attribute("class")
    assert pn.page.locator("#previewImg").get_attribute("alt")
    # Docked at the bottom edge, below the notes, which keep the rest of the height.
    box = pn.page.evaluate(LAYOUT)
    assert abs(box["dockBottom"] - box["inner"]) <= 1 and abs(box["noteBottom"] - box["dockTop"]) <= 1
    assert box["dock"] > 150 and box["note"] > 120  # every block open at 900 px: still a readable notes view
    pn.close()


def test_preview_refreshes_only_while_open_and_visible(browser, env):
    _, port, _ = env
    pn = Panel(browser, port)
    pn.head("preview").click()
    assert pn.fetches_during(4500) >= 2
    pn.set_visibility("hidden")
    pn.page.wait_for_timeout(300)  # a fetch already in flight may finish
    assert pn.fetches_during(4500) == 0
    n = len(pn.fetches)
    pn.set_visibility("visible")  # becoming visible fetches right away
    pn.page.wait_for_timeout(800)
    assert len(pn.fetches) - n >= 1
    pn.head("preview").click()
    pn.page.wait_for_timeout(300)
    assert pn.fetches_during(4500) == 0
    pn.close()


def test_stale_image_and_disconnected_mirror_are_greyed(browser, env):
    _, port, mirror = env
    pn = Panel(browser, port)
    pn.head("preview").click()
    pn.page.wait_for_function("document.querySelector('#previewImg').naturalWidth > 0", timeout=3000)
    stale = "document.querySelector('#preview').classList.contains('stale')"
    mirror.status["preview"] = {"enabled": True, "age": 30, "seq": 1}
    pn.page.wait_for_function(stale, timeout=3000)
    assert "over 10 s" in pn.page.locator("#previewNote").inner_text()
    mirror.status["preview"] = {"enabled": True, "age": 0.4, "seq": 2}
    pn.page.wait_for_function("!" + stale, timeout=3000)
    assert pn.page.locator("#previewNote").inner_text() == ""
    mirror.connected = False  # no status for > 4 s
    pn.page.wait_for_function(stale, timeout=8000)
    assert pn.page.locator("#previewNote").inner_text() == "Mirror not connected"
    assert pn.page.locator("#previewImg").is_visible()  # the last image stays, greyed out
    pn.head("preview").click()  # closed: the summary still says why
    assert "Mirror not connected" in pn.page.locator("#previewSum").inner_text()
    pn.close()


def test_frozen_and_blank_badges_in_the_preview_and_the_closed_summary(browser, env):
    _, port, mirror = env
    pn = Panel(browser, port)
    pn.head("preview").click()
    mirror.status.update(frozen=True)
    pn.page.wait_for_selector("#previewBadges .pbadge.frozen", timeout=3000)
    assert pn.page.locator("#previewBadges").inner_text().strip() == "Frozen"
    mirror.status.update(frozen=False, blank=True)
    pn.page.wait_for_selector("#previewBadges .pbadge.blank", timeout=3000)
    assert pn.page.locator("#previewBadges .pbadge").count() == 1
    pn.head("preview").click()
    assert pn.page.locator("#previewSum").inner_text() == "Blank" and pn.page.locator("#previewSum").is_visible()
    mirror.status.update(blank=False)
    pn.page.wait_for_function("document.querySelector('#previewSum').textContent === ''", timeout=3000)
    pn.close()


def test_region_mode_badge_in_the_preview_and_the_source_line(browser, env):
    _, port, mirror = env
    pn = Panel(browser, port)
    assert pn.page.locator("#srcMode").is_hidden()
    pn.head("preview").click()
    mirror.status.update(capture_mode="region", menu_overlay=False)
    pn.page.wait_for_selector("#previewBadges .pbadge.region", timeout=3000)
    assert pn.page.locator("#previewBadges").inner_text().strip() == "Region"
    assert pn.page.locator("#srcMode").is_visible() and pn.page.locator("#srcMode").inner_text() == "Region"
    assert "F8" in pn.page.locator("#srcMode").get_attribute("title")
    pn.head("source").click()  # closed: the summary still says region mode
    assert pn.page.locator("#sourceSum").inner_text().startswith("[Region] ")
    pn.head("source").click()
    mirror.status.update(capture_mode="window", menu_overlay=True)
    pn.page.wait_for_function("document.querySelector('#srcMode').hidden", timeout=3000)
    assert pn.page.locator("#previewBadges .pbadge").count() == 0
    mirror.status.update(capture_mode="region")
    pn.page.wait_for_function("!document.querySelector('#srcMode').hidden", timeout=3000)
    mirror.connected = False  # a stale status is not a mode
    pn.page.wait_for_function("document.querySelector('#srcMode').hidden", timeout=8000)
    pn.close()


def test_region_hotkey_is_listed_in_the_shortcut_overlay(browser, env):
    _, port, _ = env
    pn = Panel(browser, port)
    pn.page.keyboard.press("?")
    row = pn.page.locator("#keysGlobal tr", has_text="Region mode")
    assert row.count() == 1 and "Ctrl+Alt+R" in "".join(row.inner_text().split())
    pn.close()


def test_zh_tw_labels(browser, tmp_path):
    app, srv, mirror = make_env(tmp_path, lang="zh-TW")
    try:
        mirror.status.update(frozen=True, blank=True, preview={"enabled": True, "age": 3.2, "seq": 1})
        pn = Panel(browser, srv.server_address[1])
        assert "".join(pn.head("preview").inner_text().split()).startswith("▸投影畫面")
        pn.head("preview").click()
        pn.page.wait_for_selector("#previewBadges .pbadge.frozen", timeout=3000)
        assert pn.page.locator("#previewBadges").inner_text().split() == ["請稍候", "凍結"]
        assert "秒前" in pn.page.locator("#previewAge").inner_text()
        mirror.status.update(capture_mode="region")
        pn.page.wait_for_selector("#previewBadges .pbadge.region", timeout=3000)
        assert pn.page.locator("#previewBadges").inner_text().split() == ["請稍候", "凍結", "區域"]
        assert pn.page.locator("#srcMode").inner_text() == "區域"
        pn.close()
    finally:
        mirror.stop = True
        srv.shutdown()
        srv.server_close()


def focus_posts(pn) -> list[str]:
    """Record the panel's POST /api/focus requests (the X-Panel header included)."""
    posts: list[str] = []
    pn.page.on("request", lambda r: r.method == "POST" and r.url.endswith("/api/focus")
               and posts.append(r.headers.get("x-panel", "")))
    return posts


def wait_toast(pn, text):
    pn.page.wait_for_function("(t) => { const e = document.querySelector('#toast');"
                              " return !e.hidden && e.textContent.includes(t); }", arg=text, timeout=3000)


def test_clicking_the_preview_asks_the_mirror_to_bring_the_window_forward(browser, env):
    app, port, _ = env
    pn = Panel(browser, port)
    posts = focus_posts(pn)
    pn.head("preview").click()  # the fold header only folds: no focus request
    pn.page.wait_for_function("document.querySelector('#previewImg').naturalWidth > 0", timeout=3000)
    assert posts == []
    pv = pn.page.locator("#preview")
    assert pv.get_attribute("role") == "button" and pv.get_attribute("tabindex") == "0"
    assert "front" in pv.get_attribute("aria-label") and "front" in pv.get_attribute("title")
    assert pv.evaluate("(e) => getComputedStyle(e).cursor") == "pointer"
    pv.click()
    wait_toast(pn, "bring the projected window to the front")
    assert posts == ["1"] and pn.is_open("preview")  # clicking the picture never folds the block
    assert len(app.mirror_do) == 1
    # Keyboard: focusable, a visible focus ring, Enter and Space press it (Space does not move the notes).
    pv.focus()
    pn.page.keyboard.press("Enter")
    pn.page.wait_for_timeout(300)
    assert len(posts) == 2
    assert pv.evaluate("(e) => e.matches(':focus-visible') && getComputedStyle(e).outlineWidth === '2px'")
    note_top = pn.page.evaluate("document.querySelector('#note').scrollTop")
    pn.page.keyboard.press(" ")
    pn.page.wait_for_timeout(300)
    assert len(posts) == 3 and pn.is_open("preview")
    assert pn.page.evaluate("document.querySelector('#note').scrollTop") == note_top
    assert len(app.mirror_do) == 1  # queued once: the mirror brings it forward once
    pn.close()


def test_preview_click_toast_without_a_source_or_a_mirror(browser, env):
    app, port, mirror = env
    mirror.status.update(source_title="", source_state="none", warning="No source window.")
    pn = Panel(browser, port)
    pn.head("preview").click()
    pn.page.locator("#preview").click()
    wait_toast(pn, "press F7")  # the pick hotkey from the config
    mirror.connected = False
    with app.lock:
        app.mirror_ts -= 60  # the mirror stopped reporting
    app.mirror_do.take(0.0)
    pn.page.wait_for_timeout(500)  # the toast's own timer is restarted by the next one
    pn.page.locator("#preview").click()
    wait_toast(pn, "Mirror not connected")
    assert len(app.mirror_do) == 0  # nothing waits for a mirror that is gone
    pn.close()


def test_preview_click_toast_in_zh_tw(browser, tmp_path):
    app, srv, mirror = make_env(tmp_path, lang="zh-TW")
    try:
        mirror.status.update(following_popup=True, popup_title="Sign in")
        pn = Panel(browser, srv.server_address[1])
        pn.head("preview").click()
        assert pn.page.locator("#preview").get_attribute("aria-label").startswith("投影畫面")
        pn.page.locator("#preview").click()
        wait_toast(pn, "已請 mirror 把跟隨中的彈窗帶到前面")
        pn.close()
    finally:
        mirror.stop = True
        srv.shutdown()
        srv.server_close()


def test_collapse_state_is_saved_and_keyboard_accessible(browser, env):
    _, port, _ = env
    pn = Panel(browser, port)
    for name in ("source", "timer", "nav"):
        pn.head(name).click()
    pn.head("preview").focus()
    pn.page.keyboard.press("Enter")  # a real button: Enter and Space toggle it
    assert pn.is_open("preview")
    assert pn.page.evaluate("document.activeElement.matches('.foldhead:focus-visible')")
    pn.page.keyboard.press(" ")
    assert not pn.is_open("preview")
    pn.page.keyboard.press(" ")
    pn.reload()
    assert pn.is_open("preview") and pn.body_visible("preview")
    for name in ("source", "timer", "nav"):
        assert not pn.is_open(name) and not pn.body_visible(name)
        assert pn.head(name).inner_text().startswith("▸")
        assert pn.head(name).get_attribute("aria-controls")
    # Closed blocks summarise themselves on their header line.
    assert "Plant-care App" in pn.page.locator("#sourceSum").inner_text()
    assert pn.page.locator("#navSum").inner_text().startswith("1/")
    assert pn.page.locator("#timerSum").inner_text() == "Not started"
    pn.close()


def test_hotkeys_scroll_spy_and_notes_height_with_blocks_closed(browser, env):
    _, port, _ = env
    pn = Panel(browser, port)
    page = pn.page
    full = page.evaluate("document.querySelector('#note').getBoundingClientRect().height")
    for name in ("source", "timer", "nav"):
        pn.head(name).click()
    page.locator("#note").click()  # focus back on the notes, not a header button
    box = page.evaluate(LAYOUT)
    assert box["note"] > full + 100 and abs(box["noteBottom"] - box["dockTop"]) <= 1  # takes the freed height
    assert abs(box["dockBottom"] - box["inner"]) <= 1 and box["dock"] < 40  # closed preview: one row at the bottom
    # ← / → page sections; find the section with steps (Demo C) with →.
    page.keyboard.press("Home")
    assert page.evaluate("secIdx") == 0
    for _ in range(12):
        if page.evaluate("steps.length") > 1:
            break
        page.keyboard.press("ArrowRight")
    assert page.evaluate("steps.length") > 1, "example notes should have a section with steps"
    sec = page.evaluate("secIdx")
    page.keyboard.press("ArrowLeft")
    assert page.evaluate("secIdx") == sec - 1
    page.keyboard.press("ArrowRight")
    page.keyboard.press("j")
    assert page.evaluate("stepIdx") == 1
    page.keyboard.press("k")
    assert page.evaluate("stepIdx") == 0
    assert "(1/" in page.locator("#navSum").inner_text()
    # Scroll-spy: scrolling the notes by hand to step 2 moves the (hidden) step drop-down and the summary.
    page.evaluate("""(() => { const art = document.querySelector('#note'), s = steps[1].el;
      art.scrollTop += s.getBoundingClientRect().top - art.getBoundingClientRect().top; })()""")
    page.wait_for_function("stepIdx === 1", timeout=2000)
    assert page.locator("#stepSel").input_value() == "1"
    assert "(2/" in page.locator("#navSum").inner_text()
    # ? opens the shortcut list, Esc closes it; the fold buttons are inert behind it.
    page.keyboard.press("?")
    assert page.locator("#keysOverlay").is_visible()
    assert page.evaluate("document.querySelector('header').inert && document.querySelector('footer').inert")
    page.keyboard.press("Escape")
    assert not page.locator("#keysOverlay").is_visible()
    pn.close()


@pytest.mark.parametrize("width", [320, 400])
def test_no_horizontal_overflow(browser, env, width):
    _, port, mirror = env
    mirror.status.update(source_title="A very long projected window title " * 6, frozen=True, blank=True,
                         warning="Source window is on the projector display. Press Shift+F7 to bring it back.")
    pn = Panel(browser, port, width=width, height=700)
    pn.head("preview").click()
    pn.page.wait_for_function("document.querySelector('#previewImg').naturalWidth > 0", timeout=3000)
    check = """() => {
      const bad = [];
      // Clipped by an ancestor that hides its overflow inside the window (ellipsis lines): not visible.
      const clipped = (el) => {
        for (let a = el.parentElement; a && a !== document.body; a = a.parentElement)
          if (getComputedStyle(a).overflowX !== 'visible' && a.getBoundingClientRect().right <= innerWidth + 0.5) return true;
        return false;
      };
      for (const el of document.querySelectorAll('header *, main *, footer *')) {
        const r = el.getBoundingClientRect();
        if (r.width && r.right > innerWidth + 0.5 && el.offsetParent !== null && !clipped(el))
          bad.push(el.id || el.className || el.tagName);
      }
      return { bad, sw: document.documentElement.scrollWidth, iw: innerWidth };
    }"""
    for state in ("open", "closed"):
        if state == "closed":
            for name in FOLDS:
                pn.head(name).click()
            pn.page.wait_for_timeout(800)
        res = pn.page.evaluate(check)
        assert res["sw"] <= res["iw"] and not res["bad"], (width, state, res)
    pn.close()


def test_ai_tab_conversation_block_collapses_and_keeps_the_form(browser, env):
    _, port, _ = env
    pn = Panel(browser, port)
    pn.page.locator("#tabAi").click()
    assert pn.is_open("chat") and pn.page.locator("#chat").is_visible()
    pn.head("chat").click()
    assert not pn.page.locator("#chat").is_visible() and pn.head("chat").is_visible()
    pn.reload()  # the AI tab and the closed block are both remembered
    assert not pn.is_open("chat") and pn.page.locator("#tab-ai").is_visible()
    pn.close()


@pytest.mark.parametrize("height", [600, 700])
def test_short_panel_with_the_preview_open_keeps_the_notes(browser, env, height):
    # A 1080p laptop at 150 % gives a panel of about 650-690 CSS px: every block open, preview open.
    _, port, _ = env
    pn = Panel(browser, port, width=400, height=height)
    pn.head("preview").click()
    pn.page.wait_for_function("document.querySelector('#previewImg').naturalWidth > 0", timeout=3000)
    pn.page.wait_for_timeout(300)
    box = pn.page.evaluate(LAYOUT)
    assert box["note"] >= 0.25 * height, box                       # at least about 30vh of notes
    assert box["noteBottom"] <= box["dockTop"] + 1, box            # not under the dock
    assert abs(box["dockBottom"] - box["inner"]) <= 1, box         # dock still on the bottom edge
    assert pn.page.locator("#secSel").is_visible()
    hit = pn.page.evaluate("""(() => { const r = document.querySelector('#note').getBoundingClientRect();
      const el = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
      return !!el && document.querySelector('#note').contains(el); })()""")
    assert hit, "the notes must receive clicks"
    assert pn.head("preview").is_visible()                         # the dock keeps at least its header row
    if height >= 700:
        assert pn.page.locator("#previewImg").bounding_box()["height"] > 40  # a smaller picture, not none
    pn.close()


def test_preview_is_hidden_when_turned_off_or_deleted(browser, env):
    app, port, mirror = env
    pn = Panel(browser, port)
    pn.head("preview").click()
    pn.page.wait_for_function("document.querySelector('#previewImg').naturalWidth > 0", timeout=3000)
    mirror.status["preview"] = {"enabled": False, "age": None, "seq": 1, "errors": 0}  # e.g. an encode error
    pn.page.wait_for_function("document.querySelector('#previewImg').hidden", timeout=3000)
    assert pn.page.locator("#previewEmpty").inner_text() == "Preview off"
    mirror.status["preview"] = {"enabled": True, "age": None, "seq": 0, "errors": 0}
    (app.logs / PREVIEW_FILE).unlink()  # mirror restart: the old picture is gone
    pn.page.wait_for_function("document.querySelector('#previewEmpty').textContent === 'No image yet'", timeout=3000)
    assert pn.page.locator("#previewImg").is_hidden()
    pn.close()


# ---------------------------------------------------------------- profiles
STAGES = "[...document.querySelectorAll('#stages button')].map(b => b.textContent)"
DOCS = "[...document.querySelectorAll('#docs button')].map(b => b.textContent)"


def switch_profile(pn, name):
    pn.page.select_option("#profileSel", name)
    pn.page.wait_for_function("(n) => profile === n && !switching", arg=name, timeout=3000)


def test_profile_switch_changes_notes_stages_and_rules_together(browser, env):
    _, port, _ = env
    pn = Panel(browser, port)
    sel = pn.page.locator("#profileSel")
    assert sel.is_visible() and sel.input_value() == "talk"
    assert [o.strip() for o in sel.locator("option").all_inner_texts()] == ["talk", "meeting"]
    assert pn.page.evaluate(STAGES)[:2] == ["Intro", "Demo A"]
    switch_profile(pn, "meeting")
    assert pn.page.evaluate(STAGES) == ["Part 1", "Part 2", "Part 3", "Part 4"]
    assert pn.page.evaluate(DOCS) == ["meeting"]
    assert "Weekly sync" in pn.page.locator("#note").inner_text()
    pn.page.locator("#note").click()
    pn.page.keyboard.press("ArrowRight")  # the keys page the meeting notes now
    assert pn.page.locator("#secSel").input_value() == "1"
    switch_profile(pn, "talk")
    assert pn.page.evaluate(STAGES)[0] == "Intro" and len(pn.page.evaluate(DOCS)) == 3
    pn.reload()  # the profile picked by hand survives F5
    assert pn.page.locator("#profileSel").input_value() == "talk"
    pn.close()


def test_timers_are_kept_per_profile(browser, env):
    _, port, _ = env
    pn = Panel(browser, port)
    page = pn.page
    page.click("#btnStart")
    talk = page.evaluate("JSON.parse(JSON.stringify(timer))")
    assert talk["cur"] == 0 and talk["classStart"]
    switch_profile(pn, "meeting")
    assert page.locator("#stageName").inner_text() == "Not started"
    page.click("#btnStart")
    page.click("#btnNext")
    assert page.locator("#stageName").inner_text().startswith("Part 2")
    switch_profile(pn, "talk")
    assert page.evaluate("JSON.parse(JSON.stringify(timer))") == talk  # untouched by the meeting timer
    assert page.locator("#stageName").inner_text().startswith("Intro")
    pn.reload()
    switch_profile(pn, "meeting")
    assert page.evaluate("timer.cur") == 1
    pn.close()


def test_auto_follow_switches_profile_with_a_notice(browser, env):
    _, port, mirror = env
    pn = Panel(browser, port)  # baseline target: the talk's Demo C (not followed on open)
    assert pn.page.locator("#profileSel").input_value() == "talk"
    mirror.status["source_title"] = "Sprint board - Google Chrome"
    pn.page.wait_for_function("profile === 'meeting' && !switching", timeout=4000)
    pn.page.wait_for_function("sections[secIdx] && sections[secIdx].title.includes('Board walk')", timeout=2000)
    assert pn.page.evaluate(STAGES)[1] == "Part 2"
    assert "Profile switched to meeting" in pn.page.locator("#toast").inner_text()
    # And back when the talk's page is projected again.
    mirror.status["source_title"] = "Plant-care App · Q&A - Google Chrome"
    pn.page.wait_for_function("profile === 'talk' && !switching", timeout=4000)
    pn.page.wait_for_function("sections[secIdx] && sections[secIdx].title.includes('Q&A')", timeout=2000)
    pn.close()


def test_auto_switch_can_be_turned_off(browser, env_factory):
    _, port, mirror = env_factory(profile_auto_switch=False)
    pn = Panel(browser, port)
    mirror.status["source_title"] = "Sprint board - Google Chrome"
    pn.page.wait_for_timeout(2500)
    assert pn.page.evaluate("profile") == "talk"
    pn.close()


def test_startup_profile_request_wins_once_then_f5_keeps_your_choice(browser, env_factory):
    app, port, _ = env_factory(profile="meeting")  # panel_server --profile meeting
    pn = Panel(browser, port)
    assert pn.page.evaluate("profile") == "meeting" and pn.page.evaluate(STAGES)[0] == "Part 1"
    switch_profile(pn, "talk")
    pn.reload()
    assert pn.page.evaluate("profile") == "talk"
    # start.ps1 -Profile meeting while the server runs: POST /api/profile, open panels switch once.
    pn.page.evaluate("fetch('/api/profile', {method: 'POST', headers: {'X-Panel': '1', 'Content-Type': "
                     "'application/json'}, body: JSON.stringify({name: 'meeting'})})")
    pn.page.wait_for_function("profile === 'meeting' && !switching", timeout=4000)
    assert pn.page.locator("#toast").inner_text() == "Profile: meeting"
    pn.close()


def test_single_profile_config_hides_the_chip_and_keeps_the_0_2_timer(browser, env_factory):
    _, port, _ = env_factory(profiles=[], profile_name="default")
    ctx = browser.new_context(viewport={"width": 400, "height": 900})
    ctx.add_init_script("""if (!sessionStorage.getItem('seeded')) { sessionStorage.setItem('seeded', '1');
      localStorage.setItem('presenter.timer', JSON.stringify({cur: 1, starts: {'Demo A': Date.now() - 60000},
                                                              classStart: Date.now() - 120000})); }""")
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"http://127.0.0.1:{port}/")
    page.wait_for_function("document.querySelector('#secSel').options.length > 0")
    assert not page.locator("#profileSel").is_visible()
    assert page.locator("#stageName").inner_text().startswith("Demo A")  # 0.2.0 timer read for the first profile
    assert page.evaluate("profile") == "default"
    ctx.close()
    assert not errors


def test_server_restart_without_a_request_keeps_the_hand_picked_profile(browser, env):
    app, port, _ = env  # no --profile: the request has no id
    pn = Panel(browser, port)
    switch_profile(pn, "meeting")
    app.boot = "restarted"  # what a plain restart changes
    pn.reload()
    pn.page.wait_for_timeout(1000)
    assert pn.page.evaluate("profile") == "meeting"
    pn.close()


def test_a_profile_added_to_the_config_appears_without_f5(browser, env):
    app, port, _ = env
    pn = Panel(browser, port)
    cfg = json.loads(app.cfg_path.read_text(encoding="utf-8"))
    cfg["profiles"].append({"name": "會議", "notes_files": ["examples/notes/checklist.md"]})
    app.cfg_path.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    st = app.cfg_path.stat()
    os.utime(app.cfg_path, (st.st_atime, st.st_mtime + 5))
    pn.page.wait_for_function("profileNames.includes('會議')", timeout=4000)
    switch_profile(pn, "會議")
    assert pn.page.evaluate(DOCS) == ["checklist"]
    pn.close()


def test_every_open_panel_obeys_a_profile_request(browser, env_factory):
    _, port, _ = env_factory()
    ctx = browser.new_context(viewport={"width": 400, "height": 900})
    pages = [ctx.new_page(), ctx.new_page()]  # two panel windows, one shared localStorage
    for pg in pages:
        pg.goto(f"http://127.0.0.1:{port}/")
        pg.wait_for_function("document.querySelector('#secSel').options.length > 0")
    pages[0].evaluate("fetch('/api/profile', {method: 'POST', headers: {'X-Panel': '1', 'Content-Type': "
                      "'application/json'}, body: JSON.stringify({name: 'meeting'})})")
    for pg in pages:
        pg.wait_for_function("profile === 'meeting' && !switching", timeout=4000)
    ctx.close()


def test_config_profile_applies_on_the_next_server_start(browser, env):
    # Review repro: a panel opened before with "profile": "" (talk); then "profile": "meeting" and a restart.
    app, port, _ = env
    ctx = browser.new_context(viewport={"width": 400, "height": 900})
    first = ctx.new_page()
    first.goto(f"http://127.0.0.1:{port}/")
    first.wait_for_function("profile === 'talk' && !switching")
    first.close()
    cfg = json.loads(app.cfg_path.read_text(encoding="utf-8"))
    cfg["profile"] = "meeting"
    app.cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
    st = app.cfg_path.stat()
    os.utime(app.cfg_path, (st.st_atime, st.st_mtime + 5))
    app.boot = "restarted"
    page = ctx.new_page()  # a fresh panel window: same localStorage ("profile": talk), new session
    page.goto(f"http://127.0.0.1:{port}/")
    page.wait_for_function("profile === 'meeting' && !switching", timeout=4000)
    # Applied once: a profile picked by hand afterwards survives F5.
    page.select_option("#profileSel", "talk")
    page.wait_for_function("profile === 'talk' && !switching")
    page.reload()
    page.wait_for_function("document.querySelector('#secSel').options.length > 0")
    page.wait_for_timeout(1000)
    assert page.evaluate("profile") == "talk"
    ctx.close()
