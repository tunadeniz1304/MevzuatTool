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


# --- KİTAP ayrı alan (#1) ---
def test_parse_tree_exposes_kitap_as_field():
    idx = parse_tree(KITAP_SAMPLE)
    n = idx.by_no["5"]
    assert n.kitap_no == "BİRİNCİ KİTAP"
    assert n.kitap_baslik == "Cezalar"


# --- AYIRIM ayrı alan (#2) ---
def test_parse_tree_exposes_ayirim_as_field():
    txt = (
        "- BİRİNCİ KISIM - Borçlar (maddeId:1)\n"
        "  - İKİNCİ BÖLÜM - Sözleşme (maddeId:2)\n"
        "    - BİRİNCİ AYIRIM - Kuruluş (maddeId:3)\n"
        "      - Madde No: 7 - Öneri: (maddeId:70)\n"
    )
    idx = parse_tree(txt)
    n = idx.by_no["7"]
    assert n.ayirim_no == "BİRİNCİ AYIRIM"
    assert n.ayirim_baslik == "Kuruluş"
    assert n.bolum_no == "İKİNCİ BÖLÜM"
    assert "BİRİNCİ AYIRIM - Kuruluş" in n.hiyerarsi_yolu


# --- BAŞLANGIÇ kabı (#3): ayraçsız tek-kelime seviye, altındaki madde köksüz kalmamalı ---
def test_parse_tree_recognizes_baslangic_container():
    txt = (
        "- BAŞLANGIÇ (maddeId:1000)\n"
        "  - Madde No: 1 - Hukukun uygulanması: (maddeId:1001)\n"
    )
    idx = parse_tree(txt)
    n = idx.by_no["1"]
    # BAŞLANGIÇ no'lu kısım/bölüm değil → hiyerarşi yoluna girer, no-tekrarı yapılmaz
    assert n.hiyerarsi_yolu == "BAŞLANGIÇ › Madde 1"


def test_parse_tree_baslangic_flattened_when_kitap_follows():
    # Medeni 4721 deseni: bedesten KİTAP'ı BAŞLANGIÇ'ın ALTINA girintiler (tuhaf modelleme).
    # Hukuken KİTAP, BAŞLANGIÇ'ın kardeşidir → BAŞLANGIÇ kendi maddelerinin (M1) kabı kalır,
    # KİTAP altındaki maddeler (M8) BAŞLANGIÇ'ı hiyerarşide TAŞIMAZ (düzleştirme kararı).
    txt = (
        "- BAŞLANGIÇ (maddeId:1000)\n"
        "  - Madde No: 1 - Hukukun uygulanması: (maddeId:1001)\n"
        "  - BİRİNCİ KİTAP (maddeId:1002)\n"
        "    - BİRİNCİ KISIM (maddeId:1003)\n"
        "      - Madde No: 8 - Hak ehliyeti: (maddeId:1008)\n"
    )
    idx = parse_tree(txt)
    assert idx.by_no["1"].hiyerarsi_yolu == "BAŞLANGIÇ › Madde 1"
    m8 = idx.by_no["8"]
    assert m8.kitap_no == "BİRİNCİ KİTAP"
    assert "BAŞLANGIÇ" not in m8.hiyerarsi_yolu          # düzleştirildi
    assert m8.hiyerarsi_yolu == "BİRİNCİ KİTAP › BİRİNCİ KISIM › Madde 8"


# --- Başlıksız seviye → baslik=None (no-tekrarı YOK), null tutma kararı ---
def test_parse_tree_titleless_section_keeps_null_baslik():
    # Medeni 4721 deseni: ayraçsız 'BİRİNCİ KİTAP/KISIM/BÖLÜM' (gerçek başlık yok).
    txt = (
        "- BİRİNCİ KİTAP (maddeId:1)\n"
        "  - BİRİNCİ KISIM (maddeId:2)\n"
        "    - BİRİNCİ BÖLÜM (maddeId:3)\n"
        "      - Madde No: 8 - Hak ehliyeti: (maddeId:80)\n"
    )
    idx = parse_tree(txt)
    n = idx.by_no["8"]
    # no alanları dolu, baslik alanları None (no-tekrarı 'BİRİNCİ BÖLÜM' DEĞİL)
    assert n.kitap_no == "BİRİNCİ KİTAP" and n.kitap_baslik is None
    assert n.kisim_no == "BİRİNCİ KISIM" and n.kisim_baslik is None
    assert n.bolum_no == "BİRİNCİ BÖLÜM" and n.bolum_baslik is None
    # hiyerarşi_yolu'nda da no-tekrarı yok: sadece no yazılır
    assert n.hiyerarsi_yolu == "BİRİNCİ KİTAP › BİRİNCİ KISIM › BİRİNCİ BÖLÜM › Madde 8"
