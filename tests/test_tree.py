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

MESSY_SAMPLE = """Article Tree for mevzuatId: 999
Total nodes: 1

- BİRİNCİ BÖLÜM - Genel (maddeId:10)
    - Madde No: 1 - İlk: (maddeId:11)
- bozuk satır maddeId olmadan
"""


def test_parse_tree_skips_non_data_lines():
    idx = parse_tree(MESSY_SAMPLE)
    assert set(idx.by_no.keys()) == {"1"}        # sadece geçerli madde
    assert idx.by_no["1"].bolum_no == "BİRİNCİ BÖLÜM"


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


def test_parse_tree_handles_gerekceId_suffix():
    txt = (
        "- BİRİNCİ KISIM - Amaç (maddeId:100 | gerekceId:500)\n"
        "  - Madde No: 1 - Amaç ve kapsam: (maddeId:101 | gerekceId:501)\n"
    )
    idx = parse_tree(txt)
    assert "1" in idx.by_no
    assert idx.by_no["1"].baslik == "Amaç ve kapsam"
    assert idx.by_no["1"].maddeId == "101"
    assert idx.by_no["1"].kisim_no == "BİRİNCİ KISIM"
