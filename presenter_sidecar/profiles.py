"""Profiles: one set of notes files, pacing and auto-follow rules per kind of session (pure).

The top-level ``notes_files`` / ``pacing_file`` / ``pacing_notes`` / ``notes_rules`` /
``notes_follow_doc`` keys form the first profile, named ``profile_name`` (so a config from before
0.3.0 is one profile and behaves as before). ``profiles`` adds more, each with the same keys::

    "profiles": [{"name": "meeting", "notes_files": ["notes/meeting.md"],
                  "pacing_notes": "notes/meeting.md", "notes_rules": [...]}]

A profile's pacing is ``pacing_file`` (the pacing format) or, when that is empty, ``pacing_notes``:
a notes file whose ``##`` sections carry ``建議時間：約 N 分鐘`` / ``Suggested time: ~N min``.
The top-level profile is left out when it has no notes files and other profiles exist.
"""
from __future__ import annotations

PROFILE_KEYS = ("notes_files", "pacing_file", "pacing_notes", "notes_rules", "notes_follow_doc")
LIST_KEYS = ("notes_files", "notes_rules")


def _profile(name: str, src: dict) -> dict:
    p = {"name": name}
    for k in PROFILE_KEYS:
        v = src.get(k)
        if k in LIST_KEYS:
            p[k] = [x for x in v if x] if isinstance(v, list) else []
        else:
            p[k] = v.strip() if isinstance(v, str) else ""
    p["notes_rules"] = [r for r in p["notes_rules"] if isinstance(r, dict)]
    return p


def profiles(cfg: dict) -> list[dict]:
    """All profiles in order, normalised (missing keys empty). Names are unique; later duplicates
    and entries without a name are skipped."""
    out: list[dict] = []
    top_name = str(cfg.get("profile_name") or "default").strip() or "default"
    extra = [p for p in (cfg.get("profiles") or []) if isinstance(p, dict)]
    top = _profile(top_name, cfg)
    if top["notes_files"] or not extra:
        out.append(top)
    for raw in extra:
        name = str(raw.get("name") or "").strip()
        if name and all(p["name"] != name for p in out):
            out.append(_profile(name, raw))
    return out


def find(profs: list[dict], name: str | None) -> dict | None:
    return next((p for p in profs if p["name"] == name), None)


def startup_profile(profs: list[dict], *requested: str | None) -> str:
    """The first requested name that exists (``--profile``, ``PRESENTER_PROFILE``, ``profile`` in the
    config, in that order), else the first profile."""
    for name in requested:
        if name and find(profs, name.strip()):
            return name.strip()
    return profs[0]["name"] if profs else "default"
