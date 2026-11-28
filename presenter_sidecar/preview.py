"""Projector preview: a small JPEG of what the audience sees, for the private panel.

mirror.py hands a downscaled copy of the final projector frame to :class:`PreviewWriter` every
``preview_interval_sec`` seconds; the writer skips the write when the small image has not changed
and replaces the file atomically, so panel_server.py never serves half a file.

"Age" is the time since the mirror last *confirmed* that the file matches the projector (written or
found unchanged), not the file's mtime: an unchanged slide must not look stale. mirror.py reports it
as a relative number in its status, so panel_server.py (possibly in WSL, with its own clock) never
compares two clocks. Standard library only: panel_server.py imports this module too.
"""
from __future__ import annotations

import os
import zlib
from pathlib import Path
from typing import Callable

PREVIEW_FILE = "mirror.preview.jpg"   # in logs/, next to mirror.status.json
DEFAULT_INTERVAL = 2.0
MIN_INTERVAL = 0.5
DEFAULT_WIDTH = 480
DEFAULT_QUALITY = 70
RETRY_SECS = 0.5                      # after a failed write (e.g. the server was reading the file)
LOG_EVERY_SECS = 60.0                 # failed writes are logged at most this often


def _number(v, default: float) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v != v:  # bools and NaN are not numbers here
        return default
    return float(v)


def preview_settings(cfg: dict) -> tuple[float, int, int]:
    """(interval seconds, width px, JPEG quality) from the config.

    ``preview_interval_sec`` 0, a negative number, ``false`` or ``null`` turn the preview off
    (interval 0.0); otherwise at least :data:`MIN_INTERVAL`. Invalid values fall back to the defaults.
    """
    raw = cfg.get("preview_interval_sec", DEFAULT_INTERVAL)
    if raw is None or raw is False:
        interval = 0.0
    else:
        interval = _number(raw, DEFAULT_INTERVAL)
        interval = 0.0 if interval <= 0 else max(MIN_INTERVAL, interval)
    width = int(min(1920, max(64, _number(cfg.get("preview_width"), DEFAULT_WIDTH))))
    quality = int(min(95, max(10, _number(cfg.get("preview_quality"), DEFAULT_QUALITY))))
    return interval, width, quality


def scaled_size(w: int, h: int, max_w: int) -> tuple[int, int]:
    """Size of the preview for a ``w`` × ``h`` projector: ``max_w`` wide at most, never upscaled."""
    if w <= 0 or h <= 0:
        return (0, 0)
    if w <= max_w:
        return (w, h)
    return (max_w, max(1, round(h * max_w / w)))


def write_atomic(path: Path, data: bytes) -> None:
    """Write next to ``path`` and rename over it: readers see the old file or the new one, never a part."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


Encoder = Callable[[bytes, tuple], bytes]


class PreviewWriter:
    """Decides when to sample, skips unchanged images and writes the JPEG atomically.

    ``encode(rgb, (w, h)) -> jpeg bytes`` is injected (mirror.py uses OpenCV) so the rules are
    testable without it; ``log(message)`` hears about failed writes (the first one, then at most every
    :data:`LOG_EVERY_SECS`). Times are ``time.perf_counter()``-style seconds passed in by the caller.
    """

    def __init__(self, path: Path, interval: float, encode: Encoder | None,
                 log: Callable[[str], None] | None = None):
        self.path = Path(path)
        self.interval = float(interval)
        self.encode = encode
        self.log = log
        self.logged_at: float | None = None
        self.next_at = 0.0
        self.key: tuple | None = None      # (size, crc32) of the image in the file
        self.checked: float | None = None  # last time the file was confirmed to match the projector
        self.seq = 0                       # files written
        self.errors = 0

    @property
    def enabled(self) -> bool:
        return self.interval > 0

    def due(self, now: float) -> bool:
        return self.enabled and now >= self.next_at

    def offer(self, now: float, rgb: bytes, size: tuple[int, int]) -> bool:
        """The downscaled RGB frame, when :meth:`due`. Returns True when a new file was written.

        A failed write (OSError: the file was open in the server, disk full) is retried after
        :data:`RETRY_SECS`; encoder errors propagate (mirror.py turns the preview off).
        """
        self.next_at = now + self.interval
        key = (tuple(size), zlib.crc32(rgb))
        if key == self.key and self.path.exists():
            self.checked = now
            return False
        data = self.encode(rgb, size)
        try:
            write_atomic(self.path, data)
        except OSError as e:
            self.errors += 1
            self.next_at = now + min(self.interval, RETRY_SECS)
            if self.log and (self.logged_at is None or now - self.logged_at >= LOG_EVERY_SECS):
                self.logged_at = now
                self.log(f"write failed ({self.errors} so far, retrying): {e}")
            return False
        self.key, self.checked, self.seq = key, now, self.seq + 1
        return True

    def status(self, now: float) -> dict:
        """For the mirror status: ``age`` is relative, so the reader needs no shared clock."""
        age = None if self.checked is None else round(max(0.0, now - self.checked), 1)
        return {"enabled": self.enabled, "age": age, "seq": self.seq, "errors": self.errors}

    def clear(self) -> None:
        """Remove the file (mirror start and exit): no old screen content is left in logs/."""
        for p in (self.path, self.path.with_name(self.path.name + ".tmp")):
            try:
                p.unlink()
            except OSError:
                pass
        self.key = self.checked = None
