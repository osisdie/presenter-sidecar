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
