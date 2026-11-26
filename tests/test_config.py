import json

import pytest

from presenter_sidecar.config import DEFAULTS, ROOT, deep_merge, load_config, resolve
from presenter_sidecar.hotkeys import hotkey_table
from presenter_sidecar.notes import parse_pacing, section_headings, stage_for_heading

EXAMPLE = ROOT / "config.example.json"


def test_example_is_valid_json_and_knows_every_key():
    raw = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    unknown = {k for k in raw if not k.startswith("_")} - set(DEFAULTS)
    assert not unknown, f"keys missing from DEFAULTS: {unknown}"


def test_example_safe_defaults():
    cfg = load_config(EXAMPLE, ROOT)
    assert cfg["ai_helper"]["enabled"] is False
    assert cfg["cdp_url"] == ""
    assert cfg["source_title_contains"] == []
    assert cfg["panel_host"] == "127.0.0.1"
    assert cfg["panel_runtime"] in ("windows", "wsl")
    hotkey_table(cfg["hotkeys"])  # parses, no duplicates


def test_comment_keys_are_dropped_and_defaults_fill_gaps(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"_note": "x", "fps": 30, "ai_helper": {"enabled": True}}), encoding="utf-8")
    cfg = load_config(p, tmp_path)
    assert "_note" not in cfg and cfg["fps"] == 30
    assert cfg["ai_helper"]["enabled"] is True and cfg["ai_helper"]["timeout_sec"] == 180  # nested merge
    assert cfg["hotkeys"]["pick"] == "F7"


def test_missing_file_gives_defaults(tmp_path):
    cfg = load_config(tmp_path / "nope.json", tmp_path)
    assert cfg["panel_port"] == 8765


def test_non_object_is_rejected(tmp_path):
    p = tmp_path / "c.json"
    p.write_text("[1, 2]", encoding="utf-8")
    with pytest.raises(ValueError):
        load_config(p, tmp_path)


def test_deep_merge_does_not_mutate():
    base = {"a": {"b": 1, "c": 2}}
    out = deep_merge(base, {"a": {"b": 9}})
    assert out == {"a": {"b": 9, "c": 2}} and base == {"a": {"b": 1, "c": 2}}


def test_resolve(tmp_path):
    assert resolve(tmp_path, "x/y.md") == (tmp_path / "x" / "y.md").resolve()
    assert resolve(tmp_path, str(tmp_path / "abs.md")) == (tmp_path / "abs.md").resolve()


def test_example_content_is_consistent():
    """Every notes rule points at a real section, and every pacing entry has a notes section."""
    cfg = load_config(EXAMPLE, ROOT)
    for rel in cfg["notes_files"]:
        assert resolve(ROOT, rel).is_file(), rel
    stages = parse_pacing(resolve(ROOT, cfg["pacing_file"]).read_text(encoding="utf-8"))
    assert 6 <= len(stages) <= 7
    assert sum(s["minutes"] for s in stages) == 60
    for notes in ("examples/notes/talk-notes.md", "examples/notes/talk-notes.zh-TW.md"):
        heads = section_headings((ROOT / notes).read_text(encoding="utf-8"))
        for r in cfg["notes_rules"]:
            assert any(r["section_heading_contains"] in h for h in heads), (notes, r)
        for i, s in enumerate(stages):
            assert any(stage_for_heading(stages, h) == i for h in heads), (notes, s["short"])
