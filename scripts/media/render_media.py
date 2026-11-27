#!/usr/bin/env python3
"""Re-generate the mock screenshots in docs/media/ from examples/ only.

Everything runs headless on ephemeral 127.0.0.1 ports: a temporary panel server with the
example config, a static server for examples/demo-site and headless Chromium. No real
display, window or account is used. The projector pointer is drawn with the same shape,
sizes and colours as mirror.py (presenter_sidecar.geometry + the config defaults).

Requirements (dev only): pip install playwright pillow && python -m playwright install chromium
Usage: python scripts/media/render_media.py
"""
from __future__ import annotations

import functools
import io
import json
import sys
import threading
import time
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

import panel_server  # noqa: E402
from presenter_sidecar.config import DEFAULTS  # noqa: E402
from presenter_sidecar.geometry import arrow_polygons, fit_letterbox, map_point, ripple_radius  # noqa: E402

OUT = ROOT / "docs" / "media"
W, H = 1920, 1080          # projector
SRC_W, SRC_H = 1440, 1000  # source browser window (visible frame)
PANEL_W, PANEL_H = 400, 900


def start_panel_server(tmp: Path) -> tuple[int, ThreadingHTTPServer]:
    cfg = json.loads((ROOT / "config.example.json").read_text(encoding="utf-8"))
    cfg["content_root"] = str(ROOT)
    p = tmp / "config.json"
    p.write_text(json.dumps(cfg), encoding="utf-8")
    srv = panel_server.make_server(panel_server.App(p), "127.0.0.1", 0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv.server_address[1], srv


def start_static(directory: Path) -> tuple[int, ThreadingHTTPServer]:
    handler = functools.partial(SimpleHTTPRequestHandler, directory=str(directory))
    handler.log_message = lambda *a: None
    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv.server_address[1], srv


class FakeMirror:
    """Posts a mock mirror status every 0.5 s so the panel shows a live projector."""

    def __init__(self, port: int):
        self.port, self.title, self.stop = port, "", False
        threading.Thread(target=self.run, daemon=True).start()

    def run(self):
        while not self.stop:
            body = {"fps": 25.0, "frozen": False, "blank": False, "style": "ring", "clip": True, "backend": "wgc",
                    "source_title": self.title, "source_state": "ok", "following_popup": False,
                    "follow_popups": True, "warning": "", "notice": "", "hotkeys_failed": []}
            req = urllib.request.Request(f"http://127.0.0.1:{self.port}/api/mirror", data=json.dumps(body).encode(),
                                         method="POST", headers={"Content-Type": "application/json", "X-Panel": "1"})
            try:
                urllib.request.urlopen(req, timeout=1).read()
            except OSError:
                pass
            time.sleep(0.5)


# ---------------------------------------------------------------- projector composite
def draw_pointer(img: Image.Image, px: float, py: float, ripple_age: float | None = None) -> None:
    c = DEFAULTS
    ss = 4
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    # ripple (left click), like mirror.py: ring 6 px + soft fill
    if ripple_age is not None:
        rmax = c["ripple_max_radius"]
        rad = ripple_radius(ripple_age, rmax)
        col = tuple(c["ripple_left_color"])
        rip = Image.new("RGBA", ((rmax * 2 + 8) * ss,) * 2, (0, 0, 0, 0))
        d = ImageDraw.Draw(rip)
        m = (rmax + 4) * ss
        r1 = max(1, rad - 6) * ss
        d.ellipse((m - r1, m - r1, m + r1, m + r1), fill=(*col, int(90 * (1 - ripple_age))))
        d.ellipse((m - rad * ss, m - rad * ss, m + rad * ss, m + rad * ss), outline=(*col, int(230 * (1 - ripple_age))),
                  width=6 * ss)
        rip = rip.resize((rmax * 2 + 8,) * 2, Image.LANCZOS)
        layer.alpha_composite(rip, (int(px) - (rmax + 4), int(py) - (rmax + 4)))
    # ring
    r = c["pointer_ring_radius"]
    col = tuple(c["pointer_ring_color"])
    ring = Image.new("RGBA", ((r * 2 + 8) * ss,) * 2, (0, 0, 0, 0))
    d = ImageDraw.Draw(ring)
    m = (r + 4) * ss
    d.ellipse((m - r * ss, m - r * ss, m + r * ss, m + r * ss), fill=(*col, c["pointer_ring_alpha"]))
    d.ellipse((m - r * ss, m - r * ss, m + r * ss, m + r * ss), outline=(*col, c["pointer_ring_border_alpha"]),
              width=4 * ss)
    ring = ring.resize((r * 2 + 8,) * 2, Image.LANCZOS)
    layer.alpha_composite(ring, (int(px) - ring.width // 2, int(py) - ring.height // 2))
    # arrow
    k = c["pointer_arrow_scale"]
    big = Image.new("RGBA", (int(20 * k * ss), int(28 * k * ss)), (0, 0, 0, 0))
    outer, inner = arrow_polygons(k, ss)
    d = ImageDraw.Draw(big)
    d.polygon(outer, fill=(0, 0, 0, 255))
    d.polygon(inner, fill=(255, 255, 255, 255))
    arrow = big.resize((big.width // ss, big.height // ss), Image.LANCZOS)
    layer.alpha_composite(arrow, (int(px) - 2, int(py) - 2))
    img.alpha_composite(layer)


def render_projector(browser, demo_port: int) -> None:
    page = browser.new_page(viewport={"width": SRC_W, "height": SRC_H})
    page.goto(f"http://127.0.0.1:{demo_port}/#demo")
    page.wait_for_timeout(300)
    page.click("#dry")
    page.wait_for_timeout(200)
    box = page.locator("#dry").bounding_box()
    shot = Image.open(io.BytesIO(page.screenshot())).convert("RGBA")
    page.close()
    scale, ox, oy, tw, th = fit_letterbox(SRC_W, SRC_H, W, H)
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    canvas.alpha_composite(shot.resize((tw, th), Image.LANCZOS), (ox, oy))
    frame = (0, 0, SRC_W, SRC_H)
    mx, my = box["x"] + box["width"] * 0.62, box["y"] + box["height"] * 0.55
    px, py = map_point(mx, my, frame, ox, oy, tw, th)
    draw_pointer(canvas, px, py, ripple_age=0.45)
    canvas.convert("RGB").save(OUT / "projector.png", optimize=True)


# ---------------------------------------------------------------- panel
def panel_page(browser):
    ctx = browser.new_context(viewport={"width": PANEL_W, "height": PANEL_H}, device_scale_factor=2)
    ctx.add_init_script("""
      localStorage.setItem('presenter.fs', '17');
      localStorage.setItem('presenter.doc', '0');
      localStorage.setItem('presenter.sec.0', '2');
      localStorage.setItem('presenter.notesFollow', 'true');
      localStorage.setItem('presenter.tab', '"notes"');
    """)
    return ctx, ctx.new_page()


def seed_timer(page, stage_key: str, stage_mins_ago: float, class_mins_ago: float):
    page.evaluate("""([key, a, b]) => {
      const now = Date.now();
      const idx = stages.findIndex(s => s.key === key);
      timer = {cur: idx, starts: {[key]: now - a * 60000}, classStart: now - b * 60000};
      saveTimer(); renderStages(); tick();
      // re-evaluate the "this section belongs to another timer" hint without moving
      const hint = document.querySelector('#stageHint'); if (viewStage === timer.cur) hint.hidden = true;
    }""", [stage_key, stage_mins_ago, class_mins_ago])


def render_panel(browser, port: int, mirror: FakeMirror) -> None:
    gif_frames: list[Image.Image] = []

    def grab(page):
        return Image.open(io.BytesIO(page.screenshot())).convert("RGB")

    mirror.title = "acme/plant-care: sensor code - GitHub - Google Chrome"
    time.sleep(1.0)
    ctx, page = panel_page(browser)
    page.goto(f"http://127.0.0.1:{port}/")
    page.wait_for_timeout(1500)  # first poll only records the current target (no jump on open)
    seed_timer(page, "Demo A", 7.4, 15.2)
    page.wait_for_timeout(300)
    gif_frames.append(grab(page))

    # The projected tab changes to the spreadsheet → notes follow to Demo B with a toast.
    mirror.title = "Watering log - Google Sheets - Google Chrome"
    page.wait_for_timeout(1800)
    seed_timer(page, "Demo B", 3.1, 22.6)
    page.wait_for_timeout(300)
    gif_frames.append(grab(page))

    # The live app → Demo C, whose numbered steps show the step bar; J moves to step 2.
    mirror.title = "Plant-care App - Google Chrome"
    page.wait_for_timeout(1800)
    seed_timer(page, "Demo C", 4.6, 33.1)
    page.keyboard.press("j")
    page.wait_for_timeout(300)
    img = grab(page)
    img.save(OUT / "panel.png", optimize=True)
    gif_frames.append(img)

    # Then the demo site's Q&A anchor.
    mirror.title = "Plant-care App · Q&A - Google Chrome"
    page.wait_for_timeout(1800)
    seed_timer(page, "Q&A", 1.2, 47.9)
    page.wait_for_timeout(300)
    gif_frames.append(grab(page))
    ctx.close()

    small = [f.resize((PANEL_W, PANEL_H), Image.LANCZOS).quantize(colors=96, method=Image.MEDIANCUT)
             for f in gif_frames]
    small[0].save(OUT / "auto-follow.gif", save_all=True, append_images=small[1:], duration=[1800, 2600, 2600, 2600],
                  loop=0, optimize=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        port, psrv = start_panel_server(Path(tmp))
        demo_port, dsrv = start_static(ROOT / "examples" / "demo-site")
        mirror = FakeMirror(port)
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                render_projector(browser, demo_port)
                render_panel(browser, port, mirror)
                browser.close()
        finally:
            mirror.stop = True
            psrv.shutdown()
            dsrv.shutdown()
    for f in sorted(OUT.iterdir()):
        print(f"{f.relative_to(ROOT)}  {f.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
