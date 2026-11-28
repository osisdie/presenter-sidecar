import http.client
import json
import os
import threading

import pytest

import panel_server
from presenter_sidecar.config import ROOT
from presenter_sidecar.preview import PREVIEW_FILE


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


def _rewrite(path, cfg, bump):
    path.write_text(json.dumps(cfg), encoding="utf-8")
    st = path.stat()
    os.utime(path, (st.st_atime, st.st_mtime + bump))  # coarse mtime clocks: force a visible change


def test_notes_files_reload_without_restart(server, tmp_path):
    app, port = server
    cfg = json.loads(app.cfg_path.read_text(encoding="utf-8"))
    (tmp_path / "extra.md").write_text("# Extra\n## One\n", encoding="utf-8")
    cfg["notes_files"] = ["examples/notes/checklist.md", str(tmp_path / "extra.md")]
    _rewrite(app.cfg_path, cfg, 5)
    _, body = call(port, "GET", "/api/notes")
    assert [d["name"] for d in body["docs"]] == ["checklist.md", "extra.md"]

    cfg["notes_files"] = ["examples/notes/checklist.md"]
    cfg["pacing_file"] = ""
    _rewrite(app.cfg_path, cfg, 10)
    _, body = call(port, "GET", "/api/notes")
    assert [d["name"] for d in body["docs"]] == ["checklist.md"]
    assert call(port, "GET", "/api/pacing")[1]["stages"] == []


def test_broken_config_keeps_the_last_good_notes(server):
    app, port = server
    before = [d["name"] for d in call(port, "GET", "/api/notes")[1]["docs"]]
    app.cfg_path.write_text("{ not json", encoding="utf-8")
    st = app.cfg_path.stat()
    os.utime(app.cfg_path, (st.st_atime, st.st_mtime + 5))
    assert [d["name"] for d in call(port, "GET", "/api/notes")[1]["docs"]] == before


def test_state_passes_the_registered_hotkeys_through(server):
    # The ⌨ overlay lists what mirror.py registered at its start, not a later config.json edit.
    _, port = server
    status = {"fps": 25, "hotkeys": {"pick": "F7", "freeze": "F9"}, "hotkeys_failed": ["freeze"]}
    assert call(port, "POST", "/api/mirror", status, {"X-Panel": "1"})[0] == 200
    _, body = call(port, "GET", "/api/state")
    assert body["mirror"]["hotkeys"] == {"pick": "F7", "freeze": "F9"}
    assert body["mirror"]["hotkeys_failed"] == ["freeze"]


