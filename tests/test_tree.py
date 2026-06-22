from mevzuat_tool.tree import parse_tree

SAMPLE = """Article Tree for mevzuatId: 999
Total nodes: 3

- DÖRDÜNCÜ KISIM - Verginin Tarhı (maddeId:1279006)
  - BİRİNCİ BÖLÜM - Beyan Esası (maddeId:1279015)
    - Madde No: 84 - Beyanname çeşitleri: (maddeId:1279029)
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
