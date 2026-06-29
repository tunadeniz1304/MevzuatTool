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


def test_detects_grouped_tire_chain():
    # 'MADDE 9- 10- 11- (... yerine işlenmiştir)' — gruplu blok; ikincil no'lar içeriksiz.
    # Gerçek-veri kanıtı: ikincil no'ların gövdesi YOK (split_articles yakalamaz).
    text = "MADDE 9- 10- 11- (26/9/2004 tarihli ve 5237 sayılı Türk Ceza Kanunu ile ilgili olup yerine işlenmiştir)."
    nums = islenmis_aralik_maddeleri(text)
    assert nums == {"9", "10", "11"}


def test_detects_grouped_tire_irregular_spacing():
    # Gerçek-veri varyantı: 'MADDE 12- 13- 14- 15-16- 17-' (düzensiz boşluk/bitişik).
    text = "MADDE 12- 13- 14- 15-16- 17- 18- (4/12/2004 tarihli ve 5271 sayılı Kanun ile ilgili)."
    nums = islenmis_aralik_maddeleri(text)
    assert {"12", "13", "14", "15", "16", "17", "18"} <= nums


def test_detects_ve_conjunction():
    # 'MADDE 31 ve 32- (... işlenmiştir)' — iki madde 've' ile gruplanmış.
    text = "MADDE 31 ve 32- (13/12/1983 tarihli ve 190 sayılı Kanun ile ilgili olup yerine işlenmiştir)."
    nums = islenmis_aralik_maddeleri(text)
    assert nums == {"31", "32"}


def test_grouped_does_not_catch_single_madde_with_fikra():
    # KRİTİK guard: 'MADDE 5- (1) ... (2) ...' tek madde + fıkra → aralık DEĞİL.
    # Fıkra '(1)' parantezli; gruplu-tire 'N- M-' biçimi parantezsiz ardışık sayı ister.
    text = "MADDE 5- (1) Birinci fıkra. (2) İkinci fıkra. MADDE 6- (1) Sonraki."
    assert islenmis_aralik_maddeleri(text) == set()
