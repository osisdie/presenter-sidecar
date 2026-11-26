"""Read-only Chrome DevTools Protocol helpers, standard library only.

Used to read the URL (including ``#hash``) of the projected tab. Only loopback
endpoints are accepted: a DevTools port gives full control of the browser, so the
tool refuses to talk to one on another host.
"""
from __future__ import annotations

import base64
import hashlib
import ipaddress
import json
import os
import socket
import struct
import time
import urllib.request
from urllib.parse import urlsplit

WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
LIVE_EXPR = "JSON.stringify([document.visibilityState, document.hasFocus(), location.href])"


def is_loopback_url(url: str) -> bool:
    try:
        host = urlsplit(url).hostname or ""
    except ValueError:
        return False
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def list_url(cdp_url: str) -> str:
    """``http://127.0.0.1:9222`` → ``http://127.0.0.1:9222/json/list`` (full URLs pass through)."""
    u = cdp_url.rstrip("/")
    return u if u.endswith("/json/list") or u.endswith("/json") else u + "/json/list"


def fetch_tabs(cdp_url: str, timeout: float = 0.6) -> list[dict]:
    if not is_loopback_url(cdp_url):
        raise ValueError("cdp_url must point to localhost / 127.0.0.1")
    with urllib.request.urlopen(list_url(cdp_url), timeout=timeout) as r:
        return [t for t in json.loads(r.read()) if t.get("type") == "page"]


# ---------------------------------------------------------------- minimal WebSocket client
def accept_key(key: str) -> str:
    return base64.b64encode(hashlib.sha1((key + WS_GUID).encode()).digest()).decode()


def encode_frame(text: str, mask: bytes | None = None) -> bytes:
    """A single masked text frame (clients must mask)."""
    payload = text.encode("utf-8")
    mask = mask if mask is not None else os.urandom(4)
    n = len(payload)
    head = bytearray([0x81])
    if n < 126:
        head.append(0x80 | n)
    elif n < 1 << 16:
        head.append(0x80 | 126)
        head += struct.pack("!H", n)
    else:
        head.append(0x80 | 127)
        head += struct.pack("!Q", n)
    masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    return bytes(head) + mask + masked


def decode_frame(buf: bytes) -> tuple[int, bool, bytes, int] | None:
    """Parse one frame from ``buf``. Returns ``(opcode, fin, payload, consumed)`` or ``None`` if incomplete."""
    if len(buf) < 2:
        return None
    b0, b1 = buf[0], buf[1]
    n, pos = b1 & 0x7F, 2
    if n == 126:
        if len(buf) < 4:
            return None
        n, pos = struct.unpack("!H", buf[2:4])[0], 4
    elif n == 127:
        if len(buf) < 10:
            return None
        n, pos = struct.unpack("!Q", buf[2:10])[0], 10
    mask = None
    if b1 & 0x80:
        if len(buf) < pos + 4:
            return None
        mask, pos = buf[pos:pos + 4], pos + 4
    if len(buf) < pos + n:
        return None
    payload = buf[pos:pos + n]
    if mask:
        payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    return b0 & 0x0F, bool(b0 & 0x80), payload, pos + n


class WebSocket:
    """Just enough RFC 6455 for one request/response with a local DevTools target."""

    def __init__(self, url: str, timeout: float = 0.8, max_size: int = 1 << 20):
        u = urlsplit(url)
        if u.scheme != "ws" or not is_loopback_url(url):
            raise ValueError("only ws:// loopback URLs are allowed")
        self.max_size = max_size
        self.sock = socket.create_connection((u.hostname, u.port or 80), timeout=timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        path = (u.path or "/") + (f"?{u.query}" if u.query else "")
        req = (f"GET {path} HTTP/1.1\r\nHost: {u.hostname}:{u.port or 80}\r\n"
               "Upgrade: websocket\r\nConnection: Upgrade\r\n"
               f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n")
        self.sock.sendall(req.encode())
        resp = b""
        while b"\r\n\r\n" not in resp:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("handshake closed")
            resp += chunk
            if len(resp) > 16384:
                raise ConnectionError("handshake too large")
        head, self.buf = resp.split(b"\r\n\r\n", 1)
        lines = head.decode("latin-1").split("\r\n")
        if " 101 " not in lines[0] + " ":
            raise ConnectionError(f"handshake failed: {lines[0]}")
        hdrs = {k.strip().lower(): v.strip() for k, v in (ln.split(":", 1) for ln in lines[1:] if ":" in ln)}
        if hdrs.get("sec-websocket-accept") != accept_key(key):
            raise ConnectionError("bad Sec-WebSocket-Accept")

    def send(self, text: str) -> None:
        self.sock.sendall(encode_frame(text))

    def recv(self, timeout: float = 0.8) -> str:
        deadline = time.time() + timeout
        parts: list[bytes] = []
        while True:
            fr = decode_frame(self.buf)
            if fr is None:
                left = deadline - time.time()
                if left <= 0:
                    raise TimeoutError("websocket recv timeout")
                self.sock.settimeout(left)
                chunk = self.sock.recv(65536)
                if not chunk:
                    raise ConnectionError("websocket closed")
                self.buf += chunk
                if len(self.buf) > self.max_size + 16:
                    raise ConnectionError("websocket message too large")
                continue
            op, fin, payload, used = fr
            self.buf = self.buf[used:]
            if op == 0x8:
                raise ConnectionError("websocket closed by peer")
            if op in (0x9, 0xA):  # ping / pong: ignore
                continue
            parts.append(payload)
            if fin:
                return b"".join(parts).decode("utf-8", "replace")

    def close(self) -> None:
        try:
            self.sock.sendall(bytes([0x88, 0x80]) + os.urandom(4))
        except OSError:
            pass
        self.sock.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def tab_live(tab: dict, timeout: float = 0.8) -> tuple[str, bool, str]:
    """Ask a tab for ``(visibilityState, hasFocus, href)``. Falls back to ``("unknown", False, tab.url)``."""
    val = ("unknown", False, tab.get("url", ""))
    ws_url = tab.get("webSocketDebuggerUrl")
    if not ws_url:
        return val
    try:
        with WebSocket(ws_url, timeout=timeout) as ws:
            ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                                "params": {"expression": LIVE_EXPR, "returnByValue": True}}))
            deadline = time.time() + timeout
            while time.time() < deadline:
                m = json.loads(ws.recv(timeout=max(0.05, deadline - time.time())))
                if m.get("id") == 1:
                    v = json.loads(m.get("result", {}).get("result", {}).get("value") or "null")
                    if v:
                        val = (v[0], bool(v[1]), v[2] or val[2])
                    break
    except (OSError, ValueError, TimeoutError, ConnectionError):
        pass
    return val
