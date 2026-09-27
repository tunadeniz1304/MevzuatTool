# -*- coding: utf-8 -*-
"""Retrieval ayarları — ortam değişkenli varsayılanlar (tek doğruluk kaynağı).

Kütüphane, servis (FastAPI), ölçüm script'leri ve docker-compose aynı ayarları buradan okur.
`.env` dosyası OKUNMAZ; yalnız süreç ortam değişkenleri (docker-compose `environment:`) kullanılır.

Değişkenler (varsayılan):
  QDRANT_URL          http://localhost:6333
  MEVZUAT_COLLECTION  mevzuat
  KORPUS_YOL          data/kanun/korpus.jsonl
  ADAY_K              50        her bacağın (dense / BGE-sparse / BM25) aday sayısı
  W_DENSE/W_SPARSE/W_BM25  0.33/0.33/0.34  WSUM ağırlıkları (ÖLÇÜM 5, EŞİT)
  EMBED_BACKEND       torch     torch | onnx-fp32 | onnx-int8
  RERANK_BACKEND      kapali    kapali | torch | onnx-fp32 | onnx-int8
  RERANK_ADAY         20        reranker'ın yeniden sıraladığı ilk aday sayısı (ADR-0015)
  RERANK_MAX_LEN      512       reranker (sorgu + madde) token üst sınırı
  RERANK_MAX_KRK      3000      madde metni tokenizer'a girmeden önce bu kadar karaktere kesilir
  RERANK_VARSAYILAN   0         1 ise istek `rerank` belirtmediğinde reranker çalışır (ADR-0015)
  MODEL_DIR           models/onnx
  ORT_THREADS         4         ONNX Runtime intra-op thread (i5-11300H: 4 fiziksel çekirdek)
"""
import os
from dataclasses import dataclass

EMBED_BACKENDLER = ("torch", "onnx-fp32", "onnx-int8")
RERANK_BACKENDLER = ("kapali", "torch", "onnx-fp32", "onnx-int8")


def _env(ad, varsayilan, tip=str):
    deger = os.environ.get(ad)
    if deger is None or deger == "":
        return varsayilan
    if tip is bool:
        return deger.strip().lower() in ("1", "true", "evet", "yes", "on")
    return tip(deger)


@dataclass(frozen=True)
class Ayarlar:
    qdrant_url: str = "http://localhost:6333"
    collection: str = "mevzuat"
    korpus_yol: str = "data/kanun/korpus.jsonl"
    aday_k: int = 50
    w_dense: float = 0.33
    w_sparse: float = 0.33
    w_bm25: float = 0.34
    embed_backend: str = "torch"
    rerank_backend: str = "kapali"
    rerank_aday: int = 20
    rerank_max_len: int = 512
    rerank_max_krk: int = 3000
    rerank_varsayilan: bool = False
    model_dir: str = "models/onnx"
    ort_threads: int = 4

    @property
    def agirliklar(self):
        return (self.w_dense, self.w_sparse, self.w_bm25)

    def dogrula(self):
        """Geçersiz backend adını erken yakala (sessiz yanlış model yüklemesin)."""
        if self.embed_backend not in EMBED_BACKENDLER:
            raise ValueError(f"EMBED_BACKEND={self.embed_backend!r} — geçerli: {EMBED_BACKENDLER}")
        if self.rerank_backend not in RERANK_BACKENDLER:
            raise ValueError(f"RERANK_BACKEND={self.rerank_backend!r} — geçerli: {RERANK_BACKENDLER}")
        return self


def ayarlar_oku() -> Ayarlar:
    """Ortam değişkenlerinden Ayarlar üret (her çağrıda yeniden okur — testlerde monkeypatch edilebilir)."""
    v = Ayarlar()
    return Ayarlar(
        qdrant_url=_env("QDRANT_URL", v.qdrant_url),
        collection=_env("MEVZUAT_COLLECTION", v.collection),
        korpus_yol=_env("KORPUS_YOL", v.korpus_yol),
        aday_k=_env("ADAY_K", v.aday_k, int),
        w_dense=_env("W_DENSE", v.w_dense, float),
        w_sparse=_env("W_SPARSE", v.w_sparse, float),
        w_bm25=_env("W_BM25", v.w_bm25, float),
        embed_backend=_env("EMBED_BACKEND", v.embed_backend),
        rerank_backend=_env("RERANK_BACKEND", v.rerank_backend),
        rerank_aday=_env("RERANK_ADAY", v.rerank_aday, int),
        rerank_max_len=_env("RERANK_MAX_LEN", v.rerank_max_len, int),
        rerank_max_krk=_env("RERANK_MAX_KRK", v.rerank_max_krk, int),
        rerank_varsayilan=_env("RERANK_VARSAYILAN", v.rerank_varsayilan, bool),
        model_dir=_env("MODEL_DIR", v.model_dir),
        ort_threads=_env("ORT_THREADS", v.ort_threads, int),
    ).dogrula()
