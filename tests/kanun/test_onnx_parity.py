# -*- coding: utf-8 -*-
"""ONNX export/quantization doğruluğu — GERÇEK model gerektirir (`pytest -m model`).

Varsayılan `pytest -q`'da atlanır (pytest.ini: -m "not model"). Model dosyası yoksa skip.
Eşikler (ADR-0016, N = PARITY_N sorgu, vars. 200):
  - ONNX-FP32 vs torch dense : ortalama kosinüs ≥ 0.9999 (export doğruluğu)
  - ONNX-int8 vs torch dense : ortalama ≥ 0.99, minimum ≥ 0.97
  - sparse (FP32)            : aynı token kümesi, ağırlık farkı < 1e-3
  - reranker int8 vs FP32    : aday listesi başına top-10 kesişimi ortalaması ≥ 0.9
Çalıştır: .venv/Scripts/python.exe -m pytest -q -m model tests/kanun/test_onnx_parity.py -s
"""
import json
import os

import numpy as np
import pytest

pytestmark = pytest.mark.model

MODEL_DIR = os.environ.get("MODEL_DIR", "models/onnx")
EMB = os.path.join(MODEL_DIR, "bge-m3")
RR = os.path.join(MODEL_DIR, "bge-reranker-v2-m3")
N = int(os.environ.get("PARITY_N", "200"))
RR_N = int(os.environ.get("PARITY_RR_N", "50"))
RR_ADAY = int(os.environ.get("RERANK_ADAY", "20"))
ADAY_DOSYA = "data/kanun/olcum/rerank_aday_3bacak.jsonl"


def _gerekli(*yollar):
    for y in yollar:
        if not os.path.exists(y):
            pytest.skip(f"model/veri yok: {y}")


@pytest.fixture(scope="module")
def sorgular():
    _gerekli("data/gold/altinset_temiz.jsonl", "data/kanun/korpus.jsonl")
    from kanun.retrieval.olcum import gold_sorgular
    return [s for s, _ in gold_sorgular(N)]


@pytest.fixture(scope="module")
def torch_vektorler(sorgular):
    from kanun.retrieval.embed import embed_sorgu
    return [embed_sorgu(s) for s in sorgular]


def _kosinus(a, b):
    a, b = np.asarray(a), np.asarray(b)
    return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)))


def test_onnx_fp32_dense_ve_sparse(sorgular, torch_vektorler):
    _gerekli(os.path.join(EMB, "model.onnx"))
    from kanun.retrieval.embed_onnx import OnnxEmbedder
    emb = OnnxEmbedder(os.path.join(EMB, "model.onnx"))
    kos, sp_fark = [], []
    for s, (d_t, sp_t) in zip(sorgular, torch_vektorler):
        d_o, sp_o = emb(s)
        kos.append(_kosinus(d_t, d_o))
        assert set(sp_o) == set(sp_t)
        sp_fark.append(max((abs(sp_o[k] - sp_t[k]) for k in sp_t), default=0.0))
    print(f"\nONNX-FP32 dense kosinüs ort {np.mean(kos):.6f} min {np.min(kos):.6f}; "
          f"sparse max fark {max(sp_fark):.2e}")
    assert np.mean(kos) >= 0.9999
    assert max(sp_fark) < 1e-3


def test_onnx_int8_dense(sorgular, torch_vektorler):
    _gerekli(os.path.join(EMB, "model.int8.onnx"))
    from kanun.retrieval.embed_onnx import OnnxEmbedder
    emb = OnnxEmbedder(os.path.join(EMB, "model.int8.onnx"))
    kos = [_kosinus(d_t, emb(s)[0]) for s, (d_t, _) in zip(sorgular, torch_vektorler)]
    print(f"\nONNX-int8 dense kosinüs ort {np.mean(kos):.5f} min {np.min(kos):.5f}")
    assert np.mean(kos) >= 0.99
    assert np.min(kos) >= 0.97


def test_reranker_int8_top10_kesisimi():
    """int8 ile FP32 ONNX reranker aynı aday listesini ~aynı sıralıyor mu (top-10 kesişimi)."""
    _gerekli(os.path.join(RR, "model.onnx"), os.path.join(RR, "model.int8.onnx"), ADAY_DOSYA)
    from kanun.retrieval.rerank import OnnxReranker
    from kanun.retrieval.search import bm25_kur
    metin = bm25_kur().metinler
    fp32 = OnnxReranker(os.path.join(RR, "model.onnx"))
    int8 = OnnxReranker(os.path.join(RR, "model.int8.onnx"))
    kesisim = []
    with open(ADAY_DOSYA, encoding="utf-8") as f:
        satirlar = [json.loads(l) for l in f][:RR_N]
    for s in satirlar:
        adaylar = [tuple(a) for a in s["adaylar"][:RR_ADAY]]
        metinler = [(metin.get(a) or "")[:3000] for a in adaylar]
        a = np.argsort(-np.asarray(fp32.skorla(s["sorgu"], metinler)), kind="stable")[:10]
        b = np.argsort(-np.asarray(int8.skorla(s["sorgu"], metinler)), kind="stable")[:10]
        kesisim.append(len(set(a) & set(b)) / 10)
    print(f"\nreranker int8 vs FP32 top-10 kesişimi ort {np.mean(kesisim):.3f} "
          f"min {np.min(kesisim):.2f} ({len(kesisim)} liste × {RR_ADAY} aday)")
    assert np.mean(kesisim) >= 0.9
