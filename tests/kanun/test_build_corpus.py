"""build_corpus.build_one — R.G. tarihi/sayısı + mevzuat_tur entegrasyonu (ağ/veri yok, sahte fetcher).

Liste kaydı (bedesten searchDocuments) kanun düzeyidir: kanunun TÜM chunk'larına (yönlendirme dahil)
aynen geçer. Yalnız EKLEMELİ: chunk seti, id, text ve diğer metadata alanları liste kaydı olsa da
olmasa da birebir aynı kalır (build_corpus çıktısının mevcut alanları ve chunk sayısı korunur).
"""
import asyncio
import importlib.util
import json
import pathlib
import sys

_KOK = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_KOK / "src"))
from kanun.fetch import LISTE_CACHE, parse_tree_json, strip_html  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "build_corpus", str(_KOK / "scripts" / "kanun" / "build_corpus.py"))
_bc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_bc)

# Küçük ama gerçekçi kanun: başlıklı maddeler, bent listesi, içeriksiz 'yerine işlenmiştir' maddesi.
_HTML = (
    "<p>KİŞİSEL VERİLERİN KORUNMASI KANUNU</p>"
    "<p>Amaç</p>"
    "<p>MADDE 1- (1) Bu Kanunun amacı, kişisel verilerin işlenmesinde temel hak ve özgürlükleri "
    "korumaktır.</p>"
    "<p>İlgili kişinin hakları</p>"
    "<p>MADDE 11- (1) Herkes, veri sorumlusuna başvurarak kendisiyle ilgili;</p>"
    "<p>a) Kişisel veri işlenip işlenmediğini öğrenme,</p>"
    "<p>b) Kişisel verileri işlenmişse buna ilişkin bilgi talep etme,</p>"
    "<p>haklarına sahiptir.</p>"
    "<p>MADDE 21- (25/10/1984 tarihli ve 3065 sayılı Katma Değer Vergisi Kanunu ile ilgili olup "
    "yerine işlenmiştir.)</p>"
    "<p>Yürürlük</p>"
    "<p>MADDE 31- (1) Bu Kanun yayımı tarihinde yürürlüğe girer.</p>"
)
_AGAC = [
    {"maddeNo": "1", "maddeId": "100", "maddeBaslik": "Amaç", "children": []},
    {"maddeNo": "11", "maddeId": "110", "maddeBaslik": "İlgili kişinin hakları", "children": []},
    {"maddeNo": "21", "maddeId": "210", "maddeBaslik": None, "children": []},
    {"maddeNo": "31", "maddeId": "310", "maddeBaslik": "Yürürlük", "children": []},
]
# Gerçek bedesten liste kaydı biçimi (KVKK, canlı yanıt 2026-10-18; ilgili alanlar).
_KAYIT = {"mevzuatId": "104383", "mevzuatNo": 6698, "mevzuatAdi": "KİŞİSEL VERİLERİN KORUNMASI KANUNU",
          "mevzuatTur": {"id": 1, "name": "KANUN", "description": "Kanunlar"},
          "mevzuatTertip": 5, "resmiGazeteTarihi": "2016-04-07T00:00:00",
          "resmiGazeteSayisi": "29677", "mukerrer": "HAYIR"}
_ATIF = {("6698", "21")}        # 21. maddeye atıf var → yönlendirme chunk'ı üretilir (FAZ 22f)


class _SahteFetcher:
    """Ağsız fetcher: build_one'ın kullandığı üç yöntem (cache'li gerçek fetcher'ın sözleşmesi)."""

    async def fetch_tree(self, mid):
        return parse_tree_json(_AGAC)

    async def fetch_html(self, mid):
        return _HTML

    @staticmethod
    def html_to_text(html):
        return strip_html(html) if html else ""


def _build(**kw):
    return asyncio.run(_bc.build_one(_SahteFetcher(), "6698", "104383", "KVKK", **kw))


def _rg_haric(md):
    return {k: v for k, v in md.items() if not k.startswith("resmi_gazete_")}


def test_build_one_rg_ve_tur_tum_chunklarda():
    chunks = _build(atif_madde=_ATIF, liste_kaydi=_KAYIT)
    tipler = {c["metadata"]["madde_tipi"] for c in chunks}
    assert "islenmistir_yonlendirme" in tipler and "asil" in tipler   # iki chunk türü de var
    for c in chunks:
        md = c["metadata"]
        assert md["mevzuat_tur"] == "KANUN"
        assert md["resmi_gazete_tarihi"] == "2016-04-07"
        assert md["resmi_gazete_sayisi"] == "29677"