# ---------------------------------------------------------------- projector preview
@pytest.fixture()
def preview_server(tmp_path):
    cfg = json.loads((ROOT / "config.example.json").read_text(encoding="utf-8"))
    cfg["content_root"] = str(ROOT)
    p = tmp_path / "config.json"
    p.write_text(json.dumps(cfg), encoding="utf-8")
    logs = tmp_path / "logs"
    logs.mkdir()
    app = panel_server.App(p, logs=logs)
    srv = panel_server.make_server(app, "127.0.0.1", 0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield app, srv.server_address[1], logs / PREVIEW_FILE
    srv.shutdown()
    srv.server_close()


def raw_get(port, path, host=None):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    c.request("GET", path, headers={"Host": host or f"127.0.0.1:{port}"})
    r = c.getresponse()
    out = r.status, dict(r.getheaders()), r.read()
    c.close()
    return out


def test_preview_missing_is_404_and_not_cached(preview_server):
    _, port, _ = preview_server
    st, headers, body = raw_get(port, "/api/preview")
    assert st == 404 and headers["Cache-Control"] == "no-store" and json.loads(body)["error"]
    _, state = call(port, "GET", "/api/state")
    assert state["preview"] == {"available": False, "enabled": None, "age": None}


def test_preview_is_served_uncached_and_same_origin_only(preview_server):
    _, port, f = preview_server
    f.write_bytes(b"\xff\xd8fake-jpeg\xff\xd9")
    st, headers, body = raw_get(port, "/api/preview?t=123")  # cache-busting query is ignored
    assert st == 200 and body == b"\xff\xd8fake-jpeg\xff\xd9"
    assert headers["Content-Type"] == "image/jpeg" and headers["Cache-Control"] == "no-store"
    assert headers["Cross-Origin-Resource-Policy"] == "same-origin"
    assert headers["X-Content-Type-Options"] == "nosniff"


def test_preview_has_the_same_host_check(preview_server):
    _, port, f = preview_server
    f.write_bytes(b"x")
    assert raw_get(port, "/api/preview", host="evil.example:80")[0] == 403
    assert raw_get(port, "/api/preview", host=f"localhost:{port}")[0] == 200


def test_preview_age_comes_from_the_mirror_not_the_file_clock(preview_server):
    app, port, f = preview_server
    f.write_bytes(b"x")
    os.utime(f, (1, 1))  # a file mtime far in the past (or a skewed WSL clock) does not matter
    call(port, "POST", "/api/mirror", {"preview": {"enabled": True, "age": 1.5, "seq": 3}}, {"X-Panel": "1"})
    _, state = call(port, "GET", "/api/state")
    pv = state["preview"]
    assert pv["available"] is True and pv["enabled"] is True and 1.5 <= pv["age"] < 3


def test_preview_disabled_and_disconnected_mirror(preview_server):
    app, port, f = preview_server
    call(port, "POST", "/api/mirror", {"preview": {"enabled": False, "age": None, "seq": 0}}, {"X-Panel": "1"})
    assert call(port, "GET", "/api/state")[1]["preview"] == {"available": False, "enabled": False, "age": None}
    # Mirror gone (no status for > 4 s): the last file's mtime gives the age, enabled is unknown.
    f.write_bytes(b"x")
    os.utime(f, (os.path.getmtime(f) - 30,) * 2)
    with app.lock:
        app.mirror_ts -= 60
    pv = call(port, "GET", "/api/state")[1]["preview"]
    assert pv["available"] is True and pv["enabled"] is None and 29 <= pv["age"] < 40


def test_preview_from_an_older_mirror_without_the_field(preview_server):
    _, port, _ = preview_server
    call(port, "POST", "/api/mirror", {"fps": 25}, {"X-Panel": "1"})
    assert call(port, "GET", "/api/state")[1]["preview"] == {"available": False, "enabled": None, "age": None}


# ---------------------------------------------------------------- profiles
def test_config_lists_profiles_and_the_startup_profile(server):
    _, port = server
    _, body = call(port, "GET", "/api/config")
    assert body["profiles"] == ["talk", "meeting"] and body["profile_auto_switch"] is True
    # No --profile / PRESENTER_PROFILE / POST: no request id, so a server restart never overrides a hand pick.
    assert body["profile_req"] == {"name": "talk", "id": None}
    assert call(port, "GET", "/api/state")[1]["profiles"] == ["talk", "meeting"]


def test_notes_and_pacing_per_profile(server):
    _, port = server
    _, talk = call(port, "GET", "/api/pacing")
    _, meet = call(port, "GET", "/api/pacing?profile=meeting")
    assert talk["profile"] == "talk" and talk["stages"][0]["short"] == "Intro"
    assert meet["profile"] == "meeting" and [s["minutes"] for s in meet["stages"]] == [5, 15, 10, 5]
    _, notes = call(port, "GET", "/api/notes?profile=meeting")
    assert [d["name"] for d in notes["docs"]] == ["meeting.md"]
    _, unknown = call(port, "GET", "/api/notes?profile=nope")  # unknown: the startup profile
    assert unknown["profile"] == "talk" and len(unknown["docs"]) == 3


def test_auto_follow_finds_another_profiles_rule(server):
    app, port = server
    call(port, "POST", "/api/mirror", {"source_title": "Sprint board - Google Chrome"}, {"X-Panel": "1"})
    nt = call(port, "GET", "/api/state?profile=talk")[1]["notes_target"]
    assert nt["profile"] == "meeting" and nt["key"] == "Board walk"
    # The active profile's own rules come first.
    call(port, "POST", "/api/mirror", {"source_title": "Plant-care App · Q&A - Google Chrome"}, {"X-Panel": "1"})
    nt = call(port, "GET", "/api/state?profile=meeting")[1]["notes_target"]
    assert nt["profile"] == "talk" and nt["key"] == "Q&A"
    # No rule anywhere: no key, the active profile.
    call(port, "POST", "/api/mirror", {"source_title": "Something else"}, {"X-Panel": "1"})
    nt = call(port, "GET", "/api/state?profile=meeting")[1]["notes_target"]
    assert nt["key"] is None and nt["profile"] == "meeting"


def test_auto_switch_off_keeps_to_the_active_profile(server):
    app, port = server
    cfg = json.loads(app.cfg_path.read_text(encoding="utf-8"))
    cfg["profile_auto_switch"] = False
    _rewrite(app.cfg_path, cfg, 5)
    call(port, "POST", "/api/mirror", {"source_title": "Sprint board - Google Chrome"}, {"X-Panel": "1"})
    assert call(port, "GET", "/api/state?profile=talk")[1]["notes_target"]["key"] is None
    assert call(port, "GET", "/api/state?profile=meeting")[1]["notes_target"]["key"] == "Board walk"


def test_startup_profile_and_switch_request(tmp_path):
    cfg = json.loads((ROOT / "config.example.json").read_text(encoding="utf-8"))
    cfg["content_root"] = str(ROOT)
    p = tmp_path / "config.json"
    p.write_text(json.dumps(cfg), encoding="utf-8")
    app = panel_server.App(p, profile="meeting")  # --profile meeting
    srv = panel_server.make_server(app, "127.0.0.1", 0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_address[1]
    try:
        req = call(port, "GET", "/api/state")[1]["profile_req"]
        assert req["name"] == "meeting"
        assert [d["name"] for d in call(port, "GET", "/api/notes")[1]["docs"]] == ["meeting.md"]
        assert call(port, "POST", "/api/profile", {"name": "talk"})[0] == 403  # X-Panel needed
        st, body = call(port, "POST", "/api/profile", {"name": "nope"}, {"X-Panel": "1"})
        assert st == 400 and body["profiles"] == ["talk", "meeting"]
        st, body = call(port, "POST", "/api/profile", {"name": "talk"}, {"X-Panel": "1"})
        assert st == 200 and body["profile_req"]["name"] == "talk" and body["profile_req"]["id"] != req["id"]
    finally:
        srv.shutdown()
        srv.server_close()


def test_profile_comes_from_cli_then_env(monkeypatch, tmp_path):
    seen = {}

    class Stop(Exception):
        pass

    def fake_make_server(app, host=None, port=None):
        seen["profile"] = app.profile_asked
        raise Stop

    monkeypatch.setattr(panel_server, "make_server", fake_make_server)
    monkeypatch.setenv("PRESENTER_PROFILE", "meeting")
    with pytest.raises(Stop):
        panel_server.main([])
    assert seen["profile"] == "meeting"
    with pytest.raises(Stop):
        panel_server.main(["--profile", "talk"])
    assert seen["profile"] == "talk"


def test_cjk_profile_names_over_http_and_cli(tmp_path):
    # start.ps1 posts the name as UTF-8 bytes (Windows PowerShell 5.1 would send a string as ISO-8859-1).
    cfg = json.loads((ROOT / "config.example.json").read_text(encoding="utf-8"))
    cfg["content_root"] = str(ROOT)
    cfg["profiles"][0]["name"] = "會議"
    p = tmp_path / "config.json"
    p.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    app = panel_server.App(p, profile="會議")
    srv = panel_server.make_server(app, "127.0.0.1", 0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_address[1]
    try:
        req = call(port, "GET", "/api/config")[1]["profile_req"]
        assert req["name"] == "會議" and req["id"]
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        body = json.dumps({"name": "會議"}, ensure_ascii=False).encode("utf-8")
        c.request("POST", "/api/profile", body=body, headers={"Host": f"127.0.0.1:{port}", "X-Panel": "1",
                                                              "Content-Type": "application/json; charset=utf-8"})
        r = c.getresponse()
        out = json.loads(r.read())
        c.close()
        assert r.status == 200 and out["profile_req"]["name"] == "會議"
        latin1 = json.dumps({"name": "??"}).encode()  # what the old start.ps1 delivered
        assert call(port, "POST", "/api/profile", json.loads(latin1), {"X-Panel": "1"})[0] == 400
        _, notes = call(port, "GET", "/api/notes?profile=%E6%9C%83%E8%AD%B0")
        assert notes["profile"] == "會議" and notes["docs"][0]["name"] == "meeting.md"
    finally:
        srv.shutdown()
        srv.server_close()


def test_an_unknown_cli_profile_is_no_request(tmp_path):
    cfg = json.loads((ROOT / "config.example.json").read_text(encoding="utf-8"))
    p = tmp_path / "config.json"
    p.write_text(json.dumps(cfg), encoding="utf-8")
    assert panel_server.App(p, profile="nope").profile_request() == {"name": "talk", "id": None}
