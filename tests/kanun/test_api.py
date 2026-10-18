# -*- coding: utf-8 -*-
"""FastAPI servisi — TestClient + sahte HybridArama (ağ yok, model yok)."""
import pytest
from fastapi.testclient import TestClient

from kanun.api.app import uygulama_olustur
from kanun.retrieval.config import Ayarlar
from kanun.retrieval.search import AramaSonucu, BM25Index, Sonuc


class SahteClient:
    def __init__(self, var=True):
        self.var = var

    def collection_exists(self, ad):
        if self.var is None:
            raise ConnectionError("qdrant kapalı")
        return self.var


class SahteArama:
    def __init__(self, reranker=False, rerank_varsayilan=False, qdrant=True):
        self.client = SahteClient(qdrant)
        self.collection = "mevzuat"
        self.bm25 = BM25Index(None, [("1", "1", "a"), ("1", "2", "b")],
                              metinler={"a": "Birinci madde metni."})          # madde_id → metin
        self.aday_k = 50
        self.agirliklar = (0.33, 0.33, 0.34)
        self.rerank_aday = 20
        self.rerank_varsayilan = rerank_varsayilan
        self.reranker = object() if reranker else None
        self.cagrilar = []

    def ara(self, sorgu, top_k=10, yururlukte_only=True, rerank=None):
        self.cagrilar.append({"sorgu": sorgu, "top_k": top_k, "yururlukte_only": yururlukte_only,
                              "rerank": rerank})
        acik = self.rerank_varsayilan if rerank is None else rerank
        if acik and self.reranker is None:
            raise ValueError("rerank istendi ama reranker yüklü değil")
        sonuclar = [Sonuc("a", "1", "Bir Kanunu", "1", 0.9, 3.2 if acik else None),
                    Sonuc("b", "1", "Bir Kanunu", "2", 0.5)][:top_k]
        return AramaSonucu(sonuclar, sure_ms={"embed": 1.0, "toplam": 2.0}, rerank=acik)


def _istemci(arama):
    app = uygulama_olustur(arama_fabrika=lambda: arama,
                           ayar=Ayarlar(embed_backend="onnx-int8", rerank_backend="kapali"))
    return TestClient(app)


def test_saglik():
    with _istemci(SahteArama()) as c:
        r = c.get("/saglik")
    assert r.status_code == 200
    j = r.json()
    assert j["qdrant"] is True and j["durum"] == "ok"
    assert j["embed_backend"] == "onnx-int8" and j["madde_sayisi"] == 2 and j["rerank_aday"] == 20


def test_saglik_qdrant_kapali_yine_200():
    with _istemci(SahteArama(qdrant=None)) as c:
        j = c.get("/saglik").json()
    assert j["qdrant"] is False and j["durum"] == "qdrant-yok"


def test_ara_semasi():
    arama = SahteArama()
    with _istemci(arama) as c:
        r = c.post("/ara", json={"sorgu": "kira artışı", "top_k": 2})
    assert r.status_code == 200
    j = r.json()
    assert set(j) == {"sonuclar", "sure_ms", "config"}
    s = j["sonuclar"][0]
    assert s == {"sira": 1, "madde_id": "a", "kanun_no": "1", "kanun_ad": "Bir Kanunu",
                 "madde_no": "1", "skor": 0.9, "rerank_skor": None, "metin": None}
    assert j["config"]["rerank"] is False and j["sure_ms"]["toplam"] == 2.0
    assert arama.cagrilar[0] == {"sorgu": "kira artışı", "top_k": 2, "yururlukte_only": True,
                                 "rerank": None}


def test_ara_metin_istenirse_doner():
    with _istemci(SahteArama()) as c:
        j = c.post("/ara", json={"sorgu": "x", "metin": True}).json()
    assert j["sonuclar"][0]["metin"] == "Birinci madde metni."


@pytest.mark.parametrize("govde", [
    {"sorgu": ""}, {"sorgu": "   "}, {"sorgu": "a" * 2001}, {"sorgu": "x", "top_k": 0},
    {"sorgu": "x", "top_k": 51}, {}, {"sorgu": "x", "rerank": "belki"},
])
def test_ara_422(govde):
    with _istemci(SahteArama()) as c:
        assert c.post("/ara", json=govde).status_code == 422


