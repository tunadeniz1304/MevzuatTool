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


def test_unifies_minus_sign_marker():
    # Gerçek veri: [6223] kanunu madde markerini U+2212 (MINUS SIGN) ile yazıyor: "MADDE 1 − (1)".
    # Bu normal hyphen'e (U+002D) çevrilmeli, yoksa chunker maddeyi tanıyamaz (0 parça → çöküş).
    raw = "MADDE 1 − (1) Bu Kanunun amacı"
    assert normalize_text(raw) == "MADDE 1 - (1) Bu Kanunun amacı"
    assert "−" not in normalize_text(raw)


def test_unifies_other_dash_variants():
    # Diğer tire-varyantları da normal hyphen'e: U+2010 hyphen, U+2011 non-breaking hyphen,
    # U+2015 horizontal bar. (Türk mevzuat metinlerinde madde markerinde görülebilir.)
    assert normalize_text("MADDE 2 ‐ metin") == "MADDE 2 - metin"
    assert normalize_text("MADDE 3 ‑ metin") == "MADDE 3 - metin"
    assert normalize_text("MADDE 4 ― metin") == "MADDE 4 - metin"
