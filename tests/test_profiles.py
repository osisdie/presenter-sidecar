import pytest

from presenter_sidecar.config import DEFAULTS, ROOT, deep_merge, load_config, resolve
from presenter_sidecar.notes import (pacing_from_notes, section_headings, stage_for_heading, stage_for_section,
                                     stage_label, suggested_minutes)
from presenter_sidecar.profiles import find, profile_warnings, profiles, startup_profile

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
    ("- 建議時間：約 20 分鐘", 20), ("* **Suggested time**: 3 min", 3), ("  + Suggested time: 4 min", 4),
    ("建議時間：1.5 小時", 90), ("建議時間：約 1 小時 30 分", 90), ("Suggested time: 1 hour", 60),
    ("Suggested time: 2h", 120), ("Suggested time: 1.5 min", 1.5), ("建議時間：2 鐘頭", 120),
])
def test_suggested_time_lines(line, minutes):
    assert suggested_minutes(line) == minutes
    assert pacing_from_notes(f"## Part\n\n{line}\n")[0]["minutes"] == minutes


@pytest.mark.parametrize("line", [
    "We kept to the suggested time: 5 min, mostly.",       # prose: not at the start of the line
    "> Suggested time: 5 min",                              # a quote is an aside, not the agenda
    "Suggested time: 0 min", "建議時間：0 分鐘",            # 0: not a stage
    "Suggested time: soon", "建議時間：彈性",
    "Suggested time: 5 minutesish",
])
def test_not_a_suggested_time(line):
    assert suggested_minutes(line) is None
    assert pacing_from_notes(f"## Part\n\n{line}\n") == []


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
    assert all(set(s) == {"key", "short", "title", "offset", "minutes", "detail", "heading", "nth"} for s in st)
    # Each stage matches its own section heading in the panel (stage_for_heading / stageOfTitle).
    heads = section_headings(md)
    assert [stage_for_heading(st, h) for h in heads] == [-1, 0, 1, -1, 2]


def test_duplicate_stage_names_get_their_own_keys_and_sections():
    md = "## Q&A\nSuggested time: 5 min\n## Break\n## Q&A\nSuggested time: 7 min\n"
    st = pacing_from_notes(md)
    assert [(s["key"], s["heading"], s["nth"], s["minutes"]) for s in st] == [("Q&A", "Q&A", 1, 5), ("Q&A (2)", "Q&A", 2, 7)]
    # The second "## Q&A" section belongs to the second Q&A timer, not the first (same short name).
    assert stage_for_section(st, "Q&A", 1) == 0 and stage_for_section(st, "Q&A", 2) == 1
    assert stage_for_heading(st, "Q&A") == 0  # the old rule could not tell them apart


def test_stage_for_section_falls_back_to_short_names():
    st = [{"key": "Demo A", "short": "Demo A", "minutes": 5}]   # pacing_file stages have no heading
    assert stage_for_section(st, "2. Demo A — code", 1) == 0 and stage_for_section(st, "Other", 1) == -1


def test_time_lines_in_code_blocks_are_ignored():
    assert pacing_from_notes("## Part\n```\nSuggested time: 5 min\n```\n") == []
    assert pacing_from_notes("## A\nSuggested time: 0 min\nSuggested time: 4 min\n")[0]["minutes"] == 4


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


def test_profile_warnings():
    assert profile_warnings(DEFAULTS) == []
    ok = deep_merge(DEFAULTS, {"notes_files": ["a"], "profiles": [{"name": "m"}]})
    assert profile_warnings(ok) == []
    dropped = deep_merge(DEFAULTS, {"profiles": [{"name": "m", "notes_files": ["m.md"]}]})
    assert any("'default' is left out" in w for w in profile_warnings(dropped))
    messy = deep_merge(DEFAULTS, {"notes_files": ["a"], "profiles": ["x", {"notes_files": []}, {"name": "default"},
                                                                    {"name": "m"}, {"name": "m"}]})
    w = " | ".join(profile_warnings(messy))
    assert "not objects" in w and "without a name" in w and "duplicate profile name 'default'" in w and "'m'" in w
    assert "must be a list" in profile_warnings(deep_merge(DEFAULTS, {"profiles": {"name": "m"}}))[0]
    assert [p["name"] for p in profiles(deep_merge(DEFAULTS, {"profiles": {"name": "m"}}))] == ["default"]
