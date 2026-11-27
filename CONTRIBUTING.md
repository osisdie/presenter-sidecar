# Contributing

Thanks for helping! Small, focused pull requests are easiest to review.

## Setup

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
scripts/check/install-hooks.sh   # pre-commit: gitleaks + private-term scan
```

The tests need no display and run on Linux, macOS and Windows. The Windows-only mirror is
checked with `python mirror.py --selfcheck` (imports dependencies, parses the config, opens no
window).

## Code layout

- `presenter_sidecar/`: pure, standard-library modules (geometry, window rules, notes rules,
  hotkey parsing, config, CDP). Put logic here so it can be unit-tested.
- `mirror.py`: Win32 / pygame glue only.
- `panel_server.py`: standard library only. Do not add third-party dependencies to it.
- `web/`: the panel (plain HTML/CSS/JS, no build step). Add UI strings to both `en` and `zh-TW`
  in `web/panel.js`, and server/mirror strings to `presenter_sidecar/i18n.py`.
- `web/md.js` and `web/steps.js` must not touch the DOM: `node --test tests/js/*.test.js` runs them. The step rule
  exists twice (`steps.js` and `presenter_sidecar/notes.py`); add a case to `tests/fixtures/steps/`
  (Markdown + `expected.json`) and both test suites check it.

## Screenshots

`docs/media/` holds mock screenshots only. Re-generate them from `examples/` (headless, ephemeral
local ports, no real display or account):

```bash
python -m pip install playwright pillow && python -m playwright install chromium
python scripts/media/render_media.py
```

Never add screenshots of real screens, events or documents.

## Privacy rule for examples

Everything in this repository must be generic. Do not commit real names, e-mail addresses,
document IDs, local paths, screenshots of real content or anything from a private event.

- Keep a local `.private-denylist` (gitignored, one regex per line) with your own terms.
- `scripts/check/scan-private.sh --all` checks tracked and untracked files against it and
  against `scripts/check/generic-denylist.txt` (absolute user paths, document URLs).
- In CI the scan also reads a `PRIVATE_DENYLIST` repository secret if you define one.

## Commits

`scope: message` in lower-case English, e.g. `fix: keep panel docked after display change`.
Update `CHANGELOG.md` under an "Unreleased" heading for user-visible changes.
