from mevzuat_tool.enrich import _madde_tipi, enrich, Madde
from mevzuat_tool.chunker import Article
from mevzuat_tool.tree import parse_tree

TREE = parse_tree(
    "- DÖRDÜNCÜ KISIM - Verginin Tarhı (maddeId:9)\n"
    "  - BİRİNCİ BÖLÜM - Beyan Esası (maddeId:10)\n"
    "    - Madde No: 84 - Beyanname çeşitleri: (maddeId:1279029)\n"
)

TREE_BLEED = parse_tree(
    "- DÖRDÜNCÜ KISIM - X (maddeId:9)\n"
    "  - BİRİNCİ BÖLÜM - Beyan Esası (maddeId:10)\n"
    "    - Madde No: 84 - Beyanname çeşitleri: (maddeId:1279029)\n"
    "  - YEDİNCİ BÖLÜM - Diğer Kazanç (maddeId:20)\n"
    "    - Madde No: 85 - Gelire giren: (maddeId:30)\n"
)


def _maddeler(arts, tree):
    maddeler, _dipnotlar = enrich(arts, tree, "193")
    return maddeler


def test_madde_tipi_from_no():
    assert _madde_tipi("84") == "asil"
    assert _madde_tipi("257/A") == "asil"
    assert _madde_tipi("Geçici 84") == "gecici"
    assert _madde_tipi("Ek 2") == "ek"
    assert _madde_tipi("Mükerrer 80") == "mukerrer"


def test_enrich_returns_tuple_of_maddeler_and_dipnotlar():
    arts = [Article(no="84", body="içerik.")]
    res = enrich(arts, TREE, "193")
    assert isinstance(res, tuple) and len(res) == 2
    maddeler, dipnotlar = res
    assert isinstance(maddeler, list) and isinstance(dipnotlar, list)


def test_enrich_asil_joins_tree():
    arts = [Article(no="84", body="Gelir Vergisi beyanları: ...")]
    m = _maddeler(arts, TREE)[0]
    assert m.madde_tipi == "asil"
    assert m.madde_baslik == "Beyanname çeşitleri"
    assert m.bolum_no == "BİRİNCİ BÖLÜM"
    assert m.maddeId == "1279029"
    assert m.yurutluk == "yürürlükte"


def test_enrich_prefixed_inherits_section_and_flags():
    arts = [
        Article(no="84", body="asıl madde."),
        Article(no="Geçici 84", body="(Ek: 3/4/2013-6456/1 md.) geçici hüküm."),
    ]
    g = _maddeler(arts, TREE)[1]
    assert g.madde_tipi == "gecici"
    assert g.maddeId is None
    assert g.madde_baslik is None
    assert g.bolum_no == "BİRİNCİ BÖLÜM"


def test_enrich_strips_section_header_bleed():
    arts = [
        Article(no="84", body="asıl içerik. YEDİNCİ BÖLÜM Diğer Kazanç Gelire giren:"),
        Article(no="85", body="sonraki."),
    ]
    m = _maddeler(arts, TREE_BLEED)[0]
    assert "YEDİNCİ BÖLÜM" not in m.body
    assert m.body == "asıl içerik."


def test_enrich_status_uses_clean_body_not_next_madde_bleed():
    arts = [
        Article(no="84", body="bu madde yürürlükte. YEDİNCİ BÖLÜM Diğer Kazanç Gelire giren:"),
        Article(no="85", body="(Mülga: 1/1/2020-1234 md.) sonraki."),
    ]
    m = _maddeler(arts, TREE_BLEED)[0]
    assert m.yurutluk == "yürürlükte"


def test_enrich_plain_madde_missing_in_tree_does_not_crash():
    arts = [
        Article(no="84", body="ağaçtaki."),
        Article(no="999", body="ağaçta olmayan düz madde."),
    ]
    m = _maddeler(arts, TREE)[1]
    assert m.madde_tipi == "asil"
    assert m.maddeId is None
    assert m.bolum_no == "BİRİNCİ BÖLÜM"


def test_enrich_populates_new_fields():
    arts = [Article(no="84", body="(Değişik: 9/4/2003-4842/3 md.) (1) Birinci fıkra.")]
    m = _maddeler(arts, TREE)[0]
    assert m.id == "193-84"
    assert len(m.degisiklik_gecmisi) == 1
    assert m.degisiklik_gecmisi[0].kanun_no == "4842"
    assert "Değişik" not in m.body_temiz
    assert len(m.fikralar) == 1


def test_enrich_separates_footnote_appendix_into_global():
    arts = [Article(
        no="84",
        body=(
            "Madde gövdesi.\n"
            "[1] birinci dipnot tanımı.\n"
            "[2] ikinci dipnot tanımı.\n"
            "[3] üçüncü dipnot tanımı."
        ),
    )]
    maddeler, dipnotlar = enrich(arts, TREE, "193")
    assert "[1]" not in maddeler[0].body_temiz
    assert [d.no for d in dipnotlar] == [1, 2, 3]


def test_enrich_links_inline_footnote_to_madde():
    arts = [Article(
        no="84",
        body=(
            "Bu hüküm [2] ile değişti.\n"
            "[1] birinci.\n"
            "[2] ikinci.\n"
            "[3] üçüncü."
        ),
    )]
    maddeler, _ = enrich(arts, TREE, "193")
    assert [d.no for d in maddeler[0].dipnotlar] == [2]


def test_enrich_backward_compatible_without_html():
    # html_* verilmezse mevcut davranış birebir: tablolar boş, dipnotlar regex'ten.
    arts = [Article(no="84", body="(Değişik: 9/4/2003-4842/3 md.) içerik.")]
    maddeler, _ = enrich(arts, TREE, "193")
    m = maddeler[0]
    assert m.tablolar == []
    assert m.madde_baslik == "Beyanname çeşitleri"  # mevcut tree-join korunur


def test_enrich_injects_html_tables():
    arts = [Article(no="103", body="Tarife metni düz halde.")]
    html_tables = {"103": ["| dilim | oran |\n| --- | --- |\n| 18.000 TL | %15 |"]}
    maddeler, _ = enrich(arts, TREE, "193", html_tables=html_tables)
    m = maddeler[0]
    assert len(m.tablolar) == 1
    assert "%15" in m.tablolar[0]
    assert "| dilim | oran |" in m.body_temiz   # body_temiz'e gömüldü


def test_enrich_html_dipnot_overrides_regex():
    from mevzuat_tool.dipnot import Dipnot
    arts = [Article(no="5", body="Metin [1] atıf.\n[1] regex-tanımı.\n[2] x.\n[3] y.")]
    html_dipnotlar = {"5": [Dipnot(no=1, text="ANCHOR-tanımı")]}
    maddeler, _ = enrich(arts, TREE, "193", html_dipnotlar=html_dipnotlar)
    m = maddeler[0]
    assert [d.text for d in m.dipnotlar] == ["ANCHOR-tanımı"]   # anchor asıl
