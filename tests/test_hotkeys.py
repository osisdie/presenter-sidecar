import pytest

from presenter_sidecar.config import DEFAULT_HOTKEYS
from presenter_sidecar.hotkeys import MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, hotkey_table, parse_hotkey


def test_parse_function_keys_and_modifiers():
    assert parse_hotkey("F7") == (0, 0x76)
    assert parse_hotkey("Shift+F7") == (MOD_SHIFT, 0x76)
    assert parse_hotkey("F24") == (0, 0x87)
    assert parse_hotkey("ctrl + alt + q") == (MOD_CONTROL | MOD_ALT, ord("Q"))
    assert parse_hotkey("Ctrl+Alt+PgDn") == (MOD_CONTROL | MOD_ALT, 0x22)
    assert parse_hotkey("Ctrl+Alt+PageUp") == (MOD_CONTROL | MOD_ALT, 0x21)
    assert parse_hotkey("Win+Shift+5") == (MOD_WIN | MOD_SHIFT, ord("5"))


@pytest.mark.parametrize("bad", ["", "Hyper+F7", "Ctrl+", "Ctrl+Alt+Banana", "F25"])
def test_parse_rejects_unknown(bad):
    with pytest.raises(ValueError):
        parse_hotkey(bad)


def test_default_table_is_valid_and_unique():
    table = hotkey_table(DEFAULT_HOTKEYS)
    assert set(table) == set(DEFAULT_HOTKEYS)
    assert len(set(table.values())) == len(table)


def test_empty_spec_disables_and_duplicates_fail():
    assert "style" not in hotkey_table({"style": "", "pick": "F7"})
    with pytest.raises(ValueError):
        hotkey_table({"pick": "F7", "bring": "f7"})
