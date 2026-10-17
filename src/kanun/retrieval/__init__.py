"""Retrieval katmanı (Faz 5-6): BGE-M3 embed + Qdrant 3-bacak hybrid arama + ops. reranker.

- config.py     : ortam değişkenli ayarlar (QDRANT_URL, ADAY_K, W_*, EMBED/RERANK_BACKEND, ...)
- embed.py      : sorgu -> dense (CLS) + sparse (sparse_linear) vektör (transformers/torch)
- embed_onnx.py : aynı embed, ONNX Runtime ile (FP32 / dinamik int8, torch'suz)
- search.py     : HybridArama — dense + BGE-sparse (Qdrant) + klasik BM25 -> WSUM füzyon (+ reranker)
- rerank.py     : cross-encoder reranker (bge-reranker-v2-m3; torch ve ONNX)
- fabrika.py    : ayarlar -> çalışan HybridArama (backend seçimi, geç importlar)
- olcum.py      : ölçüm protokolü (gold seti SEED 4721, R@k, MRR@10, nDCG@10)

Korpus vektörlerini Qdrant'a yükleme: scripts/kanun/retrieval/ingest_qdrant.py.
Not: Korpus embed'i Colab'da (FlagEmbedding) yapıldı. Sorgu embed'i burada
(transformers) yapılır — dense birebir hizalı (0.9998 aynı-metin testi).
"""
