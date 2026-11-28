import pytest

from presenter_sidecar.config import DEFAULTS, ROOT, deep_merge, load_config, resolve
from presenter_sidecar.notes import pacing_from_notes, section_headings, stage_for_heading, stage_label
from presenter_sidecar.profiles import find, profiles, startup_profile

RULE = {"title_contains": "Board", "section_heading_contains": "Board walk"}


def test_config_without_profiles_is_one_default_profile():
    # A 0.2.0 config: the top-level keys are the only profile, named "default".
    cfg = deep_merge(DEFAULTS, {"notes_files": ["a.md"], "pacing_file": "p.md", "notes_rules": [RULE]})
    assert profiles(cfg) == [{"name": "default", "notes_files": ["a.md"], "pacing_file": "p.md",
                              "pacing_notes": "", "notes_rules": [RULE], "notes_follow_doc": ""}]
    assert profiles(DEFAULTS)[0]["name"] == "default"  # even with nothing configured


def test_profiles_follow_the_top_level_one_and_keep_their_own_keys():
    cfg = deep_merge(DEFAULTS, {"profile_name": "talk", "notes_files": ["a.md"], "notes_rules": [RULE],
                                "profiles": [{"name": " meeting ", "notes_files": ["m.md"], "pacing_notes": "m.md"}]})
    talk, meeting = profiles(cfg)
    assert talk["name"] == "talk" and meeting["name"] == "meeting"
    assert meeting["notes_rules"] == [] and meeting["pacing_file"] == "" and meeting["pacing_notes"] == "m.md"


def test_empty_top_level_is_left_out_when_profiles_exist():
    cfg = deep_merge(DEFAULTS, {"profiles": [{"name": "a", "notes_files": ["a.md"]}, {"name": "b"}]})
    assert [p["name"] for p in profiles(cfg)] == ["a", "b"]


def test_bad_entries_are_skipped_and_duplicates_ignored():
    cfg = deep_merge(DEFAULTS, {"notes_files": ["x.md"], "profiles": [
        "not a dict", {"notes_files": ["no-name.md"]}, {"name": "default", "notes_files": ["dup.md"]},
        {"name": "m", "notes_files": "one.md", "notes_rules": [RULE, "junk"], "pacing_file": 5}]})
    profs = profiles(cfg)
    assert [p["name"] for p in profs] == ["default", "m"]
    assert profs[0]["notes_files"] == ["x.md"]
    assert profs[1]["notes_files"] == [] and profs[1]["notes_rules"] == [RULE] and profs[1]["pacing_file"] == ""


def test_startup_profile_order():
    profs = profiles(deep_merge(DEFAULTS, {"profile_name": "talk", "notes_files": ["a"],
                                           "profiles": [{"name": "meeting"}]}))
    assert startup_profile(profs) == "talk"
    assert startup_profile(profs, None, "", "meeting") == "meeting"     # config "profile"
    assert startup_profile(profs, "meeting ", "talk") == "meeting"      # --profile wins
    assert startup_profile(profs, "nope", None, "") == "talk"           # unknown: the first
    assert find(profs, "meeting")["name"] == "meeting" and find(profs, "x") is None


@pytest.mark.parametrize("line, minutes", [
    ("建議時間：約 8 分鐘", 8), ("建議時間: 8分", 8), ("**建議時間**：約 12 分鐘", 12), ("建議時間：10–15 分鐘", 10),
    ("Suggested time: ~5 min", 5), ("suggested time: about 20 minutes", 20), ("_Suggested time_: 7-9 min", 7),
])
def test_suggested_time_lines(line, minutes):
    assert pacing_from_notes(f"## Part\n\n{line}\n")[0]["minutes"] == minutes


def test_pacing_from_notes_stages_in_order():
    md = ("# Title\n\nSuggested time: 99 min (the title section is never a stage)\n\n"
          "## Part 0 暖身與期待\n\n建議時間：約 8 分鐘\n\n"
          "## Demo A: code walk\n\nSuggested time: ~12 min\n\n"
          "```\n## not a heading\nSuggested time: 3 min\n```\n\n"
          "## Appendix\n\nno time here\n\n"
          "## 第 2 段 實作\n\n- 建議時間：約 20 分鐘\n")
    st = pacing_from_notes(md)
    assert [(s["short"], s["title"], s["minutes"]) for s in st] == [
        ("Part 0", "暖身與期待", 8), ("Demo A", "code walk", 12), ("第 2 段", "實作", 20)]
    assert all(set(s) == {"key", "short", "title", "offset", "minutes", "detail"} for s in st)
    # Each stage matches its own section heading in the panel (stage_for_heading / stageOfTitle).
    heads = section_headings(md)
    assert [stage_for_heading(st, h) for h in heads] == [-1, 0, 1, -1, 2]


def test_duplicate_stage_names_get_their_own_keys():
    st = pacing_from_notes("## Q&A\nSuggested time: 5 min\n## Q&A\nSuggested time: 5 min\n")
    assert [s["key"] for s in st] == ["Q&A", "Q&A (2)"]


def test_stage_label():
    assert stage_label("Module 3. Wrap") == ("Module 3", "Wrap")
    assert stage_label("Session 2 Questions") == ("Session 2", "Questions")
    assert stage_label("Q&A") == ("Q&A", "")
    assert stage_label("Stage") == ("Stage", "")


def test_example_meeting_profile_is_consistent():
    cfg = load_config(ROOT / "config.example.json", ROOT)
    talk, meeting = profiles(cfg)
    assert talk["name"] == "talk" and talk["notes_files"] == cfg["notes_files"]
    assert meeting["name"] == "meeting" and cfg["profile_auto_switch"] is True
    md = resolve(ROOT, meeting["pacing_notes"]).read_text(encoding="utf-8")
    st = pacing_from_notes(md)
    assert [s["short"] for s in st] == ["Part 1", "Part 2", "Part 3", "Part 4"]
    assert sum(s["minutes"] for s in st) == 35
    heads = section_headings(md)
    for r in meeting["notes_rules"]:
        assert any(r["section_heading_contains"] in h for h in heads), r
    # Meeting rules never match a talk page and the other way round (auto-switch stays predictable).
    talk_titles = {r.get("title_contains") for r in talk["notes_rules"]}
    assert not talk_titles & {r.get("title_contains") for r in meeting["notes_rules"]}
