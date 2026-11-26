from presenter_sidecar.geometry import (arrow_polygons, contains, crop_in_window, fit_letterbox, frame_margins, intersects,
                                        map_point, mostly_black, outer_rect_for, panel_and_work_rects, ripple_radius,
                                        panel_width, sample_grid)


def test_letterbox_wider_source_gets_bars_top_and_bottom():
    # 1920x1080 window onto a 1280x1024 projector: width-limited
    scale, ox, oy, tw, th = fit_letterbox(1920, 1080, 1280, 1024)
    assert (tw, th) == (1280, 720)
    assert ox == 0 and oy == (1024 - 720) // 2
    assert abs(scale - 1280 / 1920) < 1e-9


def test_letterbox_taller_source_gets_bars_left_and_right():
    # work area beside the panel (1421x1140) onto a 1920x1080 projector: height-limited
    scale, ox, oy, tw, th = fit_letterbox(1421, 1140, 1920, 1080)
    assert th == 1080 and oy == 0
    assert tw == int(1421 * 1080 / 1140)
    assert ox == (1920 - tw) // 2 and ox > 0


def test_letterbox_exact_fit_and_tiny_source():
    assert fit_letterbox(1920, 1080, 1920, 1080) == (1.0, 0, 0, 1920, 1080)
    scale, ox, oy, tw, th = fit_letterbox(1, 1, 1920, 1080)
    assert tw >= 1 and th >= 1


def test_map_point_corners_and_centre():
    frame = (100, 200, 1100, 700)  # 1000x500 visible window
    scale, ox, oy, tw, th = fit_letterbox(1000, 500, 1920, 1080)
    assert map_point(100, 200, frame, ox, oy, tw, th) == (ox, oy)
    px, py = map_point(600, 450, frame, ox, oy, tw, th)
    assert abs(px - (ox + tw / 2)) < 1e-6 and abs(py - (oy + th / 2)) < 1e-6
    px, py = map_point(1100, 700, frame, ox, oy, tw, th)
    assert abs(px - (ox + tw)) < 1e-6 and abs(py - (oy + th)) < 1e-6


def test_map_point_negative_desktop_coordinates():
    # monitors left of / above the primary have negative coordinates
    frame = (-1920, -486, 0, 594)
    px, py = map_point(-960, 54, frame, 0, 0, 1920, 1080)
    assert (px, py) == (960, 540)


def test_intersects_and_contains():
    assert intersects((0, 0, 10, 10), (5, 5, 15, 15))
    assert not intersects((0, 0, 10, 10), (10, 0, 20, 10))  # touching edges do not intersect
    assert contains((0, 0, 10, 10), 0, 0)
    assert not contains((0, 0, 10, 10), 10, 5)


def test_frame_margins_roundtrip():
    window = (93, -7, 1428, 1147)
    visible = (100, 0, 1421, 1140)
    m = frame_margins(window, visible)
    assert m == (7, 7, 7, 7)
    x, y, w, h = outer_rect_for(visible, m)
    assert (x, y, x + w, y + h) == window


def test_crop_in_window():
    assert crop_in_window((107, 10, 507, 310), (100, 3, 514, 317)) == (7, 7, 400, 300)


def test_panel_and_work_rects():
    mon = (0, 0, 1920, 1200)
    w = panel_width(mon, 0.26)
    assert w == 499
    panel, work = panel_and_work_rects(mon, 1140, w)
    assert panel == (1421, 0, 1920, 1140)
    assert work == (0, 0, 1421, 1140)
    assert panel_width(mon, 0.26, 600) == 600


def test_sample_grid_inside_frame():
    pts = sample_grid((0, 0, 100, 50))
    assert len(pts) == 25
    assert all(0 < x < 100 and 0 < y < 50 for x, y in pts)
    assert (2, 2) in pts and (98, 48) in pts


def test_mostly_black():
    assert mostly_black(bytes(4 * 5000))
    buf = bytearray(4 * 5000)
    buf[1] = 200  # first sampled green byte
    assert not mostly_black(bytes(buf))


def test_arrow_polygons_match_original_shape():
    import math
    outer, inner = arrow_polygons(2.2, 4)
    assert len(outer) == len(inner) == 7
    assert outer[0] == (8, 8)  # tip at (2, 2) * supersample
    w, h = 20 * 2.2 * 4, 28 * 2.2 * 4
    assert all(0 <= x <= w and 0 <= y <= h for x, y in outer)
    cx, cy = sum(p[0] for p in outer) / 7, sum(p[1] for p in outer) / 7
    for (ox, oy), (ix, iy) in zip(outer, inner):  # inner is pulled 1.6*ss towards the centroid
        assert abs(math.dist((ox, oy), (ix, iy)) - 6.4) < 1e-6
        assert math.dist((ix, iy), (cx, cy)) < math.dist((ox, oy), (cx, cy))


def test_ripple_radius():
    assert ripple_radius(0, 70) == 14
    assert ripple_radius(0.5, 70) == 42
    assert ripple_radius(0.999, 70) == 69
