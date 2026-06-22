from mevzuat_tool.chunker import split_articles


def test_splits_on_madde_markers_case_insensitive():
    text = "Madde 1- (1) Birinci. MADDE 2- (1) İkinci. Madde 3 - (1) Üçüncü."
    arts = split_articles(text)
    assert [a.no for a in arts] == ["1", "2", "3"]
    assert arts[0].body.startswith("(1) Birinci")


def test_splits_madde_with_dot_after_number():
    # Nadir dizgi varyantı: numaradan sonra nokta (TCK Madde 61. / 328.).
    text = "MADDE 61. - (1) Hakim. Madde 62- (1) Komşu. Madde 328. - (1) Devlet."
    arts = split_articles(text)
    assert [a.no for a in arts] == ["61", "62", "328"]
    assert arts[0].body.startswith("(1) Hakim")


def test_dot_tolerance_does_not_match_sentence_number_without_dash():
    # '5. fıkra' gibi tire'siz numara madde başlığı SAYILMAMALI (yan etki kontrolü).
    text = "Madde 10- (1) Bu konuda 5. fıkra hükmü uygulanır."
    arts = split_articles(text)
    assert [a.no for a in arts] == ["10"]


def test_splits_fikralar_on_paren_numbers():
    from mevzuat_tool.chunker import split_fikralar
    body = "(1) Birinci fıkra. (2) İkinci fıkra."
    assert split_fikralar(body) == ["(1) Birinci fıkra.", "(2) İkinci fıkra."]


def test_detects_mulga_else_yururlukte():
    from mevzuat_tool.chunker import extract_status
    assert extract_status("(Mülga: 1/1/2020-1234 md.) ...") == "mülga"
    assert extract_status("(Değişik: ...) hüküm") == "yürürlükte"
    assert extract_status("normal hüküm") == "yürürlükte"


def test_prefix_and_suffix_maddeler_get_unique_no():
    text = (
        "Madde 1- (1) Asıl. "
        "GEÇİCİ MADDE 1- (1) Geçici. "
        "Ek Madde 2- (1) Ek. "
        "Mükerrer Madde 257- (1) Mük. "
        "Madde 257/A- (1) Suffix."
    )
    nos = [a.no for a in split_articles(text)]
    assert nos == ["1", "Geçici 1", "Ek 2", "Mükerrer 257", "257/A"]
    assert len(nos) == len(set(nos))  # benzersiz, çakışma yok
