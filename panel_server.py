#!/usr/bin/env python3
"""Local server for the private presenter panel. Standard library only; runs on Windows, WSL, Linux, macOS.

- GET  /                 panel web page (web/)
- GET  /api/health       health check
- GET  /api/config       UI settings (language, hotkeys, AI helper on/off)
- GET  /api/notes        speaker notes (only the files listed in notes_files)
- GET  /api/pacing       per-section minutes parsed from pacing_file
- GET  /api/state        mirror status + notes target + queued hotkey commands
- POST /api/mirror       mirror.py reports its status
- POST /api/cmd          mirror.py forwards notes paging hotkeys
- POST /api/panel        panel reports which section it shows
- POST /api/ask          ask the AI helper (streamed NDJSON; disabled by default)
- POST /api/cancel       stop the current answer
- POST /api/reset        start a new conversation
- POST /api/shutdown     stop the server (used by stop.ps1)

Binds to 127.0.0.1 only. POST requires the header ``X-Panel: 1`` (blocks cross-site form
posts) and every request must carry ``Host: 127.0.0.1`` or ``localhost`` (blocks DNS rebinding).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from presenter_sidecar import PANEL_TITLE, __version__, cdp
from presenter_sidecar.config import ROOT, config_path, content_root, load_config, resolve
from presenter_sidecar.i18n import t
from presenter_sidecar.notes import choose_active_tab, clean_title, notes_target, parse_pacing, projected_title

WEB = ROOT / "web"
LOGS = ROOT / "logs"
SESSION_FILE = LOGS / "claude_session.txt"
IS_WINDOWS = os.name == "nt"

DEFAULT_SYSTEM_PROMPT = """You are a live assistant for a presenter. Only the presenter sees your answers, in a side panel, while they are speaking.
Rules:
- Answer in the language of the question. Be short and actionable: one-line answer first, then at most 5 steps or points.
- Base answers on the files in the working directory and name the file you used. If you cannot find it, say so; do not invent facts or numbers.
- Never read, search for or reveal .env files, keys, passwords, tokens, certificates or *.local.md files. Refuse and explain why if asked.
- You can only read files. You cannot run commands or edit files; tell the presenter what to do instead."""

# Settings-level deny rules, enforced by the CLI before any tool runs.
DENY = [
    "Read(./.env)", "Read(./.env.*)", "Read(**/.env)", "Read(**/.env.*)",
    "Read(**/*.key)", "Read(**/*.pem)", "Read(**/*.pfx)", "Read(**/id_rsa*)", "Read(**/id_ed25519*)",
    "Read(**/.clasprc.json)", "Read(**/.clasp.json)", "Read(**/*.local.md)", "Read(**/.git/**)",
    "Read(**/config.json)", "Read(**/logs/**)",
    "Grep(**/.env*)", "Glob(**/.env*)",
    "Bash", "Edit", "Write", "NotebookEdit", "WebFetch", "WebSearch",
]
READ_TOOLS = ["Read", "Grep", "Glob"]
BLOCKED_TOOLS = ["Bash", "Edit", "Write", "NotebookEdit", "WebFetch", "WebSearch"]


def find_claude(bin_cfg: str = "") -> str:
    if bin_cfg:
        return str(Path(bin_cfg).expanduser())
    found = shutil.which("claude")
    if found:
        return found
    return str(Path.home() / ".local" / "bin" / ("claude.exe" if IS_WINDOWS else "claude"))


def claude_cmd(claude: str, ai: dict, session_id: str | None) -> list[str]:
    """Read-only, non-interactive Claude Code CLI invocation."""
    settings = {"permissions": {"deny": DENY, "defaultMode": "dontAsk"}}
    cmd = [
        claude, "-p",
        "--output-format", "stream-json", "--verbose", "--include-partial-messages",
        "--restricted", "--strict-mcp-config",
        "--tools", ",".join(READ_TOOLS),
        "--permission-mode", "dontAsk", "--permission-prompts", "none",
        "--settings", json.dumps(settings),
        "--append-system-prompt", ai.get("system_prompt") or DEFAULT_SYSTEM_PROMPT,
        "--allowedTools", *READ_TOOLS,
        "--disallowedTools", *BLOCKED_TOOLS,
    ]
    if ai.get("model"):
        cmd += ["--model", ai["model"]]
    cmd += [str(a) for a in (ai.get("extra_args") or [])]
    if session_id:
        cmd += ["--resume", session_id]
    return cmd


def kill_tree(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    try:
        if IS_WINDOWS:
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        else:
            os.killpg(proc.pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError, OSError):
        pass


# ---------------------------------------------------------------- application state
class App:
    def __init__(self, cfg_path: Path | None = None, root: Path = ROOT):
        self.root = root
        self.cfg_path = Path(cfg_path) if cfg_path else config_path(root)
        self.cfg = load_config(self.cfg_path, root)
        self.cfg_mtime = self._mtime()
        self.lock = threading.Lock()
        self.session_id: str | None = None
        self.proc: subprocess.Popen | None = None
        self.busy = False
        self.mirror: dict = {}
        self.mirror_ts = 0.0
        self.cmd_seq = 0
        self.cmds: list[dict] = []
        self.panel: dict = {}
        self._cdp = {"t": 0.0, "tabs": [], "err": None}
        self._live: dict[str, tuple[float, tuple[str, bool, str]]] = {}
        self._last_active: dict[str, str] = {}

    # ---- config (hot reload: notes rules, notes files and pacing change without a restart)
    def _mtime(self) -> float:
        try:
            return self.cfg_path.stat().st_mtime
        except OSError:
            return 0.0

    def live_cfg(self) -> dict:
        mt = self._mtime()
        if mt != self.cfg_mtime:
            try:
                self.cfg = load_config(self.cfg_path, self.root)
                self.cfg_mtime = mt
            except (OSError, ValueError):
                pass
        return self.cfg

    @property
    def lang(self) -> str:
        return self.cfg.get("ui_lang", "en")

    @property
    def ai(self) -> dict:
        return self.cfg.get("ai_helper") or {}

    def content_root(self) -> Path:
        return content_root(self.cfg)

    # ---- notes (the file list and pacing file reload live too: no restart after adding a notes file)
    def read_notes(self) -> list[dict]:
        cfg = self.live_cfg()
        base = content_root(cfg)
        out = []
        for rel in cfg.get("notes_files") or []:
            p = resolve(base, rel)
            try:
                out.append({"name": p.name, "path": rel, "text": p.read_text(encoding="utf-8")})
            except OSError as e:
                out.append({"name": p.name, "path": rel, "text": f"> Cannot read file: {e.strerror or e}"})
        return out

    def pacing(self) -> list[dict]:
        cfg = self.live_cfg()
        if not cfg.get("pacing_file"):
            return []
        try:
            return parse_pacing(resolve(content_root(cfg), cfg["pacing_file"]).read_text(encoding="utf-8"))
        except OSError:
            return []

    # ---- CDP (optional; titles only when cdp_url is empty)
    def cdp_tabs(self, url: str) -> list[dict]:
        now = time.time()
        ttl = 5.0 if self._cdp["err"] else 1.0
        if now - self._cdp["t"] < ttl:
            return self._cdp["tabs"]
        self._cdp["t"] = now
        try:
            self._cdp["tabs"], self._cdp["err"] = cdp.fetch_tabs(url), None
        except Exception as e:  # noqa: BLE001 - any failure means "titles only"
            self._cdp["tabs"], self._cdp["err"] = [], str(e)
        return self._cdp["tabs"]

    def tab_live(self, tab: dict) -> tuple[str, bool, str]:
        tid = tab.get("id", "")
        hit = self._live.get(tid)
        if hit and time.time() - hit[0] < 1.0:
            return hit[1]
        val = cdp.tab_live(tab)
        self._live[tid] = (time.time(), val)
        return val

    def notes_target(self, mirror: dict, age: float | None) -> dict | None:
        cfg = self.live_cfg()
        if not mirror or age is None or age > 4:
            return None
        title = clean_title(projected_title(mirror))
        if not title:
            return None
        url, tab_id = "", ""
        if cfg.get("cdp_url"):
            url, tab_id = choose_active_tab(self.cdp_tabs(cfg["cdp_url"]), title, self.tab_live, self._last_active)
        return notes_target(cfg.get("notes_rules") or [], title, url, tab_id, cfg.get("notes_follow_doc", ""))

    def web_version(self) -> str:
        try:
            return str(max(f.stat().st_mtime_ns for f in WEB.rglob("*") if f.is_file()))
        except ValueError:
            return "0"

    def kill_current(self) -> None:
        with self.lock:
            p = self.proc
        if p:
            kill_tree(p)


# ---------------------------------------------------------------- HTTP
CTYPES = {".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".svg": "image/svg+xml",
          ".png": "image/png", ".ico": "image/x-icon"}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"
    server_version = "presenter-sidecar"
    app: App  # set by make_server

    def log_message(self, fmt, *args):
        if "/api/state" in (str(args[0]) if args else "") or "/api/mirror" in (str(args[0]) if args else ""):
            return
        sys.stderr.write("%s %s\n" % (time.strftime("%H:%M:%S"), fmt % args))

    def _host_ok(self) -> bool:
        host = (self.headers.get("Host") or "").strip().lower()
        host = host.split("]")[0] + "]" if host.startswith("[") else host.split(":")[0]
        return host in ("127.0.0.1", "localhost", "[::1]")

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0 or n > 64_000:
            return {}
        try:
            data = json.loads(self.rfile.read(n) or b"{}")
            return data if isinstance(data, dict) else {}
        except ValueError:
            return {}

    def do_GET(self):
        app = self.app
        if not self._host_ok():
            return self._json({"error": "bad host"}, 403)
        path = self.path.split("?")[0]
        if path == "/api/health":
            return self._json({"ok": True, "version": __version__, "ai_helper": bool(app.ai.get("enabled"))})
        if path == "/api/config":
            cfg = app.live_cfg()
            return self._json({"ui_lang": cfg.get("ui_lang", "en"), "hotkeys": cfg.get("hotkeys", {}),
                               "ai_helper": bool(app.ai.get("enabled")), "panel_title": PANEL_TITLE,
                               "cdp": bool(cfg.get("cdp_url")), "version": __version__})
        if path == "/api/notes":
            return self._json({"docs": app.read_notes()})
        if path == "/api/pacing":
            return self._json({"stages": app.pacing()})
        if path == "/api/state":
            with app.lock:
                age = time.time() - app.mirror_ts if app.mirror_ts else None
                mirror = app.mirror
                busy, sess, cmds, panel = app.busy, bool(app.session_id), app.cmds[-20:], app.panel
            cfg = app.live_cfg()
            return self._json({"mirror": mirror, "mirror_age": age, "cmds": cmds, "busy": busy, "session": sess,
                               "notes_target": app.notes_target(mirror, age),
                               "notes_auto_follow_default": bool(cfg.get("notes_auto_follow", True)),
                               "web_version": app.web_version(), "panel": panel})
        rel = "index.html" if path in ("/", "") else path.lstrip("/")
        f = (WEB / rel).resolve()
        if WEB.resolve() not in f.parents or not f.is_file():
            return self._json({"error": "not found"}, 404)
        ctype = CTYPES.get(f.suffix, "application/octet-stream")
        data = f.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype + ("; charset=utf-8" if ctype.startswith("text") else ""))
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        app = self.app
        if not self._host_ok() or self.headers.get("X-Panel") != "1":
            return self._json({"error": "forbidden"}, 403)
        path = self.path.split("?")[0]
        body = self._body()
        if path == "/api/mirror":
            with app.lock:
                app.mirror, app.mirror_ts = body, time.time()
            return self._json({"ok": True})
        if path == "/api/panel":
            with app.lock:
                app.panel = {**body, "ts": time.time()}
            return self._json({"ok": True})
        if path == "/api/cmd":
            try:
                nav = int(body.get("nav", 0))
            except (TypeError, ValueError):
                nav = 0
            with app.lock:
                app.cmd_seq += 1
                app.cmds.append({"seq": app.cmd_seq, "nav": max(-1, min(1, nav))})
                app.cmds = app.cmds[-50:]
            return self._json({"ok": True})
        if path == "/api/reset":
            with app.lock:
                app.session_id = None
            SESSION_FILE.unlink(missing_ok=True)
            return self._json({"ok": True})
        if path == "/api/cancel":
            app.kill_current()
            return self._json({"ok": True})
        if path == "/api/shutdown":
            self._json({"ok": True})
            threading.Thread(target=lambda: (app.kill_current(), self.server.shutdown()), daemon=True).start()
            return
        if path == "/api/ask":
            return self._ask(str(body.get("q", "")).strip(), str(body.get("context", ""))[:300])
        return self._json({"error": "not found"}, 404)

    # -------------------------------------------------- AI helper (streamed)
    def _ask(self, q: str, context: str):
        app = self.app
        lang = app.lang
        ai = app.ai
        if not ai.get("enabled"):
            return self._json({"error": t(lang, "ai.disabled")}, 403)
        if not q:
            return self._json({"error": "empty"}, 400)
        with app.lock:
            if app.busy:
                return self._json({"error": t(lang, "ai.busy")}, 409)
            app.busy = True
            sid = app.session_id
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

        def emit(obj):
            try:
                self.wfile.write((json.dumps(obj, ensure_ascii=False) + "\n").encode())
                self.wfile.flush()
            except OSError:
                pass

        timeout = int(ai.get("timeout_sec") or 180)
        prompt = (t(lang, "ai.context", context=context) + "\n" if context else "") + q
        workdir = resolve(app.content_root(), ai.get("workdir") or ".")
        t0 = time.time()
        timed_out = threading.Event()
        popen_kw: dict = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if IS_WINDOWS \
            else {"start_new_session": True}
        try:
            proc = subprocess.Popen(
                claude_cmd(find_claude(ai.get("claude_bin", "")), ai, sid), cwd=str(workdir),
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding="utf-8", errors="replace", **popen_kw)
        except OSError as e:
            with app.lock:
                app.busy = False
            emit({"t": "error", "msg": t(lang, "ai.start_failed", err=e)})
            return
        with app.lock:
            app.proc = proc

        def killer():
            try:
                proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out.set()
                kill_tree(proc)

        threading.Thread(target=killer, daemon=True).start()
        emit({"t": "status", "msg": t(lang, "ai.sent"), "resume": bool(sid)})
        try:
            proc.stdin.write(prompt)
            proc.stdin.close()
        except OSError:
            pass

        stderr_buf: list[str] = []
        threading.Thread(target=lambda: stderr_buf.append(proc.stderr.read() if proc.stderr else ""),
                         daemon=True).start()
        final_text, got_delta, new_sid = "", False, sid
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            typ = ev.get("type")
            if typ == "system" and ev.get("subtype") == "init":
                new_sid = ev.get("session_id") or new_sid
            elif typ == "stream_event":
                e = ev.get("event", {})
                if e.get("type") == "content_block_delta" and e.get("delta", {}).get("type") == "text_delta":
                    got_delta = True
                    emit({"t": "delta", "text": e["delta"]["text"]})
                elif e.get("type") == "message_start":
                    emit({"t": "turn"})
            elif typ == "assistant":
                for block in ev.get("message", {}).get("content", []):
                    if block.get("type") == "tool_use":
                        inp = block.get("input", {})
                        target = inp.get("file_path") or inp.get("pattern") or inp.get("path") or ""
                        try:
                            target = os.path.relpath(str(target), str(workdir)) if os.path.isabs(str(target)) else target
                        except ValueError:
                            pass
                        emit({"t": "tool", "name": block.get("name"), "target": str(target)[:160]})
            elif typ == "user":
                for block in ev.get("message", {}).get("content", []) or []:
                    if isinstance(block, dict) and block.get("type") == "tool_result" and block.get("is_error"):
                        c = block.get("content")
                        msg = c if isinstance(c, str) else json.dumps(c, ensure_ascii=False)
                        emit({"t": "tool_denied", "msg": msg[:200]})
            elif typ == "result":
                final_text = ev.get("result") or ""
                new_sid = ev.get("session_id") or new_sid
                emit({"t": "done", "text": final_text, "streamed": got_delta,
                      "secs": round(time.time() - t0, 1),
                      "cost": ev.get("total_cost_usd"), "is_error": ev.get("is_error", False)})
        proc.wait()
        time.sleep(0.05)
        err = "".join(stderr_buf)
        with app.lock:
            app.busy, app.proc = False, None
            if new_sid and proc.returncode == 0:
                app.session_id = new_sid
                try:
                    SESSION_FILE.write_text(new_sid)
                except OSError:
                    pass
        if timed_out.is_set():
            emit({"t": "error", "msg": t(lang, "ai.timeout", secs=timeout)})
        elif proc.returncode not in (0, None) and not final_text:
            emit({"t": "error", "msg": t(lang, "ai.exit", code=proc.returncode, err=err.strip()[-400:])})


def make_server(app: App, host: str | None = None, port: int | None = None) -> ThreadingHTTPServer:
    handler = type("BoundHandler", (Handler,), {"app": app})
    srv = ThreadingHTTPServer((host or app.cfg.get("panel_host", "127.0.0.1"),
                               int(app.cfg.get("panel_port", 8765)) if port is None else port), handler)
    srv.daemon_threads = True
    return srv


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", help="config file (default: config.json, else config.example.json)")
    ap.add_argument("--port", type=int, help="override panel_port")
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    app = App(Path(args.config) if args.config else None)
    host = app.cfg.get("panel_host", "127.0.0.1")
    if host not in ("127.0.0.1", "localhost", "::1"):
        sys.exit("panel_host must be a loopback address (127.0.0.1)")
    srv = make_server(app, port=args.port)
    LOGS.mkdir(exist_ok=True)
    (LOGS / "panel_server.pid").write_text(str(os.getpid()))
    if SESSION_FILE.exists():  # keep the same AI conversation across restarts
        app.session_id = SESSION_FILE.read_text().strip() or None
    print(f"panel server {__version__} on http://{host}:{srv.server_address[1]}  config={app.cfg_path.name}  "
          f"ai_helper={'on' if app.ai.get('enabled') else 'off'}", flush=True)
    try:
        srv.serve_forever()
    finally:
        app.kill_current()
        (LOGS / "panel_server.pid").unlink(missing_ok=True)


if __name__ == "__main__":
    main()
