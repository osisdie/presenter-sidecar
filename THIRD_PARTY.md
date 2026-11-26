# Third-party software

presenter-sidecar itself is MIT-licensed (see `LICENSE`). It does **not** bundle or
redistribute any third-party code: the packages below are installed by the user with
`pip install -r requirements-windows.txt` and loaded at run time.

Versions are the pins in `requirements-windows.txt`; licences were checked against each
package's published metadata for that version.

| Package | Version | Licence | Used for |
|---|---|---|---|
| [mss](https://github.com/BoboTiG/python-mss) | 10.2.0 | MIT | Screen-copy fallback capture |
| [pygame-ce](https://github.com/pygame-community/pygame-ce) | 2.5.8 | LGPL-2.1 | Projector window, scaling, pointer drawing |
| [windows-capture](https://github.com/NiiightmareXD/windows-capture) | 2.0.1 | MIT | Windows Graphics Capture backend |
| [numpy](https://numpy.org) | 2.5.5 (2.2.x on Python 3.11) | BSD-3-Clause (bundled parts: 0BSD, MIT, Zlib, CC0-1.0) | Frame buffers (dependency of windows-capture) |
| [opencv-python](https://github.com/opencv/opencv-python) | 5.1.0.95 | Apache-2.0 (plus bundled third-party licences) | Imported by windows-capture |

Development only: [pytest](https://pytest.org) (MIT).

## About pygame-ce (LGPL-2.1)

pygame-ce is used as an unmodified, separately installed library that is imported
dynamically. That is compatible with distributing this project under MIT. If you ship
a frozen/bundled build (for example with PyInstaller) you must also meet the LGPL
terms for pygame-ce and SDL: include their licence texts and let users replace the
library (for example by keeping it as a separate, replaceable file).

## Runtime tools (not Python packages)

- **Google Chrome or Microsoft Edge**: hosts the panel as an `--app` window.
- **Claude Code CLI** (optional, only when `ai_helper.enabled` is true): used under its own
  terms; install and sign in separately.
