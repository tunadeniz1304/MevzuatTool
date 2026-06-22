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
