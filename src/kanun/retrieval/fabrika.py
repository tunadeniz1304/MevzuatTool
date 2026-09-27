# -*- coding: utf-8 -*-
"""Ayarlar → çalışan HybridArama. Backend seçimi (torch / ONNX FP32 / ONNX int8) tek yerde.

Importlar geç (fonksiyon içinde) yapılır: `EMBED_BACKEND=onnx-int8` + `RERANK_BACKEND=onnx-int8`
seçildiğinde torch HİÇ import edilmez → servis imajı torch'suz çalışır (ADR-0018).
"""
import os

from .config import Ayarlar, ayarlar_oku
from .search import HybridArama, bm25_kur


def _onnx_yol(ayar, model_klasoru, backend):
    dosya = "model.int8.onnx" if backend.endswith("int8") else "model.onnx"
    return os.path.join(ayar.model_dir, model_klasoru, dosya)


def embedder_sec(ayar: Ayarlar):
    """EMBED_BACKEND → callable(str) -> (dense, sparse)."""
    if ayar.embed_backend == "torch":
        from .embed import embed_sorgu
        return embed_sorgu
    from .embed_onnx import OnnxEmbedder
    return OnnxEmbedder(_onnx_yol(ayar, "bge-m3", ayar.embed_backend), threads=ayar.ort_threads)


def reranker_sec(ayar: Ayarlar, backend=None):
    """RERANK_BACKEND → `skorla` sunan nesne ya da None (kapali)."""
    backend = backend or ayar.rerank_backend
    if backend == "kapali":
        return None
    if backend == "torch":
        from .rerank import TorchReranker
        return TorchReranker(max_length=ayar.rerank_max_len)
    from .rerank import OnnxReranker
    return OnnxReranker(_onnx_yol(ayar, "bge-reranker-v2-m3", backend),
                        max_length=ayar.rerank_max_len, threads=ayar.ort_threads)


def arama_kur(ayar: Ayarlar = None, client=None, bm25=None, embedder=None, reranker="ayar"):
    """Tüm bileşenleri kurup HybridArama döndür. Verilen bileşen (test/ölçüm) kurulmaz, olduğu gibi kullanılır."""
    ayar = ayar or ayarlar_oku()
    if client is None:
        from qdrant_client import QdrantClient
        client = QdrantClient(url=ayar.qdrant_url)
    if bm25 is None:
        bm25 = bm25_kur(ayar.korpus_yol)
    if embedder is None:
        embedder = embedder_sec(ayar)
    if reranker == "ayar":
        reranker = reranker_sec(ayar)
    return HybridArama(embedder, client, bm25, collection=ayar.collection, aday_k=ayar.aday_k,
                       agirliklar=ayar.agirliklar, reranker=reranker, rerank_aday=ayar.rerank_aday,
                       rerank_varsayilan=ayar.rerank_varsayilan and reranker is not None,
                       rerank_max_krk=ayar.rerank_max_krk)
