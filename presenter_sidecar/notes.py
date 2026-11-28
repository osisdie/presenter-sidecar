"""Speaker-notes logic (pure): pick the notes section for the projected tab, parse pacing.

Rules come from ``notes_rules`` in the config and are checked top to bottom; the first
match wins::

    {"title_contains": "Google Sheets", "section_heading_contains": "Demo B"}
    {"url_contains": "#qa",            "section_heading_contains": "Q&A"}

``url_contains`` sees the full URL including the ``#hash`` and needs ``cdp_url``.
"""
from __future__ import annotations

import re
from typing import Callable

BROWSER_SUFFIX = re.compile(
    r"\s+[-—]\s+(Google Chrome|Microsoft​? Edge|Chromium|Brave|Mozilla Firefox|Opera)$")


def clean_title(title: str) -> str:
    """``"Docs - Google Chrome"`` → ``"Docs"`` (Chrome window title = active tab title + suffix)."""
    return BROWSER_SUFFIX.sub("", title or "").strip()


def match_rule(rules: list[dict], title: str, url: str = "") -> tuple[int, dict, str] | None:
    """First rule matching ``title`` (``title_contains``) or ``url`` (``url_contains``).

    Returns ``(index, rule, by)`` where ``by`` is ``"title"`` or ``"url"``, or ``None``.
    """
    for i, r in enumerate(rules or []):
        if r.get("title_contains") and r["title_contains"] in title:
            return i, r, "title"
        if r.get("url_contains") and url and r["url_contains"] in url:
            return i, r, "url"
    return None


def notes_target(rules: list[dict], raw_title: str, url: str = "", tab_id: str = "", doc: str = "") -> dict | None:
    """What the panel should show for the projected window. ``key`` is ``None`` when no rule matches."""
    title = clean_title(raw_title)
    if not title:
        return None
    hit = match_rule(rules, title, url)
    if not hit:
        return {"key": None, "title": title, "url": url}
    i, r, by = hit
    sec = r.get("section_heading_contains", "")
    return {"key": sec, "section": sec, "rule": i, "by": by, "title": title, "url": url,
            "tab": tab_id[:8], "doc": r.get("doc") or doc}


def projected_title(mirror: dict) -> str:
    """Title of what is on the projector: the followed popup if any, else the source."""
    if not mirror:
        return ""
    return (mirror.get("popup_title") if mirror.get("following_popup") else mirror.get("source_title")) or ""


LiveFn = Callable[[dict], tuple[str, bool, str]]


def choose_active_tab(tabs: list[dict], title: str, live: LiveFn, last_active: dict[str, str],
                      limit: int = 8) -> tuple[str, str]:
    """Among CDP tabs whose title equals ``title`` pick the one on screen.

    ``/json/list`` neither marks the active tab nor sorts by use, so each candidate is asked
    via ``live(tab) -> (visibilityState, hasFocus, href)``. Score: visible 2, focused 1,
    picked last time 0.5; ties go to list order. Returns ``(url, tab_id)``.
    """
    cands = [t for t in tabs if t.get("title", "").strip() == title][:limit]
    if not cands:
        return "", ""
    if len(cands) == 1:
        t = cands[0]
        return live(t)[2], t.get("id", "")
    scored = []
    for i, t in enumerate(cands):
        vis, focus, href = live(t)
        score = (2 if vis == "visible" else 0) + (1 if focus else 0) + \
            (0.5 if last_active.get(title) == t.get("id") else 0)
        scored.append((score, -i, href, t.get("id", "")))
    best = max(scored)
    last_active[title] = best[3]
    return best[2], best[3]


# ---------------------------------------------------------------- pacing
PACING_LINE = re.compile(r"^(\d{1,2}:\d{2}|\+\d{1,2}:\d{2})\s+(.+?)\s+\((\d+)m\)", re.M)
PACING_DETAIL = re.compile(r"^\|\s*(.+?)\s*\((\d+)m\)\s*\|\s*(.+?)\s*\|\s*$", re.M)
LABEL_SPLIT = re.compile(r"^(.+?)\s*(?:[:：]|\s[—–-]\s)\s*(.*)$")


def split_label(label: str) -> tuple[str, str]:
    """``"Demo A: code walkthrough"`` → ``("Demo A", "code walkthrough")``."""
    m = LABEL_SPLIT.match(label.strip())
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return label.strip(), ""


def parse_pacing(text: str) -> list[dict]:
    """Parse the pacing file (see ``examples/pacing.md``).

    Schedule lines: ``<HH:MM | +H:MM>  <Short>: <title>  (<N>m)``.
    Optional detail rows: ``| <Short> (<N>m) | <breakdown> |``.
    """
    stages: list[dict] = []
    for m in PACING_LINE.finditer(text):
        short, title = split_label(m.group(2))
        stages.append({"key": short, "short": short, "title": title,
                       "offset": m.group(1), "minutes": int(m.group(3)), "detail": ""})
    for m in PACING_DETAIL.finditer(text):
        label = m.group(1).strip()
        for s in stages:
            if s["short"] == label:
                s["detail"] = m.group(3)
    return stages


