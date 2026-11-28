"""Configuration loading: ``config.json`` (local, gitignored) over built-in defaults.

``config.example.json`` is the only config shipped in the repo. When ``config.json``
does not exist the example is used, so a fresh clone runs without any setup.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

from .overlay import DEFAULT_MENU_CLASSES

ROOT = Path(__file__).resolve().parent.parent

DEFAULT_HOTKEYS = {
    "pick": "F7",
    "bring": "Shift+F7",
    "freeze": "F8",
    "blank": "F9",
    "style": "F10",
    "popups": "Ctrl+Alt+P",
    "clip": "Ctrl+Alt+L",
    # Region mode (capture the screen rectangle). Not F11: that is the browser's full-screen key.
    "region": "Ctrl+Alt+R",
    "next": "Ctrl+Alt+PgDn",
    "prev": "Ctrl+Alt+PgUp",
    "quit": "Ctrl+Alt+Q",
}

DEFAULTS: dict = {
    "ui_lang": "en",
    "hotkeys": DEFAULT_HOTKEYS,
    # Displays: "" = source is the primary display, target is the first other display.
    "source_display": "",
    "target_display": "",
    "panel_width_ratio": 0.26,
    "panel_width_px": 0,
    "panel_topmost": True,
    "reserve_work_area": False,
    "clip_cursor_to_source": True,
    # [] = use the foreground window at start; press the "pick" hotkey to change it.
    "source_title_contains": [],
    "never_source_classes": [
        "CASCADIA_HOSTING_WINDOW_CLASS",
        "ConsoleWindowClass",
        "mintty",
        "VirtualConsoleClass",
    ],
    "capture_backend": "auto",
    "follow_popups": True,
    "popup_min_size": [320, 240],
    # Paste menus and other popups (separate windows) over the projected window (presenter_sidecar.overlay).
    "menu_overlay": True,
    "menu_overlay_classes": list(DEFAULT_MENU_CLASSES),
    "menu_overlay_heuristic": False,
    "menu_overlay_margin": 8,  # scan pre-filter only: pasted menus are always cut at the window's edge
    "menu_overlay_max_size": [1600, 1400],
    "menu_overlay_interval_sec": 0.1,
    # Start in region mode (screen copy of the window's rectangle) instead of window capture.
    "region_mode": False,
    "fps": 25,
    "smooth_scale": True,
    # Panel preview of the projector (logs/mirror.preview.jpg): seconds between samples, 0 = off.
    "preview_interval_sec": 2,
    "preview_width": 480,
    "preview_quality": 70,
    "pointer_style": "ring",
    "pointer_ring_radius": 46,
    "pointer_ring_color": [255, 214, 0],
    "pointer_ring_alpha": 90,
    "pointer_ring_border_alpha": 220,
    "pointer_arrow_scale": 2.2,
    "spotlight_radius": 170,
    "spotlight_dim_alpha": 170,
    "ripple_left_color": [255, 59, 48],
    "ripple_right_color": [0, 122, 255],
    "ripple_ms": 550,
    "ripple_max_radius": 70,
    "blank_text": "Please wait",
    "blank_subtext": "Back in a moment",
    "blank_bg": [24, 28, 36],
    "font_path": "",
    "panel_host": "127.0.0.1",
    "panel_port": 8765,
    "panel_runtime": "windows",
    "wsl_distro": "",
    "panel_browser": "",
    "content_root": ".",
    # The keys below up to notes_rules form the first profile (named profile_name); "profiles" adds more.
    "profile_name": "default",
    "notes_files": [],
    "pacing_file": "",
    "pacing_notes": "",
    "notes_auto_follow": True,
    "notes_follow_doc": "",
    "cdp_url": "",
    "notes_rules": [],
    "profiles": [],
    # Startup profile ("" = the first); --profile / PRESENTER_PROFILE override it.
    "profile": "",
    # Auto-follow may switch to another profile whose rule matches the projected page.
    "profile_auto_switch": True,
    "ai_helper": {
        "enabled": False,
        "claude_bin": "",
        "model": "",
        "timeout_sec": 180,
        "extra_args": [],
        "workdir": ".",
        "system_prompt": "",
    },
}


def deep_merge(base: dict, over: dict) -> dict:
    """Return ``base`` updated with ``over``; nested dicts are merged, everything else replaced."""
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def config_path(root: Path = ROOT) -> Path:
    """``config.json`` if present, else ``config.example.json``."""
    local = root / "config.json"
    return local if local.exists() else root / "config.example.json"


def load_config(path: Path | str | None = None, root: Path = ROOT) -> dict:
    """Load a config file merged over :data:`DEFAULTS`. Keys starting with ``_`` are comments."""
    p = Path(path) if path else config_path(root)
    raw = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    if not isinstance(raw, dict):
        raise ValueError(f"{p}: top level must be a JSON object")
    raw = {k: v for k, v in raw.items() if not k.startswith("_")}
    cfg = deep_merge(DEFAULTS, raw)
    cfg["_path"] = str(p)
    cfg["_root"] = str(root)
    return cfg


def resolve(root: Path | str, p: str) -> Path:
    """Resolve ``p`` relative to ``root`` unless it is already absolute."""
    q = Path(p).expanduser()
    return (q if q.is_absolute() else Path(root) / q).resolve()


def content_root(cfg: dict) -> Path:
    return resolve(cfg.get("_root") or ROOT, cfg.get("content_root") or ".")
