# -*- coding: utf-8 -*-
"""kanun.retrieval.search — norm / wsum / HybridArama (sahte embedder + sahte Qdrant + sahte BM25).

Ağ yok, model yok: Qdrant'ın `query_points` cevabı ve BM25 skorları elle verilir.
"""
from types import SimpleNamespace

import numpy as np
import pytest

from kanun.retrieval.search import (
    SURE_ANAHTARLARI, BM25Index, HybridArama, norm, tokenize, wsum, wsum_puan,
)


# ---- norm ----------------------------------------------------------------
def test_norm_bos():
    assert norm({}) == {}


def test_norm_sabit_skor_sifira_bolmez():
    assert norm({"a": 3.0, "b": 3.0}) == {"a": 0.0, "b": 0.0}


def test_norm_min_max():
    assert norm({"a": 1.0, "b": 3.0, "c": 2.0}) == {"a": 0.0, "b": 1.0, "c": 0.5}


# ---- wsum ----------------------------------------------------------------
def test_wsum_agirlik_ve_eksik_anahtar():
    d = {"x": 1.0, "y": 0.0}          # norm: x=1, y=0
    b = {"y": 5.0, "z": 1.0}          # norm: y=1, z=0
    puan = wsum_puan([d, b], (0.7, 0.3))
    assert puan == pytest.approx({"x": 0.7, "y": 0.3, "z": 0.0})
    assert wsum([d, b], (0.7, 0.3)) == ["x", "y", "z"]


def test_wsum_uzunluk_uyusmazligi():
    with pytest.raises(ValueError):
        wsum_puan([{"a": 1}], (0.5, 0.5))


def test_tokenize_turkce():
    assert tokenize("Kira ARTIŞI, 2024'te %25!") == ["kira", "artişi", "2024", "te", "25"]


# ---- sahte bileşenler ----------------------------------------------------
def _nokta(kn, mn, skor, mid=None, ad="K"):
    return SimpleNamespace(score=skor, payload={"kanun_no": kn, "madde_no": mn,
                                                 "madde_id": mid or f"{kn}-{mn}", "kanun_ad": ad})


class SahteClient:
    def __init__(self, dense_noktalar, sparse_noktalar):
        self.cevap = {"dense": dense_noktalar, "sparse": sparse_noktalar}
        self.cagrilar = []

    def query_points(self, collection_name, query, using, limit, query_filter, with_payload):
        self.cagrilar.append({"collection": collection_name, "using": using, "limit": limit,
                              "filtre": query_filter})
        return SimpleNamespace(points=self.cevap[using][:limit])


class SahteBM25:
    def __init__(self, skorlar):
        self.skorlar = np.asarray(skorlar, dtype=float)

    def get_scores(self, tokenler):
        return self.skorlar


def _embedder(sorgu):
    return [0.1] * 4, {"5": 0.3, "9": 0.1}


def _arama(dense, sparse, bm_skor, maddeler, **kw):
    bm25 = BM25Index(SahteBM25(bm_skor), maddeler,
                     metinler={(m[0], m[1]): f"metin {m[0]}/{m[1]}" for m in maddeler})
    client = SahteClient(dense, sparse)
    return HybridArama(_embedder, client, bm25, **kw), client


def _temel():
    dense = [_nokta("1", "1", 0.9), _nokta("1", "2", 0.5), _nokta("2", "1", 0.1)]
    sparse = [_nokta("1", "2", 12.0), _nokta("2", "1", 2.0)]
    maddeler = [("1", "1", "m11"), ("3", "7", "m37"), ("2", "1", "m21")]
    return dense, sparse, [4.0, 0.0, 1.0], maddeler


# ---- HybridArama ---------------------------------------------------------
def test_yururluk_filtresi_qdrant_cagrisina_gecer():
    arama, client = _arama(*_temel())
    arama.ara("soru")
    assert [c["using"] for c in client.cagrilar] == ["dense", "sparse"]
    for c in client.cagrilar:
        kosul = c["filtre"].must[0]
        assert kosul.key == "yurutluk" and kosul.match.value == "yürürlükte"


def test_yururluk_filtresi_kapali():
    arama, client = _arama(*_temel())
    arama.ara("soru", yururlukte_only=False)
    assert all(c["filtre"] is None for c in client.cagrilar)


def test_aday_k_limit_olarak_gider():
    arama, client = _arama(*_temel(), aday_k=2)
    arama.ara("soru")
    assert all(c["limit"] == 2 for c in client.cagrilar)


def test_bm25_sifir_ve_negatif_skor_atilir():
    dense, sparse, _, maddeler = _temel()
    arama, _ = _arama(dense, sparse, [4.0, 0.0, -1.0], maddeler)
    anahtarlar = {s.anahtar for s in arama.ara("soru", top_k=50)}
    assert ("3", "7") not in anahtarlar     # yalnız BM25'te, skor 0 → aday bile değil


def test_wsum_siralama_ve_top_k():
    arama, _ = _arama(*_temel())
    sonuc = arama.ara("soru", top_k=2)
    assert len(sonuc) == 2
    # 1/1: dense 1.0*.33 + bm25 1.0*.34 = .67 ; 1/2: dense .5*.33 + sparse 1.0*.33 = .495
    assert [s.anahtar for s in sonuc] == [("1", "1"), ("1", "2")]
    assert sonuc[0].skor == pytest.approx(0.67)
    assert sonuc[0].rerank_skor is None


def test_sure_ms_anahtarlari():
    arama, _ = _arama(*_temel())
    sonuc = arama.ara("soru")
    assert set(sonuc.sure_ms) == set(SURE_ANAHTARLARI)
    assert sonuc.sure_ms["rerank"] == 0.0
    assert all(v >= 0 for v in sonuc.sure_ms.values())


def test_sadece_bm25_adayinin_kanun_adi_korpustan():
    dense, sparse, _, maddeler = _temel()
    bm25 = BM25Index(SahteBM25([0.0, 9.0, 0.0]), maddeler, kanun_adlari={("3", "7"): "Üç Kanunu"})
    arama = HybridArama(_embedder, SahteClient(dense, sparse), bm25)
    s = next(s for s in arama.ara("soru", top_k=10) if s.anahtar == ("3", "7"))
    assert s.kanun_ad == "Üç Kanunu" and s.madde_id == "m37"


def test_bos_sonuc():
    arama = HybridArama(_embedder, SahteClient([], []), BM25Index(SahteBM25([]), []))
    sonuc = arama.ara("soru")
    assert list(sonuc) == [] and "toplam" in sonuc.sure_ms

