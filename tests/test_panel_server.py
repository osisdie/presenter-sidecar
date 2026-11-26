import http.client
import json
import threading

import pytest

import panel_server
from presenter_sidecar.config import ROOT


@pytest.fixture()
def server(tmp_path):
    cfg = json.loads((ROOT / "config.example.json").read_text(encoding="utf-8"))
    cfg["content_root"] = str(ROOT)
    p = tmp_path / "config.json"
    p.write_text(json.dumps(cfg), encoding="utf-8")
    app = panel_server.App(p)
    srv = panel_server.make_server(app, "127.0.0.1", 0)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    yield app, srv.server_address[1]
    srv.shutdown()
    srv.server_close()


def call(port, method, path, body=None, headers=None):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    h = {"Host": f"127.0.0.1:{port}"}
    h.update(headers or {})
    data = json.dumps(body).encode() if body is not None else None
    if data is not None:
        h["Content-Type"] = "application/json"
    c.request(method, path, body=data, headers=h)
    r = c.getresponse()
    raw = r.read()
    c.close()
    try:
        return r.status, json.loads(raw)
    except ValueError:
        return r.status, raw


def test_health_and_config(server):
    _, port = server
    st, body = call(port, "GET", "/api/health")
    assert st == 200 and body["ok"] is True and body["ai_helper"] is False
    st, body = call(port, "GET", "/api/config")
    assert body["ui_lang"] == "en" and body["hotkeys"]["pick"] == "F7" and body["cdp"] is False


def test_dns_rebinding_host_is_refused(server):
    _, port = server
    st, _ = call(port, "GET", "/api/health", headers={"Host": "evil.example:80"})
    assert st == 403


def test_post_requires_x_panel_header(server):
    _, port = server
    assert call(port, "POST", "/api/cmd", {"nav": 1})[0] == 403
    assert call(port, "POST", "/api/cmd", {"nav": 1}, {"X-Panel": "1"})[0] == 200


def test_notes_and_pacing(server):
    _, port = server
    _, body = call(port, "GET", "/api/notes")
    names = [d["name"] for d in body["docs"]]
    assert names == ["talk-notes.md", "talk-notes.zh-TW.md", "checklist.md"]
    _, body = call(port, "GET", "/api/pacing")
    assert [s["short"] for s in body["stages"]][:2] == ["Intro", "Demo A"]


def test_state_follows_projected_title(server):
    _, port = server
    call(port, "POST", "/api/mirror", {"source_title": "Plant-care App · Q&A - Google Chrome"}, {"X-Panel": "1"})
    call(port, "POST", "/api/cmd", {"nav": 5}, {"X-Panel": "1"})
    _, st = call(port, "GET", "/api/state")
    assert st["notes_target"]["key"] == "Q&A" and st["notes_target"]["by"] == "title"
    assert st["cmds"][-1]["nav"] == 1  # clamped


def test_ai_helper_disabled_by_default(server):
    _, port = server
    st, body = call(port, "POST", "/api/ask", {"q": "hello"}, {"X-Panel": "1"})
    assert st == 403 and "ai_helper" in body["error"]


def test_static_files_and_traversal(server):
    _, port = server
    st, raw = call(port, "GET", "/")
    assert st == 200 and b"<title>Presenter Panel</title>" in raw
    assert call(port, "GET", "/../config.example.json")[0] == 404
    assert call(port, "GET", "/%2e%2e/panel_server.py")[0] == 404


def test_claude_command_is_read_only():
    cmd = panel_server.claude_cmd("claude", {"model": "m", "extra_args": ["--x"]}, "sid")
    tools = cmd[cmd.index("--tools") + 1]
    assert tools == "Read,Grep,Glob"
    disallowed = cmd[cmd.index("--disallowedTools") + 1:]
    for t in ("Bash", "Edit", "Write", "WebFetch"):
        assert t in disallowed
    settings = json.loads(cmd[cmd.index("--settings") + 1])
    assert "Read(**/.env)" in settings["permissions"]["deny"]
    assert cmd[cmd.index("--permission-mode") + 1] == "dontAsk"
    assert cmd[-2:] == ["--resume", "sid"] and "--model" in cmd and "--x" in cmd