@pytest.mark.parametrize("top_k", [1, 50])
def test_top_k_sinirlari_gecerli(top_k):
    with _istemci(SahteArama()) as c:
        assert c.post("/ara", json={"sorgu": "x", "top_k": top_k}).status_code == 200


def test_rerank_null_sunucu_varsayilani():
    arama = SahteArama(reranker=True, rerank_varsayilan=True)
    with _istemci(arama) as c:
        j = c.post("/ara", json={"sorgu": "x", "rerank": None}).json()
        j2 = c.post("/ara", json={"sorgu": "x", "rerank": False}).json()
    assert j["config"]["rerank"] is True and j["sonuclar"][0]["rerank_skor"] == 3.2
    assert j2["config"]["rerank"] is False
    assert arama.cagrilar[0]["rerank"] is None


def test_reranker_yokken_rerank_true_400():
    with _istemci(SahteArama(reranker=False)) as c:
        r = c.post("/ara", json={"sorgu": "x", "rerank": True})
    assert r.status_code == 400


def test_generation_endpointi_yok():
    with _istemci(SahteArama()) as c:
        yollar = {r.path for r in c.app.routes}
    assert "/ara" in yollar and not any(p in yollar for p in ("/cevap", "/generate", "/chat"))


# ---- atıf modu (ADR-0019): mod = otomatik | atif | dogal ---------------------------------------
ESKI_SONUC_ALANLARI = {"sira", "madde_id", "kanun_no", "kanun_ad", "madde_no", "skor", "rerank_skor", "metin"}


def _chunk(mid, kanun_no, madde_no, kanun_ad, fikralar=(), yurutluk="yürürlükte"):
    return {"id": f"{mid}-{madde_no}", "text": f"{kanun_ad} m.{madde_no} metni",
            "metadata": {"mevzuat_id": mid, "kanun_no": kanun_no, "kanun_ad": kanun_ad, "madde_no": madde_no,
                         "madde_baslik": "Başlık", "madde_tipi": "asil", "yurutluk": yurutluk,
                         "fikralar": list(fikralar)}}


def _fikra(no, text, bentler=()):
    return {"no": no, "text": text, "yurutluk": "yürürlükte",
            "bentler": [{"isaret": i, "text": t, "yurutluk": "yürürlükte", "alt_bentler": []} for i, t in bentler]}


ATIF_KORPUS = [
    _chunk("100", "5237", "141", "TÜRK CEZA KANUNU", [_fikra("(1)", "(1) birinci"), _fikra("(2)", "(2) ikinci")]),
    _chunk("100", "5237", "143", "TÜRK CEZA KANUNU", [_fikra(None, "(Mülga)")], yurutluk="mülga"),
    _chunk("300", "193", "40", "GELİR VERGİSİ KANUNU", [_fikra(None, "giriş: 1. ... 7. ...",
                                                             [("1.", "1. bir"), ("7.", "7. yedi")])]),
    _chunk("400", "6551", "5", "ÖRNEK MAHALLİ İDARELER KANUNU"),
    _chunk("401", "6551", "5", "ÖRNEK ENERJİ PİYASASI KANUNU"),
]


def _atif_istemci(arama, korpus=ATIF_KORPUS, atif_fabrika=None):
    from kanun.retrieval.atif_getir import AtifIndeks
    app = uygulama_olustur(arama_fabrika=lambda: arama,
                           atif_fabrika=atif_fabrika or (lambda: AtifIndeks.bellekten(korpus)),
                           ayar=Ayarlar(embed_backend="onnx-int8", rerank_backend="kapali"))
    return TestClient(app)


@pytest.mark.parametrize("mod", ["hepsi", "", None, 1])
def test_gecersiz_mod_422(mod):
    with _atif_istemci(SahteArama()) as c:
        assert c.post("/ara", json={"sorgu": "x", "mod": mod}).status_code == 422


def test_dogal_dil_yaniti_eski_semada_mod_configte():
    arama = SahteArama()
    with _atif_istemci(arama) as c:                          # atıf indeksi yüklü, sorgu atıf değil
        j = c.post("/ara", json={"sorgu": "kira artışı", "top_k": 2}).json()
    assert set(j) == {"sonuclar", "sure_ms", "config"}
    assert all(set(s) == ESKI_SONUC_ALANLARI for s in j["sonuclar"])
    assert j["config"]["mod"] == "dogal" and j["config"]["istenen_mod"] == "otomatik"
    assert arama.cagrilar == [{"sorgu": "kira artışı", "top_k": 2, "yururlukte_only": True, "rerank": None}]


