"""presenter-sidecar: mirror one window to the projector, keep your notes private.

The modules in this package are pure Python (standard library only) so they can be
unit-tested on any OS. The Windows-only parts live in ``mirror.py`` at the repo root.
"""

__version__ = "0.1.0"

# Window titles that belong to the tool itself. They are never projected and the
# panel window is found by this title.
PANEL_TITLE = "Presenter Panel"
MIRROR_TITLE = "Presenter Mirror"
