# -*- coding: utf-8 -*-
"""HybridArama + reranker — sahte reranker ile yeniden sıralama kuralları (model yok)."""
from types import SimpleNamespace

import numpy as np
import pytest

from kanun.retrieval.rerank import _uzunluk_sirali_batchler
from kanun.retrieval.search import BM25Index, HybridArama


class SahteClient:
    def __init__(self, noktalar):
        self.noktalar = noktalar

    def query_points(self, collection_name, query, using, limit, query_filter, with_payload):
        return SimpleNamespace(points=self.noktalar[:limit] if using == "dense" else [])


class SahteBM25:
    def get_scores(self, tokenler):
        return np.zeros(0)


class SahteReranker:
    """Metindeki sayıyı skor olarak döndürür; kaç metin gördüğünü kaydeder."""

    def __init__(self, sabit=None):
        self.gorulen = []
        self.sabit = sabit

    def skorla(self, sorgu, metinler):
        self.gorulen.append(list(metinler))
        if self.sabit is not None:
            return [self.sabit] * len(metinler)
        return [float(m.split()[-1]) for m in metinler]


def _kur(n=6, rerank_aday=3, reranker=None, rerank_varsayilan=False):
    # WSUM sırası: m0 > m1 > ... (dense skor azalan)
    noktalar = [SimpleNamespace(score=float(n - i), payload={
        "kanun_no": "1", "madde_no": f"m{i}", "madde_id": f"1-m{i}", "kanun_ad": "K"}) for i in range(n)]
    # reranker skoru = i → WSUM'un tersini tercih eder
    metinler = {("1", f"m{i}"): f"madde {i}" for i in range(n)}
    idx = BM25Index(SahteBM25(), [], metinler=metinler)
    reranker = reranker or SahteReranker()
    arama = HybridArama(lambda s: ([0.0], {}), SahteClient(noktalar), idx, reranker=reranker,
                        rerank_aday=rerank_aday, rerank_varsayilan=rerank_varsayilan)
    return arama, reranker


def _sira(sonuc):
    return [s.madde_no for s in sonuc]


def test_rerank_kapaliyken_sira_wsum():
    arama, rr = _kur()
    sonuc = arama.ara("q", top_k=6, rerank=False)
    assert _sira(sonuc) == ["m0", "m1", "m2", "m3", "m4", "m5"]
    assert rr.gorulen == [] and all(s.rerank_skor is None for s in sonuc)
    assert sonuc.rerank is False


def test_rerank_yalniz_ilk_rerank_aday_etkilenir():
    arama, rr = _kur(rerank_aday=3)
    sonuc = arama.ara("q", top_k=6, rerank=True)
    assert rr.gorulen == [["madde 0", "madde 1", "madde 2"]]
    assert _sira(sonuc) == ["m2", "m1", "m0", "m3", "m4", "m5"]
    assert [s.rerank_skor for s in sonuc] == [2.0, 1.0, 0.0, None, None, None]
    assert sonuc.sure_ms["rerank"] >= 0 and sonuc.rerank is True


def test_esit_rerank_skorunda_kararli_siralama():
    arama, _ = _kur(rerank_aday=4, reranker=SahteReranker(sabit=0.5))
    assert _sira(arama.ara("q", top_k=6, rerank=True)) == ["m0", "m1", "m2", "m3", "m4", "m5"]


def test_rerank_none_ayar_varsayilanini_kullanir():
    arama, rr = _kur(rerank_varsayilan=True)
    assert arama.ara("q").rerank is True
    arama2, _ = _kur(rerank_varsayilan=False)
    assert arama2.ara("q").rerank is False


def test_reranker_yokken_rerank_istenirse_hata():
    arama, _ = _kur()
    arama.reranker = None
    with pytest.raises(ValueError):
        arama.ara("q", rerank=True)


def test_rerank_metni_krk_sinirinda_kesilir():
    arama, rr = _kur(rerank_aday=1)
    arama.rerank_max_krk = 3
    arama.bm25.metinler[("1", "m0")] = "7 uzun metin 9"
    arama.reranker = SahteReranker(sabit=0.0)
    arama.ara("q", rerank=True)
    assert arama.reranker.gorulen == [["7 u"]]


def test_uzunluk_sirali_batch_indeksleri_korur():
    ciftler = [["q", "cccc"], ["q", "a"], ["q", "bb"]]
    parcalar = list(_uzunluk_sirali_batchler(ciftler, 2))
    assert [idx for idx, _ in parcalar] == [[1, 2], [0]]
    assert sorted(i for idx, _ in parcalar for i in idx) == [0, 1, 2]
