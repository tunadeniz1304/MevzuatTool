"""corpus.py — Madde → RAG korpus chunk ({id, text, metadata}) dönüşümü (Faz 4).

text = madde_baslik + body_temiz (embedding girdisi). metadata zengin: hiyerarşi + yürürlük +
fıkra/bent ağacı + değişiklik künyeleri + dipnot/tablo. Boş-gövde maddeler filtrelenir
(içeriksiz işlenmiş maddeler — RAG'a gitmez). Mülga DAHİL ama yurutluk ile işaretli.
"""
from mevzuat_tool.corpus import madde_to_chunk, maddeler_to_chunks
from mevzuat_tool.enrich import enrich, Madde
from mevzuat_tool.chunker import Article
from mevzuat_tool.tree import parse_tree

TREE = parse_tree(
    "- ÜÇÜNCÜ BÖLÜM - Haklar ve Yükümlülükler (maddeId:10)\n"
    "  - Madde No: 11 - İlgili kişinin hakları: (maddeId:1643063)\n"
)


def _madde(no, body):
    maddeler, _ = enrich([Article(no=no, body=body)], TREE, "6698")
    return maddeler[0]


def test_chunk_id_and_text():
    m = _madde("11", "(1) Herkes, veri sorumlusuna başvurabilir.")
    c = madde_to_chunk(m, kanun_ad="KİŞİSEL VERİLERİN KORUNMASI KANUNU")
    assert c["id"] == "6698-11"
    # text = başlık + temiz gövde (başlık ilk satır, gövde ardından)
    assert c["text"].startswith("İlgili kişinin hakları")
    assert "Herkes, veri sorumlusuna başvurabilir." in c["text"]


def test_chunk_metadata_core_fields():
    m = _madde("11", "(1) Herkes başvurabilir.")
    c = madde_to_chunk(m, kanun_ad="KVKK")
    md = c["metadata"]
    assert md["kanun_no"] == "6698"
    assert md["kanun_ad"] == "KVKK"
    assert md["madde_no"] == "11"
    assert md["madde_baslik"] == "İlgili kişinin hakları"
    assert md["yurutluk"] == "yürürlükte"
    assert md["bolum_no"] == "ÜÇÜNCÜ BÖLÜM"
    assert md["bolum_baslik"] == "Haklar ve Yükümlülükler"
    # null seviyeler de alan olarak DURUR (filtre tutarlılığı için)
    assert md["kitap_no"] is None


def test_chunk_metadata_embeds_fikra_tree():
    # Zengin metadata: fıkra/bent ağacı gömülü (dict listesi olarak, JSON-serileştirilebilir).
    m = _madde("11", "(1) Herkes, şu haklara sahiptir:\na) öğrenme,\nb) düzeltme isteme.")
    c = madde_to_chunk(m, kanun_ad="KVKK")
    fk = c["metadata"]["fikralar"]
    assert isinstance(fk, list) and len(fk) == 1
    assert fk[0]["no"] == "(1)"
    assert [b["isaret"] for b in fk[0]["bentler"]] == ["a)", "b)"]


def test_chunk_is_json_serializable():
    import json
    m = _madde("11", "(Değişik: 2/3/2024-7499/33 md.) (1) Herkes başvurabilir.")
    c = madde_to_chunk(m, kanun_ad="KVKK")
    s = json.dumps(c, ensure_ascii=False)        # patlamadan serileşmeli
    assert "6698-11" in s
    # değişiklik künyesi de metadata'da yapısal
    assert len(c["metadata"]["degisiklik_gecmisi"]) == 1


def test_empty_body_madde_is_filtered():
    # İçeriksiz işlenmiş madde (boş gövde) → korpusa GİRMEZ (None döner).
    m = _madde("11", "")
    assert madde_to_chunk(m, kanun_ad="KVKK") is None


def test_islenmistir_only_body_is_filtered():
    # text'i SADECE 'yerine işlenmiştir' yönlendirme notundan ibaret madde → korpusa GİRMEZ.
    # Gerçek hukuki içerik yok (metin başka kanuna işlendi). Gerçek veri: 7579 M1.
    m = _madde("1", "(22/12/1934 tarihli ve 2644 sayılı Tapu Kanunu ile ilgili olup, yerine işlenmiştir.)")
    assert madde_to_chunk(m, kanun_ad="TAPU ... DEĞİŞİKLİK KANUNU") is None


def test_ilgili_olup_only_body_is_filtered():
    # 'ile ilgili olup ... işlenmiştir' varyantı da içeriksiz → filtrelenir. Gerçek veri: KVKK M30.
    m = _madde("1", "(10/12/2003 tarihli ve 5018 sayılı Kanun ile ilgili olup yerine işlenmiştir.)")
    assert madde_to_chunk(m, kanun_ad="X DEĞİŞİKLİK KANUNU") is None


def test_real_content_with_islenmistir_mention_is_kept():
    # KORUMA (false-positive): gerçek hüküm İÇİNDE 'işlenmiştir' geçse bile, içerik dolu → KALIR.
    body = ("(1) Kişisel veriler, kanunda öngörülen usullere uygun işlenir ve sicile işlenmiştir. "
            "(2) Veri sorumlusu gerekli tedbirleri alır ve denetimleri yapar.")
    m = _madde("11", body)
    c = madde_to_chunk(m, kanun_ad="KVKK")
    assert c is not None                          # gerçek içerik elenmemeli
    assert "tedbirleri alır" in c["text"]


def test_maddeler_to_chunks_filters_empty():
    arts = [Article(no="11", body="(1) Dolu madde."), Article(no="12", body="   ")]
    maddeler, _ = enrich(arts, TREE, "6698")
    chunks = maddeler_to_chunks(maddeler, kanun_ad="KVKK")
    assert [c["metadata"]["madde_no"] for c in chunks] == ["11"]   # boş 12 elendi


def test_mulga_madde_is_included_but_marked():
    # Mülga madde korpusta KALIR (tarihsel sorgu) ama yurutluk='mülga' ile işaretli.
    m = _madde("11", "(1) (Mülga: 1/1/2020-1234/5 md.)")
    c = madde_to_chunk(m, kanun_ad="KVKK")
    assert c is not None
    assert c["metadata"]["yurutluk"] == "mülga"