def stage_for_heading(stages: list[dict], heading: str) -> int:
    """Index of the stage whose short name appears in a notes heading (longest name wins), or -1."""
    h = heading.lower()
    best, best_len = -1, 0
    for i, s in enumerate(stages):
        name = s["short"].lower()
        if name and name in h and len(name) > best_len:
            best, best_len = i, len(name)
    return best


def section_headings(markdown: str) -> list[str]:
    """``##`` headings outside code fences, plus the ``#`` title of the opening section."""
    out, fence, first = [], False, None
    for ln in markdown.replace("\r", "").split("\n"):
        if ln.startswith("```"):
            fence = not fence
        if fence:
            continue
        if ln.startswith("## "):
            out.append(ln[3:].strip())
        elif ln.startswith("# ") and first is None and not out:
            first = ln[2:].strip()
    return ([first] if first else []) + out


# ---------------------------------------------------------------- steps inside a section
# Same rule as planSteps() in web/steps.js (which works on the rendered HTML); the shared cases in
# tests/fixtures/steps run against both. A step is a paragraph whose ONLY content is a bold,
# numbered title such as ``**3. Open the sheet**``; when a section has none, its ``###`` headings
# are used instead. ASCII digits only (``[0-9]``: Python's ``\d`` would also take ``１``). ``3.`` needs
# a space before the title, so ``**2.5 million**`` is not a step; the full-width ``3．`` may be
# followed directly (CJK text puts no space after it).
STEP_NUMBER = re.compile(r"^[0-9]+(?:\.\s+|．\s*)\S")
_BLOCK_START = re.compile(r"^(#|```|\s*>|\s*[-*+]\s|\s*\d+[.)]\s|\s*\|)")
_LIST_ITEM = re.compile(r"^(\s*)([-*+]|\d+[.)])\s+")
_TABLE_SEP = re.compile(r"^\s*\|?\s*:?-{2,}")


_CODE = re.compile(r"`([^`]+)`")
_STRONG = re.compile(r"\*\*(.+?)\*\*")
_EM = re.compile(r"(^|[^*])\*([^*\s][^*]*?)\*")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")


def _hide_code(s: str) -> tuple[str, list[str]]:
    """Code spans first, as ``inline()`` in web/md.js: their content is never read as ``*`` markup."""
    codes: list[str] = []

    def keep(m):
        codes.append(m.group(1))
        return f"\0{len(codes) - 1}\0"
    return _CODE.sub(keep, s), codes


def _text(s: str, codes: list[str]) -> str:
    """Markup → visible text, in the order ``inline()`` applies it (what ``textContent`` returns)."""
    s = _EM.sub(r"\1\2", _STRONG.sub(r"\1", s))
    s = _LINK.sub(r"\1", s)
    return re.sub("\0(\\d+)\0", lambda m: codes[int(m.group(1))], s).strip()


def _plain(s: str) -> str:
    """Inline Markdown → visible text (what ``textContent`` returns in the panel)."""
    return _text(*_hide_code(s))


def _blocks(markdown: str):
    """Block structure as panel.js ``md()`` sees it: ``("h", level, text)``, ``("p", lines)``, ``("x",)``."""
    lines = markdown.replace("\r", "").split("\n")
    i, n = 0, len(lines)
    while i < n:
        ln = lines[i]
        if ln.startswith("```"):
            i += 1
            while i < n and not lines[i].startswith("```"):
                i += 1
            i += 1
            yield ("x",)
            continue
        if not ln.strip():
            i += 1
            continue
        m = re.match(r"^(#{1,6})\s+(.*)", ln)
        if m:
            yield ("h", len(m.group(1)), m.group(2))
            i += 1
            continue
        if re.match(r"^(-{3,}|\*{3,})\s*$", ln) or re.match(r"^\s*>", ln):
            i += 1
            while ln.lstrip().startswith(">") and i < n and re.match(r"^\s*>", lines[i]):
                i += 1
            yield ("x",)
            continue
        if re.match(r"^\s*\|", ln) and i + 1 < n and _TABLE_SEP.match(lines[i + 1]):
            i += 2
            while i < n and re.match(r"^\s*\|", lines[i]):
                i += 1
            yield ("x",)
            continue
        if _LIST_ITEM.match(ln):
            i += 1
            while i < n and re.match(r"^\s{2,}\S", lines[i]) and not _LIST_ITEM.match(lines[i]):
                i += 1
            yield ("x",)
            continue
        buf = [ln]
        i += 1
        while i < n and lines[i].strip() and not _BLOCK_START.match(lines[i]):
            buf.append(lines[i])
            i += 1
        yield ("p", buf)


def bold_step_title(paragraph: list[str]) -> str | None:
    """``["**4. Run it**"]`` → ``"4. Run it"``; ``None`` unless the paragraph is one numbered bold title."""
    if len(paragraph) != 1:
        return None
    s, codes = _hide_code(paragraph[0].strip())
    m = _STRONG.match(s)  # the panel's test: the paragraph's only child is ONE <strong>
    if not m or m.end() != len(s):
        return None
    title = _text(m.group(1), codes)
    return title if STEP_NUMBER.match(title) else None


