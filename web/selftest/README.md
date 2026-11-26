# Self-test pages

Open these from the panel server (for example `http://127.0.0.1:8765/selftest/source.html`).

| Page | What to check |
|---|---|
| `source.html` | Pick it as the source (F7). Green top-left and blue bottom-right quarters must appear on the projector, letterboxed, with the pointer ring. |
| `cover.html` | Drag it over the source window. The projector must still show `source.html` (WGC / PrintWindow) and never the magenta page. |
| `source.html?popup=3000&life=8000` | Opens `popup.html` after 3 s and closes it after 8 s. The projector follows the popup, then returns to the source. Start the browser with `--disable-popup-blocking` or click to allow popups. |
