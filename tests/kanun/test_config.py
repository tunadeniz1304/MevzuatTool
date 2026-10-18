import pytest

from kanun.retrieval.config import Ayarlar, ayarlar_oku


def test_varsayilan_wsum_agirliklari_adr_0022():
    a = Ayarlar()
    assert a.agirliklar == (0.65, 0.20, 0.15)
    assert sum(a.agirliklar) == pytest.approx(1.0)


def test_agirliklar_ortam_degiskeniyle_ezilir(monkeypatch):
    monkeypatch.setenv("W_DENSE", "0.33")
    monkeypatch.setenv("W_SPARSE", "0.33")
    monkeypatch.setenv("W_BM25", "0.34")
    assert ayarlar_oku().agirliklar == (0.33, 0.33, 0.34)
