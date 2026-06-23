from mevzuat_tool.normalize import normalize_text


def test_joins_wrapped_lines_and_unifies_dashes():
    raw = "Madde\n2 – (Değişik)\n\nMadde 3"
    assert normalize_text(raw) == "Madde 2 - (Değişik)\n\nMadde 3"


def test_strips_soft_hyphen():
    # Soft-hyphen (U+00AD) görünmez kelime-bölme ipucu; metinde anlamsız, tamamen kaldırılır.
    # Gerçek veri: Borçlar Madde 464 "464­- Malzeme" → "464- Malzeme" olmalı ki chunker kessin.
    raw = "MADDE 464­- Malzeme ve iş araçları"
    assert normalize_text(raw) == "MADDE 464- Malzeme ve iş araçları"
    assert "­" not in normalize_text(raw)
