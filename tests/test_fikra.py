from mevzuat_tool.fikra import Bent, Fikra, parse_fikralar


def test_splits_paren_numbered_fikralar():
    body = "(1) Birinci fıkra. (2) İkinci fıkra."
    fs = parse_fikralar(body)
    assert [f.no for f in fs] == ["(1)", "(2)"]
    assert fs[0].text.startswith("(1) Birinci")


def test_no_paren_number_is_single_unnumbered_fikra():
    body = "Numarasız tek paragraf gövde."
    fs = parse_fikralar(body)
    assert len(fs) == 1
    assert fs[0].no is None
    assert fs[0].text == "Numarasız tek paragraf gövde."


def test_splits_letter_bentler_within_fikra():
    body = "Aşağıdakiler kazançtır:\na) birinci bent\nb) ikinci bent"
    f = parse_fikralar(body)[0]
    assert [b.isaret for b in f.bentler] == ["a)", "b)"]
    assert f.bentler[1].text == "b) ikinci bent"


def test_splits_numbered_bentler_within_fikra():
    body = "Şunlar:\n1. birinci\n2. ikinci\n3. üçüncü"
    f = parse_fikralar(body)[0]
    assert [b.isaret for b in f.bentler] == ["1.", "2.", "3."]


def test_bent_level_yurutluk():
    body = "Liste:\na) yürürlükteki bent\nb) (Mülga: 1/1/2020-1234 md.) kaldırılan bent"
    f = parse_fikralar(body)[0]
    assert f.bentler[0].yurutluk == "yürürlükte"
    assert f.bentler[1].yurutluk == "mülga"


def test_splits_inline_numbered_bentler_single_line():
    # normalize-sonrası: tek satırda boşlukla ayrık numaralı bentler
    body = "Şunlar gelirdir: 1. birinci gelir, 2. ikinci gelir, 3. üçüncü gelir."
    f = parse_fikralar(body)[0]
    assert [b.isaret for b in f.bentler] == ["1.", "2.", "3."]


def test_non_sequential_numbers_are_not_bentler():
    # '103.' gibi madde/yıl atıfları sıralı 1,2,3 koşusu oluşturmadığı için bent SAYILMAZ
    body = "103. maddede belirtilen oran ve 1985. yıldan beri uygulanan kural."
    f = parse_fikralar(body)[0]
    assert f.bentler == []


def test_splits_alt_bentler_within_bent():
    # Resmî hiyerarşi: madde → fıkra → bent → alt bent. Alt-bent işareti '1)' '2)' (parantez-rakam),
    # bent ('a)') içinde yer alır. Gerçek veri ([7528] M13): 'a) ... : 1) ... 2) ...'.
    body = "(1) Disiplin:\na) Çalışma usulü: 1) birinci alt bent 2) ikinci alt bent\nb) Karar şekli"
    f = parse_fikralar(body)[0]
    assert [b.isaret for b in f.bentler] == ["a)", "b)"]
    abent = f.bentler[0].alt_bentler
    assert [a.isaret for a in abent] == ["1)", "2)"]
    assert abent[0].text.startswith("1) birinci alt bent")


def test_bent_without_alt_bentler_has_empty_list():
    # Alt-bent içermeyen bent → alt_bentler boş liste (alan her zaman var).
    body = "Liste:\na) basit bent\nb) ikinci basit bent"
    f = parse_fikralar(body)[0]
    assert f.bentler[0].alt_bentler == []


def test_alt_bent_non_sequential_not_split():
    # Bent metnindeki '1) ... 5) ...' sıralı koşu değilse alt-bent SAYILMAZ (yıl/atıf gürültüsü).
    body = "a) 1) tek başına bir alt bent ama 7) atlamalı numara, alt-bent değil"
    f = parse_fikralar(body)[0]
    assert f.bentler[0].alt_bentler == []


def test_inline_paren_number_references_are_not_fikra():
    # A: cümle ortasında '(1), (2) ve (3) sayılı cetveller' fıkra DEĞİL — cetvel atfı.
    # Gerçek veri (5564 M3): tek hüküm, 3 fıkraya bölünmemeli.
    body = "(1) Toksik maddeler bu Kanunun eki (1), (2) ve (3) sayılı cetvellerde gösterilmiştir."
    fs = parse_fikralar(body)
    assert [f.no for f in fs] == ["(1)"]  # tek gerçek fıkra; (2),(3) cetvel atfı


def test_fikra_reference_within_sentence_not_split():
    # A: 'birinci fıkrasının (2), (3) numaralı bentleri' fıkra atfı — fıkra başı sanılmamalı.
    body = "(1) Birinci fıkra. Bu maddenin (2), (3) numaralı bentleri uygulanmaz."
    fs = parse_fikralar(body)
    assert [f.no for f in fs] == ["(1)"]


def test_real_fikra_after_sentence_end_is_kept():
    # A koruma: cümle-sonu ('. ') sonrası gelen sıralı '(n)' GERÇEK fıkra — kaçırılmamalı.
    body = "(1) Birinci fıkra hükmü. (2) İkinci fıkra hükmü. (3) Üçüncü fıkra hükmü."
    fs = parse_fikralar(body)
    assert [f.no for f in fs] == ["(1)", "(2)", "(3)"]
