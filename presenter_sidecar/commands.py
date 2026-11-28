"""Panel → mirror commands (pure; tested without Windows).

The panel cannot reach mirror.py directly. It posts an action to the panel server (``POST /api/focus``),
the server queues it, and mirror.py collects the queue in the reply to its next status report
(``POST /api/mirror`` → ``{"ok": true, "do": [...]}``, about once a second).

Only actions in :data:`MIRROR_ACTIONS` travel, each at most once per batch, in both directions: the server
refuses to queue anything else and the mirror ignores anything else in a reply. A queued action that no
mirror collects within :data:`QUEUE_TTL_SECS` is dropped, so a click made while the mirror is down does not
fire minutes later when it comes back. To add an action: add it here, queue it from a panel endpoint and
handle it in mirror.py's event loop.
"""
from __future__ import annotations

import threading

# focus: bring the projected window (the followed popup, else the source) to the front.
MIRROR_ACTIONS = frozenset({"focus"})
QUEUE_TTL_SECS = 5.0


def accept(actions) -> list[str]:
    """Whitelisted actions from untrusted input, first occurrence only, in order. Anything but a list is []."""
    out: list[str] = []
    if isinstance(actions, (list, tuple)):
        for a in actions:
            if isinstance(a, str) and a in MIRROR_ACTIONS and a not in out:
                out.append(a)
    return out


class CommandQueue:
    """Server side: actions waiting for the mirror's next report. Not locked: the caller holds its own lock."""

    def __init__(self, ttl: float = QUEUE_TTL_SECS):
        self.ttl = ttl
        self._items: dict[str, float] = {}  # action -> time of the last request (insertion order kept)

    def push(self, action: str, now: float) -> bool:
        """Queue ``action`` (again: refreshes its time, never a duplicate). False if it is not whitelisted."""
        if action not in MIRROR_ACTIONS:
            return False
        self._items[action] = now
        return True

    def take(self, now: float) -> list[str]:
        """Everything still fresh, once; the queue is empty afterwards."""
        got = [a for a, ts in self._items.items() if now - ts <= self.ttl]
        self._items = {}
        return got

    def __len__(self) -> int:
        return len(self._items)


class Inbox:
    """Mirror side: actions from the server's replies (reporter thread), popped by the main loop."""

    def __init__(self):
        self._lock = threading.Lock()
        self._items: list[str] = []

    def add_reply(self, reply) -> list[str]:
        """Keep the whitelisted actions of one ``/api/mirror`` reply; returns what was accepted."""
        got = accept(reply.get("do")) if isinstance(reply, dict) else []
        with self._lock:
            for a in got:
                if a not in self._items:
                    self._items.append(a)
        return got

    def pop(self) -> list[str]:
        with self._lock:
            got, self._items = self._items, []
        return got
