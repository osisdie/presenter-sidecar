"""Step detection inside a notes section (mirrors planSteps() in web/steps.js).

tests/fixtures/steps holds the shared cases: this file runs them through the Python rule and
tests/js/steps.test.js runs them through the panel's JavaScript (md.js + steps.js).
"""
import json
from pathlib import Path

import pytest

from presenter_sidecar.notes import bold_step_title, section_steps, step_label

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures" / "steps"
EXPECTED = json.loads((FIXTURES / "expected.json").read_text(encoding="utf-8"))


def test_every_fixture_has_expected_titles():
    assert sorted(p.name for p in FIXTURES.glob("*.md")) == sorted(EXPECTED)


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_shared_fixture(name):
    assert section_steps((FIXTURES / name).read_text(encoding="utf-8")) == EXPECTED[name]


def test_step_number_needs_a_space_after_an_ascii_dot():
    assert bold_step_title(["**2.5 million**"]) is None
    assert bold_step_title(["**1.Title**"]) is None
    assert bold_step_title(["**10．全形**"]) == "10．全形"


def test_bold_numbered_paragraphs_are_steps():
    md = "## Demo\n\nIntro text.\n\n**1. Open the app**\n\n- click\n\n**2. Add a plant**\n\ntext\n\n**10．Wrap up**\n"
    assert section_steps(md) == ["1. Open the app", "2. Add a plant", "10．Wrap up"]


def test_bold_must_be_the_whole_paragraph():
    assert bold_step_title(["**1. Title** and more"]) is None
    assert bold_step_title(["**1. a** **b**"]) is None
    assert bold_step_title(["**1. Title**", "second line"]) is None
    assert bold_step_title(["**Before you start:**"]) is None  # not numbered
    assert bold_step_title(["**1.**"]) is None                  # number without a title
    assert bold_step_title(["  **3. Run `make`**  "]) == "3. Run make"


def test_bold_line_glued_to_a_paragraph_is_not_a_step():
    md = "Some text\n**1. Not a step**\n\n**2. A step**\n"
    assert section_steps(md) == ["2. A step"]


def test_bold_after_a_list_item_starts_a_new_paragraph():
    md = "- item\n  continued\n**1. Step**\n"
    assert section_steps(md) == ["1. Step"]


def test_ignores_code_fences_quotes_and_lists():
    md = "```\n**1. code**\n### code\n```\n> **2. quote**\n\n- **3. list item**\n1. **4. ordered**\n"
    assert section_steps(md) == []


def test_falls_back_to_h3_headings():
    md = "## Section\n\n### First `part`\ntext\n#### deeper\n### Second\n"
    assert section_steps(md) == ["First part", "Second"]


def test_bold_steps_win_over_h3():
    md = "### Heading\n\n**1. Bold step**\n"
    assert section_steps(md) == ["1. Bold step"]


def test_step_label():
    assert step_label("4. Run it", 5, 9) == "4. Run it (5/9)"
    assert step_label("4. 執行", 5, 9, "zh-TW") == "4. 執行（5/9）"


def test_example_notes_have_a_step_section():
    for name in ("talk-notes.md", "talk-notes.zh-TW.md"):
        text = (ROOT / "examples" / "notes" / name).read_text(encoding="utf-8")
        demo_c = text[text.index("## 4. Demo C"):text.index("## 5. Q&A")]
        steps = section_steps(demo_c)
        assert len(steps) == 4 and steps[0].startswith("1. ")
        # other sections have no steps, so the step bar stays hidden there
        assert section_steps(text[text.index("## 1."):text.index("## 2.")]) == []
