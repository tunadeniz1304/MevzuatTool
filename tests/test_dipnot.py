from mevzuat_tool.dipnot import Dipnot, split_dipnot_apendiksi, baglanan_dipnotlar


def test_splits_trailing_footnote_block_of_three_or_more():
    body = (
        "Madde gövdesi burada biter.\n"
        "[1] 9/4/2003-4842 sayılı Kanunla eklenmiştir.\n"
        "[2] 22/7/1998-4369 sayılı Kanunla değiştirilmiştir.\n"
        "[3] İptal: Anayasa Mahkemesi kararı.\n"
    )
    clean, dipnotlar = split_dipnot_apendiksi(body)
    assert clean == "Madde gövdesi burada biter."
    assert [d.no for d in dipnotlar] == [1, 2, 3]
    assert dipnotlar[0].text == "9/4/2003-4842 sayılı Kanunla eklenmiştir."
    assert dipnotlar[2].text == "İptal: Anayasa Mahkemesi kararı."


def test_below_threshold_is_noop():
    body = "Gövde metni. [5] tek referans satırı.\n[6] ikinci satır."
    clean, dipnotlar = split_dipnot_apendiksi(body)
    assert clean == body
    assert dipnotlar == []


def test_no_footnotes_returns_body_unchanged():
    body = "Sıradan madde gövdesi, dipnot yok."
    clean, dipnotlar = split_dipnot_apendiksi(body)
    assert clean == body
    assert dipnotlar == []


def test_links_inline_markers_to_footnotes():
    tum = [Dipnot(1, "birinci"), Dipnot(2, "ikinci"), Dipnot(3, "üçüncü")]
    body = "Bu hüküm [2] ve ayrıca [3] ile değişti."
    bagli = baglanan_dipnotlar(body, tum)
    assert [d.no for d in bagli] == [2, 3]


def test_unmatched_marker_is_skipped():
    tum = [Dipnot(1, "birinci")]
    body = "Atıf [9] global listede yok."
    assert baglanan_dipnotlar(body, tum) == []


def test_duplicate_markers_dedup_keep_order():
    tum = [Dipnot(5, "beş"), Dipnot(7, "yedi")]
    body = "[7] sonra yine [7] ve [5]."
    bagli = baglanan_dipnotlar(body, tum)
    assert [d.no for d in bagli] == [7, 5]


def test_splits_inline_single_line_appendix():
    # normalize sonrası gerçek senaryo: tek satırda boşlukla ayrık [n] entry'leri
    body = "Madde gövdesi biter. [1] birinci tanım. [2] ikinci tanım. [3] üçüncü tanım."
    clean, dipnotlar = split_dipnot_apendiksi(body)
    assert clean == "Madde gövdesi biter."
    assert [d.no for d in dipnotlar] == [1, 2, 3]
    assert dipnotlar[1].text == "ikinci tanım."
