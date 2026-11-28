# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [0.3.0] - Unreleased

### Added

- Projector preview in the panel ("Projector view" / 投影畫面), docked at the bottom and closed by default:
  a small picture of what the audience sees now, including the frozen frame (F8), the blank screen (F9)
  and followed popups.
  - mirror.py samples the final projector frame every `preview_interval_sec` (default 2 s, `0` = off),
    downscales it to `preview_width` (480 px) first, skips the write when the small image is unchanged
    (CRC32) and replaces `logs/mirror.preview.jpg` atomically (JPEG `preview_quality` 70, OpenCV, already
    installed for windows-capture). Never on every frame; any preview error turns only the preview off.
  - `GET /api/preview` (same `Host` check, `Cache-Control: no-store`, `Cross-Origin-Resource-Policy: same-origin`);
    `/api/state` reports `preview: {available, enabled, age}`, where the age comes from the mirror's own
    relative report (no Windows / WSL clock comparison).
  - The panel reloads it every ~2 s only while it is open and the page is visible; shows "3 s ago",
    Frozen / Blank badges, and greys it out after 10 s without an update or when the mirror is not connected.
  - The file is deleted when the mirror starts and stops, and by `mirror.py --cleanup` (`stop.ps1` after a
    forced kill); it lives only in the gitignored `logs/`. Failed writes are retried, logged at most once a
    minute and counted in the status (`preview.errors`).
  - "Preview off" or a deleted file hides the last picture instead of showing an old screen in colour;
    the fetch gives up after 5 s.
- Collapsible panel blocks: Source, Timer, Notes & sections, Conversation (AI helper tab) and Projector view.
  Header buttons with ▾ / ▸ and `aria-expanded`; a closed block shows a one-line summary (warnings replace the
  source title, so they stay visible); state saved per block in localStorage. The notes keep the remaining height,
  and the hotkeys and step scroll-spy work unchanged.
- `web/view.js` (fold defaults, preview status; DOM-free, `tests/js/view.test.js`), `presenter_sidecar/preview.py`
  (settings, sampling, unchanged-skip, atomic write; `tests/test_preview.py`), and `tests/test_panel_ui.py`:
  headless Chromium checks of the panel (skipped without Playwright).

- CI: a `ui` job runs `tests/test_panel_ui.py` in headless Chromium (`REQUIRE_UI_TESTS=1`: never skipped there).
- Profiles: a set of notes files, timer sections and auto-follow rules that switch together, so the stage bar
  always belongs to the notes on screen.
  - The top-level keys are the first profile (`profile_name`, default `default`): configs from 0.2.0 work unchanged.
    `profiles` adds more, each with `name`, `notes_files`, `pacing_file` or `pacing_notes`, `notes_rules`,
    `notes_follow_doc`.
  - `pacing_notes`: pacing derived from a notes file, one timer section per `##` section with a line that starts
    with `建議時間：約 N 分鐘` / `Suggested time: ~N min` (hours and decimals too; 0 is skipped). A repeated heading
    maps to its own timer (`presenter_sidecar.notes.pacing_from_notes`, `stage_for_section`).
  - Panel: a profile chip at the end of the tabs row; each profile keeps its own timer (`timer@<profile>`),
    open notes file and place (the 0.2.0 keys are read once for the first profile).
  - Auto-follow checks the active profile's rules first, then the others, and switches profile with a notice
    (`profile_auto_switch`, default on).
  - Startup profile: `panel_server.py --profile`, `PRESENTER_PROFILE`, `"profile"`; `start.bat` / `start.ps1 -Profile NAME`
    (a running server gets `POST /api/profile` as UTF-8; every open panel window switches once; F5 and a plain server
    restart keep a profile picked by hand). Profiles added to `config.json` appear without F5; profiles left out
    (empty top-level `notes_files`, no name, repeated name) are logged.
  - `/api/notes` and `/api/pacing` take `?profile=`; `/api/state?profile=` returns the target's `profile` and
    the startup request `profile_req`.
  - Example: a `meeting` profile with `examples/notes/meeting.md`.

### Fixed

- The notes article no longer grows past the window in a short panel: its bottom scroll room is a spacer
  instead of 40vh of padding (padding cannot shrink). The notes keep at least 25vh; the preview dock shrinks
  first (checked at 600 and 700 px tall with every block open).

