from mevzuat_tool.dipnot import Dipnot, split_dipnot_apendiksi


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