def section_steps(markdown: str) -> list[str]:
    """Step titles of one notes section: numbered bold paragraphs, else ``###`` headings."""
    blocks = list(_blocks(markdown))
    bold = [t for b in blocks if b[0] == "p" and (t := bold_step_title(b[1]))]
    if bold:
        return bold
    return [_plain(b[2]) for b in blocks if b[0] == "h" and b[1] == 3]


def step_label(title: str, index: int, total: int, lang: str = "en") -> str:
    """Drop-down label, 1-based: ``"4. Run it (5/9)"`` (``zh-TW``: full-width brackets)."""
    if lang == "zh-TW":
        return f"{title}（{index}/{total}）"
    return f"{title} ({index}/{total})"


# ---------------------------------------------------------------- pacing derived from a notes file
# A notes file can be its own pacing: every ``## `` section that states a suggested time is a stage.
# The marker must START a line (after an optional list bullet; bold / italic / code marks are ignored):
# ``建議時間：約 8 分鐘``, ``- **Suggested time**: ~1.5 hours``, ``建議時間：1 小時 30 分``. A range counts its
# first number (``10–15 分鐘`` → 10); a time of 0 is not a stage. Prose that merely mentions it does not count.
_TIME_MARK = re.compile(r"^\s*(?:建議時間|suggested\s+time)\s*[:：]?\s*(?:約|大約|about|approx\.?|~|≈|～)?\s*", re.I)
_MIN_UNIT = r"(?:分鐘|分|minutes?|mins?|m)(?![a-z])"
_HOUR_UNIT = r"(?:小時|鐘頭|hours?|hrs?|h)(?![a-z])"
_AMOUNT = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:[-–~～至到]\s*\d+(?:\.\d+)?\s*)?"
    rf"(?:(?P<h>{_HOUR_UNIT})(?:\s*(?P<extra>\d+)\s*{_MIN_UNIT})?|{_MIN_UNIT})", re.I)


def suggested_minutes(line: str) -> float | None:
    """Minutes from one suggested-time line, or None when the line is not one (or says 0)."""
    s = re.sub(r"^\s*[-*+]\s+", "", line)           # list bullet first: "*" is also bold
    s = re.sub(r"[*_`]", "", s)
    m = _TIME_MARK.match(s)
    a = _AMOUNT.match(s[m.end():]) if m else None
    if not a:
        return None
    n = float(a.group(1)) * (60 if a.group("h") else 1) + float(a.group("extra") or 0)
    n = round(n, 2)
    return (int(n) if n == int(n) else n) if n > 0 else None


STAGE_PREFIX = re.compile(
    r"^((?:stage|part|session|module|lab|day)\s*\d+[a-z]?|第\s*[0-9一二三四五六七八九十]+\s*[段節章部課天])\s*[.、．]?\s+(\S.*)$",
    re.I)


def stage_label(heading: str) -> tuple[str, str]:
    """A notes heading → (short, title) for a stage button: ``"Part 0 暖身"`` → ``("Part 0", "暖身")``,
    ``"Demo A: code"`` → ``("Demo A", "code")``; anything else is all short."""
    m = STAGE_PREFIX.match(heading.strip())
    return (m.group(1).strip(), m.group(2).strip()) if m else split_label(heading)


def pacing_from_notes(markdown: str) -> list[dict]:
    """Stages from a notes file: each ``##`` section with a suggested-time line, in order.

    ``short`` / ``title`` come from :func:`stage_label`. ``heading`` (the ``##`` text as written) and ``nth``
    (its occurrence, for repeated headings) tie each stage to its own section: see :func:`stage_for_section`.
    Sections without a time line (the ``#`` title section, an appendix) are not stages.
    """
    stages: list[dict] = []
    seen: dict[str, int] = {}
    heading, raw, minutes, fence = None, "", None, False

    def flush():
        if heading is None or minutes is None:
            return
        short, title = stage_label(heading)
        key, n = short, 2
        while any(s["key"] == key for s in stages):  # duplicate short names stay separate timers
            key, n = f"{short} ({n})", n + 1
        stages.append({"key": key, "short": short, "title": title, "offset": "", "minutes": minutes,
                       "detail": "", "heading": raw, "nth": seen[raw]})

    for ln in markdown.replace("\r", "").split("\n"):
        if ln.startswith("```"):
            fence = not fence
            continue
        if fence:
            continue
        if ln.startswith("## "):
            flush()
            raw = ln[3:].strip()
            seen[raw] = seen.get(raw, 0) + 1
            heading, minutes = _plain(raw), None
        elif heading is not None and minutes is None:
            minutes = suggested_minutes(ln)
    flush()
    return stages


def stage_for_section(stages: list[dict], heading: str, nth: int = 1) -> int:
    """The stage of a notes section: the stage made from exactly this section (``heading`` + ``nth``,
    pacing from notes, so repeated headings map to their own stage), else :func:`stage_for_heading`.
    Same rule as ``stageIndex`` in web/view.js."""
    h = heading.strip()
    for i, s in enumerate(stages):
        if s.get("heading") == h and s.get("nth", 1) == nth:
            return i
    return stage_for_heading(stages, h)
