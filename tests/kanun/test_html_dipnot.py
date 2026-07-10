from kanun.html_dipnot import parse_anchors
from kanun.dipnot import Dipnot


def test_links_marker_to_definition():
    html = (
        # İşaret (gövdede): href=#_ftn1 name=_ftnref1
        "<p><span>Madde 1 - (1) Bu hüküm "
        "<a href=\"#_ftn1\" name=\"_ftnref1\"><span>[1]</span></a> ile değişti.</span></p>"
        # Tanım (kuyrukta): href=#_ftnref1 name=_ftn1 + metin
        "<div><a href=\"#_ftnref1\" name=\"_ftn1\"><span>[1]</span></a> "
        "9/4/2003-4842 sayılı Kanunla eklenmiştir.</div>"
    )
    result = parse_anchors(html)
    assert "1" in result
    assert len(result["1"]) == 1
    d = result["1"][0]
    assert isinstance(d, Dipnot)
    assert d.no == 1
    assert "4842 sayılı Kanunla" in d.text


def test_multiple_footnotes_in_one_madde():
    html = (
        "<p><span>Madde 2 - (1) Metin "
        "<a href=\"#_ftn5\" name=\"_ftnref5\">[5]</a> ve "
        "<a href=\"#_ftn6\" name=\"_ftnref6\">[6]</a>.</span></p>"
        "<div><a href=\"#_ftnref5\" name=\"_ftn5\">[5]</a> beşinci dipnot.</div>"
        "<div><a href=\"#_ftnref6\" name=\"_ftn6\">[6]</a> altıncı dipnot.</div>"
    )
    result = parse_anchors(html)
    assert [d.no for d in result["2"]] == [5, 6]


def test_marker_without_definition_skipped():
    html = (
        "<p><span>Madde 3 - (1) Eksik "
        "<a href=\"#_ftn9\" name=\"_ftnref9\">[9]</a> atıf.</span></p>"
    )  # tanım yok
    result = parse_anchors(html)
    assert result.get("3", []) == []
