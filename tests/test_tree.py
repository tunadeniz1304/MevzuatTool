from mevzuat_tool.tree import parse_tree

SAMPLE = """Article Tree for mevzuatId: 999
Total nodes: 3

- DÖRDÜNCÜ KISIM - Verginin Tarhı (maddeId:1279006)
  - BİRİNCİ BÖLÜM - Beyan Esası (maddeId:1279015)
    - Madde No: 84 - Beyanname çeşitleri: (maddeId:1279029)
"""

KITAP_SAMPLE = """- BİRİNCİ KİTAP - Cezalar (maddeId:1)
  - İKİNCİ KISIM - Suçlar (maddeId:2)
    - ÜÇÜNCÜ BÖLÜM - Hükümler (maddeId:3)
      - Madde No: 5 - Tanımlar: (maddeId:50)
"""


def test_parse_tree_joins_madde_to_section():
    idx = parse_tree(SAMPLE)
    n = idx.by_no["84"]
    assert n.baslik == "Beyanname çeşitleri"   # trailing ':' kırpılır
    assert n.kisim_no == "DÖRDÜNCÜ KISIM"
    assert n.kisim_baslik == "Verginin Tarhı"
    assert n.bolum_no == "BİRİNCİ BÖLÜM"
    assert n.bolum_baslik == "Beyan Esası"
    assert n.maddeId == "1279029"


def test_parse_tree_keeps_full_path_including_kitap():
    idx = parse_tree(KITAP_SAMPLE)
    n = idx.by_no["5"]
    assert n.kisim_no == "İKİNCİ KISIM"
    assert n.bolum_no == "ÜÇÜNCÜ BÖLÜM"
    assert n.hiyerarsi_yolu == (
        "BİRİNCİ KİTAP - Cezalar › İKİNCİ KISIM - Suçlar › "
        "ÜÇÜNCÜ BÖLÜM - Hükümler › Madde 5"
    )
