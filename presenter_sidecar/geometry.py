"""Rectangle math shared by the mirror. Rects are ``(left, top, right, bottom)`` in physical pixels."""
from __future__ import annotations

Rect = tuple[int, int, int, int]


def intersects(a: Rect, b: Rect) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def contains(r: Rect, x: float, y: float) -> bool:
    return r[0] <= x < r[2] and r[1] <= y < r[3]


def fit_letterbox(src_w: int, src_h: int, dst_w: int, dst_h: int) -> tuple[float, int, int, int, int]:
    """Scale ``src`` to fit inside ``dst`` keeping aspect ratio, centred with black bars.

    Returns ``(scale, offset_x, offset_y, target_w, target_h)``.
    """
    scale = min(dst_w / src_w, dst_h / src_h)
    tw, th = max(1, int(src_w * scale)), max(1, int(src_h * scale))
    return scale, (dst_w - tw) // 2, (dst_h - th) // 2, tw, th


def map_point(mx: float, my: float, frame: Rect, ox: int, oy: int, tw: int, th: int) -> tuple[float, float]:
    """Map a desktop point inside ``frame`` to the projector surface."""
    px = ox + (mx - frame[0]) * tw / max(1, frame[2] - frame[0])
    py = oy + (my - frame[1]) * th / max(1, frame[3] - frame[1])
    return px, py


def frame_margins(window_rect: Rect, frame_rect: Rect) -> tuple[int, int, int, int]:
    """Invisible resize borders: ``GetWindowRect`` minus the DWM extended frame bounds."""
    return (frame_rect[0] - window_rect[0], frame_rect[1] - window_rect[1],
            window_rect[2] - frame_rect[2], window_rect[3] - frame_rect[3])


def outer_rect_for(visible: Rect, margins: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    """``SetWindowPos`` arguments ``(x, y, w, h)`` so the *visible* frame lands on ``visible``."""
    ml, mt, mr, mb = margins
    l, t, r, b = visible
    return l - ml, t - mt, (r - l) + ml + mr, (b - t) + mt + mb


def crop_in_window(frame_rect: Rect, window_rect: Rect) -> tuple[int, int, int, int]:
    """Visible frame as ``(x, y, w, h)`` inside a PrintWindow bitmap of ``window_rect``."""
    return (frame_rect[0] - window_rect[0], frame_rect[1] - window_rect[1],
            frame_rect[2] - frame_rect[0], frame_rect[3] - frame_rect[1])


def panel_and_work_rects(monitor: Rect, work_bottom: int, panel_w: int) -> tuple[Rect, Rect]:
    """Panel docked on the right of the source monitor; the work area is what remains on the left."""
    l, t, r, _ = monitor
    panel = (r - panel_w, t, r, work_bottom)
    work = (l, t, panel[0], work_bottom)
    return panel, work


def panel_width(monitor: Rect, ratio: float, px: int = 0) -> int:
    return int(px or round((monitor[2] - monitor[0]) * float(ratio)))


def sample_grid(frame: Rect, n: int = 5, inset: int = 2) -> list[tuple[int, int]]:
    """``n``×``n`` probe points inside ``frame`` (used to check a window is not covered)."""
    l, t, r, b = frame
    pts = []
    for i in range(n):
        for j in range(n):
            pts.append((l + inset + (r - l - 2 * inset) * i // (n - 1),
                        t + inset + (b - t - 2 * inset) * j // (n - 1)))
    return pts


def mostly_black(buf, step: int = 4 * 997) -> bool:
    """Sample the green channel of a BGRA buffer; True when the capture is (almost) all black."""
    mv = memoryview(buf).cast("B")
    s = mv[1::step]
    return max(s, default=0) < 12


# ---------------------------------------------------------------- presenter pointer shape
ARROW_POINTS = [(0, 0), (0, 21), (5, 16.5), (8.6, 24.5), (12, 23), (8.6, 15.2), (15, 15)]


def arrow_polygons(scale: float, supersample: int = 1) -> tuple[list[tuple[float, float]], list[tuple[float, float]]]:
    """Outer (black) and inner (white) polygons of the projector arrow, tip near (2, 2)·supersample.

    The bitmap that holds them is ``(20·scale·ss, 28·scale·ss)`` pixels.
    """
    ss = supersample
    outer = [(2 * ss + x * scale * ss, 2 * ss + y * scale * ss) for x, y in ARROW_POINTS]
    cx = sum(p[0] for p in outer) / len(outer)
    cy = sum(p[1] for p in outer) / len(outer)
    shrink = 1.6 * ss
    inner = []
    for x, y in outer:
        d = max(1.0, ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5)
        inner.append((x + (cx - x) * shrink / d, y + (cy - y) * shrink / d))
    return outer, inner


def ripple_radius(age: float, max_radius: int) -> int:
    """Ripple radius for ``age`` in [0, 1): grows from 14 px to ``max_radius``."""
    return int(14 + (max_radius - 14) * age)
