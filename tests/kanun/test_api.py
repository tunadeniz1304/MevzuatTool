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
                              metinler={("1", "1"): "Birinci madde metni."})
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
