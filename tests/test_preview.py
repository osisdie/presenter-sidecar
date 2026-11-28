import os

import pytest

from presenter_sidecar.config import DEFAULTS, ROOT, load_config
from presenter_sidecar.preview import (DEFAULT_INTERVAL, DEFAULT_QUALITY, DEFAULT_WIDTH, LOG_EVERY_SECS, MIN_INTERVAL,
                                       PREVIEW_FILE, RETRY_SECS, PreviewWriter, preview_settings, scaled_size,
                                       write_atomic)


def test_defaults_and_example_config():
    assert preview_settings(DEFAULTS) == (2.0, 480, 70)
    assert preview_settings(load_config(ROOT / "config.example.json", ROOT)) == (2.0, 480, 70)
    assert preview_settings({}) == (DEFAULT_INTERVAL, DEFAULT_WIDTH, DEFAULT_QUALITY)


@pytest.mark.parametrize("raw", [0, 0.0, -1, False, None])
def test_zero_negative_false_or_null_turn_it_off(raw):
    assert preview_settings({"preview_interval_sec": raw})[0] == 0.0


@pytest.mark.parametrize("raw, want", [(5, 5.0), (0.1, MIN_INTERVAL), ("2", DEFAULT_INTERVAL), (True, DEFAULT_INTERVAL),
                                       (float("nan"), DEFAULT_INTERVAL)])
def test_interval_is_clamped_and_invalid_values_use_the_default(raw, want):
    assert preview_settings({"preview_interval_sec": raw})[0] == want


def test_width_and_quality_are_clamped():
    assert preview_settings({"preview_width": 10, "preview_quality": 500})[1:] == (64, 95)
    assert preview_settings({"preview_width": 9999, "preview_quality": 1})[1:] == (1920, 10)
    assert preview_settings({"preview_width": "wide", "preview_quality": None})[1:] == (480, 70)
    assert preview_settings({"preview_width": 320.7})[1] == 320


def test_scaled_size_keeps_the_aspect_and_never_upscales():
    assert scaled_size(1920, 1080, 480) == (480, 270)
    assert scaled_size(1024, 768, 480) == (480, 360)
    assert scaled_size(400, 300, 480) == (400, 300)
    assert scaled_size(5000, 1, 480) == (480, 1)
    assert scaled_size(0, 1080, 480) == (0, 0)


def test_write_atomic_replaces_and_leaves_no_temp(tmp_path):
    p = tmp_path / PREVIEW_FILE
    write_atomic(p, b"one")
    write_atomic(p, b"two")
    assert p.read_bytes() == b"two"
    assert sorted(f.name for f in tmp_path.iterdir()) == [PREVIEW_FILE]


class Enc:
    def __init__(self):
        self.calls = 0

    def __call__(self, rgb, size):
        self.calls += 1
        return b"JPEG" + bytes(rgb[:4]) + bytes(size)


def test_samples_on_the_interval_and_skips_unchanged_images(tmp_path):
    enc = Enc()
    w = PreviewWriter(tmp_path / PREVIEW_FILE, 2.0, enc)
    assert w.due(0.0)
    assert w.offer(0.0, b"\x01" * 12, (2, 2)) is True and w.seq == 1
    assert not w.due(1.9) and w.due(2.0)
    # Same picture: no encode, no write, but the age restarts (an unchanged slide is not stale).
    mtime = (tmp_path / PREVIEW_FILE).stat().st_mtime_ns
    assert w.offer(2.0, b"\x01" * 12, (2, 2)) is False
    assert enc.calls == 1 and w.seq == 1 and (tmp_path / PREVIEW_FILE).stat().st_mtime_ns == mtime
    assert w.status(3.0) == {"enabled": True, "age": 1.0, "seq": 1, "errors": 0}
    # A different picture is written.
    assert w.offer(4.0, b"\x02" * 12, (2, 2)) is True and w.seq == 2 and enc.calls == 2


def test_a_deleted_file_is_written_again_even_when_unchanged(tmp_path):
    w = PreviewWriter(tmp_path / PREVIEW_FILE, 2.0, Enc())
    w.offer(0.0, b"\x01" * 12, (2, 2))
    (tmp_path / PREVIEW_FILE).unlink()
    assert w.offer(2.0, b"\x01" * 12, (2, 2)) is True and (tmp_path / PREVIEW_FILE).exists()


def test_disabled_writer_is_never_due(tmp_path):
    w = PreviewWriter(tmp_path / PREVIEW_FILE, 0, Enc())
    assert not w.due(0.0) and not w.due(1e9)
    assert w.status(5.0) == {"enabled": False, "age": None, "seq": 0, "errors": 0}


def test_failed_write_is_retried_soon(tmp_path, monkeypatch):
    w = PreviewWriter(tmp_path / PREVIEW_FILE, 2.0, Enc())

    def busy(src, dst):
        raise PermissionError("in use")  # Windows: the server was reading the file

    monkeypatch.setattr(os, "replace", busy)
    assert w.offer(10.0, b"\x01" * 12, (2, 2)) is False
    assert w.errors == 1 and w.checked is None and w.next_at == 10.0 + RETRY_SECS
    monkeypatch.undo()
    assert w.offer(10.5, b"\x01" * 12, (2, 2)) is True  # same picture: still written, nothing was saved before


def test_encoder_errors_propagate(tmp_path):
    def broken(rgb, size):
        raise ValueError("no codec")

    with pytest.raises(ValueError):
        PreviewWriter(tmp_path / PREVIEW_FILE, 2.0, broken).offer(0.0, b"\x00" * 12, (2, 2))


def test_clear_removes_the_file_and_temp(tmp_path):
    w = PreviewWriter(tmp_path / PREVIEW_FILE, 2.0, Enc())
    w.offer(0.0, b"\x01" * 12, (2, 2))
    (tmp_path / (PREVIEW_FILE + ".tmp")).write_bytes(b"x")
    w.clear()
    assert list(tmp_path.iterdir()) == [] and w.status(1.0)["age"] is None
    w.clear()  # nothing left: no error


def test_logs_dir_is_gitignored():
    # The preview is screen content: it must never be committed.
    text = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "logs/" in text and "*.jpg" in text


def test_failed_writes_are_counted_in_the_status_and_logged_rarely(tmp_path, monkeypatch):
    logs = []
    w = PreviewWriter(tmp_path / PREVIEW_FILE, 2.0, Enc(), log=logs.append)

    def busy(src, dst):
        raise PermissionError("in use")

    monkeypatch.setattr(os, "replace", busy)
    for t in (0.0, 0.5, 1.0, LOG_EVERY_SECS - 1):
        w.offer(t, b"\x01" * 12, (2, 2))
    assert len(logs) == 1 and "in use" in logs[0]          # the first failure only ...
    w.offer(LOG_EVERY_SECS + 0.1, b"\x01" * 12, (2, 2))
    assert len(logs) == 2 and "5 so far" in logs[1]        # ... then at most once a minute
    assert w.status(70.0)["errors"] == 5


def test_a_disabled_writer_needs_no_encoder(tmp_path):
    (tmp_path / PREVIEW_FILE).write_bytes(b"old")
    w = PreviewWriter(tmp_path / PREVIEW_FILE, 0, None)    # what mirror --cleanup uses
    w.clear()
    assert not (tmp_path / PREVIEW_FILE).exists()
