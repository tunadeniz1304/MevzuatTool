"""Retrieval katmanı (Faz 5-6): BGE-M3 embed + Qdrant hybrid arama.

- embed.py   : sorgu -> dense (CLS) + sparse (sparse_linear) vektör (transformers ile)
- ingest.py  : Colab'da üretilmiş korpus vektörlerini Qdrant'a yükle
- search.py  : sorgu -> hybrid arama (dense + sparse + RRF)

Not: Korpus embed'i Colab'da (FlagEmbedding) yapıldı. Sorgu embed'i burada
(transformers) yapılır — dense birebir hizalı (0.9998 aynı-metin testi).
"""
