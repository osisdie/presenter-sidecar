"""Panel -> mirror commands: whitelist, de-duplication and expiry on both ends (presenter_sidecar.commands)."""
import threading

from presenter_sidecar.commands import MIRROR_ACTIONS, QUEUE_TTL_SECS, CommandQueue, Inbox, accept


def test_accept_keeps_only_whitelisted_strings_once_in_order():
    assert MIRROR_ACTIONS == {"focus"}
    assert accept(["focus", "quit", "focus", 3, None, {"a": 1}, "FOCUS", " focus"]) == ["focus"]
    assert accept(("focus",)) == ["focus"]
    for bad in (None, "focus", {"focus": True}, 1, b"focus"):
        assert accept(bad) == []  # a bare string is not a list of actions


def test_queue_refuses_unknown_actions_and_never_duplicates():
    q = CommandQueue()
    assert q.push("quit", 0.0) is False and len(q) == 0
    assert q.push("focus", 0.0) and q.push("focus", 0.5)
    assert len(q) == 1
    assert q.take(1.0) == ["focus"]
    assert q.take(1.0) == [] and len(q) == 0  # handed out once


def test_queue_drops_actions_nobody_collected_in_time():
    q = CommandQueue()
    q.push("focus", 100.0)
    assert q.take(100.0 + QUEUE_TTL_SECS + 0.1) == []
    assert len(q) == 0  # expired entries are gone too
    q.push("focus", 100.0)
    q.push("focus", 108.0)  # a second click refreshes the time
    assert q.take(110.0) == ["focus"]


def test_reporter_inbox_takes_only_whitelisted_actions_from_replies():
    box = Inbox()
    assert box.add_reply({"ok": True, "do": ["focus", "quit", "focus"]}) == ["focus"]
    assert box.add_reply({"ok": True, "do": ["focus"]}) == ["focus"]
    for reply in ({}, {"ok": True}, {"do": "focus"}, {"do": None}, None, [], "focus", {"do": [["focus"]]}):
        assert box.add_reply(reply) == []
    assert box.pop() == ["focus"]  # not twice: one bring-to-front per batch
    assert box.pop() == []


def test_inbox_is_safe_between_the_reporter_thread_and_the_main_loop():
    box, got = Inbox(), []
    stop = threading.Event()

    def reporter():
        for _ in range(2000):
            box.add_reply({"do": ["focus"]})
        stop.set()

    th = threading.Thread(target=reporter)
    th.start()
    while not stop.is_set():
        got += box.pop()
    th.join()
    got += box.pop()
    assert got and set(got) == {"focus"}
