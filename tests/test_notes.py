from presenter_sidecar.notes import (choose_active_tab, clean_title, match_rule, notes_target, parse_pacing,
                                     projected_title, section_headings, split_label, stage_for_heading)

RULES = [
    {"url_contains": "#qa", "section_heading_contains": "Q&A"},
    {"url_contains": "#intro", "section_heading_contains": "Intro"},
    {"url_contains": "localhost:3000", "section_heading_contains": "Demo C"},
    {"title_contains": "Google Sheets", "section_heading_contains": "Demo B"},
    {"url_contains": "github.com", "section_heading_contains": "Demo A"},
]


def test_clean_title_strips_browser_suffix():
    assert clean_title("Budget - Google Sheets - Google Chrome") == "Budget - Google Sheets"
    assert clean_title("Repo - Microsoft​ Edge") == "Repo"
    assert clean_title("Page — Mozilla Firefox") == "Page"
    assert clean_title("  plain  ") == "plain"
    assert clean_title(None) == ""


def test_hash_rules_win_by_order():
    assert match_rule(RULES, "Plant-care App", "http://localhost:3000/#qa")[1]["section_heading_contains"] == "Q&A"
    assert match_rule(RULES, "Plant-care App", "http://localhost:3000/#intro")[0] == 1
    hit = match_rule(RULES, "Plant-care App", "http://localhost:3000/#demo")
    assert hit[0] == 2 and hit[2] == "url"


def test_url_rules_need_a_url():
    assert match_rule(RULES, "Plant-care App", "") is None
    assert match_rule(RULES, "Budget - Google Sheets", "")[2] == "title"


def test_title_rule_checked_before_url_in_same_rule():
    rules = [{"title_contains": "Sheets", "url_contains": "#qa", "section_heading_contains": "X"}]
    assert match_rule(rules, "Budget - Google Sheets", "http://x/#qa")[2] == "title"


def test_notes_target_shapes():
    nt = notes_target(RULES, "Budget - Google Sheets - Google Chrome", doc="talk-notes.md")
    assert nt["key"] == "Demo B" and nt["by"] == "title" and nt["title"] == "Budget - Google Sheets"
    assert nt["doc"] == "talk-notes.md"
    miss = notes_target(RULES, "Some other page - Google Chrome")
    assert miss == {"key": None, "title": "Some other page", "url": ""}
    assert notes_target(RULES, "") is None
    per_rule_doc = notes_target([{"title_contains": "x", "section_heading_contains": "s", "doc": "b.md"}], "x", doc="a.md")
    assert per_rule_doc["doc"] == "b.md"


def test_projected_title_prefers_followed_popup():
    assert projected_title({"source_title": "A", "following_popup": True, "popup_title": "B"}) == "B"
    assert projected_title({"source_title": "A", "following_popup": False, "popup_title": "B"}) == "A"
    assert projected_title({}) == ""


def _tabs():
    return [
        {"id": "t1", "title": "Plant-care App", "url": "http://localhost:3000/#intro"},
        {"id": "t2", "title": "Plant-care App", "url": "http://localhost:3000/#qa"},
        {"id": "t3", "title": "Other", "url": "http://example.test/"},
    ]


def test_same_title_visible_tab_wins():
    live = {"t1": ("hidden", False, "http://localhost:3000/#intro"),
            "t2": ("visible", False, "http://localhost:3000/#qa")}
    last = {}
    url, tid = choose_active_tab(_tabs(), "Plant-care App", lambda t: live[t["id"]], last)
    assert (url, tid) == ("http://localhost:3000/#qa", "t2")
    assert last["Plant-care App"] == "t2"


def test_same_title_focus_breaks_visibility_tie():
    live = {"t1": ("visible", True, "u1"), "t2": ("visible", False, "u2")}
    assert choose_active_tab(_tabs(), "Plant-care App", lambda t: live[t["id"]], {})[1] == "t1"


def test_same_title_remembers_last_choice_when_no_signal():
    live = {"t1": ("unknown", False, "u1"), "t2": ("unknown", False, "u2")}
    assert choose_active_tab(_tabs(), "Plant-care App", lambda t: live[t["id"]], {"Plant-care App": "t2"})[1] == "t2"
    # no memory: list order
    assert choose_active_tab(_tabs(), "Plant-care App", lambda t: live[t["id"]], {})[1] == "t1"


def test_single_and_missing_title():
    live = {"t3": ("visible", True, "http://example.test/#live")}
    assert choose_active_tab(_tabs(), "Other", lambda t: live[t["id"]], {}) == ("http://example.test/#live", "t3")
    assert choose_active_tab(_tabs(), "Nope", lambda t: ("", False, ""), {}) == ("", "")


PACING = """
```text
14:00  Intro: who we are       (8m)
+0:08  Demo A: code walkthrough (12m)
+0:20  Q&A                      (10m)
+1:30  Wrap-up — thanks         (5m)
15:00  END
```
| Section | Breakdown |
|---|---|
| Intro (8m) | Hook 2 | 
| Demo A (12m) | Repo 4｜Tests 8 |
"""


def test_parse_pacing():
    st = parse_pacing(PACING)
    assert [s["short"] for s in st] == ["Intro", "Demo A", "Q&A", "Wrap-up"]
    assert [s["minutes"] for s in st] == [8, 12, 10, 5]
    assert st[0]["offset"] == "14:00" and st[1]["offset"] == "+0:08"
    assert st[0]["title"] == "who we are" and st[2]["title"] == "" and st[3]["title"] == "thanks"
    assert st[1]["detail"] == "Repo 4｜Tests 8"
    assert parse_pacing("nothing here") == []


def test_split_label():
    assert split_label("Demo A: code") == ("Demo A", "code")
    assert split_label("Demo A：程式碼") == ("Demo A", "程式碼")
    assert split_label("Wrap-up - bye") == ("Wrap-up", "bye")
    assert split_label("Wrap-up") == ("Wrap-up", "")


def test_stage_for_heading_longest_match():
    stages = [{"short": "Demo"}, {"short": "Demo A"}, {"short": "Q&A"}]
    assert stage_for_heading(stages, "2. Demo A — code walkthrough") == 1
    assert stage_for_heading(stages, "5. q&a") == 2
    assert stage_for_heading(stages, "Thanks") == -1


def test_section_headings_ignore_code_fences():
    md = "# Title\nintro\n## One\n```\n## not a heading\n```\n## Two\n"
    assert section_headings(md) == ["Title", "One", "Two"]