def test_otomatik_atif_sorgusu_atif_modunda_doner():
    arama = SahteArama()
    with _atif_istemci(arama) as c:
        r = c.post("/ara", json={"sorgu": "TCK m. 141/2"})
    assert r.status_code == 200 and arama.cagrilar == []      # doğal dil araması hiç çağrılmadı
    j = r.json()
    assert j["config"]["mod"] == "atif" and j["config"]["rerank"] is False
    assert set(j["sure_ms"]) == {"ayristirma", "getirme", "toplam"}
    s = j["sonuclar"][0]
    assert (s["sira"], s["madde_id"], s["kanun_no"], s["madde_no"], s["skor"]) == (1, "100-141", "5237", "141", 1.0)
    assert s["metin"] == "TÜRK CEZA KANUNU m.141 metni"           # atıf modunda metin varsayılan açık
    assert s["atif"]["yurutluk"] == "yürürlükte" and s["atif"]["mevzuat_id"] == "100"
    assert s["atif"]["alt_parca"] == {"fikra": "(2)", "bent": None, "metin": "(2) ikinci",
                                      "yurutluk": "yürürlükte", "tolerans": None}
    a = j["atif"]
    assert (a["durum"], a["dusus"]) == ("eslesti", False)
    assert a["atiflar"][0]["kanun_nolari"] == ["5237"] and a["atiflar"][0]["fikra"] == 2


def test_atif_modunda_metin_kapatilabilir():
    with _atif_istemci(SahteArama()) as c:
        j = c.post("/ara", json={"sorgu": "TCK m. 141", "metin": False}).json()
    assert j["config"]["mod"] == "atif" and j["sonuclar"][0]["metin"] is None


def test_dogal_mod_atif_sorgusunu_dogal_dilde_arar():
    arama = SahteArama()
    with _atif_istemci(arama) as c:
        j = c.post("/ara", json={"sorgu": "TCK m. 141", "mod": "dogal"}).json()
    assert set(j) == {"sonuclar", "sure_ms", "config"} and j["config"]["mod"] == "dogal"
    assert len(arama.cagrilar) == 1 and j["sonuclar"][0]["madde_id"] == "a"


def test_eslesmeyen_atif_dogal_dile_duser_ve_belirtir():
    arama = SahteArama()
    with _atif_istemci(arama) as c:
        j = c.post("/ara", json={"sorgu": "TCK m. 999"}).json()
    assert j["config"]["mod"] == "dogal" and len(arama.cagrilar) == 1
    assert [s["madde_id"] for s in j["sonuclar"]] == ["a", "b"]
    assert all(set(s) == ESKI_SONUC_ALANLARI for s in j["sonuclar"])
    a = j["atif"]
    assert (a["durum"], a["dusus"]) == ("eslesme_yok", True) and "999" in a["aciklama"]
    assert a["atiflar"][0]["durum"] == "madde_yok"


def test_atif_modu_ayristirilamazsa_dogal_dile_duser():
    with _atif_istemci(SahteArama()) as c:
        j = c.post("/ara", json={"sorgu": "kira artışı", "mod": "atif"}).json()
    assert j["config"]["mod"] == "dogal" and j["config"]["istenen_mod"] == "atif"
    assert (j["atif"]["durum"], j["atif"]["dusus"], j["atif"]["atiflar"]) == ("ayristirilamadi", True, [])


def test_atif_indeksi_yoksa_dogal_dile_duser():
    with _istemci(SahteArama()) as c:                         # atif_fabrika yok → indeks yok
        j = c.post("/ara", json={"sorgu": "TCK m. 141"}).json()
    assert j["config"]["mod"] == "dogal" and j["atif"]["durum"] == "indeks_yok"
    assert j["atif"]["atiflar"][0]["durum"] is None


def test_mulga_madde_atif_modunda_yurutlukle_doner():
    with _atif_istemci(SahteArama()) as c:
        j = c.post("/ara", json={"sorgu": "TCK m. 143", "yururlukte_only": True}).json()
    s = j["sonuclar"][0]
    assert j["config"]["mod"] == "atif" and s["atif"]["yurutluk"] == "mülga"
    assert any("mülga" in u for u in s["atif"]["uyarilar"])


