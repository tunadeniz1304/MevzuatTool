from mevzuat_tool.html_split import split_html_articles


def test_splits_tag_embedded_madde_markers():
    # Madde işareti <span> içinde gömülü, en-dash ayraçlı (gerçek HTML deseni)
    html = (
        "<p><span>Madde 1 – (1) Birinci madde gövdesi.</span></p>"
        "<p><span>Madde 2 - (1) İkinci madde gövdesi.</span></p>"
    )
    parts = split_html_articles(html)
    assert set(parts.keys()) == {"1", "2"}
    assert "Birinci madde" in parts["1"]
    assert "İkinci madde" in parts["2"]
    assert "Madde 2" not in parts["1"]  # 1'in parçası 2'ye taşmaz


def test_handles_crlf_and_nested_tags():
    html = (
        "<p class=MsoNormal><span style='x'>Madde 5\r\n– (1) Beşinci.</span></p>"
        "<p><span>Madde 6 - (1) Altıncı.</span></p>"
    )
    parts = split_html_articles(html)
    assert set(parts.keys()) == {"5", "6"}


def test_no_madde_returns_empty():
    assert split_html_articles("<p>başlık metni, madde yok</p>") == {}
