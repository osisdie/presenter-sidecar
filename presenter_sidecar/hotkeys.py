"""Parse hotkey strings such as ``"Ctrl+Alt+PgDn"`` into Win32 ``RegisterHotKey`` arguments."""
from __future__ import annotations

MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN = 0x1, 0x2, 0x4, 0x8

MODIFIERS = {
    "ctrl": MOD_CONTROL, "control": MOD_CONTROL,
    "alt": MOD_ALT,
    "shift": MOD_SHIFT,
    "win": MOD_WIN, "super": MOD_WIN,
}

NAMED_KEYS = {
    "pgup": 0x21, "pageup": 0x21, "prior": 0x21,
    "pgdn": 0x22, "pagedown": 0x22, "next": 0x22,
    "end": 0x23, "home": 0x24,
    "left": 0x25, "up": 0x26, "right": 0x27, "down": 0x28,
    "insert": 0x2D, "ins": 0x2D, "delete": 0x2E, "del": 0x2E,
    "space": 0x20, "pause": 0x13, "scrolllock": 0x91,
}
for _i in range(1, 25):
    NAMED_KEYS[f"f{_i}"] = 0x6F + _i  # F1 = 0x70


def parse_hotkey(spec: str) -> tuple[int, int]:
    """``"Shift+F7"`` → ``(MOD_SHIFT, 0x76)``. Raises ``ValueError`` on unknown keys."""
    parts = [p.strip() for p in str(spec).split("+") if p.strip()]
    if not parts:
        raise ValueError(f"empty hotkey: {spec!r}")
    mods = 0
    for p in parts[:-1]:
        m = MODIFIERS.get(p.lower())
        if m is None:
            raise ValueError(f"unknown modifier {p!r} in {spec!r}")
        mods |= m
    key = parts[-1].lower()
    if key in NAMED_KEYS:
        return mods, NAMED_KEYS[key]
    if len(key) == 1 and (key.isascii() and key.isalnum()):
        return mods, ord(key.upper())
    raise ValueError(f"unknown key {parts[-1]!r} in {spec!r}")


def hotkey_table(mapping: dict[str, str]) -> dict[str, tuple[int, int]]:
    """Parse a ``{action: spec}`` map. Empty spec disables an action. Raises on duplicates."""
    out: dict[str, tuple[int, int]] = {}
    used: dict[tuple[int, int], str] = {}
    for action, spec in mapping.items():
        if not spec:
            continue
        combo = parse_hotkey(spec)
        if combo in used:
            raise ValueError(f"hotkey {spec!r} is used by both {used[combo]!r} and {action!r}")
        used[combo] = action
        out[action] = combo
    return out
