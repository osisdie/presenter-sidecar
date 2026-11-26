import json
import socket
import threading

import pytest

from presenter_sidecar import cdp


@pytest.mark.parametrize("url,ok", [
    ("http://127.0.0.1:9222", True), ("http://localhost:9222/json/list", True), ("http://[::1]:9222", True),
    ("http://127.8.8.8:9222", True), ("http://192.168.1.5:9222", False), ("http://example.com:9222", False),
    ("ws://10.0.0.1/devtools/page/x", False), ("not a url", False),
])
def test_loopback_only(url, ok):
    assert cdp.is_loopback_url(url) is ok


def test_fetch_tabs_refuses_remote_host():
    with pytest.raises(ValueError):
        cdp.fetch_tabs("http://203.0.113.9:9222")


def test_list_url():
    assert cdp.list_url("http://127.0.0.1:9222") == "http://127.0.0.1:9222/json/list"
    assert cdp.list_url("http://127.0.0.1:9222/") == "http://127.0.0.1:9222/json/list"
    assert cdp.list_url("http://127.0.0.1:9222/json/list") == "http://127.0.0.1:9222/json/list"


def test_accept_key_rfc6455_example():
    assert cdp.accept_key("dGhlIHNhbXBsZSBub25jZQ==") == "s3pPLMBiTxaQ9kYGzzhZRbK+xOo="


@pytest.mark.parametrize("size", [5, 125, 126, 70000])
def test_frame_roundtrip(size):
    text = "x" * size
    raw = cdp.encode_frame(text, mask=b"\x01\x02\x03\x04")
    op, fin, payload, used = cdp.decode_frame(raw)
    assert (op, fin, payload.decode(), used) == (1, True, text, len(raw))
    assert cdp.decode_frame(raw[:-1]) is None  # incomplete


def _server_frame(text: str) -> bytes:
    p = text.encode()
    head = bytes([0x81, len(p)]) if len(p) < 126 else bytes([0x81, 126]) + len(p).to_bytes(2, "big")
    return head + p


def test_tab_live_against_fake_devtools_target():
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]

    def serve():
        conn, _ = srv.accept()
        req = b""
        while b"\r\n\r\n" not in req:
            req += conn.recv(4096)
        key = [ln.split(":", 1)[1].strip() for ln in req.decode().split("\r\n") if ln.lower().startswith("sec-websocket-key")][0]
        conn.sendall(("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                      f"Sec-WebSocket-Accept: {cdp.accept_key(key)}\r\n\r\n").encode())
        buf = b""
        while cdp.decode_frame(buf) is None:
            buf += conn.recv(65536)
        _, _, payload, _ = cdp.decode_frame(buf)
        msg = json.loads(payload)
        assert msg["method"] == "Runtime.evaluate"
        value = json.dumps(["visible", True, "http://localhost:3000/#qa"])
        conn.sendall(_server_frame(json.dumps({"id": 99, "result": {}})))  # unrelated message first
        conn.sendall(_server_frame(json.dumps({"id": msg["id"], "result": {"result": {"value": value}}})))
        conn.recv(64)
        conn.close()

    th = threading.Thread(target=serve, daemon=True)
    th.start()
    tab = {"id": "t", "url": "http://localhost:3000/", "webSocketDebuggerUrl": f"ws://127.0.0.1:{port}/devtools/page/t"}
    assert cdp.tab_live(tab, timeout=2) == ("visible", True, "http://localhost:3000/#qa")
    th.join(2)
    srv.close()


def test_tab_live_falls_back_without_target():
    assert cdp.tab_live({"url": "http://a/"}) == ("unknown", False, "http://a/")
    remote = {"url": "http://a/", "webSocketDebuggerUrl": "ws://203.0.113.9:9222/devtools/page/x"}
    assert cdp.tab_live(remote) == ("unknown", False, "http://a/")
