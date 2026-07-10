from kanun.html_split import split_html_articles


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


def test_splits_prefixed_maddeler_with_canonical_keys():
    html = (
        "<p><span>Madde 28 - (1) Asıl madde.</span></p>"
        "<p><span>Mükerrer Madde 28 – (1) Mükerrer gövde.</span></p>"
        "<p><span>Geçici Madde 5 - (1) Geçici gövde.</span></p>"
        "<p><span>Ek Madde 2 – (1) Ek gövde.</span></p>"
    )
    parts = split_html_articles(html)
    assert set(parts.keys()) == {"28", "Mükerrer 28", "Geçici 5", "Ek 2"}
    assert "Asıl madde" in parts["28"]
    assert "Mükerrer gövde" in parts["Mükerrer 28"]
    assert "28" in parts and "Mükerrer 28" in parts  # no collision


def test_suffix_madde_still_works():
    html = "<p><span>Madde 257/A – (1) Suffix gövde.</span></p>"
    parts = split_html_articles(html)
    assert set(parts.keys()) == {"257/A"}


def test_splits_madde_with_anchor_footnote_before_dash():
    # Gerçek HTML (Gümrük): numara ile tire arasında <a> dipnot tag(ler)i.
    # 'Madde 15<a href="#_ftn14">[14]</a> - ...' → 15 yakalanır, tag/[n] tüketilir.
    html = (
        '<p><span>Madde 15<a href="#_ftn14">[14]</a><a href="#_ftn15">[15]</a> - '
        '(1) Gümrük vergileri.</span></p>'
        '<p><span>Madde 16 - (1) Diğer.</span></p>'
    )
    parts = split_html_articles(html)
    assert set(parts.keys()) == {"15", "16"}
    assert "Gümrük vergileri" in parts["15"]


def test_splits_tireless_madde_uppercase_in_html():
    # Gerçek HTML (Borçlar): tire YOK, numaradan sonra büyük-harf başlık.
    html = (
        "<p><span>MADDE 427 - (1) Önceki.</span></p>"
        "<p><span>MADDE 428 İşyerinin tamamı veya bir bölümü devri.</span></p>"
        "<p><span>MADDE 429 - (1) Sonraki.</span></p>"
    )
    parts = split_html_articles(html)
    assert set(parts.keys()) == {"427", "428", "429"}


def test_splits_tireless_madde_kunye_in_html():
    # Gerçek HTML (İş 87): tire YOK, numaradan sonra (Mülga künyesi.
    html = (
        "<p><span>Madde 86 - (1) Önceki.</span></p>"
        "<p><span>Madde 87 (Mülga: 20/6/2012-6331/37 md.) Gebe kadınlar.</span></p>"
        "<p><span>Madde 88 - (1) Sonraki.</span></p>"
    )
    parts = split_html_articles(html)
    assert set(parts.keys()) == {"86", "87", "88"}


def test_html_tireless_guard_rejects_lowercase_body_reference():
    # Yan-etki guard'ı: gövde-içi küçük-harf 'madde N' atfı madde SAYILMAMALI.
    html = "<p><span>Madde 1 - (1) Burada madde 10 hükmü ve madde 25 fıkrası uygulanır.</span></p>"
    parts = split_html_articles(html)
    assert set(parts.keys()) == {"1"}


def test_html_tireless_guard_rejects_mixedcase_uppercase_reference():
    # KRİTİK (review bulgusu): karışık 'Madde N <BÜYÜK>' gövde-içi ATIF madde SAYILMAMALI.
    # Tiresiz büyük-harf dalı YALNIZ tam-büyük 'MADDE' ile (chunker ile simetrik).
    html = (
        "<p><span>Madde 1 - (1) Bu husus Madde 32 Tebliğ hükümlerine tabidir; "
        "Madde 10 Anayasa'ya uygundur.</span></p>"
    )
    parts = split_html_articles(html)
    assert set(parts.keys()) == {"1"}


def test_html_dot_after_footnote_marker_still_splits():
    # Reviewer minor: 'Madde 61[3]. -' (numara + [n] + nokta + tire) — nokta-yeri simetrisi.
    html = '<p><span>Madde 61<a href="#_ftn3">[3]</a>. - (1) Hakim.</span></p>'
    parts = split_html_articles(html)
    assert set(parts.keys()) == {"61"}


def test_html_tireless_guard_rejects_allcaps_body_reference():
    # KRİTİK (2. review turu): tümü-büyük 'MADDE N KAPSAMINDA' gövde-içi ATIF madde SAYILMAMALI.
    # Tiresiz başlık title-case ('İşyerinin'); atıf all-caps → reddedilir (chunker ile simetrik).
    html = "<p><span>MADDE 1 - (1) BU MADDE 5 KAPSAMINDA değerlendirilir.</span></p>"
    parts = split_html_articles(html)
    assert set(parts.keys()) == {"1"}


def test_html_tireless_title_titlecase_still_splits():
    # Gerçek tiresiz başlık (Borçlar): tam-büyük MADDE + title-case kelime → yakalanır.
    html = (
        "<p><span>MADDE 428 İşyerinin tamamı devri.</span></p>"
        "<p><span>MADDE 429 - (1) Sonraki.</span></p>"
    )
    parts = split_html_articles(html)
    assert set(parts.keys()) == {"428", "429"}
