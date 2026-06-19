from mevzuat_tool.chunker import split_articles


def test_splits_on_madde_markers_case_insensitive():
    text = "Madde 1- (1) Birinci. MADDE 2- (1) İkinci. Madde 3 - (1) Üçüncü."
    arts = split_articles(text)
    assert [a.no for a in arts] == ["1", "2", "3"]
    assert arts[0].body.startswith("(1) Birinci")


def test_splits_fikralar_on_paren_numbers():
    from mevzuat_tool.chunker import split_fikralar
    body = "(1) Birinci fıkra. (2) İkinci fıkra."
    assert split_fikralar(body) == ["(1) Birinci fıkra.", "(2) İkinci fıkra."]