## [0.2.0] - 2026-11-27

### Added

- Panel step bar: a second bar under the section drop-down (◀ drop-down ▶) for the steps inside a section.
  - A step is a paragraph whose only content is a bold numbered title (`**3. Open the sheet**`);
    sections without one fall back to `###` headings, and the bar is hidden when there are none.
    ASCII digits only, and an ASCII dot needs a space after it, so `**2.5 million**` is not a step
    (`3．` needs none). A step runs until the next step, heading, `---` rule or `>` quote.
  - The selected step scrolls to the top of the notes (below any sticky header) and is highlighted;
    a scroll-spy keeps the drop-down in sync when you scroll by hand (and ignores the scroll a step jump
    causes, so short steps are never skipped).
  - ↑ / ↓ and K / J move between steps; a step taller than the view is paged through first; on the last
    step ↓ scrolls on to the section end; entering a section whose step 1 is not fully on screen, the first
    ↓ brings it up; ↑ returns to the current step's title first when it has scrolled out of view.
  - Changing section starts at step 1; the step is restored on reload (saved per notes path + section index).
  - Labels show the step title plus its position, e.g. `4. Recap (4/4)` (`（4/4）` in zh-TW).
- ⌨ keyboard-shortcut overlay (button next to A− / A+, or `?`, also through AltGr; Esc or ✕ closes).
  Global hotkeys are the ones mirror.py registered at start (new `hotkeys` field in its status; `config.json`
  while the mirror is not connected), with keys another program has taken flagged and a note that changing
  them needs a mirror restart; panel keys are listed below. Modal: the page behind is `inert`, Tab stays
  inside, and closing returns focus to where it was. English and Traditional Chinese.
- `presenter_sidecar.notes.section_steps` / `step_label`: the step rule as tested pure Python.
- `web/md.js` and `web/steps.js`: the Markdown renderer and step rule without DOM code, loaded by the panel
  and run under node by `tests/js/steps.test.js`; `tests/fixtures/steps` is shared with the Python tests,
  and CI runs `node --test`.
- Example notes: Demo C now uses numbered bold steps; `docs/media/panel.png` and `auto-follow.gif` show the step bar.

### Changed

- `notes_files` and `pacing_file` reload live like `notes_rules`: add a notes file to `config.json` and
  press F5 in the panel, no restart.
- Panel keys ignore Ctrl, Alt and Meta combinations, so browser shortcuts and Ctrl+Alt+PgUp / PgDn pass through.
- Panel keys are ignored while the shortcut overlay is open.
- The open notes file and the section per file are saved by notes path instead of position, so adding or
  reordering `notes_files` keeps your place (0.1.0 positions are read once as a fallback).
- Choosing a section from the drop-down hands the keys back to the notes (← / → page again right away).

## [0.1.0] - 2026-11-27

### Added

- `mirror.py`: projects one chosen window to the projector display.
  - Capture backends: Windows Graphics Capture → PrintWindow → mss fallback.
  - Follows moves and resizes, freezes on minimise, auto-follows new popups of the same process.
  - Never projects terminals or the tool's own windows.
  - Presenter pointer with ring, spotlight and click ripples.
  - Configurable global hotkeys (pick, bring back, freeze, blank, style, popups, mouse lock, notes paging, quit).
- `panel_server.py`: standard-library local server for the private panel (Windows, WSL, Linux, macOS).
- Panel (Chrome/Edge `--app` window): Markdown speaker notes, auto-follow by title rules and optional CDP URL
  rules (including `#hash`), per-section timers from a pacing file, English and Traditional Chinese UI.
- Optional read-only AI helper backed by the Claude Code CLI (disabled by default).
- `start.ps1` / `stop.ps1` with `panel_runtime: "windows" | "wsl"`.
- Mock example talk, pacing, checklist and a static demo site; self-test pages.
- Unit tests (no display needed), CI on Ubuntu and Windows, private-term scan and pre-commit hook.
- Mock screenshots and a layout diagram in `docs/media/`, re-generated by `scripts/media/render_media.py`.

[0.2.0]: https://github.com/osisdie/presenter-sidecar/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/osisdie/presenter-sidecar/releases/tag/v0.1.0
