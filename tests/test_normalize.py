from mevzuat_tool.normalize import normalize_text


def test_joins_wrapped_lines_and_unifies_dashes():
    raw = "Madde\n2 – (Değişik)\n\nMadde 3"
    assert normalize_text(raw) == "Madde 2 - (Değişik)\n\nMadde 3"
