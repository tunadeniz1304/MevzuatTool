"""İçeriksiz 'MADDE N ilâ M' aralık-madde tespiti (B — metrik dürüstlüğü).

Değişiklik-paketlerinde 'MADDE 1 ilâ 64 - İlgili Kanunlara işlenmiştir' / 'MADDE 9 ila 11 -
(... Kanunu ile ilgili olup yerine işlenmiştir)' gibi satırlar, N..M maddelerini TEK blokta
özetler — ayrı gövdeleri yoktur. Bedesten ağacı bunları ayrı sayar (gt'ye ekler) ama içerikte
yokturlar → yapay FN. Bu modül o aralıkları çıkarır; eval gerçek-kayıp dışı sayar.
"""
from mevzuat_tool.aralik import islenmis_aralik_maddeleri


def test_detects_ila_range_with_islenmistir():
    text = "MADDE 1 ilâ 64 - İlgili Kanunlara işlenmiştir. GEÇİCİ MADDE 1- (1) Devam."
    # 1..64 arası tüm madde no'ları içeriksiz-aralık sayılır.
    nums = islenmis_aralik_maddeleri(text)
    assert "1" in nums and "64" in nums and "32" in nums
    assert len(nums) == 64


def test_detects_ila_with_repeated_MADDE():
    text = "MADDE 1 ila MADDE 27- İlgili Kanunlara işlenmiştir."
    nums = islenmis_aralik_maddeleri(text)
    assert nums == {str(i) for i in range(1, 28)}


def test_detects_ila_followed_by_kunye():
    # 'MADDE 9 ila 11- (... yerine işlenmiştir)' — künyeli aralık da içeriksiz.
    text = "MADDE 9 ila 11- (26/9/2004 tarihli ve 5237 sayılı Türk Ceza Kanunu ile ilgili olup, yerine işlenmiştir)."
    nums = islenmis_aralik_maddeleri(text)
    assert nums == {"9", "10", "11"}


def test_ignores_normal_single_madde():
    # Tek madde (aralık değil) içeriksiz-aralık SAYILMAZ.
    text = "MADDE 5- (1) Bu Kanunun amacı şudur. MADDE 6- (1) Tanımlar."
    assert islenmis_aralik_maddeleri(text) == set()


def test_handles_both_ila_and_ilâ_spelling():
    assert islenmis_aralik_maddeleri("MADDE 2 ila 4- (x)") == {"2", "3", "4"}
    assert islenmis_aralik_maddeleri("MADDE 2 ilâ 4- (x)") == {"2", "3", "4"}