def test_build_one_liste_kaydi_yoksa_none_build_kirilmaz():
    chunks = _build(atif_madde=_ATIF)
    assert chunks                                                      # chunk üretimi sürer
    for c in chunks:
        assert c["metadata"]["resmi_gazete_tarihi"] is None
        assert c["metadata"]["resmi_gazete_sayisi"] is None
        assert c["metadata"]["mevzuat_tur"] == "KANUN"               # tür liste kaydına bağlı değil


def test_build_one_yalniz_eklemeli_chunk_seti_ve_alanlar_ayni():
    eski = _build(atif_madde=_ATIF)
    yeni = _build(atif_madde=_ATIF, liste_kaydi=_KAYIT)
    assert len(yeni) == len(eski)
    assert [(c["id"], c["text"]) for c in yeni] == [(c["id"], c["text"]) for c in eski]
    assert [_rg_haric(c["metadata"]) for c in yeni] == [_rg_haric(c["metadata"]) for c in eski]


def test_build_one_bozuk_liste_kaydi_kanunu_dusurmez():
    # build döngüsü kanun başına exception yakalayıp kanunu ATLAR → bozuk kayıt patlatmamalı.
    eski = _build()
    for bozuk in ("bozuk", 42, {"resmiGazeteTarihi": 20160407, "resmiGazeteSayisi": ["x"]}):
        yeni = _build(liste_kaydi=bozuk)
        assert [c["id"] for c in yeni] == [c["id"] for c in eski]
        assert all(c["metadata"]["resmi_gazete_tarihi"] is None for c in yeni)


def test_build_one_chunklar_json_serilesir():
    for c in _build(atif_madde=_ATIF, liste_kaydi=_KAYIT):
        json.dumps(c, ensure_ascii=False)


def _korpus_oku(yol):
    return [json.loads(s) for s in yol.read_text(encoding="utf-8").splitlines() if s.strip()]


def test_main_uctan_uca_cache_ile_agsiz(tmp_path, monkeypatch, capsys):
    # Gerçek main() + gerçek MevzuatFetcher, yalnız cache'ten (ağ yok): önce liste cache'i YOKKEN,
    # sonra VARKEN koşulur. Chunk seti aynı kalmalı; fark yalnız R.G. alanları olmalı.
    import httpx

    async def _ag_yasak(*a, **k):
        raise AssertionError("build ağa gitmemeli (her şey cache'te)")
    monkeypatch.setattr(httpx.AsyncClient, "post", _ag_yasak)
    monkeypatch.chdir(tmp_path)
    for env in ("CORPUS_LIMIT", "CORPUS_MID"):
        monkeypatch.delenv(env, raising=False)
    raw = tmp_path / "data" / "kanun" / "raw"
    raw.mkdir(parents=True)
    (raw / "_kanun_ids.txt").write_text("6698\t104383\tKVKK", encoding="utf-8")
    (raw / "treejson_104383.json").write_text(json.dumps(_AGAC, ensure_ascii=False), encoding="utf-8")
    (raw / "html_104383.html").write_text(_HTML, encoding="utf-8")
    korpus = tmp_path / "data" / "kanun" / "korpus.jsonl"

    asyncio.run(_bc.main())
    eski = _korpus_oku(korpus)
    assert eski and all(c["metadata"]["resmi_gazete_tarihi"] is None for c in eski)
    assert "cache yok" in capsys.readouterr().out

    (raw / LISTE_CACHE).write_text(json.dumps({"104383": _KAYIT}, ensure_ascii=False),
                                   encoding="utf-8")
    asyncio.run(_bc.main())
    yeni = _korpus_oku(korpus)
    cikti = capsys.readouterr().out
    assert "[R.G.] 1/1 kanunda" in cikti
    assert f"R.G. tarihi dolu chunk: {len(yeni)}/{len(yeni)}" in cikti
    assert [(c["id"], c["text"]) for c in yeni] == [(c["id"], c["text"]) for c in eski]
    assert [_rg_haric(c["metadata"]) for c in yeni] == [_rg_haric(c["metadata"]) for c in eski]
    assert all(c["metadata"]["resmi_gazete_tarihi"] == "2016-04-07" for c in yeni)
    assert all(c["metadata"]["resmi_gazete_sayisi"] == "29677" for c in yeni)


def test_load_liste_yok_bozuk_gecerli(tmp_path, capsys):
    assert _bc._load_liste(tmp_path) == {}                          # cache yok → {} (sessiz)
    (tmp_path / LISTE_CACHE).write_text("{bozuk", encoding="utf-8")
    assert _bc._load_liste(tmp_path) == {}                          # bozuk → {} + uyarı
    assert "UYARI" in capsys.readouterr().out
    (tmp_path / LISTE_CACHE).write_text(json.dumps({"104383": _KAYIT}, ensure_ascii=False),
                                        encoding="utf-8")
    assert _bc._load_liste(tmp_path) == {"104383": _KAYIT}