def test_kanun_no_cakismasi_iki_kanun_doner():
    with _atif_istemci(SahteArama()) as c:
        j = c.post("/ara", json={"sorgu": "6551 sayılı Kanun m. 5"}).json()
    assert [s["atif"]["mevzuat_id"] for s in j["sonuclar"]] == ["400", "401"]
    assert j["atif"]["atiflar"][0]["coklu_mevzuat"] is True


def test_fikra_bent_toleransi_yanitta_isaretli():
    with _atif_istemci(SahteArama()) as c:
        j = c.post("/ara", json={"sorgu": "GVK m. 40 fıkra 7"}).json()
    p = j["sonuclar"][0]["atif"]["alt_parca"]
    assert (p["bent"], p["metin"], p["tolerans"]) == ("7.", "7. yedi", "fikra->bent")


def test_atif_modunda_rerank_istegi_yok_sayilir():
    with _atif_istemci(SahteArama(reranker=False)) as c:     # doğal dilde bu istek 400 olurdu
        r = c.post("/ara", json={"sorgu": "TCK m. 141", "rerank": True})
    assert r.status_code == 200 and r.json()["config"]["rerank"] is False


def test_saglik_atif_indeks_sayisi():
    with _atif_istemci(SahteArama()) as c:
        assert c.get("/saglik").json()["atif_indeks"] == len(ATIF_KORPUS)
    with _istemci(SahteArama()) as c:
        assert c.get("/saglik").json()["atif_indeks"] == 0


def test_openapi_semasi_mod_alanini_icerir():
    with _atif_istemci(SahteArama()) as c:
        r = c.get("/openapi.json")
    assert r.status_code == 200
    sema = r.json()["components"]["schemas"]
    assert sema["AraIstek"]["properties"]["mod"]["enum"] == ["otomatik", "atif", "dogal"]
    assert "atif" in sema["AraYanit"]["properties"] and "atif" in sema["SonucModel"]["properties"]


def test_varsayilan_lifespan_ayni_korpustan_bm25_ve_atif_indeksi_kurar(tmp_path, monkeypatch):
    """Fabrikasız (servis) dalı: arama_kur → gerçek bm25_kur, atif_indeks_kur → aynı KORPUS_YOL.
    Qdrant client'ı ve embedder sahte (ağ/model yok); atıf sorgusu ikisini de hiç çağırmaz."""
    import json
    import qdrant_client
    import kanun.retrieval.fabrika as fabrika

    yol = tmp_path / "korpus.jsonl"
    yol.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in ATIF_KORPUS), encoding="utf-8")
    monkeypatch.setenv("KORPUS_YOL", str(yol))
    monkeypatch.setenv("RERANK_BACKEND", "kapali")

    class SahteQdrant:
        def __init__(self, url=None, **kw):
            pass

        def collection_exists(self, ad):
            return True

    monkeypatch.setattr(qdrant_client, "QdrantClient", SahteQdrant)
    monkeypatch.setattr(fabrika, "embedder_sec", lambda ayar: (lambda s: ([0.0], {})))
    with TestClient(uygulama_olustur()) as c:
        saglik = c.get("/saglik").json()
        j = c.post("/ara", json={"sorgu": "TCK m. 141/2"}).json()
    yururlukte = sum(r["metadata"]["yurutluk"] == "yürürlükte" for r in ATIF_KORPUS)
    assert saglik["madde_sayisi"] == yururlukte and saglik["atif_indeks"] == len(ATIF_KORPUS)  # mülga dahil
    assert j["config"]["mod"] == "atif" and j["sonuclar"][0]["atif"]["alt_parca"]["metin"] == "(2) ikinci"


def test_korpus_degisirse_503(tmp_path):
    import json
    from kanun.retrieval.atif_getir import atif_indeks_kur
    yol = tmp_path / "korpus.jsonl"
    yol.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in ATIF_KORPUS), encoding="utf-8")
    ix = atif_indeks_kur(str(yol))
    yol.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in reversed(ATIF_KORPUS)),
                   encoding="utf-8")
    with _atif_istemci(SahteArama(), atif_fabrika=lambda: ix) as c:
        r = c.post("/ara", json={"sorgu": "TCK m. 141"})
    assert r.status_code == 503 and "yeniden başlatın" in r.json()["detail"]
